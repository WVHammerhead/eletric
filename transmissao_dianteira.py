"""Transmissão dianteira C06, cubo motriz e folgas de suspensão e esterço; anteprojeto.

CORREÇÕES IMPLEMENTADAS (Prompt 4):
1. Unificação de base e pneu: usa configurações.py (p2_dorsal) e inventario_dorsal.csv
2. Corte temporal de potência: transição obrigatória de pico (2500W) para contínua (1500W) após 15s
3. Conservação de energia: perdas de cobre divididas pela eficiência do controlador
4. Dedução de 50W de acessórios antes de limites de corrente da bateria

Quatro módulos sobre as mesmas hipóteses:
  corrente   — laço fechado de dois pinhões e uma coroa no mesmo plano: comprimento
               em elos, envolvimento, ajuste e rasgos, ramos tenso e frouxo, cargas
               nos eixos e divisão da corrente disponível em duas;
  torque     — redução, desempenho com os limites D-9, partilha entre os dois motores
               do mesmo par (comando por tensão × por corrente), falhas e curva;
  cubo       — torques de projeto na roda, flange aparafusado e semieixo;
  suspensao  — braços sobrepostos em vista frontal (cambagem, bitola, amortecedores,
               semieixo e juntas ao longo do curso) e varredura do pneu em planta ao
               esterçar contra as longarinas e obstáculos informados.

Coordenadas em mm. Vista lateral do lado esquerdo: x para trás desde a frente, z do
solo; o laço percorrido no sentido anti-horário corresponde à marcha à frente. Vista
frontal e planta do lado direito: y positivo para fora. Os valores padrão são hipóteses
ilustrativas: gerar o modelo com --salvar-config, trocar por medidas e reexecutar com
--config. Massa e CG vêm do inventário estimado. Não libera fabricação.

Uso:
    python transmissao_dianteira.py
    python transmissao_dianteira.py --salvar-config hipoteses.json
    python transmissao_dianteira.py --config hipoteses.json --html transmissao.html
    python transmissao_dianteira.py --pinhao 11 --coroa 60 --elos-disponiveis 104
"""
import argparse
import copy
import json
import math
import sys
from html import escape
from pathlib import Path

from configuracoes import base as obter_base
from estabilidade_massas import Hipoteses, cg_nominal
from modelo_estrutural import (
    BITOLA, GRAVIDADE, LONGARINA, PISO, PNEU_DIANT, X_EIXO_DIANT, X_EIXO_TRAS, X_FRENTE_TRAP,
    diametro, largura_quadro,
)
from relatorio_visual import configurar_console, tabela_dados

AVISO = ('Anteprojeto: geometria 2D, corpo rígido, cargas quase-estáticas e dados de motores, '
         'correntes e amortecedores presumidos. Não substitui desenho 3D, catálogo, ensaio nem '
         'profissional habilitado; não libera fabricação nem circulação.')

# Valores típicos de catálogo; conferir a corrente real com o fabricante.
CORRENTES = {
    '420': {'passo_mm': 12.7, 'ruptura_N': 15000},
    '428': {'passo_mm': 12.7, 'ruptura_N': 17600},
    '08B': {'passo_mm': 12.7, 'ruptura_N': 18000},
    '520': {'passo_mm': 15.875, 'ruptura_N': 30000},
}
# Parafusos métricos: área resistente (mm²); classe: tensão de prova e de ruptura (MPa).
AREA_RESISTENTE = {'M6': 20.1, 'M8': 36.6, 'M10': 58.0, 'M12': 84.3}
CLASSES = {'8.8': (600.0, 800.0), '10.9': (830.0, 1040.0)}

RAIO_RODA = diametro(*PNEU_DIANT[1:])/2
LARGURA_PNEU = PNEU_DIANT[2]
PISO_Z = Hipoteses().piso*1000

PADRAO = {
    'corrente': {
        'passo': '428',
        'carga_ruptura_N': None,          # None: valor típico de CORRENTES
        'elos_disponiveis': None,         # contar os elos da corrente doadora
        'fator_seguranca_minimo': 8.0,
        'folga_entre_rodas_mm': 8.0,
        'alongamento_desgaste_pct': 2.0,  # limite de troca adotado para dimensionar o rasgo
        'pretensao_N': 0.0,
        'rodas': [
            {'nome': 'motor A', 'tipo': 'motor', 'dentes': 11, 'x': 400.0, 'z': 330.0},
            {'nome': 'motor B', 'tipo': 'motor', 'dentes': 11, 'x': 440.0, 'z': 170.0},
            {'nome': 'coroa', 'tipo': 'coroa', 'dentes': 60, 'x': float(X_EIXO_DIANT), 'z': RAIO_RODA},
        ],
        'ajuste': {'roda': 'motor B', 'direcao': [-1.0, -1.0]},
    },
    'motor': {
        'tensao_V': 24.0, 'rpm_nominal': 2800.0, 'rpm_vazio': 3300.0,
        'corrente_nominal_A': 40.0, 'corrente_limite_A': 60.0,
        'dispersao_constante_pct': 5.0,   # diferença de constante entre os dois motores do par
    },
    'veiculo': {
        'massa_kg': None, 'cg_x_mm': None, 'cg_z_mm': None,   # None: inventário estimado
        'rolamento': .015, 'cda_m2': .8, 'densidade_ar': 1.2, 'fator_inercia': 1.05,
        'rendimento_corrente': .95, 'rendimento_juntas': .97, 'rendimento_controlador': .95,
        'aderencia': .8, 'potencia_continua_W': 1500.0, 'potencia_pico_W': 2500.0,
        'velocidade_alvo_kmh': 35.0, 'raio_curva_m': 8.0, 'velocidade_curva_kmh': 20.0,   # projeto contínuo (2026-11-05)
    },
    'cubo': {
        'furos': 4, 'diametro_furacao_mm': 90.0, 'parafuso': 'M8', 'classe': '8.8',
        'atrito_flange': .15, 'precarga_fracao_prova': .7,
        'diametro_semieixo_mm': 22.0, 'escoamento_semieixo_MPa': 310.0, 'coef_seguranca': 2.0,
        'fator_choque': 2.0, 'freio_no_chassi': False, 'torque_referencia_Nm': None,
    },
    'suspensao': {
        # Vista frontal do lado direito (y, z) em mm. Geometria ilustrativa, não medida.
        'roda': [BITOLA/2, RAIO_RODA],
        'braco_inferior': {'chassi': [260.0, 150.0], 'manga': [590.0, 140.0]},
        'braco_superior': {'chassi': [440.0, 330.0], 'manga': [570.0, 390.0]},
        'amortecedores': {'quantidade': 2, 'braco': [490.0, 143.0], 'chassi': [440.0, 430.0],
                          'comprimento_estendido_mm': 320.0, 'comprimento_comprimido_mm': 250.0,
                          'rigidez_N_mm': None},
        'junta_interna': [500.0, RAIO_RODA],   # saída do eixo intermediário
        'junta_interna_x_mm': 0.0,              # avanço da junta interna em relação ao eixo da roda
        'junta_externa_no_pino': True,          # centro da junta externa sobre o eixo de esterço
        'junta_externa': None,                  # [y, z] quando não estiver no pino
        'y_plano_corrente': 485.0,
        'curso_compressao_mm': 55.0, 'curso_extensao_mm': 40.0,
        'cambagem_estatica_graus': 0.0, 'massa_nao_suspensa_kg': 12.0,
        'angulo_max_junta_externa_graus': 45.0, 'angulo_max_junta_interna_graus': 22.0,
        'curso_axial_junta_mm': 20.0,
    },
    'esterco': {
        'folga_minima_mm': 25.0, 'angulo_projeto_graus': 30.0,
        'pivo_no_centro_da_roda': False,        # True reproduz a conta simplificada de D-7
        # Retângulos em planta do lado direito: {"nome", "x0", "x1", "y0", "y1"} em mm.
        'obstaculos': [],
    },
}


def f(valor, casas=1):
    return f'{valor:.{casas}f}'.replace('.', ',')


def mesclar(base, extra):
    resultado = copy.deepcopy(base)
    for chave, valor in (extra or {}).items():
        if chave not in resultado:
            raise ValueError(f'Chave desconhecida na configuração: {chave}')
        if isinstance(resultado[chave], dict) and isinstance(valor, dict):
            resultado[chave] = mesclar(resultado[chave], valor)
        else:
            resultado[chave] = valor
    return resultado


def positivo(*pares):
    for nome, valor in pares:
        if not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor <= 0:
            raise ValueError(f'{nome} deve ser número positivo e finito')


# ---------------------------------------------------------------- geometria plana

def girar(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (v[0]*c - v[1]*s, v[0]*s + v[1]*c)


def somar(a, b, k=1.0):
    return (a[0] + k*b[0], a[1] + k*b[1])


def dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def retangulo(centro, comprimento, largura, ang):
    return [somar(centro, girar((sx*comprimento/2, sy*largura/2), ang))
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _ponto_segmento(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0])*dx + (p[1] - a[1])*dy)/(dx*dx + dy*dy or 1)))
    return math.hypot(p[0] - a[0] - t*dx, p[1] - a[1] - t*dy)


def segmentos_cruzam(a, b, c, d):
    def lado(p, q, r):
        return (q[0] - p[0])*(r[1] - p[1]) - (q[1] - p[1])*(r[0] - p[0])
    return lado(a, b, c)*lado(a, b, d) < 0 and lado(c, d, a)*lado(c, d, b) < 0


def distancia_poligonos(P, Q):
    """Menor distância entre polígonos convexos; negativa indica sobreposição (profundidade SAT)."""
    profundidade = math.inf
    for poly in (P, Q):
        for i, a in enumerate(poly):
            b = poly[(i + 1) % len(poly)]
            n = (b[1] - a[1], a[0] - b[0])
            norma = math.hypot(*n)
            pp = [(x*n[0] + y*n[1])/norma for x, y in P]
            qq = [(x*n[0] + y*n[1])/norma for x, y in Q]
            sobre = min(max(pp), max(qq)) - max(min(pp), min(qq))
            if sobre <= 0:
                return min(min(_ponto_segmento(p, A, B) for p in X for A, B in zip(Y, Y[1:] + Y[:1]))
                           for X, Y in ((P, Q), (Q, P)))
            profundidade = min(profundidade, sobre)
    return -profundidade


# ---------------------------------------------------------------- corrente

def raio_primitivo(passo, dentes):
    return passo/(2*math.sin(math.pi/dentes))


def raio_externo(passo, dentes):
    return passo*(.6 + 1/math.tan(math.pi/dentes))/2


