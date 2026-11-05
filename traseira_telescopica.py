"""
Suspensão traseira: duas hastes telescópicas (haste interna 51410-KSS-C01: 355 mm, Ø externo 26 mm,
parede NÃO medida) + camisa externa (deslizante) + arco de lâmina de mola. CONCEITO. Não é aprovação.

Carga: reação traseira estática com 2 ocupantes = 147 kgf (ensaio_integrado.estado(2)); cenário de projeto
análogo ao da dianteira: Fz 2x + força horizontal μ·Fz (qualquer direção). μ = 0,8. Sem fadiga.
Cada haste leva metade (eixo rígido). Tensões nominais.
"""
import math
from fcl_eixo_balanco import MU

G = 9.80665
FZ_EST = 147.0 * G                 # N, roda traseira
FZ_2X = 2 * FZ_EST
SY_HASTE = 350.0                   # MPa (hipótese; confirmar material da peça Honda)
D_HASTE = 26.0
L_HASTE = 355.0
E = 210e3                          # MPa
FS_ALVO = 1.3


def momento_haste(fz=FZ_2X, d_camisa_topo_mm=200.0, l_exposto_mm=195.0):
    """Momento no grampo (cabeça): F_h por haste × (eixo→topo da camisa + trecho exposto)."""
    f_h = MU * fz / 2
    return f_h, f_h * (d_camisa_topo_mm + l_exposto_mm) / 1000     # N, N·m


def tensao_haste(m_nm, d_mm=D_HASTE, parede_mm=None):
    di = 0 if parede_mm is None else d_mm - 2 * parede_mm
    w = math.pi * (d_mm**4 - di**4) / (32 * d_mm)                   # mm³
    return m_nm * 1000 / w, w


def l_exposto_max(parede_mm, fz=FZ_2X, d_camisa_topo_mm=200.0):
    """Maior trecho exposto da haste para FS >= 1,3 na flexão."""
    f_h = MU * fz / 2
    _, w = tensao_haste(0, parede_mm=parede_mm)
    m_adm = SY_HASTE / FS_ALVO * w / 1000                            # N·m
    return m_adm / f_h * 1000 - d_camisa_topo_mm


def pressao_bucha(f_h, d_baixo_mm=40.0, l_ov_mm=100.0, d_mm=D_HASTE, l_bucha_mm=20.0):
    r_inf = f_h * (d_baixo_mm + l_ov_mm) / l_ov_mm
    return r_inf, r_inf / (d_mm * l_bucha_mm)


def rigidez_alvo(curso_mm=120.0, sag_max=0.4, fator_batente=0.8, fz_est=FZ_EST):
    """Rigidez de roda mínima: sag estático <= 40% do curso e 2x estático <= 80% do curso."""
    k1 = fz_est / (sag_max * curso_mm)
    k2 = 2 * fz_est / (fator_batente * curso_mm)
    k = max(k1, k2)
    m = fz_est / G
    f = math.sqrt(k * 1000 / m) / (2 * math.pi)
    c_crit = 2 * math.sqrt(k * 1000 * m)
    return {'k_N_mm': k, 'freq_Hz': f, 'sag_mm': fz_est / k, 'c_crit_Ns_m': c_crit,
            'c_zeta03_Ns_m': 0.3 * c_crit}


def arco(k_arco_n_mm, delta_max_mm, comprimento_m, sigma_adm=800.0):
    """Lâmina retangular biapoiada, carga central: k = 4·E·b·h³/L³; σ = 6·E·h·δ/L²."""
    k = k_arco_n_mm * 1000                                           # N/m
    d = delta_max_mm / 1000
    h = sigma_adm * 1e6 * comprimento_m**2 / (6 * E * 1e6 * d)       # m
    b = k * comprimento_m**3 / (4 * E * 1e6 * h**3)                  # m
    return {'L_mm': comprimento_m * 1000, 'h_mm': h * 1000, 'b_mm': b * 1000,
            'F_max_N': k_arco_n_mm * delta_max_mm}


if __name__ == '__main__':
    print(f"Fz estático traseiro {FZ_EST:.0f} N; 2x {FZ_2X:.0f} N")
    f_h, m = momento_haste()
    print(f"Por haste: F_h={f_h:.0f} N, M no grampo={m:.0f} N·m (lever 395 mm)")
    for t in (None, 2.0, 3.0, 4.0):
        s, w = tensao_haste(m, parede_mm=t)
        print(f"  Ø26 {'maciça' if t is None else f'parede {t}'}: σ={s:.0f} MPa FS={SY_HASTE/s:.2f} "
              f"L_exposto_max={l_exposto_max(t):.0f} mm")
    print("Bucha inferior:", pressao_bucha(f_h))
    r = rigidez_alvo()
    print("Alvo:", {k: round(v, 2) for k, v in r.items()})
    for kf in (0, 10, 20):
        ka = r['k_N_mm'] - kf
        print(f"  molas das hastes {kf} N/mm -> arco {ka:.0f} N/mm:",
              [{k: round(v) for k, v in arco(ka, 96, L).items()} for L in (0.8, 1.0)])
