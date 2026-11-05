"""Balancim em U (dois braços + tubo de pivô) para o layout de motores 'afastados_x' — CONCEITO, não aprovação.

Resolve no papel o conflito "braço único × eixo biapoiado" do estudo_decisoes_modulo: o eixo Ø28 apoia nos dois
lados da roda em dois braços longitudinais (traseiros), unidos por um tubo transversal que é também o pivô.
Os motores vão presos aos braços, então o conjunto gira inteiro em torno do pivô e a corrente #428 mantém o
comprimento em todo o curso (-40 a +80 mm).

Verificações: geometria (pneu, carroceria, motores, piso), excursão dos motores ao girar com o balancim,
folga motor × pneu (perfil de pneu ESTIMADO), cargas nos braços e no tubo de pivô, solda, lista de corte e massa.
Tensões nominais, sem fadiga, sem Kt, sem rigidez. Hipóteses marcadas como tal; medir antes de cortar aço.

Uso: python balancim_em_u.py [--L 315] [--xs 140] [--csv]
"""
import argparse
import csv
import math
import sys
from pathlib import Path

import transmissao_dianteira as td
import varredura_modulo_completo as v
from fcl_eixo_balanco import MU, R as R_CARREGADO, FZ_2X, ESPACAMENTO
from fcl_eixo_garfo import momento_max
from garfo_dimensionamento import prop_tubo, TUBOS

ROOT = Path(__file__).resolve().parent

X_EIXO, Z_EIXO, YR = v.X_EIXO, v.Z_EIXO, v.YR
R_PNEU = v.RAIO_RODA                  # 258 mm (80/100-14)
R_ARO = 177.8                         # aro 14"
LARGURA_PNEU = v.LARGURA_PNEU
Y_CARROCERIA = v.Y_MAX_CARROCERIA
Z_PISO = v.Z_PISO_ACABADO
SY_ACO = 350.0                        # MPa, tubo (hipótese; confirmar norma/fornecedor)
FS_MINIMO = 1.3                       # critério do projeto
FS_BRACO = 2.0                        # recomendado para elemento primário de suspensão
RHO_FREIO = 0.150                     # m, braço de reação do freio
LADO_FILETE_MM = 5.0
ADM_FILETE_MPA = 145.0                # 0,3·Fu do eletrodo E70 (nominal)
DENSIDADE = 7.85e-6                   # kg/mm³
FOLGA_MIN = 10.0
PAREDE_MIN_MM = 3.0                   # parede mínima de tubo estrutural soldado (evita 2 mm: queima na solda e amassa na orelha)
FOLGA_PNEU_ESTRUTURA = 25.0
D_MOTOR, D_FLANGE, E_FLANGE, L_MOTOR = 103.0, 140.0, 12.0, 190.0
Y_PLANO_CORRENTE = v.CORRENTE['y_plano_mm']      # 685

LAYOUTS = {
    'original': ((650.0, 372.0), (530.0, 372.0)),
    'afastados_x': ((757.0, 372.0), (443.0, 372.0)),   # z=372 é praticamente o mínimo: abaixo de 370,4 o ramo da corrente toca a ponta dos dentes da coroa de 60 (ver folga_ramo_coroa)
    'pinhoes_490': ((650.0, 490.0), (530.0, 490.0)),
    'afastados_x_B_a_frente': ((757.0, 372.0), (389.0, 372.0)),   # B com o corpo (x ate 440,5) antes do inicio do leito (x=441)
}


# ---------------------------------------------------------------- geometria
def geometria_u(L=315.0, x_s=140.0, d_braco=50.8, d_trav=50.8, d_perna=63.5):
    """Estações do U (mm). L = distância pivô → eixo; x_s = distância do plano da roda ao centro de cada braço."""
    x_pivo = X_EIXO - L
    y_int, y_ext = YR - x_s, YR + x_s
    apoio_min = 100.0 + 8.0 + 12.0 + 10.0      # rolamento (±100) + meia largura + espaçador + meia orelha
    return {
        'L_mm': L, 'x_pivo_mm': x_pivo, 'z_pivo_mm': Z_EIXO,
        'y_braco_interno_mm': y_int, 'y_braco_externo_mm': y_ext,
        'extremo_externo_mm': y_ext + d_braco/2,
        'excesso_sobre_carroceria_mm': y_ext + d_braco/2 - Y_CARROCERIA,
        'folga_tubo_pivo_pneu_mm': L - R_PNEU - d_trav/2,
        'folga_perna_pneu_mm': L - R_PNEU - d_perna/2,
        'x_s_minimo_mm': apoio_min, 'folga_apoio_rolamento_mm': x_s - apoio_min,
        'vao_entre_orelhas_mm': 2*x_s,
        'comprimento_tubo_pivo_mm': 2*x_s + d_braco + 2*25.0,
    }