def laco(rodas, passo):
    """Corrente fechada percorrida no sentido anti-horário (marcha à frente).

    Rodas 'externo' ficam por fora do laço e giram como a roda do veículo; rodas 'interno'
    (serpentina ou esticador por dentro) engrenam pelo lado de dentro e giram ao contrário.
    Só com rodas externas a ordem é a do contorno; com alguma interna vale a ordem informada,
    que deve seguir a corrente na marcha à frente.
    """
    if len(rodas) < 2:
        raise ValueError('O laço exige ao menos duas rodas dentadas')
    if all(r.get('lado', 'externo') == 'externo' for r in rodas):
        cx = sum(r['x'] for r in rodas)/len(rodas)
        cz = sum(r['z'] for r in rodas)/len(rodas)
        ordem = sorted(rodas, key=lambda r: math.atan2(r['z'] - cz, r['x'] - cx))
    else:
        ordem = list(rodas)
    sinais = [1 if r.get('lado', 'externo') == 'externo' else -1 for r in ordem]
    raios = [raio_primitivo(passo, r['dentes']) for r in ordem]
    rho = [s*r for s, r in zip(sinais, raios)]       # raio com sinal: tangentes cruzadas nas internas
    n = len(ordem)
    trechos = []
    for i, a in enumerate(ordem):
        j = (i + 1) % n
        b = ordem[j]
        D = math.hypot(b['x'] - a['x'], b['z'] - a['z'])
        if D <= abs(rho[i] - rho[j]) + 1e-9:
            raise ValueError(f'{a["nome"]} e {b["nome"]}: rodas sobrepostas para este caminho de corrente')
        normal = math.atan2(b['z'] - a['z'], b['x'] - a['x']) - math.pi/2 + math.asin((rho[i] - rho[j])/D)
        u = (math.cos(normal), math.sin(normal))
        trechos.append({'de': a['nome'], 'para': b['nome'],
                        'comprimento_mm': math.sqrt(D*D - (rho[i] - rho[j])**2), 'normal': normal,
                        'inicio': somar((a['x'], a['z']), u, rho[i]), 'fim': somar((b['x'], b['z']), u, rho[j])})
    envolvimentos = [(s*(trechos[i]['normal'] - trechos[i - 1]['normal'])) % (2*math.pi)
                     for i, s in enumerate(sinais)]
    if abs(sum(s*w for s, w in zip(sinais, envolvimentos)) - 2*math.pi) > 1e-6:
        raise ValueError('Caminho da corrente inválido: roda externa dentro do laço, ordem fora do sentido '
                         'de marcha ou ramos cruzados; reposicionar as rodas ou rever a ordem')
    for i, a in enumerate(trechos):
        for j in range(i + 1, n):
            if segmentos_cruzam(a['inicio'], a['fim'], trechos[j]['inicio'], trechos[j]['fim']):
                raise ValueError(f'Ramos {a["de"]} → {a["para"]} e {trechos[j]["de"]} → {trechos[j]["para"]} se cruzam')
        for k, r in enumerate(ordem):
            if k not in (i, (i + 1) % n) and _ponto_segmento((r['x'], r['z']), a['inicio'], a['fim']) < raios[k]:
                raise ValueError(f'Ramo {a["de"]} → {a["para"]} atravessa {r["nome"]}')
    # Arcos contados em passos envolvidos (polígono primitivo), como na fórmula usual de comprimento.
    arcos = sum(w*r['dentes']*passo/(2*math.pi) for w, r in zip(envolvimentos, ordem))
    comprimento = sum(t['comprimento_mm'] for t in trechos) + arcos
    return {
        'ordem': [r['nome'] for r in ordem],
        'rodas': [dict(r, raio_primitivo_mm=rp, raio_externo_mm=raio_externo(passo, r['dentes']),
                       envolvimento_graus=math.degrees(w), dentes_engrenados=w/(2*math.pi)*r['dentes'],
                       sentido='mesmo da roda' if s > 0 else 'inverso (motor com polaridade invertida)')
                  for r, rp, w, s in zip(ordem, raios, envolvimentos, sinais)],
        'trechos': trechos, 'comprimento_mm': comprimento, 'elos': comprimento/passo,
    }


def mover(rodas, nome, desloc):
    return [dict(r, x=r['x'] + desloc[0], z=r['z'] + desloc[1]) if r['nome'] == nome else r for r in rodas]


def deslocamento_para(rodas, passo, nome, direcao, elos_alvo, limite=300.0):
    """Deslocamento ao longo do rasgo que leva o laço a `elos_alvo` passos; None se fora do alcance."""
    norma = math.hypot(*direcao)
    if norma == 0:
        raise ValueError('Direção do ajuste nula')
    u = (direcao[0]/norma, direcao[1]/norma)

    def g(s):
        try:
            return laco(mover(rodas, nome, (s*u[0], s*u[1])), passo)['elos'] - elos_alvo
        except ValueError:
            return None
    g0 = g(0)
    if g0 is None:
        return None
    if abs(g0) < 1e-9:
        return 0.0
    candidatos = []
    for sentido in (1, -1):
        anterior, s_ant = g0, 0.0
        for k in range(1, int(limite) + 1):
            s = sentido*k
            atual = g(s)
            if atual is None:
                break
            if anterior*atual <= 0:
                a, b = s_ant, s
                for _ in range(60):
                    m = (a + b)/2
                    if g(a)*g(m) <= 0:
                        b = m
                    else:
                        a = m
                candidatos.append((a + b)/2)
                break
            anterior, s_ant = atual, s
    return min(candidatos, key=abs) if candidatos else None


def tensoes(geo, deltas, pretensao=0.0):
    """Tração em cada ramo no sentido de marcha: coroa acrescenta força, motores retiram."""
    t, valores = 0.0, []
    for nome in geo['ordem']:
        t += deltas.get(nome, 0.0)
        valores.append(t)
    minimo = min(valores)
    valores = [v - minimo + pretensao for v in valores]
    resultado = []
    for i, roda in enumerate(geo['rodas']):
        chega, sai = geo['trechos'][i - 1], geo['trechos'][i]
        dc = _unit(chega['inicio'], chega['fim'])
        ds = _unit(sai['inicio'], sai['fim'])
        F = somar((-valores[i - 1]*dc[0], -valores[i - 1]*dc[1]), ds, valores[i])
        resultado.append({'roda': roda['nome'], 'carga_radial_no_eixo_N': math.hypot(*F),
                          'direcao_graus': math.degrees(math.atan2(F[1], F[0]))})
    ramos = [{'ramo': f"{t['de']} → {t['para']}", 'tracao_N': v} for t, v in zip(geo['trechos'], valores)]
    return ramos, resultado


def _unit(a, b):
    d = dist(a, b)
    return ((b[0] - a[0])/d, (b[1] - a[1])/d)


def calcular_corrente(cfg, mot):
    c = cfg['corrente']
    if c['passo'] not in CORRENTES:
        raise ValueError(f'Passo {c["passo"]} sem cadastro; usar {", ".join(CORRENTES)}')
    passo = CORRENTES[c['passo']]['passo_mm']
    ruptura = c['carga_ruptura_N'] or CORRENTES[c['passo']]['ruptura_N']
    rodas = [dict({'lado': 'externo'}, **r) for r in c['rodas']]
    nomes = [r['nome'] for r in rodas]
    if len(set(nomes)) != len(nomes):
        raise ValueError('Nomes das rodas dentadas devem ser únicos')
    coroas = [r for r in rodas if r['tipo'] == 'coroa']
    motores = [r for r in rodas if r['tipo'] == 'motor']
    if len(coroas) != 1 or not motores:
        raise ValueError('O laço exige uma coroa e ao menos um motor')
    if coroas[0]['lado'] != 'externo':
        raise ValueError('A coroa deve ficar por fora do laço para girar como a roda')
    for r in rodas:
        if r['tipo'] not in ('motor', 'coroa', 'esticador') or r['lado'] not in ('externo', 'interno'):
            raise ValueError(f'{r["nome"]}: tipo motor/coroa/esticador e lado externo/interno')
        if not isinstance(r['dentes'], int) or r['dentes'] < 8:
            raise ValueError(f'{r["nome"]}: número de dentes inteiro ≥ 8')
        if not all(isinstance(r[k], (int, float)) and math.isfinite(r[k]) for k in ('x', 'z')):
            raise ValueError(f'{r["nome"]}: coordenadas x e z finitas')
    inicial = laco(rodas, passo)
    elos_par = 2*round(inicial['elos']/2)
    aj = c['ajuste']
    if aj['roda'] not in nomes:
        raise ValueError(f'Roda de ajuste desconhecida: {aj["roda"]}')
    s_montagem = deslocamento_para(rodas, passo, aj['roda'], aj['direcao'], elos_par)
    if s_montagem is None:
        raise ValueError('Ajuste não alcança número par de elos; rever posições ou direção do rasgo')
    norma = math.hypot(*aj['direcao'])
    u = (aj['direcao'][0]/norma, aj['direcao'][1]/norma)
    rodas = mover(rodas, aj['roda'], (s_montagem*u[0], s_montagem*u[1]))
    geo = laco(rodas, passo)
    gasta = elos_par*(1 + c['alongamento_desgaste_pct']/100)
    s_desgaste = deslocamento_para(rodas, passo, aj['roda'], aj['direcao'], gasta)

    folgas = []
    for i, a in enumerate(geo['rodas']):
        for b in geo['rodas'][i + 1:]:
            folga = math.hypot(a['x'] - b['x'], a['z'] - b['z']) - a['raio_externo_mm'] - b['raio_externo_mm']
            folgas.append({'entre': f'{a["nome"]} e {b["nome"]}', 'folga_mm': folga})

    coroa = next(r for r in geo['rodas'] if r['tipo'] == 'coroa')
    pico = mot['ke']*cfg['motor']['corrente_limite_A']
    deltas = {r['nome']: -pico/(r['raio_primitivo_mm']/1000) for r in geo['rodas'] if r['tipo'] == 'motor'}
    deltas[coroa['nome']] = -sum(deltas.values())
    frente, eixos_frente = tensoes(geo, deltas, c['pretensao_N'])
    re, eixos_re = tensoes(geo, {k: -v for k, v in deltas.items()}, c['pretensao_N'])
    maxima = max(r['tracao_N'] for r in frente)
    frouxo = min(frente, key=lambda r: r['tracao_N'])['ramo']
    frouxo_re = min(re, key=lambda r: r['tracao_N'])['ramo']

    m_ref = geo['rodas'][[r['tipo'] for r in geo['rodas']].index('motor')]
    velocidade = cfg['motor']['rpm_nominal']*m_ref['dentes']*passo/60000
    pinhao_min = min(r['dentes'] for r in geo['rodas'] if r['tipo'] == 'motor')
    pontos = [p for r in geo['rodas'] for p in ((r['x'], r['z'] - r['raio_externo_mm']), (r['x'], r['z'] + r['raio_externo_mm']))]
    disp = c['elos_disponiveis']
    divisao = None
    if disp:
        divisao = {'elos_disponiveis': disp, 'elos_por_laco': elos_par, 'elos_necessarios': 2*elos_par,
                   'sobra_elos': disp - 2*elos_par, 'basta': disp >= 2*elos_par,
                   'emendas': 'duas (uma por laço; reaproveitar a original só se compatível e sem desgaste)'}
    return {
        'passo': c['passo'], 'passo_mm': passo, 'ruptura_N': ruptura,
        'reducao': {r['nome']: coroa['dentes']/r['dentes'] for r in geo['rodas'] if r['tipo'] == 'motor'},
        'ordem_no_sentido_de_marcha': geo['ordem'],
        'rodas': [{k: r[k] for k in ('nome', 'tipo', 'lado', 'sentido', 'dentes', 'x', 'z', 'raio_primitivo_mm',
                                     'raio_externo_mm', 'envolvimento_graus', 'dentes_engrenados')} for r in geo['rodas']],
        'elos_teoricos_posicao_informada': inicial['elos'],
        'elos_adotados': elos_par,
        'comprimento_mm': elos_par*passo,
        'ajuste': {'roda': aj['roda'], 'direcao': list(u), 'deslocamento_montagem_mm': s_montagem,
                   'deslocamento_com_desgaste_mm': s_desgaste,
                   'curso_minimo_rasgo_mm': None if s_desgaste is None else abs(s_desgaste) + 10},
        'folgas_entre_rodas': folgas,
        'velocidade_corrente_m_s': velocidade,
        'variacao_poligonal_pinhao_pct': 100*(1 - math.cos(math.pi/pinhao_min)),
        'tracao_pico_frente': frente, 'cargas_eixos_frente': eixos_frente,
        'tracao_pico_re_ou_regeneracao': re, 'cargas_eixos_re': eixos_re,
        'ramo_frouxo_frente': frouxo, 'ramo_frouxo_re': frouxo_re,
        'tracao_maxima_N': maxima, 'fator_seguranca_ruptura': ruptura/maxima if maxima else None,
        'envelope_vista_lateral_mm': {'x': [min(p[0] for p in pontos) - max(r['raio_externo_mm'] for r in geo['rodas']),
                                            max(p[0] for p in pontos) + max(r['raio_externo_mm'] for r in geo['rodas'])],
                                      'z': [min(p[1] for p in pontos), max(p[1] for p in pontos)]},
        'divisao_da_corrente': divisao,
        '_geo': geo,
    }


