"""Geração de dados sintéticos de ensaios mecânicos e ergonômicos do módulo dianteiro.

CORREÇÕES IMPLEMENTADAS (Prompt 3):
1. Comprimento da corrente recalculado com coordenadas reais dos pinhões e coroa
2. Verificação de fechamento com ajuste do tensor (±8mm)
3. Coordenadas axiais (y_centro) preenchidas na configuração
4. Verificação de acessibilidade de ferramentas para montagem

Este script NÃO valida o projeto. Ele gera dados sintéticos e separa três tipos de resultado:
- INCOMPATIBILIDADE: diferença dimensional entre peças do projeto, já documentada
  (ex.: caixa Ø60 mm × rolamento 30209 Ø85 mm).
- ERRO_MODELO: divergência entre o modelo do código e a geometria declarada
  (ex.: balancim modelado com 100 mm × 260 mm declarados).
- HIPOTESE_PENDENTE: valor calculado com premissas não verificadas, a validar com medição ou FEM.

Premissas não verificadas (sem fonte no projeto):
- carga de 150 kgf por roda, μ = 0.5 + 0.02·θ, tensão admissível de 400 MPa
- limiares de colisão por faixa de ângulo (≤15°, ≤20°, ≤25°)
- curso e comprimento livre do amortecedor (120 mm e 300 mm)
- carga de 250 kgf no eixo e vão de 200 mm usados no cálculo de flecha
- antropometria genérica (sem usuário real)

USO: python ensaios_sinteticos_modulo.py --ensaio [mecanico|ergonomico|montagem|todos]
"""

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Tuple, Optional


# ==================== GEOMETRIA E COMPONENTES ====================

BITOLA = 1420.0
YR = BITOLA / 2.0
RAIO_RODA = 258.0  # 80/100-14

# Componentes declarados (não verificados)
CUBO = {
    'espacamento_rolamentos_mm': 200.0,
    'diametro_corpo_mm': 80.0,
    'diametro_eixo_mm': 28.0,  # decisão 05/11/2026
    'carga_referencia_kgf': 500.0,
}

DIRECAO = {
    'caixa_diametro_declarado_mm': 95.0,   # atualizado (Prompt 1): era Ø60; fonte: varredura_modulo_completo.CAIXA_DIRECAO
    'rolamento_cabecote_modelo': '30209',
    'rolamento_cabecote_de_mm': 85.0,  # diâmetro externo
    'rolamento_cabecote_di_mm': 45.0,
    'rolamento_cabecote_altura_mm': 24.75,
}

BALANCIM = {
    'comprimento_declarado_mm': 260.0,
    'tubo_diametro_mm': 32.0,
    'tubo_espessura_mm': 3.0,
    'material': 'AISI 4130',
    'tensao_admissivel_mpa': 400.0,  # simplificado, sem fadiga
}

try:
    from varredura_modulo_completo import CAIXA_DIRECAO as _CX, BALANCIM as _BAL, ModuloCompleto as _Mod
    DIRECAO_CAIXA_MODELO = _CX['diametro_mm']
except Exception:
    _BAL = _Mod = None
    DIRECAO_CAIXA_MODELO = None


MOTORES = {
    'quantidade_por_roda': 2,
    'potencia_hp': 1.0,
    'massa_kg': 14.2,
    'torque_nominal_nm': 5.3,  # estimado 1HP @ 1500rpm
    # CORREÇÃO PROMPT 3.1: Coordenadas reais dos pinhões conforme projeto
    'posicoes_pinhao': {
        'A': (650.0, 685.0, 372.0),  # x, y, z - motor traseiro
        'B': (530.0, 685.0, 372.0),  # motor frente
    },
    'y_centro_eixo': 710.0,  # CORREÇÃO PROMPT 3.2: coordenada axial (YR = 710mm)
}

CORRENTE = {
    'passo_mm': 12.7,  # #428
    'resistencia_kgf': 1830.0,  # típica #428
    'dentes_pinhao': 11,
    'dentes_coroa': 60,
    'elos_declarados': 71,
    # CORREÇÃO PROMPT 3.1: Posição da coroa no eixo
    'posicao_coroa': (600.0, 685.0, 258.0),  # x, y, z_base (varia com suspensão)
    'tensor_ajuste_mm': 8.0,  # ±8mm de ajuste disponível
}

AMORTECEDOR = {
    'curso_declarado_mm': 120.0,  # +80/-40 = 120mm
    'olhal_chassi': (480.0, YR + 60.0, 520.0),
    'olhal_balancim': (520.0, YR + 60.0, 298.0),
    'constante_k_n_mm': 30.0,  # estimativa
    'comprimento_livre_mm': 300.0,  # estimativa
}

# Limitações físicas
CARROCERIA_Y_MAX = 820.0
PISO_Z = 295.0


# ==================== DADOS SINTÉTICOS ====================

@dataclass
class EnsaioIncompatibilidade:
    """Ensaio de incompatibilidade dimensional."""
    componente_a: str
    componente_b: str
    dimensao_declarada_mm: float
    dimensao_requerida_mm: float
    incompatibilidade_mm: float
    severidade: str  # CRITICA, ALTA, MEDIA, MODELO, PENDENTE
    correcao_sugerida: str
    impacto_projeto: str
    tipo: str = 'INCOMPATIBILIDADE'  # INCOMPATIBILIDADE, ERRO_MODELO, HIPOTESE_PENDENTE
    fonte: str = ''  # documento ou código de origem


@dataclass
class EnsaioEsterco:
    """Ensaio sintético de esterço progressivo."""
    angulo_graus: float
    angulo_alcancado_graus: float
    limitante: str  # GEOMETRICO, MECANICO, ESTRUTURAL
    colisao_componentes: Optional[str]
    torque_direcao_nm: float
    carga_balancim_kgf: float
    tensao_balancim_mpa: float
    margem_seguranca: float
    comentario: str