def _girar(x, z, curso, L):
    xp = X_EIXO - L
    th = math.asin(curso/L)
    dx, dz = x - xp, z - Z_EIXO
    return xp + dx*math.cos(th) - dz*math.sin(th), Z_EIXO + dx*math.sin(th) + dz*math.cos(th)


def excursao_motores(layout, L=315.0, cursos=(-40.0, 0.0, 80.0)):
    """Posição dos motores ao girar com o balancim (rotação rígida em torno do pivô)."""
    saida = {'por_curso': {}}
    zmins, zmaxs = [], []
    for c in cursos:
        pts = [_girar(x, z, c, L) for (x, z) in layout]
        saida['por_curso'][c] = [(round(x, 1), round(z, 1)) for x, z in pts]
        zmins.append(min(z for x, z in pts) - D_MOTOR/2)
        zmaxs.append(max(z for x, z in pts) + D_MOTOR/2)
    saida.update(z_min_corpo_mm=min(zmins), z_max_corpo_mm=max(zmaxs),
                 invasao_piso_mm=max(0.0, Z_PISO - min(zmins)), deslocamento_vertical_mm=max(zmaxs) - min(zmins))
    return saida


def _semi_largura_pneu(r):
    """Meia largura do pneu na altura do raio r (mm) — perfil ESTIMADO: 25 mm no aro, 45 mm no ombro."""
    if r <= R_ARO:
        return 25.0
    if r >= R_PNEU - 20:
        return LARGURA_PNEU/2
    return 25.0 + (r - R_ARO)/((R_PNEU - 20) - R_ARO)*(LARGURA_PNEU/2 - 25.0)


def _folga_cilindro_pneu(x, z, y_max, raio):
    g = math.inf
    for k in range(72):
        a = 2*math.pi*k/72
        r = math.hypot(x + raio*math.cos(a) - X_EIXO, z + raio*math.sin(a) - Z_EIXO)
        if R_ARO < r < R_PNEU:
            g = min(g, (YR - _semi_largura_pneu(r)) - y_max)
    return g


def folga_motor_pneu(layout, deslocamento_interno=0.0):
    """Menor folga (mm) entre corpo/flange dos motores e o flanco do pneu (perfil estimado). <0 = interfere."""
    y = Y_PLANO_CORRENTE - deslocamento_interno
    corpo = min(_folga_cilindro_pneu(x, z, y, D_MOTOR/2) for x, z in layout)
    flange = min(_folga_cilindro_pneu(x, z, y + E_FLANGE, D_FLANGE/2) for x, z in layout)
    return {'corpo_mm': corpo, 'flange_mm': flange, 'menor_mm': min(corpo, flange)}


def deslocamento_interno_minimo(layout, folga=FOLGA_MIN):
    """Quanto deslocar motores + plano da corrente + coroa para dentro (mm) para ter 'folga' do pneu."""
    d = 0.0
    while folga_motor_pneu(layout, d)['menor_mm'] < folga and d < 150:
        d += 1.0
    return d


def folga_braco_interno_motor(layout, L=315.0, x_s=140.0, d_braco=50.8, deslocamento_interno=0.0):
    """Folga vertical (mm) entre o braço interno e o corpo dos motores que ficam sobre ele (x entre pivô e eixo).
    Como os motores giram com o braço, a folga é a mesma em todo o curso."""
    x_pivo = X_EIXO - L
    y_braco = YR - x_s
    y_hi = Y_PLANO_CORRENTE - deslocamento_interno
    y_lo = y_hi - L_MOTOR
    if not (y_lo < y_braco + d_braco/2 and y_braco - d_braco/2 < y_hi):
        return math.inf
    gaps = [(z - D_MOTOR/2) - (Z_EIXO + d_braco/2) for x, z in layout if x_pivo - D_MOTOR/2 < x < X_EIXO + D_MOTOR/2]
    return min(gaps) if gaps else math.inf