# ---------------------------------------------------------------- motores e desempenho

def constantes_motor(cfg):
    m = cfg['motor']
    positivo(*((k, m[k]) for k in ('tensao_V', 'rpm_nominal', 'rpm_vazio', 'corrente_nominal_A', 'corrente_limite_A')))
    if m['rpm_nominal'] >= m['rpm_vazio']:
        raise ValueError('Rotação nominal deve ser menor que a de vazio')
    w0, wn = m['rpm_vazio']*math.pi/30, m['rpm_nominal']*math.pi/30
    ke = m['tensao_V']/w0
    R = (m['tensao_V'] - ke*wn)/m['corrente_nominal_A']
    return {'ke': ke, 'R': R, 'constante_V_s_rad': ke, 'resistencia_ohm': R,
            'torque_nominal_Nm': ke*m['corrente_nominal_A'], 'torque_pico_Nm': ke*m['corrente_limite_A'],
            'potencia_mecanica_nominal_W': ke*m['corrente_nominal_A']*wn,
            'rendimento_eletrico_nominal_pct': 100*ke*wn/m['tensao_V']}


class Veiculo:
    def __init__(self, cfg, mot, cor):
        v = cfg['veiculo']
        h_dorsal, caminho_dorsal = obter_base('p2_dorsal')
        ref = cg_nominal(caminho_dorsal, h_dorsal)
        self.m = v['massa_kg'] or ref['massa_kg']
        self.x = (v['cg_x_mm'] or ref['cg_x_m']*1000)/1000
        self.h = (v['cg_z_mm'] or ref['cg_z_m']*1000)/1000
        self.origem = 'configuração' if v['massa_kg'] else ref['origem']
        self.xf, self.xr = h_dorsal.eixo_dianteiro, h_dorsal.eixo_traseiro
        self.L = self.xr - self.xf
        # Usar raio da roda dianteira da base p2_dorsal: diâmetro de PNEU_DIANT[1:]
        self.r = diametro(*PNEU_DIANT[1:])/2000
        self.v, self.mot, self.motor = v, mot, cfg['motor']
        motores = [r for r in cor['rodas'] if r['tipo'] == 'motor']
        coroa = next(r for r in cor['rodas'] if r['tipo'] == 'coroa')
        self.i = [coroa['dentes']/r['dentes'] for r in motores]   # por motor de um lado
        self.eta = v['rendimento_corrente']*v['rendimento_juntas']
        positivo(('massa', self.m), ('altura do CG', self.h), ('aderência', v['aderencia']))
        if not self.xf < self.x < self.xr:
            raise ValueError('CG fora do entre-eixos')

    def normal_frente(self, rampa=0.0):
        th = math.atan(rampa)
        return self.m*GRAVIDADE*(math.cos(th)*(self.xr - self.x) - math.sin(th)*self.h)/self.L

    def resistencia(self, vel, rampa=0.0):
        th = math.atan(rampa)
        return (self.m*GRAVIDADE*(self.v['rolamento']*math.cos(th) + math.sin(th))
                + .5*self.v['densidade_ar']*self.v['cda_m2']*vel*vel)

    def limite_aderencia(self, rampa=0.0):
        mu = self.v['aderencia']
        return mu*self.normal_frente(rampa)*self.L/(self.L + mu*self.h)

    def corrente_motor(self, w, potencia_bateria):
        ke, R, V = self.mot['ke'], self.mot['R'], self.motor['tensao_V']
        p = potencia_bateria*self.v['rendimento_controlador']
        por_potencia = (-ke*w + math.sqrt((ke*w)**2 + 4*R*p))/(2*R)
        return max(0.0, min(self.motor['corrente_limite_A'], por_potencia, (V - ke*w)/R))

    def forca(self, vel, potencia_total, rampa=0.0, aderencia=True):
        w_roda = vel/self.r
        lado = sum(self.mot['ke']*self.corrente_motor(w_roda*i, potencia_total/4)*i for i in self.i)
        F = 2*lado*self.eta/self.r
        return min(F, self.limite_aderencia(rampa)) if aderencia else F

    def velocidade_livre(self):
        return self.motor['rpm_vazio']*math.pi/30/max(self.i)*self.r

    def vmax(self, potencia, rampa=0.0):
        a, b = .05, self.velocidade_livre()*.9999
        if self.forca(a, potencia, rampa) < self.resistencia(a, rampa):
            return 0.0
        if self.forca(b, potencia, rampa) >= self.resistencia(b, rampa):
            return b
        for _ in range(80):
            m = (a + b)/2
            if self.forca(m, potencia, rampa) >= self.resistencia(m, rampa):
                a = m
            else:
                b = m
        return a

    def rampa_max(self, vel, potencia):
        a, b = 0.0, 1.0
        if self.forca(vel, potencia, 0) < self.resistencia(vel, 0):
            return 0.0
        for _ in range(60):
            m = (a + b)/2
            if self.forca(vel, potencia, m) >= self.resistencia(vel, m):
                a = m
            else:
                b = m
        return a

    def tempo_ate(self, alvo, potencia, duracao_pico_s=None, potencia_apos_pico=None):
        """Integra aceleração; sem duração explícita, potência constante é hipotética.
        
        CORREÇÃO PROMPT 4.2: Implementa transição obrigatória da potência de pico 
        para potência contínua após o limite estrito de 15 segundos.
        Se duracao_pico_s for None, aplica limite padrão de 15s com potência contínua do cfg.
        """
        # CORREÇÃO PROMPT 4.2: Se não especificado, usa transição obrigatória em 15s
        if duracao_pico_s is None and potencia > 1500.0:
            duracao_pico_s = 15.0  # limite estrito
            potencia_apos_pico = 1500.0  # potência contínua
        
        if (duracao_pico_s is not None) != (potencia_apos_pico is not None):
            raise ValueError('Informe duração do pico e potência posterior juntas')
        
        if duracao_pico_s is not None and (duracao_pico_s < 0 or potencia_apos_pico < 0):
            raise ValueError('Duração e potência posterior devem ser não negativas')
        
        t, vel, dt = 0.0, 0.0, .005
        meff = self.m*self.v['fator_inercia']
        while vel < alvo:
            # CORREÇÃO PROMPT 4.2: Aplicar corte temporal de potência
            p = potencia if duracao_pico_s is None or t < duracao_pico_s else potencia_apos_pico
            a = (self.forca(max(vel, .05), p) - self.resistencia(vel))/meff
            if a <= 1e-4:
                return None
            vel += a*dt
            t += dt
            if t > 120:
                return None
        return t


def partilha_tensao(torque_coroa, w_coroa, kes, i, R):
    """Mesma tensão nos dois motores do par: cada um entrega o que sua força contraeletromotriz permite."""
    soma = sum(k*ii for k, ii in zip(kes, i))/R
    V = (torque_coroa + sum(k*k*w_coroa*ii*ii for k, ii in zip(kes, i))/R)/soma
    return V, [(V - k*w_coroa*ii)/R for k, ii in zip(kes, i)]