@dataclass
class EnsaioCorrente:
    """Ensaio sintético de montagem da corrente."""
    angulo_esterco_graus: float
    curso_suspensao_mm: float
    distancia_motor_a_coroa_mm: float
    distancia_motor_b_coroa_mm: float
    elos_necessarios_a: int
    elos_necessarios_b: int
    elos_disponiveis: int
    fechamento_a: str  # OK, CURTA, LONGA
    fechamento_b: str
    ajuste_tensor_mm: float
    comentario: str
    folga_dentes_a_mm: float = 0.0     # distância entre centros − soma dos raios primitivos (<0 = pinhão e coroa se sobrepõem)
    folga_dentes_b_mm: float = 0.0
    elos_laco_unico: Optional[float] = None   # laço único de 3 rodas (transmissao_dianteira.calcular_corrente)
    geometria_laco: str = ''


@dataclass
class EnsaioMontagem:
    """Ensaio ergonômico de montagem/manutenção."""
    operacao: str
    ferramenta_necessaria: str
    acesso: str  # BOM, RESTRITO, IMPOSSIVEL
    espacamento_minimo_mm: float
    angulo_chave_graus: float
    maos_necessarias: int
    tempo_estimado_min: float
    dificuldade: str  # BAIXA, MEDIA, ALTA, MUITO_ALTA
    risco_erro: str
    comentario: str
    proposta_layout: str = ''   # alteração PROPOSTA (hipótese a validar em CAD/protótipo)


# ==================== GERADORES DE DADOS SINTÉTICOS ====================

def gerar_incompatibilidades() -> List[EnsaioIncompatibilidade]:
    """Gera dados sintéticos de incompatibilidades dimensionais conhecidas."""
    
    incompatibilidades = []
    
    # 1. Caixa de direção vs. rolamento cabeçote: sede Ø85 exige caixa >= 95 (parede ≥ 5 mm).
    caixa = DIRECAO_CAIXA_MODELO if DIRECAO_CAIXA_MODELO is not None else DIRECAO['caixa_diametro_declarado_mm']
    requerido = DIRECAO['rolamento_cabecote_de_mm'] + 2*5.0
    falta = max(0.0, requerido - caixa)
    incompatibilidades.append(EnsaioIncompatibilidade(
        componente_a='Caixa de direção', componente_b='Rolamento cabeçote 30209',
        dimensao_declarada_mm=caixa, dimensao_requerida_mm=requerido, incompatibilidade_mm=falta,
        severidade='CRITICA' if falta > 0 else 'RESOLVIDA',
        correcao_sugerida=('Aumentar Ø externo da caixa' if falta > 0 else 'Nenhuma: caixa comporta a sede Ø85 com parede ≥ 5 mm'),
        impacto_projeto=('Redesenho cabeçote + caixa' if falta > 0 else 'Altura resolvida em cabecote_pivo.geometria_caixa (topo sob o capô)'),
        tipo='INCOMPATIBILIDADE' if falta > 0 else 'RESOLVIDA',
        fonte='cabecote_pivo.py; varredura_modulo_completo.py'))

    # 2. Eixo Ø28mm vs. cubo 200mm (biapoiado): HIPÓTESE, não incompatibilidade.
    # Flecha de referência: carga 250kgf, vão 200mm, E=200GPa, I=(π/64)*28^4.
    # Fadiga não verificada; o valor 32 mm é palpite sem cálculo.
    I = math.pi * (28**4) / 64  # mm^4
    E = 200000  # MPa = N/mm^2
    P = 250 * 9.81  # kgf -> N
    L = 200  # mm
    flecha_max = (P * L**3) / (48 * E * I)  # viga biapoiada, carga centro

    pend_eixo = EnsaioIncompatibilidade(
        componente_a='Eixo Ø28mm',
        componente_b='Cubo 200mm biapoiado',
        dimensao_declarada_mm=28.0,
        dimensao_requerida_mm=32.0,  # PALPITE: não verificado, não usar como cota
        incompatibilidade_mm=round(flecha_max, 3),  # flecha em mm, NÃO é incompatibilidade dimensional
        severidade='PENDENTE',
        correcao_sugerida=f'Verificar flecha ({flecha_max:.2f}mm a 250kgf, cálculo simples) e fadiga com carga e vão medidos; 32mm é hipótese',
        impacto_projeto='Alteração eixo, cubo, rolamentos somente se a verificação reprovar; verificar interferência com freio',
        tipo='HIPOTESE_PENDENTE',
        fonte='cálculo de viga biapoiada em ensaios_sinteticos_modulo.py'
    )
    incompatibilidades.append(pend_eixo)

    # 3. Balancim: distância pivô→eixo realmente modelada contra a declarada (medida no modelo).
    if _Mod is not None:
        m = _Mod(0, 0, 'direito')
        pivo_eixo = math.sqrt((600.0 - m.x_pivo)**2 + (m.cilindros[0].p1.y - YR)**2)
        dif = abs(pivo_eixo - BALANCIM['comprimento_declarado_mm'])
        incompatibilidades.append(EnsaioIncompatibilidade(
            componente_a='Balancim modelado (código)', componente_b='Balancim especificado',
            dimensao_declarada_mm=BALANCIM['comprimento_declarado_mm'], dimensao_requerida_mm=round(pivo_eixo, 1),
            incompatibilidade_mm=round(dif, 1), severidade='RESOLVIDA' if dif < 1 else 'MODELO',
            correcao_sugerida='Nenhuma: x do pivô é derivado do comprimento declarado' if dif < 1 else 'Corrigir o modelo',
            impacto_projeto=f'Pivô do balancim em x = {m.x_pivo:.0f} mm (antes 520 mm): conferir olhal do amortecedor e o furo no chassi',
            tipo='RESOLVIDA' if dif < 1 else 'ERRO_MODELO', fonte='varredura_modulo_completo.py'))

        # 4. Amortecedor: olhal do chassi fixo e comprimento variável com o curso, medido no modelo.
        def comp_amort(curso):
            c = [x for x in _Mod(0, curso, 'direito').cilindros if x.nome.startswith('Amortecedor')][0]
            return c.p1.distancia(c.p2)
        l_ext, l_rep, l_comp = comp_amort(-40), comp_amort(0), comp_amort(80)
        variavel = abs(l_comp - l_ext) > 1
        incompatibilidades.append(EnsaioIncompatibilidade(
            componente_a='Amortecedor (modelo)', componente_b='Curso -40/+80 mm',
            dimensao_declarada_mm=round(l_rep, 1), dimensao_requerida_mm=round(abs(l_comp - l_ext), 1),
            incompatibilidade_mm=0.0, severidade='RESOLVIDA' if variavel else 'MODELO',
            correcao_sugerida=f'Comprimento no modelo: {l_ext:.0f} mm (-40) / {l_rep:.0f} (0) / {l_comp:.0f} (+80)',
            impacto_projeto='Verificar contra o curso real do amortecedor escolhido (hipótese 120 mm)',
            tipo='RESOLVIDA' if variavel else 'ERRO_MODELO', fonte='varredura_modulo_completo.py'))

    return incompatibilidades


