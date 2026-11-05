"""
Eixo Ø28 apoiado nos DOIS lados da roda (garfo/duplo braço) — carga de projeto
Fz 2x + lateral (μ·Fz), roda externa. Complementa fcl_eixo_balanco.py.

Modelo: eixo = viga simplesmente apoiada em y = ±x_s (apoios no garfo); a roda
transmite ao eixo as reações dos rolamentos A (y=-100) e B (y=+100):
  vertical: Fz/2 ± Fy·r/L   horizontal: Fx/2   axial Fy (num só apoio).
Torque de frenagem: como a ponta roscada M24 do eixo Ø28 mm suporta apenas ~58%
do torque limite (494 N·m), 100% do torque é transferido pelo braço de reação
(barra 30×6 mm, ρ = 150 mm) diretamente para a perna do garfo.
Bucha de centragem: força radial líquida das sapatas sobre a bucha no eixo.
Tensões nominais maciças, sem fadiga/impacto lateral/corrente. Não é dimensionamento.
"""
import csv, math
from pathlib import Path
from fcl_eixo_balanco import SY, MU, R, FZ_2X, FZ_ESTATICO, ESPACAMENTO, C0_ROLAMENTO

ROOT = Path(__file__).resolve().parent
A, B = -ESPACAMENTO / 2, ESPACAMENTO / 2

# Braço de reação do freio (da braco_reacao_freio.py)
RHO_BRACO_MM = 150.0              # distância eixo → parafuso do garfo
COMP_BRACO_MM = 100.0
LARGURA_BRACO_MM = 30.0
ESPESSURA_BRACO_MM = 6.0
SY_BRACO = 250.0                  # MPa (hipótese: aço baixo carbono)

# Bucha de centragem do espelho (backing plate) no eixo
D_BUCHA_CENT_MM = 28.0            # diâmetro da bucha (aprox. diâmetro do eixo)
L_BUCHA_CENT_MM = 40.0            # comprimento da bucha
P_ADM_BUCHA_MPa = 10.0            # pressão admissível


def momento_max(x_s, carga_a, carga_b):
    """Momento fletor máximo (N·m) de viga apoiada em ±x_s com cargas pontuais em A e B."""
    L = 2 * x_s
    r_dir = (carga_a * (A + x_s) + carga_b * (B + x_s)) / L   # apoio em +x_s
    r_esq = carga_a + carga_b - r_dir
    m_a = r_esq * (A + x_s)
    m_b = r_esq * (B + x_s) - carga_a * (B - A)
    return max(abs(m_a), abs(m_b)), r_esq, r_dir


def forca_bucha_centragem(torque_freio_nm):
    """Força radial líquida das sapatas sobre a bucha de centragem no eixo.
    
    As sapatas de freio aplicam forças radiais na superfície interna do tambor.
    Essas forças se transmitem ao espelho (backing plate) que gira livre sobre
    a bucha de centragem. A resultante radial líquida carrega a bucha.
    Hipótese simplificada: força radial ≈ torque / raio do tambor.
    """
    F_radial = torque_freio_nm / R  # N
    area_proj = D_BUCHA_CENT_MM * L_BUCHA_CENT_MM
    pressao = F_radial / area_proj
    return {'F_radial_bucha_N': F_radial, 'pressao_bucha_MPa': pressao,
            'uso_bucha': pressao / P_ADM_BUCHA_MPa}


def caso(nome, fz, fx_frac, fy_frac, f_torque, x_s, d_mm=28):
    """Calcula esforços no eixo biapoiado.
    
    f_torque: fração do torque de frenagem transmitida pelo eixo (0 a 1).
              O restante (1 - f_torque) vai pelo braço de reação direto ao garfo.
    """
    fx, fy = fx_frac * MU * fz, fy_frac * MU * fz
    c = fy * R / ESPACAMENTO
    va, vb = fz / 2 - c, fz / 2 + c
    hz = fx / 2
    mv, rv_e, rv_d = momento_max(x_s, va, vb)
    mh, rh_e, rh_d = momento_max(x_s, hz, hz)
    M = math.hypot(mv, mh)
    T_total = fx * R                           # torque total de frenagem
    T_eixo = f_torque * T_total                # torque no eixo
    T_braco = (1 - f_torque) * T_total         # torque no braço de reação
    
    # Braço de reação: força no braço
    F_braco = T_braco / (RHO_BRACO_MM / 1000) if T_braco > 0 else 0.0
    area_braco = LARGURA_BRACO_MM * ESPESSURA_BRACO_MM
    sigma_braco = F_braco / area_braco if F_braco > 0 else 0.0
    fs_braco = SY_BRACO / sigma_braco if sigma_braco > 0 else math.inf
    
    # Bucha de centragem do espelho
    bucha_data = forca_bucha_centragem(T_total)
    
    d = d_mm / 1000
    sigma = 32 * M / (math.pi * d**3) / 1e6
    tau = 16 * T_eixo / (math.pi * d**3) / 1e6
    vm = math.sqrt(sigma**2 + 3 * tau**2)
    apoio = max(math.hypot(rv_e, rh_e), math.hypot(rv_d, rh_d))
    return {'caso': nome, 'Fz_N': fz, 'x_s_mm': x_s * 1000, 'd_mm': d_mm,
            'M_eixo_Nm': M, 'torcao_eixo_Nm': T_eixo, 'torcao_total_Nm': T_total,
            'fracao_torque_eixo': f_torque, 'torque_braco_Nm': T_braco,
            'F_braco_N': F_braco, 'sigma_braco_MPa': sigma_braco, 'FS_braco': fs_braco,
            **bucha_data,
            'VM_MPa': vm, 'FS_escoamento': SY / vm,
            'FS_com_Kt2': SY / math.sqrt((2 * sigma)**2 + 3 * tau**2),
            'reacao_apoio_N': apoio,
            'rolamento_max_N': max(math.hypot(va, hz), math.hypot(vb, hz))}