def calcular_torque(cfg, mot, cor):
    ve = Veiculo(cfg, mot, cor)
    v = cfg['veiculo']
    disp = cfg['motor']['dispersao_constante_pct']/100
    n = len(ve.i)
    kes = [mot['ke']*(1 + disp*(n - 1 - 2*k)/(2*max(n - 1, 1))) for k in range(n)]
    R, Vmax, Ilim = mot['R'], cfg['motor']['tensao_V'], cfg['motor']['corrente_limite_A']
    kmh = 3.6
    alvo = v['velocidade_alvo_kmh']/kmh
    i_alvo = cfg['motor']['rpm_nominal']*math.pi/30*ve.r/alvo

    casos = []
    for nome, vel_kmh, rampa in (('cruzeiro no plano', 30, 0), ('rampa de 10 %', 10, .10),
                                 ('arrancada em rampa de 15 %', 2, .15)):
        vel = vel_kmh/kmh
        F = ve.resistencia(vel, rampa)
        torque_coroa = F/2*ve.r/ve.eta
        w_coroa = vel/ve.r
        V, correntes = partilha_tensao(torque_coroa, w_coroa, kes, ve.i, R)
        igual = torque_coroa/sum(k*ii for k, ii in zip(kes, ve.i))
        um = torque_coroa/(kes[0]*ve.i[0])
        # CORREÇÃO PROMPT 4.3: As perdas de cobre também são divididas pela eficiência do controlador
        # Energia total = energia mecânica / eta_mecanica + perdas_cobre
        # Tudo isso passa pelo controlador, então divide pela eta_controlador
        potencia = (F*vel/ve.eta + 2*n*igual**2*R)/v['rendimento_controlador']
        casos.append({
            'caso': nome, 'velocidade_kmh': vel_kmh, 'rampa_pct': 100*rampa,
            'forca_total_N': F, 'torque_por_roda_Nm': F/2*ve.r,
            'potencia_bateria_aprox_W': potencia,
            'comando_por_tensao': {'tensao_V': V, 'correntes_A': correntes,
                                   'parcela_pct': [100*c/sum(correntes) for c in correntes],
                                   'satura': V > Vmax, 'motor_gerando': any(c < 0 for c in correntes)},
            'comando_por_corrente': {'corrente_por_motor_A': igual},
            'um_motor_desligado': {'corrente_no_outro_A': um, 'acima_do_limite': um > Ilim},
        })

    # Motor de ímã com terminais em curto: torque de frenagem ke²·ω/R no eixo do motor.
    w_motor = 30/kmh/ve.r*ve.i[0]
    arrasto = mot['ke']**2*w_motor/R*ve.i[0]               # levado à coroa
    f_arrasto = arrasto/ve.r
    t_kp = BITOLA/1000
    curva = None
    Rc = v['raio_curva_m']
    if Rc > t_kp/2:
        vel = v['velocidade_curva_kmh']/kmh
        F = ve.resistencia(vel)
        w_in, w_out = vel*(Rc - t_kp/2)/Rc/ve.r, vel*(Rc + t_kp/2)/Rc/ve.r
        # Mesma tensão nos dois lados: resolver V para a força total.
        a = sum(k*ii for k, ii in zip(kes, ve.i))/R
        b = lambda w: sum(k*k*w*ii*ii for k, ii in zip(kes, ve.i))/R
        V = (F*ve.r/ve.eta + b(w_in) + b(w_out))/(2*a)
        f_in = (a*V - b(w_in))*ve.eta/ve.r
        f_out = (a*V - b(w_out))*ve.eta/ve.r
        curva = {'raio_m': Rc, 'velocidade_kmh': v['velocidade_curva_kmh'],
                 'razao_rotacao_externa_interna': w_out/w_in,
                 'tensao_unica': {'forca_interna_N': f_in, 'forca_externa_N': f_out,
                                  'momento_guinada_contra_curva_Nm': (f_in - f_out)*t_kp/2},
                 'comando_por_corrente': 'forças iguais; o lado externo gira mais rápido sem diferencial mecânico'}

    pico, cont = v['potencia_pico_W'], v['potencia_continua_W']
    return {
        'massa_kg': ve.m, 'cg_x_m': ve.x, 'cg_z_m': ve.h, 'origem_massa': ve.origem,
        'raio_roda_m': ve.r, 'reducao_por_motor': ve.i,
        'reducao_para_velocidade_alvo': i_alvo,
        'velocidade_livre_kmh': ve.velocidade_livre()*kmh,
        'velocidade_max_plano_continua_kmh': ve.vmax(cont)*kmh,
        'velocidade_max_plano_pico_kmh': ve.vmax(pico)*kmh,
        'rampa_max_10kmh_continua_pct': 100*ve.rampa_max(10/kmh, cont),
        'rampa_max_10kmh_pico_pct': 100*ve.rampa_max(10/kmh, pico),
        'rampa_max_arrancada_pico_pct': 100*ve.rampa_max(.5, pico),
        'tempo_0_30kmh_pico_s': ve.tempo_ate(30/kmh, pico, duracao_pico_s=15.0, potencia_apos_pico=cont),
        'nota_tempo_pico': 'Potência de pico limitada a 15 segundos; transição para potência contínua após esse limite.',
        'forca_arrancada_N': ve.forca(.05, pico, aderencia=False),
        'limite_aderencia_N': ve.limite_aderencia(),
        'arrancada_limitada_pela_aderencia': ve.forca(.05, pico, aderencia=False) > ve.limite_aderencia(),
        'constantes_motores_do_par_V_s_rad': kes,
        'casos': casos,
        'falha_em_curto_a_30kmh': {'torque_arrasto_na_coroa_Nm': arrasto,
                                   'forca_frenagem_na_roda_N': f_arrasto,
                                   'momento_guinada_Nm': f_arrasto*t_kp/2,
                                   'nota': 'motor de ímã em curto freia só um lado; prever corte ou desacoplamento'},
        'curva': curva,
        '_veiculo': ve,
    }


# ---------------------------------------------------------------- cubo

def calcular_cubo(cfg, mot, tor):
    c = cfg['cubo']
    ve = tor['_veiculo']
    if c['parafuso'] not in AREA_RESISTENTE or c['classe'] not in CLASSES:
        raise ValueError('Parafuso ou classe sem cadastro')
    positivo(('furos', c['furos']), ('diâmetro da furação', c['diametro_furacao_mm']),
             ('diâmetro do semieixo', c['diametro_semieixo_mm']), ('escoamento', c['escoamento_semieixo_MPa']))
    pico_motor = mot['ke']*cfg['motor']['corrente_limite_A']
    tracao = pico_motor*sum(ve.i)*ve.eta
    aderencia = ve.v['aderencia']*ve.normal_frente()/2*ve.r
    a = .8
    n_freio = ve.m*(GRAVIDADE*(ve.xr - ve.x) + a*ve.h)/ve.L/2
    frenagem = ve.v['aderencia']*n_freio*ve.r
    projeto = max(tracao*c['fator_choque'], frenagem if c['freio_no_chassi'] else 0.0)
    As = AREA_RESISTENTE[c['parafuso']]
    prova, ruptura = CLASSES[c['classe']]
    Fp = c['precarga_fracao_prova']*prova*As
    rb = c['diametro_furacao_mm']/2000
    escorregamento = c['furos']*Fp*c['atrito_flange']*rb
    corte = c['furos']*.6*ruptura*As/1.25*rb
    d = c['diametro_semieixo_mm']
    tau = 16*projeto*1000/(math.pi*d**3)
    tau_adm = .577*c['escoamento_semieixo_MPa']/c['coef_seguranca']
    d_min = (16*projeto*1000/(math.pi*tau_adm))**(1/3)
    return {
        'torque_tracao_pico_por_roda_Nm': tracao,
        'torque_limite_aderencia_estatico_Nm': aderencia,
        'torque_frenagem_0_8g_por_roda_Nm': frenagem,
        'torque_projeto_Nm': projeto,
        'criterio': ('tração de pico × fator de choque' +
                     (' ou frenagem pelo semieixo' if c['freio_no_chassi'] else '; freio no cubo não passa pelo semieixo')),
        'flange': {'parafusos': f"{c['furos']} × {c['parafuso']} {c['classe']} em Ø {f(c['diametro_furacao_mm'], 0)} mm",
                   'precarga_por_parafuso_N': Fp, 'torque_escorregamento_Nm': escorregamento,
                   'fator_escorregamento': escorregamento/projeto, 'torque_corte_parafusos_Nm': corte,
                   'fator_corte': corte/projeto},
        'semieixo': {'diametro_mm': d, 'tensao_torcao_MPa': tau, 'tensao_admissivel_MPa': tau_adm,
                     'diametro_minimo_macico_mm': d_min, 'atende': tau <= tau_adm},
        'referencia_cubo_original_Nm': c['torque_referencia_Nm'],
        'acima_da_referencia': (projeto > c['torque_referencia_Nm']) if c['torque_referencia_Nm'] else None,
    }


# ---------------------------------------------------------------- suspensão e esterço

def _circulos(c1, r1, c2, r2, referencia):
    d = dist(c1, c2)
    if d == 0 or d > r1 + r2 or d < abs(r1 - r2):
        return None
    a = (r1*r1 - r2*r2 + d*d)/(2*d)
    h = math.sqrt(max(r1*r1 - a*a, 0.0))
    u = ((c2[0] - c1[0])/d, (c2[1] - c1[1])/d)
    pm = somar(c1, u, a)
    opcoes = [somar(pm, (-u[1], u[0]), h), somar(pm, (u[1], -u[0]), h)]
    return min(opcoes, key=lambda p: dist(p, referencia))


def _intersecao_retas(p1, p2, p3, p4):
    d = (p1[0] - p2[0])*(p3[1] - p4[1]) - (p1[1] - p2[1])*(p3[0] - p4[0])
    if abs(d) < 1e-9:
        return None
    a = p1[0]*p2[1] - p1[1]*p2[0]
    b = p3[0]*p4[1] - p3[1]*p4[0]
    return ((a*(p3[0] - p4[0]) - (p1[0] - p2[0])*b)/d, (a*(p3[1] - p4[1]) - (p1[1] - p2[1])*b)/d)


class Suspensao:
    """Quadrilátero de braços sobrepostos em vista frontal, lado direito."""

    def __init__(self, cfg):
        s = cfg['suspensao']
        self.s = s
        self.W0 = tuple(s['roda'])
        self.Al, self.Bl0 = tuple(s['braco_inferior']['chassi']), tuple(s['braco_inferior']['manga'])
        self.Au, self.Bu0 = tuple(s['braco_superior']['chassi']), tuple(s['braco_superior']['manga'])
        self.Ll, self.Lu, self.Lk = dist(self.Al, self.Bl0), dist(self.Au, self.Bu0), dist(self.Bl0, self.Bu0)
        if min(self.Ll, self.Lu, self.Lk) <= 0:
            raise ValueError('Braços e manga devem ter comprimento positivo')
        self.th0 = math.atan2(self.Bl0[1] - self.Al[1], self.Bl0[0] - self.Al[0])
        self.ph0 = math.atan2(self.Bu0[1] - self.Bl0[1], self.Bu0[0] - self.Bl0[0])
        self.K0 = self.pino_em(self.Bl0, self.Bu0, self.W0[1])
        self.O0 = self.K0 if s['junta_externa_no_pino'] or not s['junta_externa'] else tuple(s['junta_externa'])
        a = s['amortecedores']
        self.Sb0, self.Sc = tuple(a['braco']), tuple(a['chassi'])
        self.J = tuple(s['junta_interna'])
        self.camb0 = math.radians(s['cambagem_estatica_graus'])

    @staticmethod
    def pino_em(Bl, Bu, z):
        t = (z - Bl[1])/(Bu[1] - Bl[1])
        return (Bl[0] + t*(Bu[0] - Bl[0]), z)

    def pose(self, th):
        Bl = somar(self.Al, (math.cos(th), math.sin(th)), self.Ll)
        Bu = _circulos(self.Au, self.Lu, Bl, self.Lk, self.Bu0)
        if Bu is None:
            return None
        dph = math.atan2(Bu[1] - Bl[1], Bu[0] - Bl[0]) - self.ph0

        def manga(p):
            return somar(Bl, girar((p[0] - self.Bl0[0], p[1] - self.Bl0[1]), dph))
        Sb = somar(self.Al, girar((self.Sb0[0] - self.Al[0], self.Sb0[1] - self.Al[1]), th - self.th0))
        return {'Bl': Bl, 'Bu': Bu, 'dph': dph, 'W': manga(self.W0), 'K': manga(self.K0),
                'O': manga(self.O0), 'Sb': Sb}

    def no_curso(self, curso):
        alvo = self.W0[1] + curso

        def g(th):
            p = self.pose(th)
            return None if p is None else p['W'][1] - alvo
        if abs(curso) < 1e-12:
            return self.pose(self.th0)
        vizinha = self.pose(self.th0 + .01)
        if vizinha is None:
            raise ValueError('Geometria bloqueada na vizinhança da posição estática')
        passo = .002 if (vizinha['W'][1] - self.W0[1])*curso > 0 else -.002
        a, ga = self.th0, g(self.th0)
        for k in range(1, 800):
            b = self.th0 + k*passo
            gb = g(b)
            if gb is None:
                break
            if ga*gb <= 0:
                for _ in range(60):
                    m = (a + b)/2
                    gm = g(m)
                    if ga*gm <= 0:
                        b = m
                    else:
                        a, ga = m, gm
                return self.pose((a + b)/2)
            a, ga = b, gb
        raise ValueError(f'Suspensão não alcança o curso de {f(curso, 0)} mm; braços travam')


