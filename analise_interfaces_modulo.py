"""Análise de interfaces e espaçamento axial do módulo dianteiro.

Este script auxilia na verificação de folgas e montabilidade do módulo,
dado um conjunto de posições y (coordenadas axiais) dos componentes.

LIMITAÇÕES IMPORTANTES:
- As posições y e as folgas das candidatas são VALORES DE ENTRADA definidos no código
  (configuracao_candidata_a/b). Uma folga "OK" aqui significa apenas que a entrada é
  consistente, não que a geometria foi verificada.
- A checagem é somente axial (eixo y). Não verifica folgas radiais, caixa de direção,
  chassi, pneu, motores nem amortecedor.
- Não é prova de montabilidade nem de passagem livre.

USO:
    python analise_interfaces_modulo.py --verificar [espacamento|montagem|todos]
    python analise_interfaces_modulo.py --proposta [indefinida|candidata_a|candidata_b|varredura]
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from itertools import combinations
import varredura_modulo_completo as varredura
from typing import List, Dict, Tuple, Optional


# ==================== DEFINIÇÕES DE COMPONENTES ====================

@dataclass
class ComponenteAxial:
    """Componente com posição e largura axial (coordenada y)."""
    nome: str
    y_centro: float  # mm, positivo = lado direito
    largura: float   # mm
    tipo: str        # 'fixo_garfo', 'fixo_chassi', 'roda', 'corrente', etc.
    raio_externo: Optional[float] = None  # mm, para verificação radial
    raio_interno: Optional[float] = None  # mm, para verificação radial
    
    @property
    def y_min(self):
        return self.y_centro - self.largura / 2
    
    @property
    def y_max(self):
        return self.y_centro + self.largura / 2
    
    def folga_para(self, outro: 'ComponenteAxial') -> float:
        """Calcula folga entre este componente e outro (negativo = interferência)."""
        # Negativo: comprimento da interseção axial, inclusive para intervalos contidos.
        return max(self.y_min, outro.y_min) - min(self.y_max, outro.y_max)
    
    def verificar_folga_radial(self, outro: 'ComponenteAxial') -> Optional[Dict]:
        """Verifica folga radial quando há sobreposição axial.
        
        Retorna None se não há dados radiais ou não há sobreposição axial.
        Retorna dict com status de folga radial se aplicável.
        """
        # Só faz sentido verificar se há sobreposição axial
        if self.folga_para(outro) >= 0:
            return None  # sem sobreposição axial
        
        # Precisa de dados radiais de ambos
        if self.raio_externo is None or outro.raio_interno is None:
            if outro.raio_externo is None or self.raio_interno is None:
                return None
        
        # Caso 1: self está dentro de outro (self.externo < outro.interno)
        if self.raio_externo and outro.raio_interno:
            folga_radial = outro.raio_interno - self.raio_externo
            return {
                'tipo': 'interno_externo',
                'folga_radial_mm': round(folga_radial, 2),
                'status': 'OK' if folga_radial >= 2 else ('CONTATO' if folga_radial >= 0 else 'COLISAO_RADIAL')
            }
        
        # Caso 2: outro está dentro de self
        if outro.raio_externo and self.raio_interno:
            folga_radial = self.raio_interno - outro.raio_externo
            return {
                'tipo': 'externo_interno',
                'folga_radial_mm': round(folga_radial, 2),
                'status': 'OK' if folga_radial >= 2 else ('CONTATO' if folga_radial >= 0 else 'COLISAO_RADIAL')
            }
        
        return None


# ==================== PROPOSTAS DE CONFIGURAÇÃO ====================

# Referência adotada: a mesma de varredura_modulo_completo.py (repouso, lado +y).
# y = 0 é o plano de simetria. Valores derivados das constantes da varredura:
#   cubo: YR = 710, comprimento entre centros de rolamentos = 200 -> 610 e 810
#   tambor: YR - (100 + 15) = 595, largura 30
#   espelho: YR - (100 + 30 + 4) = 576, espessura 8
#   corrente: y_plano = YR - 25 = 685, largura 8
# Larguras de rolamento (25) e do espaçador (175 = 200 - 2×12,5) são HIPÓTESES.
# Coroa e apoios do garfo NÃO estão definidos na varredura: não são incluídos.

def configuracao_varredura() -> List[ComponenteAxial]:
    """Configuração na referência da varredura (lado +y, repouso)."""
    yr = varredura.YR
    ec = varredura.CUBO['comprimento_mm']
    tambor_w = varredura.FREIO['largura_tambor_mm']
    espelho_w = varredura.FREIO['espelho_espessura_mm']
    rol_w = 25.0  # hipótese: largura do rolamento de roda
    y_rol_int = yr - ec / 2
    y_rol_ext = yr + ec / 2
    
    # Raios para verificação radial (estimados)
    raio_tambor_ext = 65.0  # Ø130mm / 2
    raio_tambor_int = 40.0  # furação interna estimada
    raio_rol_ext = 42.5  # estimado para rolamento de roda
    raio_rol_int = 14.0  # eixo Ø28mm
    raio_corrente_ext = 15.0  # largura corrente + folga
    raio_cubo_int = 45.0  # espaçador interno do cubo
    
    return [
        ComponenteAxial('Plano simetria', 0, 0, 'referencia'),
        ComponenteAxial('Espelho freio', yr - (ec / 2 + tambor_w + espelho_w / 2), espelho_w, 'fixo_balancim'),
        ComponenteAxial('Tambor freio Ø130mm', yr - (ec / 2 + tambor_w / 2), tambor_w, 'roda', 
                       raio_externo=raio_tambor_ext, raio_interno=raio_tambor_int),
        ComponenteAxial('Rolamento interno roda', y_rol_int, rol_w, 'roda',
                       raio_externo=raio_rol_ext, raio_interno=raio_rol_int),
        ComponenteAxial('Corrente #428', varredura.CORRENTE['y_plano_mm'], varredura.CORRENTE['largura_mm'], 'corrente',
                       raio_externo=raio_corrente_ext),
        ComponenteAxial('Espaçador do cubo', yr, ec - rol_w, 'roda',
                       raio_interno=raio_cubo_int),
        ComponenteAxial('Rolamento externo roda', y_rol_ext, rol_w, 'roda',
                       raio_externo=raio_rol_ext, raio_interno=raio_rol_int),
    ]

def configuracao_indefinida() -> List[ComponenteAxial]:
    """Configuração com coordenadas preenchidas (proposta de layout).
    
    Referência: y=710mm (YR) é o centro do eixo da roda.
    Sequência de dentro (lado -y) para fora (lado +y):
    """
    # Usando YR = 710mm como referência
    yr = 710.0
    
    # Rolamento interno: 100mm antes do centro (lado -y)
    y_rol_int = yr - 100.0
    
    # Espelho: antes do rolamento interno
    y_espelho = y_rol_int - 25/2 - 8/2 - 3  # rol/2 + espelho/2 + folga 3mm
    
    # Apoio interno: antes do espelho
    y_apoio_int = y_espelho - 8/2 - 30/2 - 5
    
    # Rolamento externo: 100mm depois do centro (lado +y)
    y_rol_ext = yr + 100.0
    
    # Tambor: depois do rolamento externo
    y_tambor = y_rol_ext + 25/2 + 30/2 + 5
    
    # Corrente: entre os rolamentos, lado interno
    y_corrente = yr - 25  # 25mm para o lado -y do eixo
    
    # Coroa: junto à corrente
    y_coroa = y_corrente - 8/2 - 12/2 - 2
    
    # Cubo corpo: centralizado entre rolamentos
    y_cubo = yr
    
    # Apoio externo: além do tambor
    y_apoio_ext = y_tambor + 30/2 + 30/2 + 10
    
    return [
        ComponenteAxial('Plano simetria', 0, 0, 'referencia'),
        ComponenteAxial('Apoio interno garfo', y_apoio_int, 30, 'fixo_garfo'),
        ComponenteAxial('Espelho freio', y_espelho, 8, 'fixo_balancim'),
        ComponenteAxial('Rolamento interno roda', y_rol_int, 25, 'roda'),
        ComponenteAxial('Coroa 60d', y_coroa, 12, 'roda'),
        ComponenteAxial('Corrente #428', y_corrente, 8, 'corrente'),
        ComponenteAxial('Cubo corpo', y_cubo, 80, 'roda'),
        ComponenteAxial('Rolamento externo roda', y_rol_ext, 25, 'roda'),
        ComponenteAxial('Tambor freio Ø130mm', y_tambor, 30, 'roda'),
        ComponenteAxial('Apoio externo garfo', y_apoio_ext, 30, 'fixo_garfo'),
    ]


def configuracao_candidata_a() -> List[ComponenteAxial]:
    """Candidata A: coroa em y=-125mm (proposta inicial)."""
    # Trabalhar de dentro para fora (plano de simetria → exterior)
    
    # Referência: coroa em y = -125mm
    y_coroa = -125.0
    
    # Corrente: junto à coroa (lado interno)
    y_corrente = y_coroa - 12/2 - 8/2 - 2  # coroa/2 + corrente/2 + folga 2mm
    
    # Rolamento interno: dentro da coroa
    y_rol_int = y_coroa - 12/2 - 25/2 - 5  # coroa/2 + rol/2 + folga 5mm
    
    # Espelho freio: mais interno ainda
    y_espelho = y_rol_int - 25/2 - 8/2 - 3  # rol/2 + espelho/2 + folga 3mm
    
    # Apoio interno garfo: atrás do espelho
    y_apoio_int = y_espelho - 8/2 - 30/2 - 5  # espelho/2 + apoio/2 + folga 5mm
    
    # Rolamento externo: ~200mm do interno
    y_rol_ext = y_rol_int + 200
    
    # Cubo corpo: entre rolamentos
    y_cubo = (y_rol_int + y_rol_ext) / 2
    
    # Tambor: lado externo dos rolamentos
    y_tambor = y_rol_ext + 25/2 + 30/2 + 5  # rol/2 + tambor/2 + folga 5mm
    
    # Apoio externo: além do tambor
    y_apoio_ext = y_tambor + 30/2 + 30/2 + 10  # tambor/2 + apoio/2 + folga 10mm
    
    return [
        ComponenteAxial('Plano simetria', 0, 0, 'referencia'),
        ComponenteAxial('Apoio interno garfo', y_apoio_int, 30, 'fixo_garfo'),
        ComponenteAxial('Espelho freio', y_espelho, 8, 'fixo_balancim'),
        ComponenteAxial('Rolamento interno roda', y_rol_int, 25, 'roda'),
        ComponenteAxial('Corrente #428', y_corrente, 8, 'corrente'),
        ComponenteAxial('Coroa 60d', y_coroa, 12, 'roda'),
        ComponenteAxial('Cubo corpo', y_cubo, 80, 'roda'),
        ComponenteAxial('Rolamento externo roda', y_rol_ext, 25, 'roda'),
        ComponenteAxial('Tambor freio Ø130mm', y_tambor, 30, 'roda'),
        ComponenteAxial('Apoio externo garfo', y_apoio_ext, 30, 'fixo_garfo'),
    ]


def configuracao_candidata_b() -> List[ComponenteAxial]:
    """Candidata B: partindo dos rolamentos com 200mm entre centros."""
    # Começar pelos rolamentos (definidos por 200mm entre centros)
    
    # Rolamento interno em posição arbitrária inicial
    y_rol_int = -150.0
    y_rol_ext = y_rol_int + 200.0  # 200mm entre centros (especificação cubo)
    
    # Cubo corpo: entre rolamentos
    y_cubo = (y_rol_int + y_rol_ext) / 2
    
    # Espelho: interno ao rolamento interno
    y_espelho = y_rol_int - 25/2 - 8/2 - 3  # rol/2 + espelho/2 + folga 3mm
    
    # Tambor: externo ao rolamento externo
    y_tambor = y_rol_ext + 25/2 + 30/2 + 5  # rol/2 + tambor/2 + folga 5mm
    
    # Coroa: próxima ao rolamento interno (lado de fora)
    y_coroa = y_rol_int + 25/2 + 12/2 + 3  # rol/2 + coroa/2 + folga 3mm
    
    # Corrente: ao lado da coroa
    y_corrente = y_coroa + 12/2 + 8/2 + 2  # coroa/2 + corrente/2 + folga 2mm
    
    # Apoio interno: atrás do espelho
    y_apoio_int = y_espelho - 8/2 - 30/2 - 5  # espelho/2 + apoio/2 + folga 5mm
    
    # Apoio externo: além do tambor
    y_apoio_ext = y_tambor + 30/2 + 30/2 + 10  # tambor/2 + apoio/2 + folga 10mm
    
    return [
        ComponenteAxial('Plano simetria', 0, 0, 'referencia'),
        ComponenteAxial('Apoio interno garfo', y_apoio_int, 30, 'fixo_garfo'),
        ComponenteAxial('Espelho freio', y_espelho, 8, 'fixo_balancim'),
        ComponenteAxial('Rolamento interno roda', y_rol_int, 25, 'roda'),
        ComponenteAxial('Coroa 60d', y_coroa, 12, 'roda'),
        ComponenteAxial('Corrente #428', y_corrente, 8, 'corrente'),
        ComponenteAxial('Cubo corpo', y_cubo, 80, 'roda'),
        ComponenteAxial('Rolamento externo roda', y_rol_ext, 25, 'roda'),
        ComponenteAxial('Tambor freio Ø130mm', y_tambor, 30, 'roda'),
        ComponenteAxial('Apoio externo garfo', y_apoio_ext, 30, 'fixo_garfo'),
    ]


# ==================== ANÁLISE ====================

def analisar_espacamento(componentes: List[ComponenteAxial]) -> Dict:
    """Analisa espaçamento e folgas entre componentes."""
    
    # Ordenar por y_centro
    comp_ordenados = sorted([c for c in componentes if c.y_centro is not None], 
                           key=lambda x: x.y_centro)
    
    folgas = []
    interferencias = []
    verificacoes_radiais = []
    
    # Todos os pares: intervalos contidos podem não ser vizinhos por centro.
    for comp_a, comp_b in combinations((c for c in comp_ordenados if c.tipo != 'referencia'), 2):
        
        folga = comp_a.folga_para(comp_b)
        
        info = {
            'comp_a': comp_a.nome,
            'comp_b': comp_b.nome,
            'y_face_a': round(comp_a.y_max, 2),
            'y_face_b': round(comp_b.y_min, 2),
            'folga_mm': round(folga, 2),
            'status': 'SEPARADOS_AXIALMENTE' if folga >= 2 else ('CONTATO_AXIAL' if folga >= 0 else 'SOBREPOSICAO_AXIAL'),
        }
        
        # Se há sobreposição axial, verificar folga radial
        if folga < 0:
            verif_radial = comp_a.verificar_folga_radial(comp_b)
            if verif_radial:
                info['verificacao_radial'] = verif_radial
                verificacoes_radiais.append({
                    'comp_a': comp_a.nome,
                    'comp_b': comp_b.nome,
                    'sobreposicao_axial_mm': round(-folga, 2),
                    **verif_radial
                })
            interferencias.append(info)
        elif folga < 2:
            folgas.append(info)
        else:
            folgas.append(info)
    
    # Resumo
    vao_apoios = None
    dist_rolamentos = None
    
    try:
        apoio_int = next(c for c in componentes if 'Apoio interno' in c.nome)
        apoio_ext = next(c for c in componentes if 'Apoio externo' in c.nome)
        vao_apoios = abs(apoio_ext.y_centro - apoio_int.y_centro)
    except StopIteration:
        pass
    
    try:
        rol_int = next(c for c in componentes if 'Rolamento interno' in c.nome)
        rol_ext = next(c for c in componentes if 'Rolamento externo' in c.nome)
        dist_rolamentos = abs(rol_ext.y_centro - rol_int.y_centro)
    except StopIteration:
        pass
    
    return {
        'componentes': [asdict(c) for c in comp_ordenados],
        'folgas': folgas,
        'interferencias': interferencias,
        'verificacoes_radiais': verificacoes_radiais,
        'resumo': {
            'total_componentes': len(comp_ordenados),
            'interferencias': len(interferencias),
            'folgas_apertadas': len([f for f in folgas if 0 <= f['folga_mm'] < 2]),
            'folgas_ok': len([f for f in folgas if f['folga_mm'] >= 2]),
            'verificacoes_radiais': len(verificacoes_radiais),
            'colisoes_radiais': len([v for v in verificacoes_radiais if v['status'] == 'COLISAO_RADIAL']),
            'vao_apoios_mm': round(vao_apoios, 1) if vao_apoios else None,
            'dist_rolamentos_mm': round(dist_rolamentos, 1) if dist_rolamentos else None,
        }
    }



def verificar_montagem(componentes: List[ComponenteAxial]) -> Dict:
    """Verifica sequência de montagem e acessibilidade."""
    
    # Sequência típica de montagem (hipotética)
    sequencia = [
        {
            'passo': 1,
            'operacao': 'Instalar rolamento interno no cubo',
            'componentes': ['Cubo corpo', 'Rolamento interno roda'],
            'ferramenta': 'Prensa hidráulica',
            'acesso_requerido': 'Livre',
            'acesso_status': 'BOM',
            'proposta_melhoria': None,
        },
        {
            'passo': 2,
            'operacao': 'Instalar rolamento externo no cubo',
            'componentes': ['Cubo corpo', 'Rolamento externo roda'],
            'ferramenta': 'Prensa hidráulica',
            'acesso_requerido': 'Livre',
            'acesso_status': 'BOM',
            'proposta_melhoria': None,
        },
        {
            'passo': 3,
            'operacao': 'Montar tambor no cubo (lado externo)',
            'componentes': ['Cubo corpo', 'Tambor freio Ø130mm'],
            'ferramenta': 'Chave allen',
            'acesso_requerido': 'Lateral livre (lado externo)',
            'acesso_status': 'BOM',
            'proposta_melhoria': None,
        },
        {
            'passo': 4,
            'operacao': 'Inserir eixo Ø28mm pelos apoios do garfo',
            'componentes': ['Apoio interno garfo', 'Apoio externo garfo'],
            'ferramenta': 'Manual ou marreta leve',
            'acesso_requerido': 'Eixo longitudinal livre',
            'acesso_status': 'BOM',
            'proposta_melhoria': None,
        },
        {
            'passo': 5,
            'operacao': 'Montar cubo+rolamentos no eixo',
            'componentes': ['Cubo corpo', 'Rolamento interno roda', 'Rolamento externo roda'],
            'ferramenta': 'Prensa ou aquecimento',
            'acesso_requerido': 'Cubo desliza no eixo entre apoios',
            'acesso_status': 'BOM',
            'proposta_melhoria': None,
        },
        {
            'passo': 6,
            'operacao': 'Parafusar espelho de freio Ø180mm no balancim',
            'componentes': ['Espelho freio'],
            'ferramenta': 'Chave combinada 13mm',
            'acesso_requerido': 'Acesso lateral interno (entre garfo e tambor)',
            'acesso_status': 'RESTRITO',
            'proposta_melhoria': 'SUGESTÃO 1: Usar parafusos de cabeça baixa (socket cap screw) para reduzir altura. SUGESTÃO 2: Reposicionar espelho 15mm mais interno (y -= 15mm) para aumentar folga com tambor de 5mm para 20mm. SUGESTÃO 3: Usar fixação por 3 parafusos M6 em vez de 4 M8 para reduzir espaço de ferramenta.',
        },
        {
            'passo': 7,
            'operacao': 'Instalar coroa no eixo (lado interno)',
            'componentes': ['Coroa 60d'],
            'ferramenta': 'Chave allen',
            'acesso_requerido': 'Acesso lateral interno (face do cubo)',
            'acesso_status': 'BOM',
            'proposta_melhoria': None,
        },
        {
            'passo': 8,
            'operacao': 'Conexão cabo de freio ao espelho',
            'componentes': ['Espelho freio'],
            'ferramenta': 'Alicate pressão + chave 10mm',
            'acesso_requerido': 'Acesso ao terminal do cabo',
            'acesso_status': 'RESTRITO',
            'proposta_melhoria': 'SUGESTÃO 1: Reorientar terminal do cabo 90° para acesso frontal em vez de lateral. SUGESTÃO 2: Usar terminal de ajuste rápido tipo "barrel adjuster" acessível do lado externo. SUGESTÃO 3: Posicionar fixação do cabo 30mm mais alta (z += 30mm) no espelho para evitar conflito com garfo.',
        },
        {
            'passo': 9,
            'operacao': 'Fechamento corrente #428 motor A (traseiro)',
            'componentes': ['Corrente #428'],
            'ferramenta': 'Extrator de elo + rebite',
            'acesso_requerido': 'Acesso entre motor e roda',
            'acesso_status': 'RESTRITO',
            'proposta_melhoria': 'SUGESTÃO 1: Usar corrente com elo de ligação rápida (master link) tipo clip em vez de rebite. SUGESTÃO 2: Posicionar ponto de fechamento no trecho superior (entre coroa e pinhão) onde há mais espaço. SUGESTÃO 3: Aumentar folga motor-roda: deslocar motor 20mm para trás (x_motor += 20mm).',
        },
    ]
    
    # Verificar folgas para cada passo
    verificacoes = []
    
    for passo in sequencia:
        comp_nomes = passo['componentes']
        comp_envolvidos = [c for c in componentes if c.nome in comp_nomes and c.y_centro is not None]
        
        if len(comp_envolvidos) < len(comp_nomes):
            status = 'INDEFINIDO (posições ausentes)'
        else:
            # O acesso é um rótulo de entrada (hipótese), não resultado de verificação geométrica 3D.
            status = f"INDEFINIDO (acesso {passo['acesso_status']} é hipótese de entrada; sem verificação geométrica 3D)"
        
        verificacoes.append({
            **passo,
            'status': status,
        })
    
    return {
        'sequencia_montagem': verificacoes,
        'observacoes': [
            'Sequência hipotética; requer validação física',
            'Folgas são valores de entrada do código, não resultados de medição ou CAD',
            'Checagem somente axial (y): folgas radiais, caixa, chassi, pneu e motores NÃO verificados',
            'Referência: varredura_modulo_completo.py (candidatas A/B estavam em outra referência)',
            'Coroa e apoios do garfo não definidos na varredura: fora desta verificação',
            'Sobreposição axial não implica interferência: componentes de raios diferentes precisam de checagem radial',
            'Acesso RESTRITO: 3 operações identificadas com propostas de melhoria de layout',
            'Pré-carga de rolamentos não considerada',
            'Tolerâncias e ajustes (H7/h6, etc.) não especificados',
        ],
        'resumo_acessibilidade': {
            'operacoes_bom': len([p for p in sequencia if p['acesso_status'] == 'BOM']),
            'operacoes_restrito': len([p for p in sequencia if p['acesso_status'] == 'RESTRITO']),
            'operacoes_impossivel': len([p for p in sequencia if p['acesso_status'] == 'IMPOSSIVEL']),
            'melhorias_propostas': len([p for p in sequencia if p['proposta_melhoria']]),
        }
    }


# ==================== SAÍDA ====================

def gerar_relatorio_txt(analise: Dict, arquivo: str = 'analise_interfaces_modulo.txt'):
    """Gera relatório em texto simples."""
    
    with open(arquivo, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ANÁLISE DE INTERFACES E ESPAÇAMENTO — MÓDULO DIANTEIRO\n")
        f.write("=" * 80 + "\n\n")
        
        # Resumo
        resumo = analise.get('espacamento', {}).get('resumo', {})
        f.write("RESUMO:\n")
        f.write(f"  Total de componentes: {resumo.get('total_componentes', '?')}\n")
        f.write(f"  Sobreposições axiais: {resumo.get('interferencias', '?')}\n")
        f.write(f"  Verificações radiais: {resumo.get('verificacoes_radiais', '?')}\n")
        f.write(f"  Colisões radiais: {resumo.get('colisoes_radiais', '?')}\n")
        f.write(f"  Folgas apertadas (<2mm): {resumo.get('folgas_apertadas', '?')}\n")
        f.write(f"  Pares separados axialmente (≥2mm): {resumo.get('folgas_ok', '?')}\n")
        f.write(f"  Vão entre apoios garfo: {resumo.get('vao_apoios_mm', '?')} mm\n")
        f.write(f"  Distância entre rolamentos roda: {resumo.get('dist_rolamentos_mm', '?')} mm\n")
        f.write("\n")
        
        # Componentes
        f.write("COMPONENTES (ordenados por posição y):\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'Nome':<30} {'y_centro (mm)':<15} {'Largura (mm)':<15} {'Tipo':<20}\n")
        f.write("-" * 80 + "\n")
        
        for comp in analise.get('espacamento', {}).get('componentes', []):
            if comp['y_centro'] is not None:
                f.write(f"{comp['nome']:<30} {comp['y_centro']:>12.2f}   {comp['largura']:>12.2f}   {comp['tipo']:<20}\n")
        
        f.write("\n")
        
        # Folgas
        f.write("SEPARAÇÕES AXIAIS ENTRE PARES (sem análise radial):\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'Componente A':<25} {'Componente B':<25} {'Folga (mm)':<12} {'Status':<15}\n")
        f.write("-" * 80 + "\n")
        
        for folga in analise.get('espacamento', {}).get('folgas', []):
            status_symbol = {
                'SEPARADOS_AXIALMENTE': '✓',
                'CONTATO_AXIAL': '~',
                'SOBREPOSICAO_AXIAL': '×',
            }.get(folga['status'], '?')
            
            f.write(f"{folga['comp_a']:<25} {folga['comp_b']:<25} {folga['folga_mm']:>10.2f}   {status_symbol} {folga['status']:<15}\n")
        
        f.write("\n")
        
        # Verificações radiais
        if analise.get('espacamento', {}).get('verificacoes_radiais', []):
            f.write("VERIFICAÇÕES RADIAIS (sobreposição axial com checagem radial):\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Componente A':<25} {'Componente B':<25} {'Folga Rad.(mm)':<15} {'Status':<15}\n")
            f.write("-" * 80 + "\n")
            for verif in analise['espacamento']['verificacoes_radiais']:
                status_symbol = {
                    'OK': '✓',
                    'CONTATO': '~',
                    'COLISAO_RADIAL': '✗',
                }.get(verif['status'], '?')
                f.write(f"{verif['comp_a']:<25} {verif['comp_b']:<25} {verif['folga_radial_mm']:>13.2f}   {status_symbol} {verif['status']:<15}\n")
            f.write("\n")
        
        # Interferências
        if analise.get('espacamento', {}).get('interferencias', []):
            f.write("SOBREPOSIÇÕES AXIAIS (não são necessariamente colisões):\n")
            f.write("-" * 80 + "\n")
            for interf in analise['espacamento']['interferencias']:
                f.write(f"  • {interf['comp_a']} ↔ {interf['comp_b']}: {interf['folga_mm']:.2f} mm (axial)\n")
                if 'verificacao_radial' in interf:
                    vr = interf['verificacao_radial']
                    f.write(f"    → Verificação radial: {vr['folga_radial_mm']:.2f} mm - {vr['status']}\n")
            f.write("\n")
        
        # Montagem
        if 'montagem' in analise:
            f.write("SEQUÊNCIA DE MONTAGEM (hipotética):\n")
            f.write("-" * 80 + "\n")
            for etapa in analise['montagem']['sequencia_montagem']:
                status_symbol = {
                    'BOM': '✓',
                    'RESTRITO': '⚠',
                    'IMPOSSIVEL': '✗',
                }.get(etapa.get('acesso_status', etapa['status']), '?')
                f.write(f"{etapa['passo']}. {etapa['operacao']} [{status_symbol} {etapa.get('acesso_status', etapa['status'])}]\n")
                f.write(f"   Ferramenta: {etapa['ferramenta']}\n")
                f.write(f"   Acesso: {etapa['acesso_requerido']}\n")
                if etapa.get('proposta_melhoria'):
                    f.write(f"   💡 {etapa['proposta_melhoria']}\n")
                f.write("\n")
            
            # Resumo de acessibilidade
            if 'resumo_acessibilidade' in analise['montagem']:
                res_acess = analise['montagem']['resumo_acessibilidade']
                f.write("\nRESUMO DE ACESSIBILIDADE:\n")
                f.write(f"  ✓ Operações com acesso BOM: {res_acess['operacoes_bom']}\n")
                f.write(f"  ⚠ Operações com acesso RESTRITO: {res_acess['operacoes_restrito']}\n")
                f.write(f"  ✗ Operações IMPOSSÍVEIS: {res_acess['operacoes_impossivel']}\n")
                f.write(f"  💡 Melhorias de layout propostas: {res_acess['melhorias_propostas']}\n")
                f.write("\n")
            
            f.write("OBSERVAÇÕES:\n")
            for obs in analise['montagem']['observacoes']:
                f.write(f"  • {obs}\n")
        
        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write("Gerado por: analise_interfaces_modulo.py\n")
        f.write("=" * 80 + "\n")
    
    print(f"✅ Relatório gerado: {arquivo}")


# ==================== MAIN ====================

def main():
    try:  # console Windows (cp1252) não imprime emojis
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--proposta',
                        choices=['indefinida', 'candidata_a', 'candidata_b', 'varredura'],
                        default='varredura',
                        help='Configuração a analisar')
    parser.add_argument('--verificar',
                        choices=['espacamento', 'montagem', 'todos'],
                        default='todos',
                        help='Tipo de análise')
    parser.add_argument('--json', action='store_true',
                        help='Saída em JSON')
    
    args = parser.parse_args()
    
    # Selecionar configuração
    if args.proposta == 'indefinida':
        componentes = configuracao_indefinida()
        print("⚠️  Analisando configuração INDEFINIDA (posições None)")
    elif args.proposta == 'candidata_a':
        componentes = configuracao_candidata_a()
        print("📐 Analisando Candidata A (coroa em y=-125mm)")
    elif args.proposta == 'varredura':
        componentes = configuracao_varredura()
        print("📐 Configuração na referência da varredura (lado +y, repouso)")
    elif args.proposta == 'candidata_b':
        componentes = configuracao_candidata_b()
        print("📐 Analisando Candidata B (partindo dos rolamentos 200mm)")
    
    print()
    
    resultado = {}
    
    # Análise de espaçamento
    if args.verificar in ['espacamento', 'todos']:
        print("Analisando espaçamento...")
        analise_esp = analisar_espacamento(componentes)
        resultado['espacamento'] = analise_esp
        
        resumo = analise_esp['resumo']
        print(f"  • Componentes: {resumo['total_componentes']}")
        print(f"  • Sobreposições axiais (não necessariamente colisões): {resumo['interferencias']}")
        print(f"  • Folgas apertadas: {resumo['folgas_apertadas']}")
        print(f"  • Vão apoios: {resumo['vao_apoios_mm']} mm")
        print(f"  • Dist rolamentos: {resumo['dist_rolamentos_mm']} mm")
        print()
    
    # Análise de montagem
    if args.verificar in ['montagem', 'todos']:
        print("Verificando montagem...")
        analise_mont = verificar_montagem(componentes)
        resultado['montagem'] = analise_mont
        print(f"  • Passos: {len(analise_mont['sequencia_montagem'])}")
        print()
    
    # Saída
    if args.json:
        with open('analise_interfaces_modulo.json', 'w', encoding='utf-8') as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        print("✅ Resultado JSON: analise_interfaces_modulo.json")
    else:
        gerar_relatorio_txt(resultado)


if __name__ == '__main__':
    main()