PASSO = v.CORRENTE['passo_mm']
RAIO_PRIMITIVO_PINHAO = PASSO/(2*math.sin(math.pi/11))
X_LEITO_FRENTE, X_LEITO_TRASEIRA = 441.0, 2236.1
# Prancha reduzida 47 mm de cada lado em relação às larguras de 1000 e 520 mm.
MEIA_LARGURA_LEITO_FRENTE, MEIA_LARGURA_LEITO_TRASEIRA = 453.0, 213.0


def folga_ramo_coroa(layout, n_coroa=60):
    """Folga (mm) entre o ramo da corrente que liga os dois pinhões (por cima) e a ponta dos dentes da coroa.
    `transmissao_dianteira.laco` usa o círculo PRIMITIVO da coroa e aceita ramo que toca os dentes; esta checagem não."""
    (xa, za), (xb, zb) = layout
    comp = math.hypot(xb - xa, zb - za)
    nx, nz = -(zb - za)/comp, (xb - xa)/comp
    if nz < 0:
        nx, nz = -nx, -nz
    px, pz = xa + RAIO_PRIMITIVO_PINHAO*nx, za + RAIO_PRIMITIVO_PINHAO*nz
    distancia_abaixo = -((X_EIXO - px)*nx + (Z_EIXO - pz)*nz)
    return distancia_abaixo - td.raio_externo(PASSO, n_coroa)


def z_pinhao_minimo(n_coroa=60, margem=FOLGA_MIN, d_braco=50.8):
    """Menor altura do pinhão (os dois à mesma altura) pelos dois critérios: ramo × dentes da coroa e corpo do motor × braço interno."""
    pelo_ramo = Z_EIXO + td.raio_externo(PASSO, n_coroa) + margem - RAIO_PRIMITIVO_PINHAO
    pelo_braco = Z_EIXO + d_braco/2 + margem + D_MOTOR/2
    return {'pelo_ramo_mm': pelo_ramo, 'pelo_braco_mm': pelo_braco, 'minimo_mm': max(pelo_ramo, pelo_braco)}


def meia_largura_leito(x):
    """Meia-largura nominal do trapézio reduzido: 453 em x=441 a 213 em x=2236,1."""
    t = (x - X_LEITO_FRENTE)/(X_LEITO_TRASEIRA - X_LEITO_FRENTE)
    return MEIA_LARGURA_LEITO_FRENTE + t*(MEIA_LARGURA_LEITO_TRASEIRA - MEIA_LARGURA_LEITO_FRENTE)


def invasao_leito(layout, deslocamento_interno=0.0):
    """Quanto (mm) o corpo de cada motor entra na largura do leito, em planta (retângulo x ± raio, y do plano da corrente
    para dentro por L_MOTOR). O motor ocupa y = y_plano − desloc − 190 … y_plano − desloc."""
    y_baixo = Y_PLANO_CORRENTE - deslocamento_interno - L_MOTOR
    invasoes = []
    for x, z in layout:
        x0, x1 = x - D_MOTOR/2, x + D_MOTOR/2
        if x1 <= X_LEITO_FRENTE or x0 >= X_LEITO_TRASEIRA:
            invasoes.append(0.0)
            continue
        invasoes.append(max(0.0, meia_largura_leito(max(x0, X_LEITO_FRENTE)) - y_baixo))
    return {'por_motor_mm': invasoes, 'max_mm': max(invasoes)}


def invasao_leito_curso(layout, deslocamento_interno=0.0, L=315.0, passo_mm=5.0):
    """Projeção conservadora dos motores ao longo do curso; esterço em zero.

    A sobreposição em planta não demonstra colisão 3D. A amostragem não prova
    folga entre amostras nem considera flanges, direção, ou deformação.
    """
    if not math.isfinite(passo_mm) or passo_mm <= 0:
        raise ValueError('passo_mm deve ser positivo e finito')
    cursos = [-40.0]
    while cursos[-1] + passo_mm < 80.0:
        cursos.append(cursos[-1] + passo_mm)
    cursos.append(80.0)
    amostras = []
    for curso in cursos:
        movido = tuple(_girar(x, z, curso, L) for x, z in layout)
        inv = invasao_leito(movido, deslocamento_interno)
        amostras.append({'curso_mm': curso, **inv})
    pior = max(amostras, key=lambda a: a['max_mm'])
    return {'max_mm': pior['max_mm'], 'curso_mm': pior['curso_mm'],
            'amostras': len(amostras), 'passo_mm': passo_mm}


