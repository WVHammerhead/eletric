"""
Cabeçote (travessa) e pivô de direção do garfo — CONCEITO preliminar. Não é aprovação.
Tensões nominais, sem fadiga, soldas detalhadas, rigidez ou vida dos rolamentos (só carga estática).

PROMPT 1: caixa Ø95 mm (sede Ø85 do 30209); altura derivada do capô (geometria_caixa) com rolamentos dentro da caixa e
travessa cruzando-a; perna interna verificada em 3D contra motores/corrente (varredura_modulo_completo).

Geometria: pernas H = 470 mm (eixo -> travessa), raio carregado 257,8 mm -> travessa a 727,8 mm do solo.
Eixo de esterço vertical a 89 mm para dentro do plano médio da roda (Decisao_modulo_biz.md);
pernas a ±175 mm do plano médio; caixa de direção Ø95mm (sede Ø85mm do rolamento 30209),
altura 160 mm, com topo limitado a 811 mm (capô). Caixa posicionada de 651 a 811 mm.
Rolamentos de rolos cônicos do pivô com afastamento s entre centros.
Carga: Fz 2x (2393 N) + força horizontal resultante μ·Fz (1914 N) em qualquer direção.
Aço do pivô: Sy = 310 MPa (1045 normalizado); travessa Sy = 350 MPa (hipótese). FS >= 1,3.
"""
import math
from fcl_eixo_balanco import MU, R, FZ_2X
from varredura_modulo_completo import CAIXA_DIRECAO, Z_CAPO_MAX, deslocamento_perna_interna_minimo
from garfo_dimensionamento import cargas_perna, prop_tubo, escolher, casos, tensao, TUBOS

H = 0.470
Z_TRAVESSA = R + H
E_ESTERCO = 0.089          # eixo de esterço a 89 mm para dentro do plano médio
X_PERNA = 0.175
FOLGA_ROL = 0.040          # travessa -> centro do rolamento inferior
ESPACAMENTO_ROL = 0.120    # entre centros dos rolamentos do pivô
SY_PIVO, SY_TRAV, FS_ALVO = 310.0, 350.0, 1.3
C0_30209 = 73.0            # kN, menor valor de listagens (Schaeffler 82 kN); confirmar no catálogo
F_H = MU * FZ_2X

# Caixa de direção e capô — fonte única: varredura_modulo_completo (CAIXA_DIRECAO, Z_CAPO_MAX)
CAIXA_DIAMETRO_MM = CAIXA_DIRECAO['diametro_mm']      # >= 95 mm para a sede Ø85 do rolamento 30209
CAIXA_ALTURA_MM = CAIXA_DIRECAO['altura_mm']
Z_CAPO_MAX_MM = Z_CAPO_MAX
Z_CAIXA_TOPO_MM = min(CAIXA_DIRECAO['z_topo_max_mm'], Z_CAPO_MAX_MM)
Z_CAIXA_BASE_MM = Z_CAIXA_TOPO_MM - CAIXA_ALTURA_MM
LARGURA_ROL_MM = 24.75     # 30209 (T)
MARGEM_ROL_MM = 5.0        # entre rolamento e extremidade da caixa
CURSO_COMPRESSAO_MM = 80.0
SEDE_ROL_MM = 85.0


