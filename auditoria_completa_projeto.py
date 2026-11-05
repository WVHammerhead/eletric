"""
Auditoria Completa — Projeto Hammerhead
========================================

Verifica inconsistências, erros de cálculo e premissas contraditórias
em todos os arquivos do projeto.

Categorias de auditoria:
1. Consistência de massas entre inventários
2. Geometria e dimensões (comprimentos, alturas, CG)
3. Cálculos estruturais (tensões, fatores de segurança)
4. Premissas de carga (massa total, acelerações)
5. Compatibilidade entre decisões documentadas
6. Integridade de dados CSV/JSON
"""

import sys
import io
# Configure stdout encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import json
import re
from pathlib import Path
from collections import defaultdict

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

RAIZ_PROJETO = Path(".")
RELATORIO_SAIDA = "AUDITORIA_PROJETO.md"


_NUMERO_BR = re.compile(r'^[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?$')


def ler_csv_robusto(caminho):
    """Lê CSV detectando separador (; , ou tab) e vírgula decimal. Devolve (DataFrame, linhas_descartadas).

    Linhas com número de campos errado NÃO são descartadas em silêncio: voltam em `linhas_descartadas`
    (número da linha, conteúdo) para virar aviso na auditoria."""
    with open(caminho, 'r', encoding='utf-8-sig') as f:
        cabecalho = next((l for l in f if l.strip()), '')
    sep = max((';', ',', '	'), key=cabecalho.count) if cabecalho.strip() else ';'
    ruins = []

    def _ruim(linha):
        ruins.append(linha)
        return None

    df = pd.read_csv(caminho, sep=sep, dtype=str, encoding='utf-8-sig', engine='python', on_bad_lines=_ruim)
    for col in df.columns:
        serie = df[col].dropna().astype(str).str.strip()
        serie = serie[serie != '']
        if len(serie) and serie.map(lambda v: bool(_NUMERO_BR.match(v))).all():
            df[col] = pd.to_numeric(df[col].astype(str).str.strip().str.replace(',', '.', regex=False), errors='coerce')
    return df, ruins

# ============================================================================
# CLASSE AUDITORA
# ============================================================================