# ---------------------------------------------------------------- cargas e seções
def cargas_braco(L=315.0, x_s=140.0, fz=FZ_2X):
    """Esforços no braço mais carregado (Fz 2x, μ = 0,8, roda externa). Soma conservadora dos efeitos."""
    xs_m = x_s/1000
    fy = MU*fz
    c = fy*R_CARREGADO/ESPACAMENTO
    _, rv_e, rv_d = momento_max(xs_m, fz/2 - c, fz/2 + c)
    rz_curva = max(abs(rv_e), abs(rv_d))
    fx = MU*fz
    rz_freio = fz/2
    f_braco = fx*R_CARREGADO/RHO_FREIO
    m_v_curva = rz_curva*L/1000
    m_h_curva = fy*L/1000
    m_v_freio = rz_freio*L/1000 + f_braco*(L/1000 - RHO_FREIO)
    return {
        'Rz_curva_N': rz_curva, 'Fy_N': fy, 'F_braco_freio_N': f_braco,
        'M_junta_curva_Nm': math.hypot(m_v_curva, m_h_curva),
        'M_junta_freio_Nm': m_v_freio,
        'M_junta_max_Nm': max(math.hypot(m_v_curva, m_h_curva), m_v_freio),
        'T_tubo_pivo_Nm': rz_curva*L/1000,          # amortecedor central: cada braço leva Rz·L ao tubo
    }


def tubo_fs(D, t, momento_nm, torque_nm=0.0):
    A, I, W, J = prop_tubo(D, t)
    sig = momento_nm*1000/W
    tau = torque_nm*1000*(D/2)/J
    vm = math.sqrt(sig**2 + 3*tau**2)
    return {'D': D, 'esp': t, 'massa_kg_m': A*DENSIDADE*1000, 'sigma_MPa': sig, 'tau_MPa': tau, 'VM_MPa': vm,
            'FS': SY_ACO/vm if vm else math.inf}


def escolher_tubo(momento_nm, torque_nm=0.0, fs=FS_BRACO):
    """Tubo redondo comercial mais leve (da lista do projeto) com FS >= fs."""
    ok = [tubo_fs(D, t, momento_nm, torque_nm) for D, t in TUBOS]
    ok = [r for r in ok if r['FS'] >= fs and r['esp'] >= PAREDE_MIN_MM]
    return min(ok, key=lambda r: r['massa_kg_m']) if ok else None


def solda_junta(d_tubo, momento_nm, perna=LADO_FILETE_MM):
    """Filete circular em volta do tubo (Zw = π/4·d²·a); tensão nominal de cisalhamento no filete."""
    a = 0.707*perna
    zw = math.pi/4*d_tubo**2*a
    tau = momento_nm*1000/zw
    return {'perna_mm': perna, 'tau_MPa': tau, 'FS': ADM_FILETE_MPA/tau}


def perna_filete_minima(d_tubo, momento_nm, fs=1.5):
    """Menor perna de filete (mm, passo 1) que dá FS >= fs na junta braço–tubo de pivô."""
    perna = 3.0
    while solda_junta(d_tubo, momento_nm, perna)['FS'] < fs and perna < 12:
        perna += 1.0
    return perna