def geometria_caixa():
    """Geometria DERIVADA da caixa: a altura do capô manda; rolamentos ficam dentro da caixa; a travessa cruza a caixa.

    Em vez de manter o rolamento inferior 40 mm acima da travessa (topo ≈ 888–920 mm, acima do capô de 811 mm),
    a caixa desce: a travessa solda no corpo da caixa e os rolamentos ficam dentro dela, sob o capô.
    Pernas continuam com H = 470 mm, logo o curso de suspensão é preservado (verificado abaixo)."""
    z_trav = Z_TRAVESSA*1000
    z_b1 = Z_CAIXA_BASE_MM + MARGEM_ROL_MM + LARGURA_ROL_MM/2
    z_b2 = z_b1 + ESPACAMENTO_ROL*1000
    topo_roda = 2*R*1000 + CURSO_COMPRESSAO_MM
    teste = {
        'caixa_comporta_sede_rolamento': CAIXA_DIAMETRO_MM >= SEDE_ROL_MM + 2*5.0,
        'topo_sob_capo': Z_CAIXA_TOPO_MM <= Z_CAPO_MAX_MM,
        'rolamento_superior_dentro_da_caixa': z_b2 + LARGURA_ROL_MM/2 + MARGEM_ROL_MM <= Z_CAIXA_TOPO_MM,
        'travessa_cruza_a_caixa': Z_CAIXA_BASE_MM <= z_trav <= Z_CAIXA_TOPO_MM,
        'roda_comprimida_abaixo_da_caixa': topo_roda < Z_CAIXA_BASE_MM,
    }
    return {'z_caixa_base_mm': Z_CAIXA_BASE_MM, 'z_caixa_topo_mm': Z_CAIXA_TOPO_MM, 'z_travessa_mm': z_trav,
            'z_rolamento_inferior_mm': z_b1, 'z_rolamento_superior_mm': z_b2,
            'folga_roda_comprimida_mm': Z_CAIXA_BASE_MM - topo_roda,
            'comprimento_perna_mm': H*1000, 'verificacoes': teste, 'ok': all(teste.values())}


def reacoes_pivo(s=ESPACAMENTO_ROL):
    z_b1 = Z_TRAVESSA + FOLGA_ROL
    m_baixo = F_H * z_b1 + FZ_2X * E_ESTERCO          # soma conservadora (planos distintos somados)
    r_sup = m_baixo / s
    r_inf = r_sup + F_H
    return {'z_b1_m': z_b1, 'M_haste_Nm': m_baixo, 'R_sup_N': r_sup, 'R_inf_N': r_inf, 'Fa_N': FZ_2X}


def reacoes_pivo_caixa(s=ESPACAMENTO_ROL):
    """Reações com os rolamentos nas posições reais dentro da caixa sob o capô (geometria_caixa)."""
    g = geometria_caixa()
    z_b1 = g['z_rolamento_inferior_mm']/1000
    m_baixo = F_H * z_b1 + FZ_2X * E_ESTERCO
    r_sup = m_baixo / s
    return {'z_b1_m': z_b1, 'M_haste_Nm': m_baixo, 'R_sup_N': r_sup, 'R_inf_N': r_sup + F_H, 'Fa_N': FZ_2X}


def haste(d_mm, m_nm):
    sig = 32 * m_nm / (math.pi * (d_mm / 1000)**3) / 1e6
    return sig, SY_PIVO / sig


def rolamento(r_inf_n, fa_n, c0_kn=C0_30209):
    p0 = (r_inf_n + fa_n) / 1000        # simplificação conservadora
    return p0, c0_kn / p0


def travessa(D, t, caso):
    """Viga entre pernas: flexão no plano y-z (axial das pernas × braço até o pivô + Fy·H) e torção."""
    A, I, W, J = prop_tubo(D, t)
    if caso == 'curva':
        c = cargas_perna(H, 0, 1)
        m = c['axial_N'] * (X_PERNA + E_ESTERCO) + c['M_op']
        t_nm = 0.0
        ax = F_H
    else:   # frenagem: torção da perna do freio + flexão pelo axial
        c = cargas_perna(H, 1, 0)
        m = c['axial_N'] * (X_PERNA + E_ESTERCO)
        t_nm = c['M_ip']
        ax = 0.0
    sig = m * 1000 / W + ax / A
    tau = t_nm * 1000 * (D / 2) / J
    vm = math.sqrt(sig**2 + 3 * tau**2)
    return {'M_Nm': m, 'T_Nm': t_nm, 'VM_MPa': vm, 'FS': SY_TRAV / vm}


