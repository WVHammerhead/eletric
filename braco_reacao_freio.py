"""
Conceito do braço de reação do freio (espelho -> garfo). NÃO é dimensionamento nem aprovação.

O espelho (backing plate) gira livre sobre uma bucha de centragem no eixo e é preso ao
garfo por um braço limitador, que leva o torque de frenagem para fora do eixo.
Torque de projeto = limite de aderência da roda com Fz 2x: T = μ·Fz·r (494 N·m).
Barra de aço baixo carbono (Sy ≈ 250 MPa, hipótese), parafuso M8 classe 8.8, ambos os sentidos
(tração e compressão). Tensões nominais, sem fadiga/impacto.
"""
import math
from fcl_eixo_balanco import MU, R, FZ_2X

SY_BARRA = 250.0      # MPa (hipótese: aço 1020/ASTM A36; confirmar)
E = 200e3             # MPa
RM_PARAFUSO = 800.0   # MPa, classe 8.8
AS_M8 = 36.6          # mm², área resistente M8
FS_ALVO = 2.0         # braço é elemento de segurança: FS maior que o do eixo


def torque_projeto(fz=FZ_2X):
    return MU * fz * R


def braco(rho_mm, comp_mm, largura, espessura, d_furo=8.0, torque=None, fator_folga=1.0):
    """Verifica barra biarticulada (tração/compressão). rho: distância eixo -> parafuso do garfo."""
    T = torque_projeto() if torque is None else torque
    F = T * fator_folga / (rho_mm / 1000)          # N
    area = largura * espessura
    area_liq = (largura - d_furo) * espessura
    sig_t = F / area_liq
    I = largura * espessura**3 / 12                 # eixo fraco
    p_cr = math.pi**2 * E * I / comp_mm**2          # Euler biarticulado
    tau_parafuso_duplo = F / (2 * AS_M8)            # cisalhamento duplo (garfo/clevis)
    cis_adm = 0.6 * RM_PARAFUSO * 0.6               # 0,6·Rm de cisalhamento, com redução de 0,6
    pressao = F / (d_furo * espessura)
    return {'rho_mm': rho_mm, 'F_N': F, 'tracao_MPa': sig_t, 'FS_tracao': SY_BARRA / sig_t,
            'FS_flambagem': p_cr / F, 'tau_parafuso_MPa': tau_parafuso_duplo,
            'FS_parafuso': cis_adm / tau_parafuso_duplo, 'pressao_furo_MPa': pressao,
            'FS_furo': SY_BARRA * 1.5 / pressao,
            'ok': min(SY_BARRA / sig_t, p_cr / F, cis_adm / tau_parafuso_duplo) >= FS_ALVO}


def main():
    print(f"Torque de projeto: {torque_projeto():.0f} N·m")
    for rho in (100, 150, 200):
        for (c, b, e) in ((100, 30, 6), (100, 25, 5)):
            r = braco(rho, c, b, e)
            print(f"rho={rho} barra {b}x{e} L={c}: F={r['F_N']:.0f} N  σ={r['tracao_MPa']:.0f} MPa "
                  f"FS_tr={r['FS_tracao']:.1f} FS_flamb={r['FS_flambagem']:.1f} "
                  f"FS_parafuso={r['FS_parafuso']:.1f} FS_furo={r['FS_furo']:.1f} {'OK' if r['ok'] else 'NOK'}")


if __name__ == '__main__':
    main()
