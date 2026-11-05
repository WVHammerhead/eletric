"""
Dimensionamento preliminar do garfo (duas pernas tubulares + orelhas) — CONCEITO.
Não é aprovação. Tensões nominais, sem fadiga, soldas detalhadas, flambagem local ou rigidez.

Cargas (Fz 2x = 2393 N, μ = 0,8, r = 0,2578 m, x_s = 175 mm), por perna:
  - Fx do freio: μFz/2 por perna no eixo; na perna do freio soma-se a força do braço
    (3,29 kN a ρ = 150 mm) — SOMA CONSERVADORA (o sinal real tende a cancelar parte).
  - Fy axial: 0,8·Fz absorvida numa só orelha; flexão fora do plano = Fy·H.
  - Axial na perna: Fz/2 ± Fy·r/(2·x_s).
H = distância eixo -> engaste da perna no cabeçote (parâmetro; a definir).
Aço da perna: Sy = 350 MPa (hipótese; confirmar tubo/norma). Critério FS >= 1,3.
"""
import math
from fcl_eixo_balanco import MU, R, FZ_2X
from braco_reacao_freio import braco

SY = 350.0
FS_ALVO = 1.3
X_S = 0.175
RHO = 0.150
OFFSET_TAB_M = 0.050   # distância da linha da força do braço ao eixo do tubo (hipótese)
TUBOS = [(D, t) for D in (38.1, 44.5, 50.8, 57.2, 63.5, 76.2) for t in (2.0, 2.65, 3.0, 4.0)]


def prop_tubo(D, t):
    d = D - 2 * t
    A = math.pi * (D**2 - d**2) / 4
    I = math.pi * (D**4 - d**4) / 64
    return A, I, I / (D / 2), 2 * I   # área, I, W (mm³), J (mm⁴)


def cargas_perna(h_m, fx_frac, fy_frac, perna_freio=True, fz=FZ_2X):
    fx, fy = fx_frac * MU * fz, fy_frac * MU * fz
    f_braco = braco(RHO * 1000, 100, 30, 6, torque=fx * R)['F_N'] if (perna_freio and fx > 0) else 0.0
    m_ip = (fx / 2) * h_m + f_braco * (h_m - RHO)           # plano da roda
    m_op = fy * h_m                                          # fora do plano (orelha mais carregada)
    axial = fz / 2 + fy * R / (2 * X_S)
    t_loc = f_braco * OFFSET_TAB_M                           # torção local no tubo
    return {'M_ip': m_ip, 'M_op': m_op, 'axial_N': axial, 'T_Nm': t_loc, 'F_braco_N': f_braco}


def tensao(D, t, c):
    A, I, W, J = prop_tubo(D, t)
    sig = math.hypot(c['M_ip'], c['M_op']) * 1000 / W + c['axial_N'] / A
    tau = c['T_Nm'] * 1000 * (D / 2) / J
    return math.sqrt(sig**2 + 3 * tau**2)


def casos(h_m):
    return {'freio reto (perna do braço)': cargas_perna(h_m, 1, 0),
            'curva externa': cargas_perna(h_m, 0, 1),
            'curva+freio 45° (perna do braço)': cargas_perna(h_m, math.sqrt(.5), math.sqrt(.5))}


def escolher(h_m):
    cs = casos(h_m)
    ok = []
    for D, t in TUBOS:
        vm = max(tensao(D, t, c) for c in cs.values())
        if SY / vm >= FS_ALVO:
            A = prop_tubo(D, t)[0]
            ok.append((A, D, t, SY / vm))
    return min(ok) if ok else None, cs


def orelha(reacao_n=2607.0, axial_n=1914.0, esp=20.0, d_furo=24.0, borda=36.0, mu_atrito=0.15):
    """Orelha-placa com furo Ø24: esmagamento, rasgamento e aperto da porca contra o axial."""
    return {'pressao_furo_MPa': reacao_n / (d_furo * esp),
            'tracao_secao_liq_MPa': reacao_n / ((2 * borda - d_furo) * esp),
            'cisalhamento_rasgo_MPa': reacao_n / (2 * (borda - d_furo / 2) * esp),
            'pre_carga_min_axial_kN': axial_n / (mu_atrito * 2) / 1000}


if __name__ == '__main__':
    for h in (0.25, 0.30, 0.35):
        esc, cs = escolher(h)
        print(f"\nH = {h*1000:.0f} mm")
        for n, c in cs.items():
            print(f"  {n:34s} Mip={c['M_ip']:.0f} Mop={c['M_op']:.0f} N·m axial={c['axial_N']:.0f} N T_loc={c['T_Nm']:.0f}")
        print("  tubo mínimo:", f"Ø{esc[1]}x{esc[2]} (A={esc[0]:.0f} mm², FS pior={esc[3]:.2f})" if esc else "nenhum da lista")
    print("\nOrelha 20 mm / furo Ø24 / borda 36:", {k: round(v, 1) for k, v in orelha().items()})