# ---------------------------------------------------------------- projeto completo
def projeto(L=315.0, x_s=140.0, layout_nome='afastados_x'):
    layout = LAYOUTS[layout_nome]
    cg = cargas_braco(L, x_s)
    braco = escolher_tubo(cg['M_junta_max_Nm'], 0.0, FS_BRACO)
    trav = escolher_tubo(0.3*cg['T_tubo_pivo_Nm'], cg['T_tubo_pivo_Nm'], FS_BRACO)   # torção + flexão residual (30% de T)
    if braco is None or trav is None:
        raise ValueError('nenhum tubo da lista atende; revisar L, x_s ou lista de tubos')
    g = geometria_u(L, x_s, braco['D'], trav['D'])
    exc = excursao_motores(layout, L)
    desloc = deslocamento_interno_minimo(layout)
    pneu0 = folga_motor_pneu(layout, 0.0)
    pneu1 = folga_motor_pneu(layout, desloc)
    arm_gap = folga_braco_interno_motor(layout, L, x_s, braco['D'], desloc)
    solda = solda_junta(braco['D'], cg['M_junta_max_Nm'])
    solda['perna_recomendada_mm'] = perna_filete_minima(braco['D'], cg['M_junta_max_Nm'])
    comp_braco = L + 40.0
    comp_trav = g['comprimento_tubo_pivo_mm']
    massa_tubos = 2*comp_braco*braco['massa_kg_m']/1000 + comp_trav*trav['massa_kg_m']/1000
    pecas = [
        ('Braço do balancim (interno/externo)', 2, f"tubo Ø{braco['D']}×{braco['esp']} aço", f"{comp_braco:.0f} mm",
         'corte a 90° + boca de lobo na junta com o tubo de pivô', 2*comp_braco*braco['massa_kg_m']/1000),
        ('Tubo de pivô', 1, f"tubo Ø{trav['D']}×{trav['esp']} aço", f"{comp_trav:.0f} mm",
         'corte a 90°; alojar buchas/rolamentos nas pontas (usinagem)', comp_trav*trav['massa_kg_m']/1000),
        ('Orelha do eixo (uma por braço)', 2, 'chapa 8 mm', '80 × 100 mm, furo Ø24 (ponta M24x1,5 do eixo)',
         'corte a laser/plasma; furo alargado após soldar (alinhamento do par)', 2*0.08*0.1*0.008*7850),
        ('Console de motor (um por motor)', 2, 'chapa 6 mm dobrada em L', '≈ 180 × 120 mm, furos 4×M9 em quadrado de 75 mm',
         'furos oblongos para ajustar a corrente; solda no braço', 2*0.18*0.12*0.006*7850),
        ('Braço de reação do freio', 1, 'barra 30×6', '100 mm, ρ = 150 mm', 'conforme braco_reacao_freio.py', 0.14),
        ('Suporte do amortecedor central', 1, 'chapa 6 mm', '≈ 100 × 80 mm', 'soldado no tubo de pivô', 0.4),
    ]
    massa_total = massa_tubos + sum(p[5] for p in pecas[2:])
    return {'layout': layout_nome, 'geometria': g, 'cargas': cg, 'braco': braco, 'tubo_pivo': trav,
            'solda_junta_braco': solda, 'excursao_motores': exc, 'folga_motor_pneu_sem_ajuste': pneu0,
            'deslocamento_interno_mm': desloc, 'folga_motor_pneu_com_ajuste': pneu1,
            'folga_braco_interno_motor_mm': arm_gap, 'pecas': pecas, 'massa_estrutura_kg': massa_total,
            'massa_motores_por_roda_kg': 2*14.2}


def avisos(p):
    a = []
    g = p['geometria']
    if g['folga_tubo_pivo_pneu_mm'] < FOLGA_PNEU_ESTRUTURA:
        a.append(f"tubo de pivô a {g['folga_tubo_pivo_pneu_mm']:.0f} mm do pneu (< {FOLGA_PNEU_ESTRUTURA:.0f}): aumentar L")
    if g['folga_perna_pneu_mm'] < FOLGA_PNEU_ESTRUTURA:
        a.append(f"perna no pivô a {g['folga_perna_pneu_mm']:.0f} mm do pneu (< {FOLGA_PNEU_ESTRUTURA:.0f}): aumentar L")
    if g['excesso_sobre_carroceria_mm'] > 0:
        a.append(f"braço externo {g['excesso_sobre_carroceria_mm']:.0f} mm além da carroceria (y={Y_CARROCERIA:.0f}): paralama local")
    if g['folga_apoio_rolamento_mm'] < 0:
        a.append('x_s menor que o mínimo para o rolamento + espaçador + orelha')
    e = p['excursao_motores']
    if e['invasao_piso_mm'] > 0:
        a.append(f"motores descem {e['invasao_piso_mm']:.0f} mm abaixo do piso no curso -40: rebaixo no piso ou motores mais altos")
    a.append(f"motores sobem até z = {e['z_max_corpo_mm']:.0f} mm (deslocamento vertical {e['deslocamento_vertical_mm']:.0f} mm): "
             'conferir espaço sob o assento/pernas do piloto')
    if p['folga_motor_pneu_sem_ajuste']['menor_mm'] < FOLGA_MIN:
        a.append(f"motor/flange {p['folga_motor_pneu_sem_ajuste']['menor_mm']:.0f} mm do pneu: deslocar motores, coroa e plano da "
                 f"corrente {p['deslocamento_interno_mm']:.0f} mm para dentro (perfil de pneu estimado)")
    lay = LAYOUTS[p['layout']]
    fr = folga_ramo_coroa(lay)
    if fr < FOLGA_MIN:
        a.append(f"ramo da corrente a {fr:.1f} mm da ponta dos dentes da coroa (< {FOLGA_MIN:.0f}): subir os pinhões")
    inv = invasao_leito(lay, p['deslocamento_interno_mm'])
    if inv['max_mm'] > 0:
        a.append(f"com o deslocamento de {p['deslocamento_interno_mm']:.0f} mm para afastar do pneu, o corpo dos motores entra até "
                 f"{inv['max_mm']:.0f} mm na largura do leito (sem deslocamento: {invasao_leito(lay, 0)['max_mm']:.0f} mm)")
    if p['solda_junta_braco']['FS'] < 1.5:
        a.append(f"filete de {p['solda_junta_braco']['perna_mm']:.0f} mm na junta braço–tubo dá FS {p['solda_junta_braco']['FS']:.2f}: "
                 f"usar perna ≥ {p['solda_junta_braco']['perna_recomendada_mm']:.0f} mm (ou penetração total)")
    if p['folga_braco_interno_motor_mm'] < FOLGA_MIN:
        a.append('braço interno interfere com o corpo do motor')
    return a