def face_interna_y(W, giro, z):
    """y da face interna do pneu (retângulo de 90 mm) à altura z; giro anti-horário = −cambagem."""
    q0 = somar(W, girar((-LARGURA_PNEU/2, 0.0), giro))
    return q0[0] + (z - q0[1])*(-math.sin(giro)/math.cos(giro))


def _angulo(u, v):
    nu, nv = math.sqrt(sum(a*a for a in u)), math.sqrt(sum(a*a for a in v))
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(a*b for a, b in zip(u, v))/(nu*nv)))))


def calcular_suspensao(cfg, cor, tor):
    s = cfg['suspensao']
    sus = Suspensao(cfg)
    ve = tor['_veiculo']
    z_topo_longarina = PISO_Z - PISO.altura
    z_long = (z_topo_longarina - LONGARINA.altura, z_topo_longarina)
    y_long = largura_quadro(X_EIXO_DIANT)/2
    longarina = [(y_long - LONGARINA.largura, z_long[0]), (y_long, z_long[0]), (y_long, z_long[1]),
                 (y_long - LONGARINA.largura, z_long[1])]
    am = s['amortecedores']
    delta = math.radians(cfg['esterco']['angulo_projeto_graus'])
    e = dist(sus.K0, sus.O0)*(1 if sus.O0[0] >= sus.K0[0] else -1)
    L_semi0 = math.hypot(s['junta_interna_x_mm'], *(a - b for a, b in zip(sus.O0, sus.J)))
    cursos = sorted({-s['curso_extensao_mm'], -s['curso_extensao_mm']/2, 0.0,
                     s['curso_compressao_mm']/2, s['curso_compressao_mm']})
    linhas = []
    for c in cursos:
        p = sus.no_curso(c)
        camb = sus.camb0 - p['dph']
        giro = -camb      # cambagem negativa: topo para dentro, roda girada no sentido anti-horário
        contato = somar(p['W'], girar((0.0, -RAIO_RODA), giro))
        pneu = retangulo(p['W'], LARGURA_PNEU, 2*RAIO_RODA, giro)
        juntas = []
        for d in (-delta, 0.0, delta):
            # Eixo do cubo girado pela cambagem e pelo esterço em torno de pino vertical.
            eixo = (-math.cos(giro)*math.sin(d), math.cos(giro)*math.cos(d), math.sin(giro))
            K3 = (0.0, p['K'][0], p['K'][1])
            O3 = tuple(k + e*a for k, a in zip(K3, eixo))
            J3 = (s['junta_interna_x_mm'], sus.J[0], sus.J[1])
            semi = tuple(o - j for o, j in zip(O3, J3))
            juntas.append({'esterco_graus': math.degrees(d),
                           'comprimento_mm': math.sqrt(sum(x*x for x in semi)),
                           'angulo_junta_externa_graus': _angulo(semi, eixo),
                           'angulo_junta_interna_graus': _angulo(semi, (0.0, 1.0, 0.0))})
        linhas.append({
            'curso_mm': c, 'cambagem_graus': math.degrees(camb),
            'variacao_meia_bitola_mm': contato[0] - sus.W0[0],
            'centro_roda_y_mm': p['W'][0],
            'comprimento_amortecedor_mm': dist(p['Sb'], sus.Sc),
            'folga_pneu_longarina_mm': distancia_poligonos(pneu, longarina),
            'face_interna_na_longarina_y_mm': min(face_interna_y(p['W'], giro, z) for z in z_long),
            'semieixo': juntas,
            '_pose': p,
        })
    estatico = next(l for l in linhas if l['curso_mm'] == 0)
    curto = [l['comprimento_amortecedor_mm'] for l in linhas]
    p_mais, p_menos = sus.no_curso(1.0), sus.no_curso(-1.0)
    mr = (dist(p_menos['Sb'], sus.Sc) - dist(p_mais['Sb'], sus.Sc))/2
    carga_roda = ve.normal_frente()/2 - s['massa_nao_suspensa_kg']*GRAVIDADE
    forca_amort = carga_roda/(am['quantidade']*mr) if mr > 0 else None
    rigidez_roda = am['quantidade']*am['rigidez_N_mm']*mr**2 if am['rigidez_N_mm'] else None
    ic = _intersecao_retas(sus.Al, sus.Bl0, sus.Au, sus.Bu0)
    contato0 = (sus.W0[0], 0.0)
    if ic is None:
        u = _unit(sus.Al, sus.Bl0)
        ic = somar(contato0, u, 1.0)
    rc = _intersecao_retas(contato0, ic, (0.0, 0.0), (0.0, 1.0))
    kpi = math.degrees(math.atan2(sus.Bl0[0] - sus.Bu0[0], sus.Bu0[1] - sus.Bl0[1]))
    y_pino_solo = sus.pino_em(sus.Bl0, sus.Bu0, 0.0)[0]

    coroa = next(r for r in cor['rodas'] if r['tipo'] == 'coroa')
    segs = {'braço inferior': (sus.Al, sus.Bl0), 'braço superior': (sus.Au, sus.Bu0),
            'amortecedor': (sus.Sb0, sus.Sc), 'semieixo': (sus.J, sus.O0),
            'coroa': ((s['y_plano_corrente'], coroa['z'] - coroa['raio_externo_mm']),
                      (s['y_plano_corrente'], coroa['z'] + coroa['raio_externo_mm']))}
    pares = [('amortecedor', 'braço superior'), ('coroa', 'braço inferior'), ('coroa', 'braço superior'),
             ('coroa', 'amortecedor'), ('semieixo', 'amortecedor'), ('semieixo', 'braço inferior'),
             ('semieixo', 'braço superior')]
    cruzamentos = [f'{a} × {b}' for a, b in pares if segmentos_cruzam(*segs[a], *segs[b])]
    todas_juntas = [j for l in linhas for j in l['semieixo']]
    return {
        'geometria_estatica': {
            'comprimento_braco_inferior_mm': sus.Ll, 'comprimento_braco_superior_mm': sus.Lu,
            'inclinacao_pino_graus': kpi, 'raio_de_rolagem_no_solo_mm': sus.W0[0] - y_pino_solo,
            'afastamento_pino_centro_roda_mm': sus.W0[0] - sus.K0[0],
            'altura_centro_rolagem_mm': rc[1] if rc else None,
            'comprimento_semieixo_mm': L_semi0,
            'junta_externa_fora_do_pino_mm': abs(e),
        },
        'curso': [{k: v for k, v in l.items() if k != '_pose'} for l in linhas],
        'variacao_cambagem_graus': [min(l['cambagem_graus'] for l in linhas), max(l['cambagem_graus'] for l in linhas)],
        'amortecedores': {
            'comprimento_usado_mm': [min(curto), max(curto)],
            'disponivel_mm': [am['comprimento_comprimido_mm'], am['comprimento_estendido_mm']],
            'folga_compressao_mm': min(curto) - am['comprimento_comprimido_mm'],
            'folga_extensao_mm': am['comprimento_estendido_mm'] - max(curto),
            'relacao_movimento': mr, 'carga_estatica_suspensa_por_roda_N': carga_roda,
            'forca_estatica_por_amortecedor_N': forca_amort, 'rigidez_na_roda_N_mm': rigidez_roda,
        },
        'semieixo': {
            'variacao_comprimento_mm': [min(j['comprimento_mm'] for j in todas_juntas) - L_semi0,
                                        max(j['comprimento_mm'] for j in todas_juntas) - L_semi0],
            'angulo_max_junta_externa_graus': max(j['angulo_junta_externa_graus'] for j in todas_juntas),
            'angulo_max_junta_interna_graus': max(j['angulo_junta_interna_graus'] for j in todas_juntas),
            'limites_graus': [s['angulo_max_junta_externa_graus'], s['angulo_max_junta_interna_graus']],
            'curso_axial_disponivel_mm': s['curso_axial_junta_mm'],
        },
        'folga_minima_pneu_longarina_vista_frontal_mm': min(l['folga_pneu_longarina_mm'] for l in linhas),
        'deslocamento_interno_max_pneu_mm': max(0.0, estatico['face_interna_na_longarina_y_mm']
                                                 - min(l['face_interna_na_longarina_y_mm'] for l in linhas)),
        'cruzamentos_vista_frontal': cruzamentos,
        '_sus': sus, '_linhas': linhas, '_longarina': longarina,
    }


def quadro_planta():
    a, b = X_FRENTE_TRAP, X_EIXO_TRAS
    return [(a, -largura_quadro(a)/2), (b, -largura_quadro(b)/2), (b, largura_quadro(b)/2), (a, largura_quadro(a)/2)]


def calcular_esterco(cfg, sus):
    es = cfg['esterco']
    yw = sus['_sus'].W0[0]
    y_pino = yw if es['pivo_no_centro_da_roda'] else sus['_sus'].K0[0]
    obst = [('longarina', quadro_planta())]
    for o in es['obstaculos']:
        obst.append((o['nome'], [(o['x0'], o['y0']), (o['x1'], o['y0']), (o['x1'], o['y1']), (o['x0'], o['y1'])]))

    def folgas(psi, recuo=0.0):
        piv = (X_EIXO_DIANT, y_pino - recuo)
        centro = somar(piv, girar((0.0, yw - y_pino), psi))
        pneu = retangulo(centro, 2*RAIO_RODA, LARGURA_PNEU, psi)
        return {nome: distancia_poligonos(pneu, poly) for nome, poly in obst}, pneu

    def limite(sentido, recuo=0.0):
        anterior = 0.0
        for k in range(0, 901):
            ang = k*.1
            if min(folgas(sentido*math.radians(ang), recuo)[0].values()) < es['folga_minima_mm']:
                return anterior
            anterior = ang
        return anterior
    recuo = sus['deslocamento_interno_max_pneu_mm']
    lim = {'frente_para_dentro_graus': limite(1), 'tras_para_dentro_graus': limite(-1),
           'frente_para_dentro_com_curso_graus': limite(1, recuo), 'tras_para_dentro_com_curso_graus': limite(-1, recuo)}
    # Roda externa: frente para dentro; roda interna: traseira para dentro (lado direito).
    L = X_EIXO_TRAS - X_EIXO_DIANT
    t = 2*y_pino
    d_ext = math.radians(min(lim['frente_para_dentro_com_curso_graus'], 80))
    d_int_lim = math.radians(min(lim['tras_para_dentro_com_curso_graus'], 80))
    giro = None
    if d_ext > 0 and d_int_lim > 0:
        cot_int = 1/math.tan(d_ext) - t/L
        d_int = math.atan(1/cot_int) if cot_int > 0 else math.pi/2
        d_int = min(d_int, d_int_lim)
        d_ext_ok = math.atan(1/(1/math.tan(d_int) + t/L))
        Rc = L/math.tan(d_int) + t/2
        externo = math.hypot(L, Rc + yw + LARGURA_PNEU/2)
        giro = {'angulo_interno_graus': math.degrees(d_int), 'angulo_externo_ackermann_graus': math.degrees(d_ext_ok),
                'raio_no_eixo_traseiro_mm': Rc, 'diametro_giro_entre_meios_fios_m': 2*externo/1000}
    proj = math.radians(es['angulo_projeto_graus'])
    return {
        'pivo_y_mm': y_pino, 'afastamento_pivo_roda_mm': yw - y_pino,
        'folga_minima_adotada_mm': es['folga_minima_mm'],
        'limites': lim,
        'folgas_no_angulo_de_projeto': {
            'frente_para_dentro_mm': folgas(proj)[0], 'tras_para_dentro_mm': folgas(-proj)[0],
            'frente_para_dentro_com_curso_mm': folgas(proj, recuo)[0]},
        'folgas_por_angulo_frente_para_dentro_mm': {
            str(a): min(folgas(math.radians(a))[0].values()) for a in (20, 25, 30, 35, 40)},
        'giro': giro,
        '_folgas': folgas, '_lim': lim,
    }