def gerar_ensaios_esterco(angulos_graus: List[float] = None) -> List[EnsaioEsterco]:
    """Gera dados sintéticos de ensaios de esterço progressivo."""
    
    if angulos_graus is None:
        angulos_graus = [0, 5, 10, 15, 20, 25, 30]
    
    ensaios = []
    
    for ang_nominal in angulos_graus:
        # Estimativa de alcance baseado em colisões hipotéticas
        if ang_nominal <= 15:
            ang_alcancado = ang_nominal
            limitante = 'NENHUM'
            colisao = None
            comentario = 'Ângulo alcançado sem restrições aparentes (modelo simplificado)'
        elif ang_nominal <= 20:
            ang_alcancado = ang_nominal
            limitante = 'GEOMETRICO'
            colisao = 'Balancim/carroceria (folga 10-20mm)'
            comentario = 'Alcançado com folga mínima; verificar AABBs vs. geometria real'
        elif ang_nominal <= 25:
            ang_alcancado = ang_nominal
            limitante = 'GEOMETRICO'
            colisao = 'Balancim/carroceria (folga < 10mm)'
            comentario = 'Folga crítica 10mm; envelope 810mm vs. 820mm; risco de contato'
        else:  # > 25°
            ang_alcancado = 25.0
            limitante = 'GEOMETRICO'
            colisao = 'Balancim/carroceria (0mm)'
            comentario = f'Nominal {ang_nominal:.0f}° NÃO alcançado: máximo estimado 25°; balancim excede 820mm'
        
        # Torque de direção estimado (resistência pneu + arrasto rolamentos)
        # T = μ(θ) * N * r_pneu. N = 150kgf/roda e μ(θ) = 0.5 + 0.02·θ são HIPÓTESES.
        # μ(θ) é uma só função para todos os ângulos (antes havia salto em 0°: 0.7 → 0.5).
        N_roda = 150  # kgf por roda (hipótese)
        mu_pneu = 0.5 + 0.02 * ang_alcancado
        r_pneu = RAIO_RODA / 1000  # m
        torque_nm = N_roda * 9.81 * mu_pneu * r_pneu  # por roda
        
        # Carga no balancim (simplificado: reação vertical + lateral do esterço)
        carga_vertical_kgf = N_roda
        carga_lateral_kgf = N_roda * math.tan(math.radians(ang_alcancado)) if ang_alcancado > 0 else 0
        carga_resultante_kgf = math.sqrt(carga_vertical_kgf**2 + carga_lateral_kgf**2)
        
        # Tensão no balancim (viga em balanço simplificada)
        L_balancim = BALANCIM['comprimento_declarado_mm'] / 1000  # m
        M_flexao = carga_resultante_kgf * 9.81 * L_balancim  # N.m
        d_ext = BALANCIM['tubo_diametro_mm']
        d_int = d_ext - 2 * BALANCIM['tubo_espessura_mm']
        W = (math.pi / 32) * (d_ext**4 - d_int**4) / d_ext  # módulo de seção, mm^3
        tensao_mpa = (M_flexao * 1000) / W  # MPa
        
        margem_seg = BALANCIM['tensao_admissivel_mpa'] / tensao_mpa if tensao_mpa > 0 else float('inf')
        
        ensaio = EnsaioEsterco(
            angulo_graus=ang_nominal,
            angulo_alcancado_graus=ang_alcancado,
            limitante=limitante,
            colisao_componentes=colisao,
            torque_direcao_nm=round(torque_nm, 1),
            carga_balancim_kgf=round(carga_resultante_kgf, 1),
            tensao_balancim_mpa=round(tensao_mpa, 1),
            margem_seguranca=round(margem_seg, 2),
            comentario=comentario
        )
        ensaios.append(ensaio)
    
    return ensaios


def _diametro_primitivo(passo: float, dentes: int) -> float:
    """Diâmetro primitivo de roda de corrente: D = p / sen(180°/Z)."""
    return passo / math.sin(math.pi / dentes)