def varredura(fz=FZ_2X):
    """Varredura de casos com diferentes frações de torque no eixo vs braço de reação."""
    out = []
    for d in (28,):
        for x_s in (0.130, 0.150, 0.180, 0.200):
            # Casos sem frenagem
            out.append(caso('vertical', fz, 0, 0, 0, x_s, d))
            out.append(caso('curva externa', fz, 0, 1, 0, x_s, d))
            # Casos com frenagem: testar 0%, 58%, e 100% do torque no eixo
            for f_torq in (0.0, 0.58, 1.0):
                label_torq = f'torque {f_torq:.0%} eixo/{100-f_torq*100:.0f}% braço'
                out.append(caso(f'frenagem reta, {label_torq}', fz, 1, 0, f_torq, x_s, d))
                out.append(caso(f'curva+freio 45°, {label_torq}', fz, math.sqrt(.5), math.sqrt(.5), f_torq, x_s, d))
    return out


def main():
    linhas = varredura()
    with (ROOT / 'dados_fcl_eixo_garfo.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=linhas[0].keys(), delimiter=';')
        w.writeheader()
        for l in linhas:
            w.writerow({k: round(v, 2) if isinstance(v, float) else v for k, v in l.items()})
    print("\n=== Eixo Ø28 biapoiado com braço de reação ===")
    for l in linhas:
        if l['x_s_mm'] in (150.0, 200.0) and 'braço' in l['caso']:
            print(f"x_s={l['x_s_mm']:.0f} {l['caso'][:50]:50s} M={l['M_eixo_Nm']:6.1f} "
                  f"T_eixo={l['torcao_eixo_Nm']:6.1f} VM={l['VM_MPa']:6.1f} FS={l['FS_escoamento']:5.2f} "
                  f"F_braço={l['F_braco_N']:6.0f} N FS_braço={l['FS_braco']:5.2f} "
                  f"bucha={l['pressao_bucha_MPa']:.1f} MPa ({100*l['uso_bucha']:.0f}%)")
    return linhas


if __name__ == '__main__':
    main()


# ---------------------------------------------------------------------------
# Layout rev. 03 (eixo 400 mm, simétrico): pontas Ø24 (M24x1,5) de 35 mm, corpo Ø28.
# Orelha do garfo (~20 mm) assenta na ponta contra o ombro em x = 35 -> reação em x ≈ 25
# -> x_s = 200 - 25 = 175 mm do plano médio. Rolamentos em 100 e 300 mm.
# ---------------------------------------------------------------------------
X_S_REV03 = 0.175
D_PONTA_MM = 24
D_PONTA_ROSCA_MENOR_MM = 22.0   # ≈ diâmetro menor de M24x1,5 (aprox.; conferir na tabela)


def torcao_ponta(torque_nm, d_mm=D_PONTA_ROSCA_MENOR_MM):
    """VM (só torção) e FS na ponta roscada; seção crítica da transmissão do torque ao garfo."""
    d = d_mm / 1000
    tau = 16 * torque_nm / (math.pi * d**3) / 1e6
    vm = math.sqrt(3) * tau
    return tau, vm, SY / vm


def fracao_max_torque_na_ponta(fs_alvo=1.3, fz=FZ_2X):
    t_freio = MU * fz * R
    _, vm100, _ = torcao_ponta(t_freio)
    return min(1.0, (SY / fs_alvo) / vm100), t_freio


if __name__ == '__main__':
    print('\n=== Rev. 03: x_s = 175 mm, Fz 2x, Braço de reação ===')
    for f_t in (0.0, 0.58, 1.0):
        print(f"\n  Fração de torque no eixo: {f_t:.0%}")
        for c in (caso('curva externa', FZ_2X, 0, 1, 0, X_S_REV03),
                  caso(f'frenagem reta, torque {f_t:.0%}', FZ_2X, 1, 0, f_t, X_S_REV03),
                  caso(f'curva+freio 45°, torque {f_t:.0%}', FZ_2X, math.sqrt(.5), math.sqrt(.5), f_t, X_S_REV03)):
            print(f"    {c['caso']:45s} M={c['M_eixo_Nm']:.0f} T_eixo={c['torcao_eixo_Nm']:.0f} "
                  f"VM={c['VM_MPa']:.0f} FS={c['FS_escoamento']:.2f} "
                  f"F_braço={c['F_braco_N']:.0f} N FS_braço={c['FS_braco']:.2f}")
    
    f, t = fracao_max_torque_na_ponta()
    print(f"\n  Torque de freio (limite de aderência) = {t:.0f} N·m")
    for fr in (0.25, 0.5, 1.0):
        tau, vm, fs = torcao_ponta(fr * t)
        print(f"  ponta M24 (d menor ≈ 22): {fr:.0%} do torque -> τ={tau:.0f} MPa, FS={fs:.2f}")
    print(f"  Fração máxima do torque pela ponta para FS 1,3: {f:.0%} (restante vai pelo braço)")
    
    # Bucha de centragem com torque total
    bucha = forca_bucha_centragem(t)
    print(f"\n  Bucha de centragem (Ø{D_BUCHA_CENT_MM}×{L_BUCHA_CENT_MM} mm):")
    print(f"    Força radial: {bucha['F_radial_bucha_N']:.0f} N")
    print(f"    Pressão: {bucha['pressao_bucha_MPa']:.1f} MPa ({100*bucha['uso_bucha']:.0f}% da admissível)")