# ---------------------------------------------------------------- integração

def calcular(cfg=None):
    cfg = mesclar(PADRAO, cfg)
    mot = constantes_motor(cfg)
    cor = calcular_corrente(cfg, mot)
    tor = calcular_torque(cfg, mot, cor)
    cub = calcular_cubo(cfg, mot, tor)
    sus = calcular_suspensao(cfg, cor, tor)
    est = calcular_esterco(cfg, sus)
    dados = {'aviso': AVISO, 'hipoteses': cfg, 'motor': mot, 'corrente': cor, 'torque': tor,
             'cubo': cub, 'suspensao': sus, 'esterco': est}
    dados['conclusoes'] = conclusoes(dados)
    return dados


def publico(valor):
    """Remove chaves internas (prefixo _) e objetos não serializáveis."""
    if isinstance(valor, dict):
        return {k: publico(v) for k, v in valor.items() if not str(k).startswith('_')}
    if isinstance(valor, (list, tuple)):
        return [publico(v) for v in valor]
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    return valor


def conclusoes(d):
    cor, tor, cub, sus, est = d['corrente'], d['torque'], d['cubo'], d['suspensao'], d['esterco']
    cfg = d['hipoteses']
    t = []
    pin = [r for r in cor['rodas'] if r['tipo'] == 'motor']
    coroa = next(r for r in cor['rodas'] if r['tipo'] == 'coroa')
    t.append(f"Corrente {cor['passo']}: {cor['elos_adotados']} elos por laço "
             f"({f(cor['elos_teoricos_posicao_informada'], 2)} na posição informada); "
             f"{cor['ajuste']['roda']} desloca {f(cor['ajuste']['deslocamento_montagem_mm'])} mm na montagem"
             + (f" e o rasgo precisa de ≥ {f(cor['ajuste']['curso_minimo_rasgo_mm'], 0)} mm para "
                f"{f(cfg['corrente']['alongamento_desgaste_pct'])} % de alongamento."
                if cor['ajuste']['curso_minimo_rasgo_mm'] else '; o ajuste não cobre o desgaste: rever o rasgo.'))
    pouco = [r for r in pin if r['dentes_engrenados'] < 3 or r['envolvimento_graus'] < 90]
    t.append('Envolvimento: ' + '; '.join(f"{r['nome']} {f(r['envolvimento_graus'], 0)}° ({f(r['dentes_engrenados'])} dentes)"
                                          for r in cor['rodas'])
             + ('. Atenção: pinhão com menos de 3 dentes ou 90° engrenados. Com as três rodas por fora, os dois '
                'pinhões dividem o que a coroa deixa (360° − envolvimento da coroa); aumentar com esticador '
                'interno, pinhão pelo lado de dentro (serpentina, motor girando ao contrário) ou mais dentes.'
                if pouco else '.'))
    inversos = [r['nome'] for r in cor['rodas'] if r['tipo'] == 'motor' and r['lado'] == 'interno']
    if inversos:
        t.append(f"Gira ao contrário da roda: {', '.join(inversos)}; inverter a polaridade e conferir o sentido "
                 "de giro admitido pelo motor e pelo controlador.")
    ruim = [x for x in cor['folgas_entre_rodas'] if x['folga_mm'] < cfg['corrente']['folga_entre_rodas_mm']]
    if ruim:
        t.append('Rodas dentadas com folga insuficiente: ' + '; '.join(f"{x['entre']} {f(x['folga_mm'])} mm" for x in ruim) + '.')
    t.append(f"Ramo frouxo na marcha à frente: {cor['ramo_frouxo_frente']}; em ré ou regeneração: {cor['ramo_frouxo_re']}. "
             f"O ramo entre os dois pinhões leva só o torque de um motor. Tração máxima {f(cor['tracao_maxima_N'], 0)} N; "
             f"fator {f(cor['fator_seguranca_ruptura'])} sobre a ruptura típica"
             + (' (abaixo do mínimo adotado).' if cor['fator_seguranca_ruptura'] < cfg['corrente']['fator_seguranca_minimo'] else '.'))
    cargas = ', '.join(f"{c['roda']} {f(c['carga_radial_no_eixo_N'], 0)} N" for c in cor['cargas_eixos_frente'])
    t.append(f"Carga radial de pico nos eixos: {cargas}; conferir com a carga admissível do eixo dos motores e dos mancais.")
    if cor['divisao_da_corrente']:
        dv = cor['divisao_da_corrente']
        t.append(f"Corrente disponível de {dv['elos_disponiveis']} elos: " +
                 (f"basta para os dois laços (sobram {dv['sobra_elos']})." if dv['basta']
                  else f"faltam {-dv['sobra_elos']} elos para dois laços de {dv['elos_por_laco']}."))
    else:
        t.append(f"Contar os elos da corrente doadora (--elos-disponiveis): dois laços exigem {2*cor['elos_adotados']}.")
    env = cor['envelope_vista_lateral_mm']['z']
    if env[1] > PISO_Z - LONGARINA.altura and env[0] < PISO_Z:
        t.append(f"O laço ocupa z = {f(env[0], 0)}–{f(env[1], 0)} mm e atravessa a faixa das longarinas e do piso "
                 f"({f(PISO_Z - LONGARINA.altura, 0)}–{f(PISO_Z, 0)} mm): o plano da corrente precisa ficar fora delas em y.")
    t.append(f"Redução {f(tor['reducao_por_motor'][0], 2)}:1 (alvo de {f(cfg['veiculo']['velocidade_alvo_kmh'], 0)} km/h pede "
             f"{f(tor['reducao_para_velocidade_alvo'], 2)}:1). Com {f(tor['massa_kg'], 0)} kg: "
             f"{f(tor['velocidade_max_plano_continua_kmh'], 0)} km/h no plano com {f(cfg['veiculo']['potencia_continua_W'], 0)} W, "
             f"{f(tor['velocidade_max_plano_pico_kmh'], 0)} km/h no pico; rampa a 10 km/h de "
             f"{f(tor['rampa_max_10kmh_continua_pct'], 0)} % contínua e {f(tor['rampa_max_10kmh_pico_pct'], 0)} % no pico; "
             f"arrancada em até {f(tor['rampa_max_arrancada_pico_pct'], 0)} %"
             + (', limitada pela aderência.' if tor['arrancada_limitada_pela_aderencia'] else '.'))
    c0 = tor['casos'][0]['comando_por_tensao']
    t.append(f"Partilha no par com {f(cfg['motor']['dispersao_constante_pct'], 0)} % de diferença entre motores, mesma tensão, "
             f"cruzeiro a 30 km/h: {' / '.join(f(p, 0) + ' %' for p in c0['parcela_pct'])}"
             + (' — um motor passa a gerar e freia o outro.' if c0['motor_gerando'] else '.')
             + ' Controle por corrente (torque) com mesmo valor de referência iguala a partilha.')
    falha = [c for c in tor['casos'] if c['um_motor_desligado']['acima_do_limite']]
    if falha:
        t.append('Com um motor desligado, o outro passa do limite de corrente em: ' + ', '.join(c['caso'] for c in falha) + '.')
    cu = tor['falha_em_curto_a_30kmh']
    t.append(f"Motor em curto a 30 km/h: ≈ {f(cu['forca_frenagem_na_roda_N'], 0)} N de frenagem em uma só roda "
             f"(guinada de {f(cu['momento_guinada_Nm'], 0)} N·m); exige contator ou fusível por motor e roda livre ou desacoplamento.")
    if tor['curva']:
        cv = tor['curva']
        t.append(f"Curva de {f(cv['raio_m'], 0)} m a {f(cv['velocidade_kmh'], 0)} km/h com uma só tensão nos dois lados: "
                 f"roda interna {f(cv['tensao_unica']['forca_interna_N'], 0)} N, externa {f(cv['tensao_unica']['forca_externa_N'], 0)} N "
                 f"(momento contra a curva de {f(cv['tensao_unica']['momento_guinada_contra_curva_Nm'], 0)} N·m). "
                 "Com controle de torque por lado, não há essa disputa.")
    fl, se = cub['flange'], cub['semieixo']
    t.append(f"Cubo: torque de projeto {f(cub['torque_projeto_Nm'], 0)} N·m por roda ({cub['criterio']}). "
             f"Flange {fl['parafusos']}: escorregamento × {f(fl['fator_escorregamento'])}, corte × {f(fl['fator_corte'])}. "
             f"Semieixo maciço Ø {f(se['diametro_mm'], 0)}: {f(se['tensao_torcao_MPa'], 0)} MPa contra "
             f"{f(se['tensao_admissivel_MPa'], 0)} admissíveis (mínimo Ø {f(se['diametro_minimo_macico_mm'])} mm)."
             + ('' if cub['acima_da_referencia'] is None else
                (' Acima' if cub['acima_da_referencia'] else ' Abaixo') + ' do torque de referência do cubo original.'))
    g = sus['geometria_estatica']
    t.append(f"Suspensão: braços de {f(g['comprimento_braco_inferior_mm'], 0)} e {f(g['comprimento_braco_superior_mm'], 0)} mm; "
             f"cambagem de {f(sus['variacao_cambagem_graus'][0])}° a {f(sus['variacao_cambagem_graus'][1])}° no curso; "
             f"pino a {f(g['afastamento_pino_centro_roda_mm'], 0)} mm do centro da roda e raio de rolagem de "
             f"{f(g['raio_de_rolagem_no_solo_mm'], 0)} mm no solo.")
    a = sus['amortecedores']
    t.append(f"Amortecedores: relação de movimento {f(a['relacao_movimento'], 2)}; usam {f(a['comprimento_usado_mm'][0], 0)}–"
             f"{f(a['comprimento_usado_mm'][1], 0)} mm de {f(a['disponivel_mm'][0], 0)}–{f(a['disponivel_mm'][1], 0)} disponíveis"
             + (' — fim de curso antes do batente: limitar curso ou mudar fixação.'
                if min(a['folga_compressao_mm'], a['folga_extensao_mm']) < 0 else '')
             + f"; {f(a['forca_estatica_por_amortecedor_N'], 0)} N estáticos em cada um.")
    sj = sus['semieixo']
    t.append(f"Semieixo de {f(g['comprimento_semieixo_mm'], 0)} mm: junta externa até {f(sj['angulo_max_junta_externa_graus'], 0)}° "
             f"e interna até {f(sj['angulo_max_junta_interna_graus'], 0)}° (curso × esterço de "
             f"{f(cfg['esterco']['angulo_projeto_graus'], 0)}°); variação de comprimento "
             f"{f(sj['variacao_comprimento_mm'][0])} a {f(sj['variacao_comprimento_mm'][1])} mm."
             + (' Acima dos limites adotados para as juntas.' if sj['angulo_max_junta_externa_graus'] > sj['limites_graus'][0]
                or sj['angulo_max_junta_interna_graus'] > sj['limites_graus'][1] else '')
             + (' Excede o curso axial adotado.' if max(map(abs, sj['variacao_comprimento_mm'])) > sj['curso_axial_disponivel_mm'] else ''))
    if sus['cruzamentos_vista_frontal']:
        t.append('Cruzam na vista frontal (exigem afastamento em x, verificar em 3D): ' + '; '.join(sus['cruzamentos_vista_frontal']) + '.')
    lim = est['limites']
    t.append(f"Esterço com pivô a {f(est['afastamento_pivo_roda_mm'], 0)} mm do centro da roda e folga mínima de "
             f"{f(est['folga_minima_adotada_mm'], 0)} mm: frente para dentro até {f(lim['frente_para_dentro_graus'])}° "
             f"({f(lim['frente_para_dentro_com_curso_graus'])}° com o pneu no pior curso), traseira para dentro até "
             f"{f(lim['tras_para_dentro_graus'])}°."
             + (f" Giro: {f(est['giro']['angulo_interno_graus'], 0)}° na roda interna, diâmetro ≈ "
                f"{f(est['giro']['diametro_giro_entre_meios_fios_m'])} m." if est['giro'] else ''))
    return t