def _elos_corrente_aberta(dist: float, passo: float, z1: int, z2: int) -> float:
    """Elos (não arredondados) de uma corrente fechada em duas rodas: N = 2L/p + (Z1+Z2)/2 + ((Z2−Z1)/2π)²·p/L."""
    return 2*dist/passo + (z1 + z2)/2 + ((z2 - z1)/(2*math.pi))**2 * passo/dist


def _par(n: float) -> int:
    """Número par de elos mais próximo (corrente sem elo cranked)."""
    return int(2*round(n/2))


def gerar_ensaios_corrente() -> List[EnsaioCorrente]:
    """Fechamento da corrente #428 para esterço × curso de suspensão.

    Duas leituras, ambas com a fórmula correta (D = p/sen(180°/Z), e NÃO p·Z/sen):
    - por motor: corrente fechada pinhão 11T ↔ coroa 60T com as coordenadas reais
      A (650, 685, 372), B (530, 685, 372) e coroa (600, 685, 258+curso);
    - laço único de 3 rodas, calculado por transmissao_dianteira.calcular_corrente (fonte do projeto).
    O esterço gira motores, coroa e garfo juntos, então não altera as distâncias; só o curso altera.
    O tensor de ±8 mm é comparado com a diferença entre os elos adotados e o comprimento exigido.
    """
    ensaios = []
    passo = CORRENTE['passo_mm']
    zp, zc = CORRENTE['dentes_pinhao'], CORRENTE['dentes_coroa']
    raio_soma = (_diametro_primitivo(passo, zp) + _diametro_primitivo(passo, zc))/2
    elos_disp = CORRENTE['elos_declarados']
    tensor = CORRENTE['tensor_ajuste_mm']

    try:
        import copy
        import transmissao_dianteira as td
        mot = td.constantes_motor(td.PADRAO_MODULO_BIZ)
    except Exception:   # modelo do projeto indisponível: segue só com a leitura por motor
        td = None

    def laco(curso):
        if td is None:
            return None, 'modelo de transmissão indisponível'
        cfg = copy.deepcopy(td.PADRAO_MODULO_BIZ)
        for r in cfg['corrente']['rodas']:
            if r['tipo'] == 'coroa':
                r['z'] = r['z'] + curso
        try:
            c = td.calcular_corrente(cfg, mot)
            return c['elos_teoricos_posicao_informada'], 'viável'
        except ValueError as e:
            return None, f'INVIÁVEL: {e}'

    for ang in [0, 15, 25]:
        for curso in [-40, 0, 80]:
            x_c, y_c, z_c = 600.0, 685.0, 258.0 + curso
            dists, elos_f, elos_i, folgas = [], [], [], []
            for chave in ('A', 'B'):
                x, y, z = MOTORES['posicoes_pinhao'][chave]
                d = math.sqrt((x_c - x)**2 + (y_c - y)**2 + (z_c - z)**2)
                dists.append(d)
                folgas.append(d - raio_soma)
                n = _elos_corrente_aberta(d, passo, zp, zc)
                elos_f.append(n)
                elos_i.append(_par(n))

            def veredito(n_nec):
                diff_mm = (elos_disp - n_nec)*passo      # >0: sobra corrente
                if abs(diff_mm) <= tensor:
                    return 'OK', diff_mm
                return ('LONGA' if diff_mm > 0 else 'CURTA'), diff_mm
            (fa, da), (fb, db) = veredito(elos_f[0]), veredito(elos_f[1])
            sobrepoe = min(folgas) < 0
            n_laco, estado_laco = laco(curso)

            if sobrepoe:
                coment = (f'GEOMETRIA INVIÁVEL: pinhão e coroa se sobrepõem ({min(folgas):.0f} mm entre primitivos); '
                          f'elos exigidos A/B = {elos_f[0]:.1f}/{elos_f[1]:.1f}, disponíveis {elos_disp}. '
                          'Afastar motores ou subir o eixo dos pinhões (ver gerar_ensaios_montagem).')
            elif fa == 'OK' and fb == 'OK':
                coment = f'OK: sobra/falta de {da:+.1f}/{db:+.1f} mm, dentro do tensor ±{tensor:.0f} mm'
            else:
                coment = (f'{fa}/{fb}: exige A {elos_f[0]:.1f} e B {elos_f[1]:.1f} elos contra {elos_disp} '
                          f'(diferença {da:+.0f}/{db:+.0f} mm vs. tensor ±{tensor:.0f} mm); adotar {elos_i[0]}/{elos_i[1]} elos')
            ensaios.append(EnsaioCorrente(
                angulo_esterco_graus=ang, curso_suspensao_mm=curso,
                distancia_motor_a_coroa_mm=round(dists[0], 1), distancia_motor_b_coroa_mm=round(dists[1], 1),
                elos_necessarios_a=elos_i[0], elos_necessarios_b=elos_i[1], elos_disponiveis=elos_disp,
                fechamento_a=fa if not sobrepoe else 'INVIAVEL', fechamento_b=fb if not sobrepoe else 'INVIAVEL',
                ajuste_tensor_mm=round(max(abs(da), abs(db)), 1), comentario=coment,
                folga_dentes_a_mm=round(folgas[0], 1), folga_dentes_b_mm=round(folgas[1], 1),
                elos_laco_unico=None if n_laco is None else round(n_laco, 2), geometria_laco=estado_laco))

    return ensaios