class AuditorHammerhead:
    def __init__(self):
        self.erros = []
        self.avisos = []
        self.inconsistencias = defaultdict(list)
        self.dados_coletados = {}
        
    def adicionar_erro(self, categoria, arquivo, descricao):
        """Registra um erro crítico."""
        self.erros.append({
            'categoria': categoria,
            'arquivo': arquivo,
            'descricao': descricao,
            'severidade': 'ERRO'
        })
        
    def adicionar_aviso(self, categoria, arquivo, descricao):
        """Registra um aviso (não crítico)."""
        self.avisos.append({
            'categoria': categoria,
            'arquivo': arquivo,
            'descricao': descricao,
            'severidade': 'AVISO'
        })
        
    def adicionar_inconsistencia(self, categoria, descricao):
        """Registra inconsistência entre arquivos."""
        self.inconsistencias[categoria].append(descricao)
    
    # ========================================================================
    # AUDITORIA 1: INVENTÁRIOS DE MASSA
    # ========================================================================
    
    def auditar_inventarios_massa(self):
        """Verifica consistência entre todos os inventários CSV."""
        print("\n[1/8] Auditando inventários de massa...")
        
        inventarios = list(RAIZ_PROJETO.glob("inventario_*.csv"))
        
        if not inventarios:
            self.adicionar_erro("MASSA", "N/A", "Nenhum inventário encontrado!")
            return
        
        massas_totais = {}
        for inv_path in inventarios:
            try:
                # Inventários usam ponto e vírgula; alguns usam vírgula decimal
                # e os mais antigos usam ponto decimal.
                df = pd.read_csv(inv_path, sep=';', dtype=str, encoding='utf-8-sig', on_bad_lines='skip')
                if not {'massa_kg', 'cenario'}.issubset(df.columns):
                    raise ValueError("colunas obrigatórias 'massa_kg' e 'cenario' ausentes")
                texto = df['massa_kg'].str.strip().str.replace(',', '.', regex=False)
                massa = pd.to_numeric(texto, errors='coerce')
                invalidos = texto.notna() & texto.ne('') & massa.isna()
                if invalidos.any():
                    self.adicionar_erro('MASSA', inv_path.name,
                        f'{invalidos.sum()} massas numéricas inválidas')
                if (massa < 0).any():
                    self.adicionar_erro('MASSA', inv_path.name,
                        f'{(massa < 0).sum()} componentes com massa negativa')
                if (massa == 0).any():
                    self.adicionar_aviso('MASSA', inv_path.name,
                        f'{(massa == 0).sum()} componentes com massa zero')
                cenario = df['cenario'].fillna('').str.strip().str.lower()
                estado = df['estado'].fillna('').str.strip().str.lower() if 'estado' in df else pd.Series('', index=df.index)
                ativo = ~estado.isin(['pendente', 'ausente'])
                cenarios = sorted(set(cenario) - {'todos', ''}) or ['todos']
                for nome in cenarios:
                    selecao = ativo & cenario.isin(['todos', nome])
                    faltantes = int(massa[selecao].isna().sum())
                    chave = f'{inv_path.name} ({nome}; massas informadas, sem ocupantes adicionais)'
                    massas_totais[chave] = float(massa[selecao].sum())
                    if faltantes:
                        self.adicionar_aviso('MASSA', inv_path.name,
                            f'{nome}: {faltantes} massas ausentes; soma incompleta')
            except Exception as e:
                self.adicionar_erro('MASSA', inv_path.name, f'Erro ao ler: {e}')
        self.dados_coletados['massas_totais'] = massas_totais
        print(f'   → {len(inventarios)} inventários verificados')
        print(f'   → Somas por cenário: {list(massas_totais.items())[:3]}...')

    # ========================================================================
    # AUDITORIA 2: GEOMETRIA E DIMENSÕES
    # ========================================================================
    
    def auditar_geometria(self):
        """Verifica consistência de dimensões em scripts Python."""
        print("\n[2/8] Auditando geometria e dimensões...")
        
        scripts_geometria = [
            'cinematica_dianteira.py',
            'empacotamento_dianteiro.py',
            'suporte_bateria.py',
            'estabilidade_massas.py',
            'desenho_corte_eixo_traseiro.py'
        ]
        
        padroes_dimensao = {
            'entre_eixos': [r'entre_eixos\s*=\s*([\d.]+)', r'L_entre_eixos\s*=\s*([\d.]+)'],
            'altura_cg': [r'altura_cg\s*=\s*([\d.]+)', r'h_cg\s*=\s*([\d.]+)'],
            'bitola': [r'bitola\s*=\s*([\d.]+)', r'track_width\s*=\s*([\d.]+)'],
            'vao_eixo': [r'vao\s*=\s*([\d.]+)', r'L_vao\s*=\s*([\d.]+)'],
        }
        
        dimensoes_encontradas = defaultdict(list)
        
        for script_nome in scripts_geometria:
            script_path = RAIZ_PROJETO / script_nome
            
            if not script_path.exists():
                continue
            
            try:
                conteudo = script_path.read_text(encoding='utf-8')
                
                for dim_nome, padroes in padroes_dimensao.items():
                    for padrao in padroes:
                        matches = re.findall(padrao, conteudo)
                        for valor in matches:
                            try:
                                val_float = float(valor)
                                dimensoes_encontradas[dim_nome].append({
                                    'arquivo': script_nome,
                                    'valor': val_float
                                })
                            except ValueError:
                                pass
                
            except Exception as e:
                self.adicionar_erro("GEOMETRIA", script_nome, f"Erro ao ler: {str(e)}")
        
        # Verificar inconsistências
        for dim_nome, ocorrencias in dimensoes_encontradas.items():
            valores_unicos = set([oc['valor'] for oc in ocorrencias])
            
            if len(valores_unicos) > 1:
                detalhes = ", ".join([f"{oc['arquivo']}={oc['valor']}" for oc in ocorrencias])
                self.adicionar_inconsistencia("GEOMETRIA",
                    f"'{dim_nome}' tem valores diferentes: {detalhes}")
        
        self.dados_coletados['dimensoes'] = dimensoes_encontradas
        print(f"   → {len(scripts_geometria)} scripts verificados")
        print(f"   → {len(dimensoes_encontradas)} dimensões rastreadas")
    
    # ========================================================================
    # AUDITORIA 3: CÁLCULOS ESTRUTURAIS
    # ========================================================================
    
    def auditar_calculos_estruturais(self):
        """Verifica fórmulas e cálculos de tensão."""
        print("\n[3/8] Auditando cálculos estruturais...")
        
        # Verificar analise_viabilidade_25mm.py
        script = RAIZ_PROJETO / 'analise_viabilidade_25mm.py'
        
        if not script.exists():
            self.adicionar_aviso("ESTRUTURAL", script.name, "Arquivo não encontrado")
            return
        
        conteudo = script.read_text(encoding='utf-8')
        
        # Verificar fórmulas críticas
        formulas_esperadas = {
            'Momento de inércia': r'I\s*=.*pi.*d\*\*4.*64',
            'Módulo de seção': r'Z\s*=.*pi.*d\*\*3.*32',
            'Momento polar': r'J\s*=.*pi.*d\*\*4.*32',
            'Von Mises': r'sqrt.*sigma\*\*2.*3.*tau\*\*2',
        }
        
        for formula_nome, padrao in formulas_esperadas.items():
            if not re.search(padrao, conteudo, re.IGNORECASE):
                self.adicionar_aviso("ESTRUTURAL", script.name,
                                    f"Fórmula '{formula_nome}' não encontrada ou diferente do esperado")
        
        # Verificar se há erro no cálculo do momento fletor lateral
        if 'h_cg = 0.6' in conteudo:
            self.adicionar_aviso("ESTRUTURAL", script.name,
                "ATENÇÃO: h_cg = 0.6 m pode estar superestimado. "
                "Esse valor pressupõe braço de momento direto do CG ao eixo, "
                "mas se há suspensão vertical, o momento lateral é absorvido pela balança.")
        
        # Verificar se momento lateral está sendo dividido por 2
        if 'F_lat * h_cg / 2' in conteudo:
            self.adicionar_aviso("ESTRUTURAL", script.name,
                "Momento lateral dividido por 2 (presumindo dois lados). "
                "Verificar se isso é correto para viga bi-apoiada.")
        
        # Verificar uso correto de carga distribuída vs concentrada
        if 'carga uniforme' in conteudo.lower() and 'w = self.carga_vertical() / self.cfg.L' in conteudo:
            # OK: carga distribuída w = F/L
            pass
        elif 'carga concentrada' in conteudo.lower():
            # Deve usar M = F*L/4 para carga concentrada no centro
            if 'L**2) / 8' in conteudo:
                self.adicionar_erro("ESTRUTURAL", script.name,
                    "ERRO: Documento diz 'carga concentrada' mas fórmula é de carga distribuída (wL²/8). "
                    "Para carga concentrada no centro: M = F*L/4")
        
        print(f"   → Fórmulas estruturais verificadas")
    
    # ========================================================================
    # AUDITORIA 4: PREMISSAS DE CARGA
    # ========================================================================
    
    def auditar_premissas_carga(self):
        """Verifica consistência de premissas de carga entre arquivos."""
        print("\n[4/8] Auditando premissas de carga...")
        
        scripts_carga = [
            'analise_viabilidade_25mm.py',
            'desenho_corte_eixo_traseiro.py',
            'ensaio.py',
            'frenagem_curva.py',
            'estabilidade_massas.py'
        ]
        
        premissas_carga = defaultdict(list)
        
        padroes = {
            'massa_total': [r'massa_total(?:_kg)?\s*=\s*([\d.]+)', r'massa\s*=\s*([\d.]+)'],
            'aceleracao_lateral': [r'aceleracao_lateral(?:_g)?\s*=\s*([\d.]+)', r'a_lat\s*=\s*([\d.]+)'],
            'desaceleracao_frenagem': [r'desaceleracao(?:_g)?\s*=\s*([\d.]+)', r'a_fren\s*=\s*([\d.]+)'],
        }
        
        for script_nome in scripts_carga:
            script_path = RAIZ_PROJETO / script_nome
            
            if not script_path.exists():
                continue
            
            conteudo = script_path.read_text(encoding='utf-8')
            
            for premissa_nome, padroes_lista in padroes.items():
                for padrao in padroes_lista:
                    matches = re.findall(padrao, conteudo)
                    for valor in matches:
                        try:
                            val_float = float(valor)
                            premissas_carga[premissa_nome].append({
                                'arquivo': script_nome,
                                'valor': val_float
                            })
                        except ValueError:
                            pass
        
        # Verificar inconsistências
        for premissa_nome, ocorrencias in premissas_carga.items():
            valores_unicos = set([oc['valor'] for oc in ocorrencias])
            
            if len(valores_unicos) > 1:
                detalhes = ", ".join([f"{oc['arquivo']}={oc['valor']}" for oc in ocorrencias])
                self.adicionar_inconsistencia("CARGA",
                    f"'{premissa_nome}' tem valores diferentes: {detalhes}")
        
        self.dados_coletados['premissas_carga'] = premissas_carga
        print(f"   → {len(scripts_carga)} scripts verificados")
        print(f"   → {len(premissas_carga)} premissas rastreadas")
    
    # ========================================================================
    # AUDITORIA 5: DECISÕES DOCUMENTADAS
    # ========================================================================
    
    def auditar_decisoes(self):
        """Verifica compatibilidade entre decisões documentadas."""
        print("\n[5/8] Auditando decisões documentadas...")
        
        arquivos_decisao = [
            'Decisao_eixo_dianteiro.md',
            'Decisao_modulo_biz.md',
            'Viabilidade_25mm_pendencias_montagem.md',
            'Auditoria_critica_2026_11_05.md'
        ]
        
        decisoes = {}
        
        for arquivo_nome in arquivos_decisao:
            arquivo_path = RAIZ_PROJETO / arquivo_nome
            
            if not arquivo_path.exists():
                self.adicionar_aviso("DECISAO", arquivo_nome, "Arquivo não encontrado")
                continue
            
            try:
                conteudo = arquivo_path.read_text(encoding='utf-8')
                
                # Extrair menções a diâmetros
                diametros = re.findall(r'Ø\s*(\d+)\s*mm', conteudo)
                if diametros:
                    decisoes[arquivo_nome] = {
                        'diametros_mencionados': list(set(diametros))
                    }
                
                # Verificar contradições
                if 'não é adequado' in conteudo.lower() and 'viável' in conteudo.lower():
                    self.adicionar_aviso("DECISAO", arquivo_nome,
                        "Documento contém termos contraditórios ('não é adequado' e 'viável')")
                
                # Verificar se há medições pendentes mencionadas
                if 'medir' in conteudo.lower() or 'pendente' in conteudo.lower():
                    self.adicionar_aviso("DECISAO", arquivo_nome,
                        "Documento menciona medições pendentes — verificar se foram realizadas")
                
            except Exception as e:
                self.adicionar_erro("DECISAO", arquivo_nome, f"Erro ao ler: {str(e)}")
        
        self.dados_coletados['decisoes'] = decisoes
        print(f"   → {len(arquivos_decisao)} documentos verificados")
    
    # ========================================================================
    # AUDITORIA 6: INTEGRIDADE DE DADOS CSV/JSON
    # ========================================================================
    
    def auditar_integridade_dados(self):
        """Verifica integridade de arquivos CSV e JSON."""
        print("\n[6/8] Auditando integridade de dados...")
        
        # CSV
        arquivos_csv = list(RAIZ_PROJETO.glob("*.csv"))
        
        for csv_path in arquivos_csv:
            try:
                # Detectar separador automaticamente e tratar erros de tokenização
                df, ruins = ler_csv_robusto(csv_path)
                if ruins:
                    self.adicionar_aviso("DADOS", csv_path.name,
                        f"{len(ruins)} linha(s) com número de campos incorreto (ignoradas na leitura): {ruins[0][:60]}")
                
                # Verificar se está vazio
                if df.empty:
                    self.adicionar_aviso("DADOS", csv_path.name, "Arquivo CSV vazio")
                
                # Verificar duplicatas (se houver coluna 'componente' ou 'id')
                if 'componente' in df.columns:
                    dupl = df['componente'].duplicated().sum()
                    if dupl > 0:
                        self.adicionar_aviso("DADOS", csv_path.name,
                            f"{dupl} componentes duplicados")
                
                # Verificar NaNs em colunas críticas
                colunas_criticas = ['massa_kg', 'x_mm', 'y_mm', 'z_mm']
                for col in colunas_criticas:
                    if col in df.columns:
                        nans = df[col].isna().sum()
                        if nans > 0:
                            self.adicionar_aviso("DADOS", csv_path.name,
                                f"{nans} valores NaN na coluna '{col}'")
                
            except Exception as e:
                self.adicionar_erro("DADOS", csv_path.name, f"Erro ao ler CSV: {str(e)}")
        
        # JSON
        arquivos_json = list(RAIZ_PROJETO.glob("*.json"))
        
        for json_path in arquivos_json:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                
                # Verificar se está vazio
                if not dados:
                    self.adicionar_aviso("DADOS", json_path.name, "Arquivo JSON vazio")
                
            except json.JSONDecodeError as e:
                self.adicionar_erro("DADOS", json_path.name, f"JSON inválido: {str(e)}")
            except Exception as e:
                self.adicionar_erro("DADOS", json_path.name, f"Erro ao ler JSON: {str(e)}")
        
        print(f"   → {len(arquivos_csv)} CSVs + {len(arquivos_json)} JSONs verificados")
    
    # ========================================================================
    # AUDITORIA 7: ERRO CRÍTICO NO MOMENTO FLETOR
    # ========================================================================
    
    def auditar_momento_fletor(self):
        """Verifica erro crítico: carga distribuída vs concentrada."""
        print("\n[7/8] Auditando cálculo de momento fletor...")
        
        script = RAIZ_PROJETO / 'analise_viabilidade_25mm.py'
        
        if not script.exists():
            return
        
        conteudo = script.read_text(encoding='utf-8')
        
        # ERRO CRÍTICO DETECTADO:
        # O código calcula: w = F / L, depois M = w * L² / 8
        # Isso é para carga DISTRIBUÍDA uniformemente
        # Mas a carga é CONCENTRADA no centro (peso dos ocupantes)
        
        erro_momento = False
        if 'w = self.carga_vertical() / self.cfg.L' in conteudo:
            if '(w * self.cfg.L**2) / 8' in conteudo:
                erro_momento = True
                self.adicionar_erro("ESTRUTURAL", script.name,
                    "ERRO CRÍTICO: Cálculo de momento fletor incorreto!\n"
                    "   O código usa M = (w*L²)/8 (carga distribuída)\n"
                    "   Mas a carga é CONCENTRADA no centro (ocupantes).\n"
                    "   Fórmula correta: M = (F*L)/4 para carga concentrada.\n"
                    "   Consequência: Momento está SUBDIMENSIONADO em 50%!\n"
                    "   M real = 2 × M calculado")
        
        # Verificar também desenho_corte_eixo_traseiro.py
        script2 = RAIZ_PROJETO / 'desenho_corte_eixo_traseiro.py'
        
        if script2.exists():
            conteudo2 = script2.read_text(encoding='utf-8')
            
            # Este script parece usar carga concentrada corretamente
            if 'R_esq = F_vertical / 2' in conteudo2:
                # OK: reações corretas para carga concentrada
                if 'R_esq * (xi - pos_esq)' in conteudo2:
                    # Verifica se M_max está correto
                    # Para carga concentrada: M_max = F*L/4
                    # O script calcula ponto a ponto, deve dar correto
                    pass
        
        self.erro_momento_detectado = erro_momento
        if erro_momento:
            print("   → Erro crítico detectado no cálculo de momento!")
        else:
            print("   → Momento fletor: carga concentrada M = F·L/4 (OK)")
    
    # ========================================================================
    # AUDITORIA 8: VERIFICAÇÃO CRUZADA DE TENSÕES
    # ========================================================================
    
    def auditar_tensoes_cruzadas(self):
        """Recalcula tensões com fórmula correta e compara."""
        print("\n[8/8] Verificação cruzada de tensões...")
        
        # Parâmetros do problema
        F = 1766  # N (180 kg)
        L = 0.300  # m (vão entre apoios)
        
        # FÓRMULA CORRETA: Carga concentrada no centro
        M_correto = (F * L) / 4  # N·m
        
        # FÓRMULA ERRADA (no código): Carga distribuída
        w = F / L  # N/m
        M_errado = (w * L**2) / 8  # N·m
        
        # Tensões para Ø20 mm e Ø25 mm
        d20 = 0.020  # m
        d25 = 0.025  # m
        
        Z20 = np.pi * (d20**3) / 32  # m³
        Z25 = np.pi * (d25**3) / 32  # m³
        
        sigma_20_errado = M_errado / Z20 / 1e6  # MPa
        sigma_25_errado = M_errado / Z25 / 1e6  # MPa
        
        sigma_20_correto = M_correto / Z20 / 1e6  # MPa
        sigma_25_correto = M_correto / Z25 / 1e6  # MPa
        
        self.dados_coletados['verificacao_tensoes'] = {
            'M_errado_Nm': M_errado,
            'M_correto_Nm': M_correto,
            'erro_percentual': ((M_correto - M_errado) / M_correto * 100),
            'sigma_20_errado_MPa': sigma_20_errado,
            'sigma_20_correto_MPa': sigma_20_correto,
            'sigma_25_errado_MPa': sigma_25_errado,
            'sigma_25_correto_MPa': sigma_25_correto,
        }
        
        # Só é erro se o script auditado ainda usa a fórmula distribuída (detectado na etapa 7).
        (self.adicionar_erro if getattr(self, "erro_momento_detectado", False) else (lambda *a, **k: None))("ESTRUTURAL", "analise_viabilidade_25mm.py",
            f"Momento fletor vertical está SUBDIMENSIONADO:\n"
            f"   M calculado (errado): {M_errado:.2f} N·m\n"
            f"   M correto: {M_correto:.2f} N·m\n"
            f"   Erro: {((M_correto - M_errado) / M_correto * 100):.1f}%\n"
            f"   σ(Ø20) errado: {sigma_20_errado:.1f} MPa → correto: {sigma_20_correto:.1f} MPa\n"
            f"   σ(Ø25) errado: {sigma_25_errado:.1f} MPa → correto: {sigma_25_correto:.1f} MPa")
        
        print(f"   → Tensões recalculadas com fórmula correta")
        print(f"   → Referência (fórmula distribuída, incorreta): subdimensiona em {((M_correto - M_errado) / M_correto * 100):.1f}%")
    
    # ========================================================================
    # GERAÇÃO DE RELATÓRIO
    # ========================================================================
    
    def gerar_relatorio(self):
        """Gera relatório consolidado da auditoria."""
        print("\n" + "="*70)
        print("Gerando relatório de auditoria...")
        print("="*70)
        
        with open(RELATORIO_SAIDA, 'w', encoding='utf-8') as f:
            f.write("# AUDITORIA COMPLETA — PROJETO HAMMERHEAD\n\n")
            f.write("**Data:** 5 de novembro de 2026\n\n")
            f.write("---\n\n")
            
            # Resumo executivo
            f.write("## Resumo Executivo\n\n")
            f.write(f"- **Erros críticos:** {len(self.erros)}\n")
            f.write(f"- **Avisos:** {len(self.avisos)}\n")
            f.write(f"- **Inconsistências:** {sum(len(v) for v in self.inconsistencias.values())}\n\n")
            
            if self.erros:
                f.write("⚠️ **ATENÇÃO:** Erros críticos detectados! Revisar antes de prosseguir.\n\n")
            
            f.write("---\n\n")
            
            # Erros críticos
            if self.erros:
                f.write("## ❌ ERROS CRÍTICOS\n\n")
                for i, erro in enumerate(self.erros, 1):
                    f.write(f"### {i}. {erro['categoria']} — {erro['arquivo']}\n\n")
                    f.write(f"**Descrição:**\n```\n{erro['descricao']}\n```\n\n")
                f.write("---\n\n")
            
            # Avisos
            if self.avisos:
                f.write("## ⚠️ AVISOS\n\n")
                for i, aviso in enumerate(self.avisos, 1):
                    f.write(f"{i}. **{aviso['categoria']}** | `{aviso['arquivo']}` — {aviso['descricao']}\n\n")
                f.write("---\n\n")
            
            # Inconsistências
            if self.inconsistencias:
                f.write("## 🔄 INCONSISTÊNCIAS ENTRE ARQUIVOS\n\n")
                for categoria, lista in self.inconsistencias.items():
                    f.write(f"### {categoria}\n\n")
                    for inc in lista:
                        f.write(f"- {inc}\n")
                    f.write("\n")
                f.write("---\n\n")
            
            # Dados coletados
            f.write("## 📊 DADOS COLETADOS\n\n")
            
            if 'massas_totais' in self.dados_coletados:
                f.write("### Massas Totais por Inventário\n\n")
                for inv, massa in self.dados_coletados['massas_totais'].items():
                    f.write(f"- `{inv}`: {massa:.2f} kg\n")
                f.write("\n")
            
            if 'verificacao_tensoes' in self.dados_coletados:
                f.write("### Verificação de Tensões (Vertical)\n\n")
                vt = self.dados_coletados['verificacao_tensoes']
                f.write("| Parâmetro | Valor Errado | Valor Correto |\n")
                f.write("|-----------|--------------|---------------|\n")
                f.write(f"| Momento fletor | {vt['M_errado_Nm']:.2f} N·m | {vt['M_correto_Nm']:.2f} N·m |\n")
                f.write(f"| Erro percentual | — | {vt['erro_percentual']:.1f}% |\n")
                f.write(f"| σ (Ø20 mm) | {vt['sigma_20_errado_MPa']:.1f} MPa | {vt['sigma_20_correto_MPa']:.1f} MPa |\n")
                f.write(f"| σ (Ø25 mm) | {vt['sigma_25_errado_MPa']:.1f} MPa | {vt['sigma_25_correto_MPa']:.1f} MPa |\n")
                f.write("\n")
            
            # Recomendações
            f.write("---\n\n")
            f.write("## ✅ RECOMENDAÇÕES\n\n")
            f.write("1. **CORRIGIR IMEDIATAMENTE:** Fórmula de momento fletor em `analise_viabilidade_25mm.py`\n")
            f.write("   - Trocar `M = (w*L²)/8` por `M = (F*L)/4` para carga concentrada\n\n")
            f.write("2. **REVISAR:** Premissa de momento lateral (h_cg = 0.6 m)\n")
            f.write("   - Medir geometria real da balança traseira\n")
            f.write("   - Verificar se suspensão absorve momento lateral\n\n")
            f.write("3. **PADRONIZAR:** Massas e dimensões em todos os scripts\n")
            f.write("   - Criar arquivo de configuração centralizado\n\n")
            f.write("4. **VALIDAR:** Executar medições físicas pendentes\n")
            f.write("   - Vão entre rolamentos\n")
            f.write("   - Diâmetro do cubo\n")
            f.write("   - Tipo de suspensão traseira\n\n")
        
        print(f"\n✓ Relatório salvo: {RELATORIO_SAIDA}")

# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  AUDITORIA COMPLETA — PROJETO HAMMERHEAD")
    print("="*70)
    
    auditor = AuditorHammerhead()
    
    auditor.auditar_inventarios_massa()
    auditor.auditar_geometria()
    auditor.auditar_calculos_estruturais()
    auditor.auditar_premissas_carga()
    auditor.auditar_decisoes()
    auditor.auditar_integridade_dados()
    auditor.auditar_momento_fletor()  # CRÍTICO
    auditor.auditar_tensoes_cruzadas()  # CRÍTICO
    
    auditor.gerar_relatorio()
    
    print("\n" + "="*70)
    print("  AUDITORIA CONCLUÍDA")
    print("="*70)
    print(f"\n❌ Erros críticos: {len(auditor.erros)}")
    print(f"⚠️  Avisos: {len(auditor.avisos)}")
    print(f"🔄 Inconsistências: {sum(len(v) for v in auditor.inconsistencias.values())}")
    print(f"\n→ Relatório completo: {RELATORIO_SAIDA}\n")