# ---------------------------------------------------------------- relatório visual

class Tela:
    def __init__(self, x0, x1, z0, z1, largura=640):
        self.x0, self.z1 = x0, z1
        self.s = largura/(x1 - x0)
        self.w, self.h = largura + 40, (z1 - z0)*self.s + 40

    def p(self, x, z):
        return 20 + (x - self.x0)*self.s, 20 + (self.z1 - z)*self.s

    def abrir(self, titulo):
        return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w:.0f} {self.h:.0f}" role="img">'
                f'<title>{escape(titulo)}</title><rect width="100%" height="100%" class="fundo"/>']

    def linha(self, a, b, cls='', extra=''):
        (x1, y1), (x2, y2) = self.p(*a), self.p(*b)
        return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{cls}" {extra}/>'

    def circulo(self, c, r, cls=''):
        x, y = self.p(*c)
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r*self.s:.1f}" class="{cls}"/>'

    def poligono(self, pts, cls=''):
        return f'<polygon points="{" ".join("%.1f,%.1f" % self.p(*q) for q in pts)}" class="{cls}"/>'

    def texto(self, c, t, cls='rotulo'):
        x, y = self.p(*c)
        return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}">{escape(t)}</text>'


def svg_corrente(d):
    cor = d['corrente']
    geo = cor['_geo']
    t = Tela(150, 950, -20, 820, 800)
    s = t.abrir('Laço da corrente em vista lateral esquerda')
    s.append(t.linha((150, 0), (950, 0), 'solo'))
    s.append(t.poligono([(X_FRENTE_TRAP, PISO_Z - LONGARINA.altura), (950, PISO_Z - LONGARINA.altura),
                         (950, PISO_Z), (X_FRENTE_TRAP, PISO_Z)], 'estrutura'))
    s.append(t.texto((X_FRENTE_TRAP + 330, PISO_Z + 12), 'longarina e piso'))
    s.append(t.poligono([(461, 590), (806, 590), (806, 785), (461, 785)], 'bateria'))
    s.append(t.texto((470, 760), 'bateria (D-10)'))
    s.append(t.circulo((X_EIXO_DIANT, RAIO_RODA), RAIO_RODA, 'pneu-fantasma'))
    # Caminho completo: ramos retos e arcos sobre o círculo primitivo de cada roda.
    trechos, n = geo['trechos'], len(geo['trechos'])
    d_path = 'M%.1f,%.1f' % t.p(*trechos[0]['inicio'])
    for i, tr in enumerate(trechos):
        roda = geo['rodas'][(i + 1) % n]
        prox = trechos[(i + 1) % n]['inicio']
        d_path += ' L%.1f,%.1f' % t.p(*tr['fim'])
        d_path += ' A%.1f,%.1f 0 %d %d %.1f,%.1f' % (
            roda['raio_primitivo_mm']*t.s, roda['raio_primitivo_mm']*t.s,
            roda['envolvimento_graus'] > 180, roda['lado'] == 'interno', *t.p(*prox))
    s.append(f'<path d="{d_path} Z" class="corrente-laco"/>')
    tracao = {r['ramo']: r['tracao_N'] for r in cor['tracao_pico_frente']}
    maxima = max(tracao.values()) or 1
    for tr in geo['trechos']:
        v = tracao[f"{tr['de']} → {tr['para']}"]
        s.append(t.linha(tr['inicio'], tr['fim'], 'corrente', f'stroke-width="{1.5 + 4*v/maxima:.1f}"'))
    for r in geo['rodas']:
        s.append(t.circulo((r['x'], r['z']), r['raio_externo_mm'], 'roda-ext'))
        s.append(t.circulo((r['x'], r['z']), r['raio_primitivo_mm'], 'roda'))
        s.append(t.texto((r['x'] - r['raio_externo_mm'], r['z'] - r['raio_externo_mm'] - 22), f"{r['nome']} {r['dentes']}T"))
    s.append(t.texto((160, 800), 'Frente à esquerda · espessura do traço ∝ tração de pico à frente · sentido anti-horário'))
    return ''.join(s + ['</svg>'])


def svg_frontal(d):
    sus = d['suspensao']
    S, linhas = sus['_sus'], sus['_linhas']
    t = Tela(0, 760, -20, 560)
    s = t.abrir('Suspensão dianteira direita em vista frontal')
    s.append(t.linha((0, 0), (760, 0), 'solo'))
    s.append(t.linha((0, -20), (0, 560), 'eixo'))
    s.append(t.poligono(sus['_longarina'], 'estrutura'))
    for l in (linhas[0], linhas[-1]):
        p = l['_pose']
        s.append(t.poligono(retangulo(p['W'], LARGURA_PNEU, 2*RAIO_RODA, -math.radians(l['cambagem_graus'])), 'pneu-fantasma'))
    est = next(l for l in linhas if l['curso_mm'] == 0)['_pose']
    s.append(t.poligono(retangulo(est['W'], LARGURA_PNEU, 2*RAIO_RODA, -S.camb0), 'pneu'))
    s.append(t.linha(S.Al, est['Bl'], 'braco'))
    s.append(t.linha(S.Au, est['Bu'], 'braco'))
    s.append(t.linha(est['Bl'], est['Bu'], 'manga'))
    s.append(t.linha(est['Sb'], S.Sc, 'amortecedor'))
    s.append(t.linha(S.J, est['O'], 'semieixo'))
    cor = d['corrente']
    coroa = next(r for r in cor['rodas'] if r['tipo'] == 'coroa')
    y = d['hipoteses']['suspensao']['y_plano_corrente']
    s.append(t.linha((y, coroa['z'] - coroa['raio_externo_mm']), (y, coroa['z'] + coroa['raio_externo_mm']), 'corrente'))
    y0 = S.pino_em(S.Bl0, S.Bu0, 0.0)
    s.append(t.linha(y0, S.Bu0, 'pino'))
    for q in (S.Al, S.Au, est['Bl'], est['Bu'], S.Sc, S.J):
        s.append(t.circulo(q, 5, 'no'))
    s.append(t.texto((10, 540), 'Centro do veículo à esquerda · pneu cheio: estático; tracejados: fim de curso'))
    return ''.join(s + ['</svg>'])


def svg_planta(d):
    est = d['esterco']
    t = Tela(250, 1000, 320, 860)
    s = t.abrir('Varredura do pneu dianteiro direito em planta')
    s.append(t.poligono(quadro_planta(), 'estrutura'))
    for o in d['hipoteses']['esterco']['obstaculos']:
        s.append(t.poligono([(o['x0'], o['y0']), (o['x1'], o['y0']), (o['x1'], o['y1']), (o['x0'], o['y1'])], 'bateria'))
    folgas = est['_folgas']
    for sentido, chave in ((1, 'frente_para_dentro_graus'), (-1, 'tras_para_dentro_graus')):
        s.append(t.poligono(folgas(sentido*math.radians(est['_lim'][chave]))[1], 'pneu-fantasma'))
    s.append(t.poligono(folgas(0.0)[1], 'pneu'))
    s.append(t.circulo((X_EIXO_DIANT, est['pivo_y_mm']), 5, 'no'))
    s.append(t.texto((260, 340), 'Frente à esquerda · y para fora · tracejados: limites de esterço com a folga adotada'))
    return ''.join(s + ['</svg>'])


def documento(d):
    estilo = '''
:root{--ink:#172638;--muted:#536477;--paper:#f1f4f8;--card:#fff;--line:#dce3eb;--steel:#1F4E8C;--chain:#c2410c;--tire:#64748b;--warn:#fff7e6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ink:#e6edf5;--muted:#9fb0c3;--paper:#0f1722;--card:#172231;--line:#2a3a4e;--steel:#6ea0e0;--chain:#fb923c;--tire:#94a3b8;--warn:#3a2f17}}
:root[data-theme="dark"]{--ink:#e6edf5;--muted:#9fb0c3;--paper:#0f1722;--card:#172231;--line:#2a3a4e;--steel:#6ea0e0;--chain:#fb923c;--tire:#94a3b8;--warn:#3a2f17}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 'Segoe UI',Arial,sans-serif}
main{max-width:1100px;margin:auto;padding:24px 16px}h1{font-size:30px;margin:8px 0}h2{font-size:20px;margin:0 0 8px}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin:20px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}
.aviso{border-left:4px solid #d29b21;background:var(--warn);padding:14px}li{margin-bottom:8px}
svg{width:100%;height:auto;font-size:12px}.fundo{fill:var(--card)}.rotulo{fill:var(--muted)}
.solo{stroke:var(--muted);stroke-width:1.5}.eixo{stroke:var(--line);stroke-dasharray:4 4}
.estrutura{fill:var(--steel);fill-opacity:.25;stroke:var(--steel)}.bateria{fill:#d29b21;fill-opacity:.2;stroke:#d29b21}
.pneu{fill:var(--tire);fill-opacity:.45;stroke:var(--tire)}.pneu-fantasma{fill:none;stroke:var(--tire);stroke-dasharray:6 5}
.corrente{stroke:var(--chain);stroke-width:3;fill:none}.corrente-laco{stroke:var(--chain);stroke-width:1.5;fill:none}.roda{fill:none;stroke:var(--ink);stroke-width:1.5}.roda-ext{fill:none;stroke:var(--muted);stroke-dasharray:3 3}
.braco{stroke:var(--steel);stroke-width:5;stroke-linecap:round}.manga{stroke:var(--ink);stroke-width:6}.amortecedor{stroke:#16a34a;stroke-width:4}
.semieixo{stroke:var(--chain);stroke-width:4;stroke-dasharray:10 4}.pino{stroke:var(--muted);stroke-dasharray:2 4}.no{fill:var(--card);stroke:var(--ink);stroke-width:1.5}
dl{display:grid;grid-template-columns:minmax(160px,1fr) minmax(0,2fr);margin:0}dt,dd{margin:0;padding:6px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}dt{color:var(--muted)}dd dl{display:block}
details summary{cursor:pointer;font-weight:600}
@media(max-width:650px){dl{display:block}h1{font-size:24px}}
'''
    itens = ''.join(f'<li>{escape(c)}</li>' for c in d['conclusoes'])
    return f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Transmissão dianteira Hammerhead</title><style>{estilo}</style>