def proposta_afastamento_motores(folga_mm: float = 10.0, curso_max_mm: float = 80.0) -> Dict:
    """Menor mudança de posição dos pinhões para não sobrepor a coroa em todo o curso (folga entre diâmetros externos)."""
    passo = CORRENTE['passo_mm']
    r_ext = lambda z: passo*(0.6 + 1/math.tan(math.pi/z))/2
    dist_min = r_ext(CORRENTE['dentes_coroa']) + r_ext(CORRENTE['dentes_pinhao']) + folga_mm
    x_c, z_c = 600.0, 258.0 + curso_max_mm       # coroa na compressão máxima (pior caso)
    opcoes = {}
    for chave, (x, y, z) in MOTORES['posicoes_pinhao'].items():
        dz = math.sqrt(max(dist_min**2 - (x - x_c)**2, 0.0))
        opcoes[chave] = {'z_pinhao_minimo_mm': round(z_c + dz, 0)}
    dz0 = abs(372.0 - z_c)
    dx = math.sqrt(max(dist_min**2 - dz0**2, 0.0))
    return {'distancia_centros_minima_mm': round(dist_min, 1), 'subir_pinhoes': opcoes,
            'afastar_em_x_mm': {'motor_A_x_min': round(600.0 + dx, 0), 'motor_B_x_max': round(600.0 - dx, 0)}}


def gerar_ensaios_montagem() -> List[EnsaioMontagem]:
    """Gera dados sintéticos de ergonomia de montagem e manutenção."""
    
    ensaios = []
    
    # 1. Instalação do eixo no cubo
    ensaio = EnsaioMontagem(
        operacao='Instalação eixo Ø28mm no cubo (prensa)',
        ferramenta_necessaria='Prensa hidráulica 5 ton',
        acesso='BOM',
        espacamento_minimo_mm=200.0,
        angulo_chave_graus=90.0,
        maos_necessarias=2,
        tempo_estimado_min=15.0,
        dificuldade='MEDIA',
        risco_erro='Dano ao cubo se desalinhado; eixo Ø28mm pode fletir na prensagem',
        comentario='Eixo fino (Ø28mm) requer alinhamento preciso; considerar Ø32mm'
    )
    ensaios.append(ensaio)
    
    # 2. Montagem do espelho de freio no balancim
    ensaio = EnsaioMontagem(
        operacao='Parafusar espelho freio Ø180mm no balancim',
        ferramenta_necessaria='Chave combinada 13mm',
        acesso='RESTRITO',
        espacamento_minimo_mm=45.0,
        angulo_chave_graus=30.0,  # ângulo limitado
        maos_necessarias=2,
        tempo_estimado_min=20.0,
        dificuldade='ALTA',
        risco_erro='Aperto insuficiente; espelho pode soltar durante frenagem',
        comentario='Acesso limitado por tambor e balancim; verificar torque 25 Nm',
        proposta_layout='PROPOSTA: mudar a sequência — fixar o espelho ao balancim ANTES de montar tambor e cubo (acesso axial livre, ferramenta reta); parafusos M8 sextavados voltados para o lado do cubo'
    )
    ensaios.append(ensaio)
    
    # 3. Fechamento da corrente motor A
    ensaio = EnsaioMontagem(
        operacao='Fechamento corrente #428 motor A (traseiro)',
        ferramenta_necessaria='Extrator de elo + rebite',
        acesso='RESTRITO',
        espacamento_minimo_mm=60.0,
        angulo_chave_graus=45.0,
        maos_necessarias=2,
        tempo_estimado_min=25.0,
        dificuldade='ALTA',
        risco_erro='Elo mal rebitado pode abrir; corrente escapa do pinhão',
        comentario='Acesso entre motor e roda; risco de pinçamento; luvas necessárias',
        proposta_layout='PROPOSTA: elo mestre (clip) em trecho livre do laço a ≥ 60 mm de motor e roda; afastar os motores da coroa (ver proposta de afastamento: %s)' % proposta_afastamento_motores()['afastar_em_x_mm']
    )
    ensaios.append(ensaio)
    
    # 4. Ajuste do tensor
    ensaio = EnsaioMontagem(
        operacao='Ajuste tensor automático (curso ±8mm)',
        ferramenta_necessaria='Chave Allen 6mm',
        acesso='RESTRITO',
        espacamento_minimo_mm=35.0,
        angulo_chave_graus=20.0,
        maos_necessarias=1,
        tempo_estimado_min=10.0,
        dificuldade='MEDIA',
        risco_erro='Curso insuficiente se corrente errada; tensor travado',
        comentario='Acesso lateral; verificar ±8mm suficiente para variação geométrica',
        proposta_layout='PROPOSTA: ±8 mm NÃO cobre o curso (a corrente varia ≈ 100 mm de -40 a +80 mm); manter distância pinhão–coroa constante (motores no balancim) e usar o tensor só para desgaste'
    )
    ensaios.append(ensaio)
    
    # 5. Instalação do rolamento 30209 no cabeçote (depende do Ø da caixa)
    caixa = DIRECAO_CAIXA_MODELO if DIRECAO_CAIXA_MODELO is not None else DIRECAO['caixa_diametro_declarado_mm']
    cabe = caixa >= DIRECAO['rolamento_cabecote_de_mm'] + 10.0
    ensaios.append(EnsaioMontagem(
        operacao='Instalação rolamento 30209 (Ø85mm) no cabeçote',
        ferramenta_necessaria='Prensa + saca-rolamento',
        acesso='BOM' if cabe else 'IMPOSSIVEL',
        espacamento_minimo_mm=(caixa - DIRECAO['rolamento_cabecote_de_mm'])/2 if cabe else 0.0,
        angulo_chave_graus=90.0 if cabe else 0.0,
        maos_necessarias=2, tempo_estimado_min=20.0 if cabe else 0.0,
        dificuldade='MEDIA' if cabe else 'MUITO_ALTA',
        risco_erro='Desalinhamento na prensagem' if cabe else f'INCOMPATIBILIDADE: Ø85mm não cabe em caixa Ø{caixa:.0f}mm',
        comentario=f'Caixa Ø{caixa:.0f}mm com parede de {(caixa-85)/2:.1f} mm; sede usinada após soldar' if cabe else 'BLOQUEIO: aumentar a caixa'
    ))

    # 6. Conexão cabo de freio
    ensaio = EnsaioMontagem(
        operacao='Conexão cabo freio ao espelho',
        ferramenta_necessaria='Alicate pressão + chave 10mm',
        acesso='RESTRITO',
        espacamento_minimo_mm=40.0,
        angulo_chave_graus=25.0,
        maos_necessarias=2,
        tempo_estimado_min=15.0,
        dificuldade='ALTA',
        risco_erro='Cabo frouxo; frenagem assimétrica; risco de travamento',
        comentario='Ajuste simultâneo das duas rodas; medir curso alavanca (≈ 30mm útil)',
        proposta_layout='PROPOSTA: regulador de bainha no lado EXTERNO do garfo (fora do envelope do tambor), acessível sem remover a roda'
    )
    ensaios.append(ensaio)
    
    # 7. Aperto parafusos motor (flange)
    ensaio = EnsaioMontagem(
        operacao='Aperto 4× M8 flanges motores (torque 25 Nm)',
        ferramenta_necessaria='Torquímetro + soquete 13mm',
        acesso='BOM',
        espacamento_minimo_mm=70.0,
        angulo_chave_graus=80.0,
        maos_necessarias=2,
        tempo_estimado_min=12.0,
        dificuldade='BAIXA',
        risco_erro='Aperto desigual; vibração; motor desloca',
        comentario='Sequência cruzada; torque 25 Nm; usar Loctite 243'
    )
    ensaios.append(ensaio)
    
    # 8. Verificação de folga roda/carroceria @ 25°
    ensaio = EnsaioMontagem(
        operacao='Medição folga roda/carroceria @ 25° esterço',
        ferramenta_necessaria='Calibrador ou paquímetro',
        acesso='BOM',
        espacamento_minimo_mm=10.0,  # especificado
        angulo_chave_graus=90.0,
        maos_necessarias=1,
        tempo_estimado_min=5.0,
        dificuldade='BAIXA',
        risco_erro='Folga < 10mm: contato roda/carroceria; bloqueio esterço',
        comentario='⚠️ Modelo reporta 10mm; AABB não garante folga real; medir fisicamente'
    )
    ensaios.append(ensaio)
    
    return ensaios


