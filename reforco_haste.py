"""
Reforço da haste Ø26 (parede mínima) — borracha x camisa de aço. CONCEITO; nominal, sem fadiga.
Momento de projeto no grampo: 456 N·m (traseira_telescopica.momento_haste: Fz 2x + μ·Fz, alavanca 395 mm).
Hipótese: parede da haste 1,5 mm e 2,0 mm (limites; NÃO medida). Camisa de aço Sy 350 MPa.
Camisa 'rigidamente acoplada' = ajuste com interferência + adesivo estrutural/pinos nas pontas, de modo que
as duas seções fletem juntas (mesma curvatura). Sem acoplamento, a haste fica sozinha.
"""
import math
from traseira_telescopica import momento_haste, SY_HASTE, FS_ALVO

E_ACO = 210e3      # MPa
E_BORRACHA = 10.0  # MPa (Shore A 60-70, ordem de grandeza)
ALAVANCA_MM = 395.0


def inercia(d_ext, d_int):
    return math.pi * (d_ext**4 - d_int**4) / 64


def haste_sozinha(parede):
    f, m = momento_haste()
    i = inercia(26, 26 - 2 * parede)
    return {'I_mm4': i, 'sigma_MPa': m * 1000 * 13 / i, 'FS': SY_HASTE / (m * 1000 * 13 / i)}


def com_borracha(parede, esp_borracha, d_camisa_int=None):
    """Haste + camada de borracha (+ camisa externa fina): ganho de rigidez da borracha."""
    i_h = inercia(26, 26 - 2 * parede)
    r_ext = 13 + esp_borracha
    i_b = inercia(2 * r_ext, 26)
    ei_total = E_ACO * i_h + E_BORRACHA * i_b
    return {'ganho_EI_pct': 100 * (E_BORRACHA * i_b) / (E_ACO * i_h), 'EI_total_Nmm2': ei_total}


def com_camisa(parede, d_camisa_ext, parede_camisa, acoplada=True):
    """Camisa de aço sobre a haste (ID = 26). Acoplada: fletem juntas; tensão máxima na fibra externa da camisa."""
    f, m = momento_haste()
    i_h = inercia(26, 26 - 2 * parede)
    i_c = inercia(d_camisa_ext, d_camisa_ext - 2 * parede_camisa)
    i_tot = i_h + i_c if acoplada else i_h
    r = d_camisa_ext / 2 if acoplada else 13
    sig = m * 1000 * r / i_tot
    delta = f * ALAVANCA_MM**3 / (3 * E_ACO * i_tot)       # mm, engastada (limite superior; camisa/bucha ajudam)
    massa_kg_m = 7.85e-3 * math.pi * (d_camisa_ext**2 - (d_camisa_ext - 2 * parede_camisa)**2) / 4 * 1.0
    return {'I_mm4': i_tot, 'sigma_MPa': sig, 'FS': SY_HASTE / sig, 'flecha_mm': delta,
            'massa_camisa_kg_por_m': massa_kg_m}


if __name__ == '__main__':
    for t in (1.5, 2.0):
        hs = haste_sozinha(t)
        print(f"\nHaste parede {t}: sozinha FS={hs['FS']:.2f}")
        for e in (3, 6):
            print(f"  + borracha {e} mm: ganho de EI = {com_borracha(t, e)['ganho_EI_pct']:.3f} %")
        for d, tc in ((32, 3), (34, 3), (34, 4), (38, 3)):
            r = com_camisa(t, d, tc)
            print(f"  + camisa aço Ø{d}x{tc}: FS={r['FS']:.2f}  flecha={r['flecha_mm']:.1f} mm  "
                  f"{r['massa_camisa_kg_por_m']:.2f} kg/m")


# ---------------------------------------------------------------------------
# Decisão do usuário (05/11/2026): camisa de aço Ø34×3 como superfície de deslize.
# Geometria preliminar da haste de 355 mm: grampo 60 + exposto 195 + sobreposição 100 (extensão).
# Camisa externa deslizante com ~260 mm de comprimento (cabe sobreposição de 220 mm na compressão
# de 120 mm + fundo), logo eixo -> topo da camisa ≈ 230 mm e alavanca eixo -> grampo ≈ 425 mm.
# ---------------------------------------------------------------------------
CAMISA_REFORCO = (34.0, 3.0)
DESLIZANTE_FURO_MM = 37.0       # Ø34 + bucha de 1,5 mm de parede
DESLIZANTE_TUBO = (44.5, 3.0)
EIXO_TOPO_CAMISA_MM = 230.0
EXPOSTO_MM = 195.0


def adotado(parede_haste=1.5, bucha_l_mm=20.0, sobreposicao_mm=100.0, d_baixo_mm=40.0):
    f, m = momento_haste(d_camisa_topo_mm=EIXO_TOPO_CAMISA_MM, l_exposto_mm=EXPOSTO_MM)
    d, tc = CAMISA_REFORCO
    i = inercia(26, 26 - 2 * parede_haste) + inercia(d, d - 2 * tc)
    sig = m * 1000 * (d / 2) / i
    r_bucha = f * (d_baixo_mm + sobreposicao_mm) / sobreposicao_mm
    p_bucha = r_bucha / (d * bucha_l_mm)
    de, te = DESLIZANTE_TUBO
    w = math.pi * (de**4 - (de - 2 * te)**4) / (32 * de)
    m_desl = f * d_baixo_mm / 1000
    return {'F_h_N': f, 'M_grampo_Nm': m, 'FS_camisa': SY_HASTE / sig,
            'pressao_bucha_MPa': p_bucha, 'sigma_deslizante_MPa': m_desl * 1000 / w,
            'comprimento_camisa_reforco_mm': EXPOSTO_MM + sobreposicao_mm}


if __name__ == '__main__':
    print('\nADOTADO Ø34×3:')
    for t in (1.5, 2.0):
        print(f'  haste {t}:', {k: round(v, 2) for k, v in adotado(t).items()})