<main><p class="rotulo">HAMMERHEAD / C06 · PROPULSÃO, CUBO, SUSPENSÃO E ESTERÇO</p><h1>Transmissão dianteira — verificação de anteprojeto</h1>
<p class="aviso">{escape(AVISO)}</p>
<section><h2>Conclusões desta execução</h2><ol>{itens}</ol></section>
<section><h2>Corrente em vista lateral</h2>{svg_corrente(d)}</section>
<div class="grid"><section><h2>Suspensão em vista frontal</h2>{svg_frontal(d)}</section>
<section><h2>Esterço em planta</h2>{svg_planta(d)}</section></div>
<section><details><summary>Todos os resultados e hipóteses</summary>{tabela_dados(publico({k: v for k, v in d.items() if k != 'conclusoes'}))}</details></section>
</main></html>'''


def _main_duplo_a(argv=None):
    configurar_console()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--config', type=Path, help='JSON com as hipóteses a substituir (mesmas chaves de --salvar-config)')
    p.add_argument('--salvar-config', type=Path, help='Gravar as hipóteses padrão em JSON novo e sair')
    p.add_argument('--pinhao', type=int, help='Dentes dos dois pinhões')
    p.add_argument('--coroa', type=int, help='Dentes da coroa')
    p.add_argument('--passo', choices=sorted(CORRENTES), help='Corrente')
    p.add_argument('--elos-disponiveis', type=int, help='Elos da corrente doadora, para dividir em duas')
    p.add_argument('--massa', type=float, help='Massa total em kg (padrão: inventário estimado)')
    p.add_argument('--html', type=Path, help='Salvar relatório visual HTML (arquivo novo)')
    p.add_argument('--resumo', action='store_true', help='Imprimir só as conclusões')
    args = p.parse_args(argv)
    try:
        if args.salvar_config:
            with args.salvar_config.open('x', encoding='utf-8') as arq:
                json.dump(PADRAO, arq, ensure_ascii=False, indent=2)
            print(f'Hipóteses gravadas em {args.salvar_config.resolve()}', file=sys.stderr)
            return
        cfg = json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
        cfg = mesclar(PADRAO, cfg)
        for r in cfg['corrente']['rodas']:
            if r['tipo'] == 'motor' and args.pinhao:
                r['dentes'] = args.pinhao
            if r['tipo'] == 'coroa' and args.coroa:
                r['dentes'] = args.coroa
        if args.passo:
            cfg['corrente']['passo'] = args.passo
        if args.elos_disponiveis:
            cfg['corrente']['elos_disponiveis'] = args.elos_disponiveis
        if args.massa:
            cfg['veiculo']['massa_kg'] = args.massa
        dados = calcular(cfg)
        if args.html:
            if args.html.suffix.lower() != '.html':
                raise ValueError('O relatório visual exige extensão .html')
            with args.html.open('x', encoding='utf-8') as arq:
                arq.write(documento(dados))
            print(f'Relatório visual: {args.html.resolve()}', file=sys.stderr)
        if args.resumo:
            print('\n'.join(f'- {c}' for c in dados['conclusoes']))
        else:
            print(json.dumps(publico(dados), ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        p.error(str(exc))


# ---------------------------------------------------------------------------
# Opção A (2026-11-04): módulo esterçante "traseira de Biz". Cada módulo tem dois motores de 1 HP
# cujos pinhões acionam, por um laço de corrente, a coroa = pinhão da roda de 14″ da Biz no eixo
# da roda. O laço gira com o módulo; só o curso da balança muda o comprimento (esticador).
# Posições em mm; plano da corrente no lado direito (y > 0).
# ---------------------------------------------------------------------------
# Unificação: usar o mesmo raio de roda de PNEU_DIANT (90/90-14) para coroa e motor
RAIO_RODA_BIZ_MM = RAIO_RODA  # Unificado com a base p2_dorsal
DENTES_COROA_BIZ = 60                              # revisão 2026-11-05: redução 60/11 = 5,45 para a meta de 50 km/h; coroa de 428 na roda da Biz a confirmar
PADRAO_MODULO_BIZ = copy.deepcopy(PADRAO)
PADRAO_MODULO_BIZ['corrente'].update({
    'passo': '428',
    'rodas': [
        {'nome': 'motor A', 'tipo': 'motor', 'dentes': 11, 'x': 650.0, 'z': 372.0},   # atrás do eixo de esterço, o mais baixo possível sobre o piso
        {'nome': 'motor B', 'tipo': 'motor', 'dentes': 11, 'x': 530.0, 'z': 372.0},   # à frente do eixo de esterço
        {'nome': 'coroa', 'tipo': 'coroa', 'dentes': DENTES_COROA_BIZ, 'x': float(X_EIXO_DIANT), 'z': RAIO_RODA_BIZ_MM},
    ],
    'ajuste': {'roda': 'motor B', 'direcao': [-1.0, -1.0]},
})


def conclusoes_modulo_biz(cor):
    texto = [
        f"Corrente 428: {cor['elos_adotados']} elos ({cor['elos_teoricos_posicao_informada']:.2f} na posição informada), "
        f"comprimento {cor['comprimento_mm']:.0f} mm.",
        f"Tração máxima {cor['tracao_maxima_N']:.0f} N; fator sobre a ruptura típica {cor['fator_seguranca_ruptura']:.1f}.",
        f"Coroa de {DENTES_COROA_BIZ} dentes presumida na roda da Biz: confirmar no desmanche. "
        'Esticador na balança para o curso (comprimento da corrente varia com a balança).',
    ]
    if cor.get('ramo_frouxo_frente'):
        texto.append(f"Ramo frouxo na marcha à frente: {cor['ramo_frouxo_frente']}.")
    return texto


def calcular_modulo_biz(cfg=None):
    """Corrente e torque do módulo esterçante: laço de dois pinhões e uma coroa (roda da Biz)."""
    cfg = mesclar(PADRAO_MODULO_BIZ, cfg)
    mot = constantes_motor(cfg)
    cor = calcular_corrente(cfg, mot)
    tor = calcular_torque(cfg, mot, cor)
    return {'aviso': AVISO, 'arranjo': 'modulo_biz', 'hipoteses': cfg, 'motor': mot, 'corrente': cor, 'torque': tor,
            'conclusoes': conclusoes_modulo_biz(cor)}


REDUCOES_ESTUDO = (40/11, 48/11, 60/11, 7.0, 8.5, 10.0)


def tabela_reducoes(reducoes=REDUCOES_ESTUDO, cfg=None, base_nome='p2_dorsal'):
    """Velocidade × rampa para cada redução por motor, com massa e CG da base escolhida.

    A força de arrancada é limitada pela corrente do motor vezes a redução; a velocidade, pela rotação e pela potência.
    Reduções acima de ≈ 5,5 pedem dois estágios ou coroa maior que a da Biz (não verificado).
    """
    from configuracoes import cg_da_base
    cfg = mesclar(PADRAO_MODULO_BIZ, cfg)
    ref = cg_da_base(base_nome)
    cfg['veiculo'].update(massa_kg=ref['massa_kg'], cg_x_mm=1000*ref['cg_x_m'], cg_z_mm=1000*ref['cg_z_m'])
    mot = constantes_motor(cfg)
    cor = calcular_corrente(cfg, mot)
    linhas = []
    for red in reducoes:
        if not math.isfinite(red) or red <= 0:
            raise ValueError('Redução deve ser positiva e finita')
        c = copy.deepcopy(cor)
        pinhao = next(r['dentes'] for r in c['rodas'] if r['tipo'] == 'motor')
        for r in c['rodas']:
            if r['tipo'] == 'coroa':
                r['dentes'] = pinhao*red
        tor = calcular_torque(cfg, mot, c)
        linhas.append({'reducao': red, 'dentes_coroa_com_pinhao_de_' + str(pinhao): round(pinhao*red, 1),
                       'velocidade_livre_kmh': tor['velocidade_livre_kmh'],
                       'velocidade_max_continua_kmh': tor['velocidade_max_plano_continua_kmh'],
                       'velocidade_max_pico_kmh': tor['velocidade_max_plano_pico_kmh'],
                       'rampa_10kmh_continua_pct': tor['rampa_max_10kmh_continua_pct'],
                       'rampa_10kmh_pico_pct': tor['rampa_max_10kmh_pico_pct'],
                       'rampa_arrancada_pico_pct': tor['rampa_max_arrancada_pico_pct'],
                       'tempo_0_30kmh_s': tor['tempo_0_30kmh_pico_s'],
                       'forca_arrancada_N': tor['forca_arrancada_N']})
    return linhas


def _main_modulo_biz(argv=None):
    configurar_console()
    p = argparse.ArgumentParser(description='Corrente e torque do módulo esterçante (Opção A).')
    p.add_argument('--config', type=Path, help='JSON com hipóteses a substituir (mesmas chaves do arranjo duplo A)')
    p.add_argument('--resumo', action='store_true', help='Imprimir só as conclusões')
    p.add_argument('--reducoes', action='store_true', help='Imprimir a tabela velocidade × rampa por redução')
    args = p.parse_args(argv)
    try:
        if args.reducoes:
            print(json.dumps(tabela_reducoes(), ensure_ascii=False, indent=2))
            return
        cfg = json.loads(args.config.read_text(encoding='utf-8')) if args.config else None
        d = calcular_modulo_biz(cfg)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    if args.resumo:
        print('\n'.join(d['conclusoes']))
    else:
        corrente = {k: v for k, v in d['corrente'].items() if not k.startswith('_')}
        print(json.dumps({'corrente': corrente, 'conclusoes': d['conclusoes']}, ensure_ascii=False, indent=2, default=str))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument('--arranjo', choices=('modulo_biz', 'duplo_a'), default='modulo_biz')
    conhecido, resto = pre.parse_known_args(argv)
    if conhecido.arranjo == 'duplo_a':
        return _main_duplo_a(resto)
    return _main_modulo_biz(resto)


if __name__ == '__main__':
    main()