# ==================== EXPORTAÇÃO ====================

def exportar_csv(dados: List, arquivo: str, campos: List[str]):
    """Exporta lista de dataclasses para CSV."""
    with open(arquivo, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        for item in dados:
            writer.writerow(asdict(item))
    print(f"✅ {len(dados)} registros exportados: {arquivo}")


def exportar_json(dados: Dict, arquivo: str):
    """Exporta dicionário para JSON."""
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    print(f"✅ Dados exportados: {arquivo}")


def gerar_relatorio_html(dados_todos: Dict, arquivo: str = 'ensaios_sinteticos_modulo.html'):
    """Gera relatório HTML consolidado."""
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Ensaios Sintéticos — Módulo Dianteiro Hammerhead</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #c0392b; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; }}
        h2 {{ color: #2c3e50; margin-top: 30px; border-left: 4px solid #3498db; padding-left: 10px; }}
        .aviso {{ background: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; margin: 20px 0; }}
        .critico {{ background: #f8d7da; border-left: 5px solid #dc3545; padding: 15px; margin: 20px 0; font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 14px; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #34495e; color: white; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .critica {{ background-color: #f8d7da; font-weight: bold; }}
        .alta {{ background-color: #fff3cd; }}
        .media {{ background-color: #d1ecf1; }}
        .impossivel {{ color: #dc3545; font-weight: bold; }}
        .restrito {{ color: #fd7e14; }}
    </style>
</head>
<body>
<div class="container">
    <h1>⚠️ Ensaios Sintéticos — Módulo Dianteiro Hammerhead</h1>
    
    <div class="aviso">
        <strong>IMPORTANTE:</strong> Estes dados são <strong>sintéticos e hipotéticos</strong>. 
        NÃO validam o projeto nem autorizam fabricação. Baseiam-se em:
        <ul>
            <li>Geometria declarada (não verificada)</li>
            <li>Modelos simplificados (AABBs, cilindros)</li>
            <li>Esforços estimados (sem FEM)</li>
            <li>Antropometria genérica (sem usuário real)</li>
        </ul>
        Objetivo: <strong>revelar problemas potenciais</strong> que exigem análise detalhada, 
        medições físicas e cálculo estrutural antes de qualquer decisão.
    </div>
    
    <div class="critico">
        🔴 <strong>INCOMPATIBILIDADES CRÍTICAS IDENTIFICADAS:</strong> 
        {len([i for i in dados_todos['incompatibilidades'] if i.severidade == 'CRITICA'])} bloqueadores
    </div>
    
    <h2>1. Incompatibilidades Dimensionais</h2>
    <table>
        <thead>
            <tr>
                <th>Componente A</th>
                <th>Componente B</th>
                <th>Declarado (mm)</th>
                <th>Requerido (mm)</th>
                <th>Incomp. (mm)</th>
                <th>Severidade</th>
                <th>Correção Sugerida</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for inc in dados_todos['incompatibilidades']:
        classe = inc.severidade.lower()
        html += f"""
            <tr class="{classe}">
                <td>{inc.componente_a}</td>
                <td>{inc.componente_b}</td>
                <td>{inc.dimensao_declarada_mm:.1f}</td>
                <td>{inc.dimensao_requerida_mm:.1f}</td>
                <td>{inc.incompatibilidade_mm:.1f}</td>
                <td><strong>{inc.severidade}</strong></td>
                <td>{inc.correcao_sugerida}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
    
    <h2>2. Ensaios de Esterço Progressivo</h2>
    <table>
        <thead>
            <tr>
                <th>Ângulo Nominal (°)</th>
                <th>Alcançado (°)</th>
                <th>Limitante</th>
                <th>Colisão</th>
                <th>Torque (Nm)</th>
                <th>Carga Balancim (kgf)</th>
                <th>Tensão (MPa)</th>
                <th>Marg. Seg.</th>
                <th>Comentário</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for ens in dados_todos['esterco']:
        classe = ''
        if ens.margem_seguranca < 1.5:
            classe = 'critica'
        elif ens.margem_seguranca < 2.0:
            classe = 'alta'
        
        html += f"""
            <tr class="{classe}">
                <td>{ens.angulo_graus:.0f}</td>
                <td>{ens.angulo_alcancado_graus:.0f}</td>
                <td>{ens.limitante}</td>
                <td>{ens.colisao_componentes or '—'}</td>
                <td>{ens.torque_direcao_nm:.1f}</td>
                <td>{ens.carga_balancim_kgf:.1f}</td>
                <td>{ens.tensao_balancim_mpa:.1f}</td>
                <td>{ens.margem_seguranca:.2f}</td>
                <td style="font-size: 12px;">{ens.comentario}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
    
    <h2>3. Ensaios de Montagem da Corrente</h2>
    <table>
        <thead>
            <tr>
                <th>Esterço (°)</th>
                <th>Suspensão (mm)</th>
                <th>Dist A (mm)</th>
                <th>Dist B (mm)</th>
                <th>Elos A</th>
                <th>Elos B</th>
                <th>Disponível</th>
                <th>Fecha A</th>
                <th>Fecha B</th>
                <th>Comentário</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for ens in dados_todos['corrente']:
        classe = ''
        if 'CURTA' in ens.fechamento_a or 'CURTA' in ens.fechamento_b or 'INVIAVEL' in ens.fechamento_a:
            classe = 'critica'
        elif 'LONGA' in ens.fechamento_a or 'LONGA' in ens.fechamento_b:
            classe = 'alta'
        
        html += f"""
            <tr class="{classe}">
                <td>{ens.angulo_esterco_graus:.0f}</td>
                <td>{ens.curso_suspensao_mm:+.0f}</td>
                <td>{ens.distancia_motor_a_coroa_mm:.1f}</td>
                <td>{ens.distancia_motor_b_coroa_mm:.1f}</td>
                <td>{ens.elos_necessarios_a}</td>
                <td>{ens.elos_necessarios_b}</td>
                <td>{ens.elos_disponiveis}</td>
                <td><strong>{ens.fechamento_a}</strong></td>
                <td><strong>{ens.fechamento_b}</strong></td>
                <td style="font-size: 12px;">{ens.comentario}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
    
    <h2>4. Ensaios Ergonômicos de Montagem/Manutenção</h2>
    <table>
        <thead>
            <tr>
                <th>Operação</th>
                <th>Ferramenta</th>
                <th>Acesso</th>
                <th>Espaço (mm)</th>
                <th>Ângulo (°)</th>
                <th>Tempo (min)</th>
                <th>Dificuldade</th>
                <th>Risco</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for ens in dados_todos['montagem']:
        classe_acesso = ens.acesso.lower().replace(' ', '_')
        
        html += f"""
            <tr>
                <td>{ens.operacao}</td>
                <td>{ens.ferramenta_necessaria}</td>
                <td class="{classe_acesso}"><strong>{ens.acesso}</strong></td>
                <td>{ens.espacamento_minimo_mm:.1f}</td>
                <td>{ens.angulo_chave_graus:.0f}</td>
                <td>{ens.tempo_estimado_min:.0f}</td>
                <td>{ens.dificuldade}</td>
                <td style="font-size: 12px;">{ens.risco_erro}</td>
            </tr>
"""
    
    html += f"""
        </tbody>
    </table>
    
    <h2>5. Resumo Executivo</h2>
    <ul>
        <li><strong>Incompatibilidades CRÍTICAS:</strong> {len([i for i in dados_todos['incompatibilidades'] if i.severidade == 'CRITICA'])}</li>
        <li><strong>Erros de modelo:</strong> {len([i for i in dados_todos['incompatibilidades'] if i.tipo == 'ERRO_MODELO'])}</li>
        <li><strong>Hipóteses pendentes:</strong> {len([i for i in dados_todos['incompatibilidades'] if i.tipo == 'HIPOTESE_PENDENTE'])}</li>
        <li><strong>Ângulo máximo alcançável (estimado):</strong> {max(e.angulo_alcancado_graus for e in dados_todos['esterco'])}°</li>
        <li><strong>Operações IMPOSSÍVEIS:</strong> {len([m for m in dados_todos['montagem'] if m.acesso == 'IMPOSSIVEL'])}</li>
        <li><strong>Operações de ALTA dificuldade:</strong> {len([m for m in dados_todos['montagem'] if m.dificuldade in ['ALTA', 'MUITO_ALTA']])}</li>
    </ul>
    
    <div class="critico">
        <strong>CORRENTE #428:</strong> {len([c for c in dados_todos.get('corrente', []) if c.fechamento_a == 'INVIAVEL'])} de {len(dados_todos.get('corrente', []))}
        configurações com pinhão e coroa sobrepostos; as demais ficam LONGAS em relação aos {CORRENTE['elos_declarados']} elos declarados.<br>
        <strong>ACESSO RESTRITO:</strong> {len([m for m in dados_todos['montagem'] if m.acesso == 'RESTRITO'])} operações (propostas de layout na tabela de montagem, a validar em CAD).<br>
        <strong>AÇÃO REQUERIDA:</strong> afastar os motores da coroa e manter a distância pinhão–coroa constante no curso antes de usar estes números.
    </div>
    
    <p style="color: #7f8c8d; font-size: 12px; margin-top: 40px;">
        Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
        Ferramenta: ensaios_sinteticos_modulo.py<br>
        Projeto: Hammerhead Tricycle — Módulo Dianteiro<br>
        <strong>Status: DADOS SINTÉTICOS — NÃO VALIDADO</strong>
    </p>
</div>
</body>
</html>
"""
    
    with open(arquivo, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Relatório HTML gerado: {arquivo}")


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
    parser.add_argument('--ensaio', 
                        choices=['incompatibilidades', 'esterco', 'corrente', 'montagem', 'todos'],
                        default='todos',
                        help='Tipo de ensaio sintético a gerar')
    parser.add_argument('--formato', 
                        choices=['csv', 'json', 'html', 'todos'],
                        default='todos',
                        help='Formato de saída')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("GERAÇÃO DE DADOS SINTÉTICOS — MÓDULO DIANTEIRO")
    print("=" * 80)
    print("⚠️  ATENÇÃO: Dados SINTÉTICOS baseados em modelos simplificados")
    print("   NÃO validam o projeto nem autorizam fabricação")
    print("   Objetivo: revelar problemas potenciais para análise detalhada")
    print("=" * 80)
    print()
    
    dados_todos = {}
    
    # Gerar dados conforme solicitado
    if args.ensaio in ['incompatibilidades', 'todos']:
        print("Gerando incompatibilidades dimensionais...")
        incomp = gerar_incompatibilidades()
        dados_todos['incompatibilidades'] = incomp
        if args.formato in ['csv', 'todos']:
            exportar_csv(incomp, 'ensaios_incompatibilidades.csv',
                        ['componente_a', 'componente_b', 'dimensao_declarada_mm', 
                         'dimensao_requerida_mm', 'incompatibilidade_mm', 'severidade',
                         'correcao_sugerida', 'impacto_projeto', 'tipo', 'fonte'])
    
    if args.ensaio in ['esterco', 'todos']:
        print("Gerando ensaios de esterço progressivo...")
        esterco = gerar_ensaios_esterco()
        dados_todos['esterco'] = esterco
        if args.formato in ['csv', 'todos']:
            exportar_csv(esterco, 'ensaios_esterco.csv',
                        ['angulo_graus', 'angulo_alcancado_graus', 'limitante',
                         'colisao_componentes', 'torque_direcao_nm', 'carga_balancim_kgf',
                         'tensao_balancim_mpa', 'margem_seguranca', 'comentario'])
    
    if args.ensaio in ['corrente', 'todos']:
        print("Gerando ensaios de montagem da corrente...")
        corrente = gerar_ensaios_corrente()
        dados_todos['corrente'] = corrente
        if args.formato in ['csv', 'todos']:
            exportar_csv(corrente, 'ensaios_corrente.csv',
                        ['angulo_esterco_graus', 'curso_suspensao_mm', 
                         'distancia_motor_a_coroa_mm', 'distancia_motor_b_coroa_mm',
                         'elos_necessarios_a', 'elos_necessarios_b', 'elos_disponiveis',
                         'fechamento_a', 'fechamento_b', 'ajuste_tensor_mm', 'comentario',
                         'folga_dentes_a_mm', 'folga_dentes_b_mm', 'elos_laco_unico', 'geometria_laco'])
    
    if args.ensaio in ['montagem', 'todos']:
        print("Gerando ensaios ergonômicos de montagem...")
        montagem = gerar_ensaios_montagem()
        dados_todos['montagem'] = montagem
        if args.formato in ['csv', 'todos']:
            exportar_csv(montagem, 'ensaios_montagem.csv',
                        ['operacao', 'ferramenta_necessaria', 'acesso',
                         'espacamento_minimo_mm', 'angulo_chave_graus', 'maos_necessarias',
                         'tempo_estimado_min', 'dificuldade', 'risco_erro', 'comentario', 'proposta_layout'])
    
    # Exportar JSON consolidado
    if args.formato in ['json', 'todos']:
        dados_export = {k: [asdict(item) for item in v] for k, v in dados_todos.items()}
        exportar_json(dados_export, 'ensaios_sinteticos_modulo.json')
    
    # Gerar relatório HTML
    if args.formato in ['html', 'todos']:
        gerar_relatorio_html(dados_todos)
    
    print()
    print("=" * 80)
    print("RESUMO:")
    if 'incompatibilidades' in dados_todos:
        criticas = len([i for i in dados_todos['incompatibilidades'] if i.severidade == 'CRITICA'])
        print(f"  • Incompatibilidades CRÍTICAS: {criticas}")
    if 'montagem' in dados_todos:
        impossiveis = len([m for m in dados_todos['montagem'] if m.acesso == 'IMPOSSIVEL'])
        print(f"  • Operações IMPOSSÍVEIS: {impossiveis}")
    print()
    if 'corrente' in dados_todos:
        inv = len([c for c in dados_todos['corrente'] if c.fechamento_a == 'INVIAVEL'])
        print(f"  • Corrente: {inv}/{len(dados_todos['corrente'])} configurações com pinhão × coroa sobrepostos; "
              f"demais fora do tensor ±{CORRENTE['tensor_ajuste_mm']:.0f} mm")
    if 'montagem' in dados_todos:
        print(f"  • Operações com acesso RESTRITO: {len([m for m in dados_todos['montagem'] if m.acesso == 'RESTRITO'])}")
    print()
    print("⚠️  Resultados sintéticos: resolver corrente e acessos RESTRITOS e validar em CAD/protótipo antes de fabricar")
    print("=" * 80)


if __name__ == '__main__':
    main()