def avaliar_layout(layout, L=315.0, n_coroa=60):
    """Todas as métricas de um par de pinhões (A, B) de uma vez, para comparar alternativas."""
    (xa, za), (xb, zb) = layout
    rodas = [{'nome': 'motor A', 'dentes': 11, 'x': xa, 'z': za},
             {'nome': 'motor B', 'dentes': 11, 'x': xb, 'z': zb},
             {'nome': 'coroa', 'dentes': n_coroa, 'x': float(X_EIXO), 'z': float(Z_EIXO)}]
    try:
        res = td.laco(rodas, PASSO)
        elos = res['elos']
        dentes = min(r['dentes_engrenados'] for r in res['rodas'] if r['nome'].startswith('motor'))
    except ValueError as e:
        elos, dentes = None, None
    desloc = deslocamento_interno_minimo(layout)
    exc = excursao_motores(layout, L)
    return {'elos': elos, 'dentes_motor': dentes, 'folga_ramo_dentes_mm': folga_ramo_coroa(layout, n_coroa),
            'deslocamento_pneu_mm': desloc,
            'invasao_leito_sem_desloc_mm': invasao_leito(layout, 0.0)['max_mm'],
            'invasao_leito_com_desloc_mm': invasao_leito(layout, desloc)['max_mm'],
            'invasao_leito_curso': invasao_leito_curso(layout, desloc, L),
            'folga_braco_mm': folga_braco_interno_motor(layout, L, 140.0, 57.2, desloc),
            'z_min_corpo_mm': exc['z_min_corpo_mm'], 'z_max_corpo_mm': exc['z_max_corpo_mm']}


