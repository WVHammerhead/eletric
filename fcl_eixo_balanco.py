"""
Diagrama de corpo livre do eixo em balanço (módulo dianteiro, Ø28 mm)
======================================================================

Arquitetura do Anteprojeto: cubo gira sobre 2 rolamentos (A, B) a ±100 mm do
plano médio do pneu; eixo ENGASTADO na balança, do lado externo (y = +x_s).

Eixos: x à frente, y para fora (transversal), z para cima.
Força do solo no pneu: F = (Fx, Fy, Fz) aplicada em (0, 0, -r) em relação ao
centro da roda. Transportada ao engaste (0, x_s, 0) do eixo:

    M_x (plano transversal) = Fz·x_s + μ-lateral·r   (roda externa em curva: somam)
    M_z (plano horizontal)  = Fx·x_s
    Axial                   = Fy
    Torção                  = f · T_freio   (f = fração do torque que passa pelo eixo)

Independe do espaçamento dos rolamentos para o momento no engaste; o espaçamento
só define as reações nos rolamentos.

Hipóteses (todas a confirmar): μ = 0,8; r carregado = 257,8 mm (80/100-14);
Fz estático por roda 1197 N e 2× = 2393 N (dados_ensaio_integrado.csv, 2 ocupantes);
x_s é a distância do plano médio ao engaste (NÃO definida no projeto: varrida).
Sem fadiga, entalhes (Kt), impacto lateral ou carga de corrente/tração.
Não é dimensionamento nem aprovação.
"""
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SY = 310.0          # MPa, AISI 1045 normalizado
MU = 0.8
R = 0.2578          # m
FZ_ESTATICO = 1197.0  # N por roda (metade de 2393 N, ver ensaio_integrado)
FZ_2X = 2393.0
ESPACAMENTO = 0.200   # m entre centros dos rolamentos
C0_ROLAMENTO = 9500.0  # N, carga estática do 62/28 (listagem de varejo; confirmar no catálogo)


def tensoes(d_mm, Mx, Mz, torque, axial=0.0):
    """Tensões nominais (MPa) na seção circular maciça do engaste."""
    d = d_mm / 1000
    M = math.hypot(Mx, Mz)
    sigma = 32 * M / (math.pi * d**3) / 1e6 + 4 * axial / (math.pi * d**2) / 1e6
    tau = 16 * torque / (math.pi * d**3) / 1e6
    vm = math.sqrt(sigma**2 + 3 * tau**2)
    return sigma, tau, vm


def caso(nome, fz, fx_frac, fy_frac, f_torque, x_s, d_mm=28):
    """fx_frac, fy_frac: múltiplos de μ·Fz (0 a 1) usados em Fx e Fy."""
    fx = fx_frac * MU * fz
    fy = fy_frac * MU * fz
    t_freio = fx * R
    Mx = fz * x_s + fy * R           # roda externa: lateral soma ao vertical
    Mz = fx * x_s
    torque = f_torque * t_freio
    sigma, tau, vm = tensoes(d_mm, Mx, Mz, torque, fy)
    # reações radiais nos rolamentos (vertical: Fz/2 ± Fy·r/L; horizontal: Fx/2)
    c = fy * R / ESPACAMENTO
    rb = math.hypot(fz / 2 + c, fx / 2)
    ra = math.hypot(fz / 2 - c, fx / 2)
    return {
        'caso': nome, 'Fz_N': fz, 'Fx_N': fx, 'Fy_N': fy, 'T_freio_Nm': t_freio,
        'f_torque_eixo': f_torque, 'x_s_mm': x_s * 1000, 'd_mm': d_mm,
        'M_engaste_Nm': math.hypot(Mx, Mz), 'torcao_Nm': torque,
        'sigma_flexao_MPa': sigma, 'tau_MPa': tau, 'VM_MPa': vm,
        'FS_escoamento': SY / vm, 'rolamento_max_N': max(ra, rb),
        'folga_C0': C0_ROLAMENTO / max(ra, rb),
    }


def varredura(d_mm=28):
    linhas = []
    for x_s in (0.110, 0.130, 0.160, 0.200):
        for fz, rot in ((FZ_ESTATICO, 'Fz estático'), (FZ_2X, 'Fz 2x')):
            linhas.append(caso(f'vertical ({rot})', fz, 0, 0, 0, x_s, d_mm))
            for f in (0.0, 0.5, 1.0):
                linhas.append(caso(f'frenagem reta μ ({rot})', fz, 1, 0, f, x_s, d_mm))
            linhas.append(caso(f'curva externa μ ({rot})', fz, 0, 1, 0, x_s, d_mm))
            for f in (0.0, 1.0):
                # combinado na borda do círculo de atrito: √(Fx²+Fy²) = μFz
                linhas.append(caso(f'curva+freio 45° ({rot})', fz, math.sqrt(.5),
                                   math.sqrt(.5), f, x_s, d_mm))
    return linhas


def main():
    todas = []
    for d in (28, 30):
        todas += varredura(d)
    campos = list(todas[0].keys())
    with (ROOT / 'dados_fcl_eixo_balanco.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=';')
        w.writeheader()
        for l in todas:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in l.items()})
    for d in (28, 30):
        print(f'\n== Ø{d} mm: pior FS por posição do engaste ==')
        for x_s in (110, 130, 160, 200):
            sub = [l for l in todas if l['d_mm'] == d and l['x_s_mm'] == x_s]
            pior = min(sub, key=lambda l: l['FS_escoamento'])
            print(f"x_s={x_s} mm: FS {pior['FS_escoamento']:.2f}  "
                  f"({pior['caso']}, f={pior['f_torque_eixo']}, M={pior['M_engaste_Nm']:.0f} N·m, "
                  f"VM={pior['VM_MPa']:.0f} MPa)")
    return todas


if __name__ == '__main__':
    main()


def requisitos(fs_alvo=1.3, fz=FZ_2X, x_s=0.130):
    """O que é preciso para atender ao cenário adotado (Fz 2x + lateral μ·Fz, roda externa)."""
    M = fz * (x_s + MU * R)
    sig_adm = SY / fs_alvo
    z_nec = M / (sig_adm * 1e6)
    d_nec = (32 * z_nec / math.pi) ** (1 / 3) * 1000
    sy_nec = fs_alvo * M / (math.pi * 0.028**3 / 32) / 1e6
    x_max = fz and (sig_adm * 1e6 * math.pi * 0.028**3 / 32) / fz - MU * R
    # apoio nos dois lados da roda (garfo), apoios a ±x_s: flexão do eixo entre apoio e rolamento
    reacao = math.hypot(fz / 2 + MU * fz * R / ESPACAMENTO, 0)
    m_garfo = reacao * (x_s - ESPACAMENTO / 2)
    d_garfo = (32 * m_garfo / (math.pi * sig_adm * 1e6)) ** (1 / 3) * 1000
    return {'M_Nm': M, 'd_necessario_mm_1045': d_nec, 'Sy_necessario_MPa_d28': sy_nec,
            'x_s_max_mm_d28': x_max * 1000, 'M_garfo_Nm': m_garfo, 'd_garfo_mm': d_garfo}


if __name__ == '__main__':
    print('\nRequisitos (Fz 2x + lateral, FS >= 1,3, x_s = 130 mm):')
    for k, v in requisitos().items():
        print(f'  {k}: {v:.1f}')