def verificar_passagem_perna_interna():
    """Perna interna Ø63,5 contra motores, flanges, proteção e laço da corrente #428 (modelo 3D da varredura).

    Se colidir na posição nominal (±175 mm do plano da roda), devolve o deslocamento axial mínimo com folga de 10 mm."""
    r = deslocamento_perna_interna_minimo()
    return {'deslocamento_nominal_mm': r['nominal_mm'], 'colide_no_nominal': r['colide_no_nominal'],
            'deslocamento_minimo_mm': r['minimo_mm'], 'vao_entre_pernas_mm': r['vao_entre_pernas_mm'],
            'status': 'OK' if not r['colide_no_nominal'] else
                      ('AJUSTAR: deslocar perna interna para %.0f mm' % r['minimo_mm'] if r['minimo_mm'] else 'SEM SOLUCAO')}


if __name__ == '__main__':
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')   # console cp1252 do Windows não codifica σ/Ø
    g = geometria_caixa()
    print(f"Travessa a {g['z_travessa_mm']:.0f} mm do solo; pernas H = {g['comprimento_perna_mm']:.0f} mm")
    print(f"Caixa Ø{CAIXA_DIAMETRO_MM:.0f}×{CAIXA_ALTURA_MM:.0f}: base {g['z_caixa_base_mm']:.0f}, topo {g['z_caixa_topo_mm']:.0f} (capô {Z_CAPO_MAX_MM:.0f})")
    print(f"Rolamentos em z = {g['z_rolamento_inferior_mm']:.0f} / {g['z_rolamento_superior_mm']:.0f} mm; folga roda comprimida → caixa: {g['folga_roda_comprimida_mm']:.0f} mm")
    print("Verificações:", g['verificacoes'], '→', 'OK' if g['ok'] else 'REPROVADO')
    rc = reacoes_pivo_caixa()
    print(f"Pivô (geometria real da caixa): M_haste={rc['M_haste_Nm']:.0f} N·m, R_sup={rc['R_sup_N']:.0f} N, R_inf={rc['R_inf_N']:.0f} N")
    esc, cs = escolher(H)
    print("Pernas H=470:", {n: (round(c['M_ip']), round(c['M_op'])) for n, c in cs.items()})
    print("  tubo mínimo:", esc)
    for D, t in ((50.8, 3.0), (57.2, 3.0), (63.5, 3.0), (63.5, 4.0)):
        print(f"  perna Ø{D}x{t}: FS", round(min(SY_TRAV / tensao(D, t, c) for c in cs.values()), 2))
    
    rp = reacoes_pivo()
    print("\nPivô:", {k: round(v, 1) for k, v in rp.items()})
    for d in (35, 40, 45, 50):
        s, fs = haste(d, rp['M_haste_Nm'])
        print(f"  haste Ø{d}: σ={s:.0f} MPa FS={fs:.2f}")
    p0, fs0 = rolamento(rp['R_inf_N'], rp['Fa_N'])
    print(f"  30209 inferior: P0={p0:.1f} kN, C0/P0={fs0:.1f}")
    for s_rol in (0.09, 0.12, 0.15):
        r = reacoes_pivo(s_rol)
        print(f"  s={s_rol*1000:.0f}: R_sup={r['R_sup_N']:.0f} R_inf={r['R_inf_N']:.0f}")
    
    print("\nTravessa:")
    for D, t in ((57.2, 4.0), (63.5, 4.0), (76.2, 4.0), (76.2, 5.0), (88.9, 4.0)):
        print(f"  Ø{D}x{t}: curva FS={travessa(D,t,'curva')['FS']:.2f}  freio FS={travessa(D,t,'freio')['FS']:.2f}")
    
    # PROMPT 1.3: Verificar passagem da perna interna
    print("\n=== Verificação Perna Interna do Garfo (Prompt 1.3) ===")
    passagem = verificar_passagem_perna_interna()
    for k, v in passagem.items():
        print(f"  {k}: {v}")