def buscar_layouts(L=315.0, n_coroa=60, deslocamento_max=45.0, dentes_min=3.2, passo_grade=20,
                   x_range=(300, 960), z_range=(320, 561), zmin_piso=None):
    """Posições (pinhão A atrás, B à frente) que cumprem: corrente (laço calculável, >= dentes_min, ramo >= 10 mm da ponta
    dos dentes), folga do pneu com deslocamento <= deslocamento_max, braço interno >= 10 mm do corpo dos motores e NENHUMA
    entrada no leito em planta nas amostras de curso com esterço zero. zmin_piso (opcional): exige corpo acima dessa cota
    durante o curso. Não verifica esterço, flanges, batentes ou outros obstáculos. Ordena pelo CG mais baixo dos motores."""
    pts = [(x, z) for x in range(x_range[0], x_range[1], passo_grade) for z in range(z_range[0], z_range[1], passo_grade)]
    achados = []
    for A in pts:
        for B in pts:
            if A[0] <= B[0]:
                continue
            lay = (A, B)
            rodas = [{'nome': 'motor A', 'dentes': 11, 'x': A[0], 'z': A[1]},
                     {'nome': 'motor B', 'dentes': 11, 'x': B[0], 'z': B[1]},
                     {'nome': 'coroa', 'dentes': n_coroa, 'x': float(X_EIXO), 'z': float(Z_EIXO)}]
            if any(math.hypot(a['x']-c['x'], a['z']-c['z']) - td.raio_externo(PASSO, a['dentes']) - td.raio_externo(PASSO, c['dentes']) < FOLGA_MIN
                   for i, a in enumerate(rodas) for c in rodas[i+1:]):
                continue
            if folga_ramo_coroa(lay, n_coroa) < FOLGA_MIN:
                continue
            try:
                res = td.laco(rodas, PASSO)
            except ValueError:
                continue
            dentes = min(r['dentes_engrenados'] for r in res['rodas'] if r['nome'].startswith('motor'))
            if dentes < dentes_min:
                continue
            desloc = deslocamento_interno_minimo(lay)
            if desloc > deslocamento_max or invasao_leito(lay, desloc)['max_mm'] > 0:
                continue
            if invasao_leito_curso(lay, desloc, L)['max_mm'] > 0:
                continue
            if folga_braco_interno_motor(lay, L, 140.0, 57.2, desloc) < FOLGA_MIN:
                continue
            exc = excursao_motores(lay, L)
            if zmin_piso is not None and exc['z_min_corpo_mm'] < zmin_piso:
                continue
            achados.append({'A': A, 'B': B, 'dentes': dentes, 'elos': res['elos'], 'deslocamento_interno_mm': desloc,
                            'z_medio_mm': (A[1]+B[1])/2, 'z_max_corpo_mm': exc['z_max_corpo_mm'],
                            'z_min_corpo_mm': exc['z_min_corpo_mm']})
    return sorted(achados, key=lambda r: (r['z_medio_mm'], r['z_max_corpo_mm']))


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--L', type=float, default=315.0, help='distância pivô → eixo (mm)')
    ap.add_argument('--xs', type=float, default=140.0, help='plano da roda → centro de cada braço (mm)')
    ap.add_argument('--layout', choices=sorted(LAYOUTS), default='afastados_x')
    ap.add_argument('--csv', action='store_true', help='grava balancim_em_u_lista_corte.csv')
    ap.add_argument('--buscar', action='store_true', help='lista layouts alternativos que cumprem as restrições')
    a = ap.parse_args(argv)
    p = projeto(a.L, a.xs, a.layout)
    g, c = p['geometria'], p['cargas']
    print(f"Balancim em U — layout {p['layout']}, L = {g['L_mm']:.0f} mm, pivô em x = {g['x_pivo_mm']:.0f} mm")
    print(f"  braços em y = {g['y_braco_interno_mm']:.0f} / {g['y_braco_externo_mm']:.0f} mm (vão {g['vao_entre_orelhas_mm']:.0f} mm)")
    print(f"  braço: tubo Ø{p['braco']['D']}×{p['braco']['esp']}  FS {p['braco']['FS']:.2f} com M = {c['M_junta_max_Nm']:.0f} N·m na junta")
    print(f"  tubo de pivô: Ø{p['tubo_pivo']['D']}×{p['tubo_pivo']['esp']}  FS {p['tubo_pivo']['FS']:.2f} com T = {c['T_tubo_pivo_Nm']:.0f} N·m")
    print(f"  solda de filete {p['solda_junta_braco']['perna_mm']:.0f} mm na junta braço–tubo: FS {p['solda_junta_braco']['FS']:.2f}")
    print(f"  massa da estrutura ≈ {p['massa_estrutura_kg']:.1f} kg (+ {p['massa_motores_por_roda_kg']:.1f} kg de motores por roda)")
    print(f"  folga braço interno × corpo do motor B: {p['folga_braco_interno_motor_mm']:.0f} mm; "
          f"folga tubo de pivô × pneu: {g['folga_tubo_pivo_pneu_mm']:.0f} mm; perna no pivô × pneu: {g['folga_perna_pneu_mm']:.0f} mm")
    print('Avisos:')
    for t in avisos(p):
        print('  -', t)
    if a.buscar:
        print('Layouts alternativos (CG mais baixo primeiro):')
        for r in buscar_layouts(a.L)[:8]:
            print('  ', {k: (round(x, 1) if isinstance(x, float) else x) for k, x in r.items()})
    if a.csv:
        with (ROOT/'balancim_em_u_lista_corte.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(['peca', 'qtd', 'material', 'dimensao', 'processo', 'massa_total_kg'])
            for peca in p['pecas']:
                w.writerow([peca[0], peca[1], peca[2], peca[3], peca[4], f'{peca[5]:.2f}'.replace('.', ',')])
    return p


if __name__ == '__main__':
    main()
