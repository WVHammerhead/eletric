"""
Análise Comparativa: Ø20 / Ø25 / Ø28 / Ø30 mm
==============================================

Compara os diâmetros do eixo sob o MESMO modelo simplificado
(viga biapoiada, carga central, torque de frenagem todo no eixo).

DECISÃO (usuário, 2026-11-05): Ø28 mm. O cubo comporta o furo Ø28.
- Rolamento de esferas com furo 28 mm: série 62/28 (28×58×16), ISO 15.
  É menos comum que o 6206; confirmar estoque local antes de comprar.
- Pior caso (torque todo no eixo): FS escoamento e fadiga atendem aos
  critérios do script (>= 1,3 e >= 1,5), com margem de escoamento menor
  que a do Ø30.

Os resultados descrevem as hipóteses do modelo, não uma geometria medida
(ver Revisao_caminho_cargas_eixo.md). Não substituem o diagrama de corpo livre.
"""

import numpy as np
import pandas as pd

DIAMETRO_ADOTADO_MM = 28

# ============================================================================
# PROPRIEDADES DO MATERIAL
# ============================================================================

Sy = 310e6  # Pa - AISI 1045 normalizado
Su = 565e6  # Pa
E = 200e9   # Pa
Se = 160e6  # Pa - limite de fadiga corrigido (média para Ø20-30)

# ============================================================================
# CARGAS
# ============================================================================

F_vertical = 1766  # N (180 kg)
L_vao = 0.300      # m (estimado)
T_frenagem = 551   # N·m
POS_ESQ = 0.050    # m: apoio esquerdo desde a ponta (mesmo arranjo de desenho_corte_eixo_traseiro.py)
X_REBAIXO_FIM = 0.165  # m: fim do rebaixo central (seção C), desde a ponta
D_REBAIXO_MM = 26      # mm: rebaixo central para eixo Ø28

# ============================================================================
# FUNÇÃO DE ANÁLISE
# ============================================================================

def analisar_diametro(d_mm, descricao=""):
    """Análise completa para um diâmetro."""

    d = d_mm / 1000  # m

    # Geometria
    I = np.pi * (d**4) / 64
    Z = np.pi * (d**3) / 32
    J = np.pi * (d**4) / 32

    # Momento fletor (carga concentrada no centro do vão)
    M = (F_vertical * L_vao) / 4

    # Tensões
    sigma_flex = M / Z
    tau_torc = (T_frenagem * (d/2)) / J
    sigma_VM = np.sqrt(sigma_flex**2 + 3 * tau_torc**2)

    # FS Escoamento
    FS_esc = Sy / sigma_VM

    # Fadiga (Kt = 2.0 para rebaixo)
    Kt = 2.0
    sigma_concentrada = sigma_flex * Kt

    sigma_m = sigma_concentrada / 2
    sigma_a = sigma_concentrada / 2

    inv_FS_fad = sigma_a / Se + sigma_m / Su
    FS_fad = 1 / inv_FS_fad if inv_FS_fad > 0 else np.inf

    # Deflexão
    deflexao = (F_vertical * L_vao**3) / (48 * E * I) * 1000  # mm

    # Caso otimista: cubo longo absorve torque
    sigma_VM_cubo = sigma_flex  # τ = 0
    FS_esc_cubo = Sy / sigma_VM_cubo

    return {
        'diametro_mm': d_mm,
        'descricao': descricao,
        'M_Nm': M,
        'sigma_flexao_MPa': sigma_flex / 1e6,
        'tau_torcao_MPa': tau_torc / 1e6,
        'sigma_VM_MPa': sigma_VM / 1e6,
        'FS_escoamento': FS_esc,
        'FS_fadiga_Kt2': FS_fad,
        'deflexao_mm': deflexao,
        'FS_cubo_longo': FS_esc_cubo,
        'adequado_pior_caso': bool(FS_esc >= 1.3 and FS_fad >= 1.5),
        'adequado_cubo_longo': bool(FS_esc_cubo >= 2.0),
    }


def secao_rebaixo(d_rebaixo_mm=D_REBAIXO_MM):
    """Tensão nominal de flexão na seção do rebaixo central (fim do rebaixo).

    Viga biapoiada, carga central: M(x) = (F/2)·(x − pos_esq) para x antes do centro.
    """
    M = (F_vertical / 2) * (X_REBAIXO_FIM - POS_ESQ)
    Z = np.pi * (d_rebaixo_mm / 1000)**3 / 32
    return M, M / Z / 1e6

# ============================================================================
# ROLAMENTOS (furo = diâmetro do eixo na sede)
# ============================================================================

rolamentos = {
    20: {'codigo': '6204',  'dim': '20×47×14', 'comum': True},
    25: {'codigo': '6205',  'dim': '25×52×15', 'comum': True},
    28: {'codigo': '62/28', 'dim': '28×58×16', 'comum': False},  # confirmar estoque
    30: {'codigo': '6206',  'dim': '30×62×16', 'comum': True},
}

# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    print("\n" + "="*70)
    print("  ANÁLISE COMPARATIVA: Ø20 / Ø25 / Ø28 / Ø30 mm")
    print(f"  Diâmetro adotado: Ø{DIAMETRO_ADOTADO_MM} mm (decisão do usuário)")
    print("="*70)

    diametros = [20, 25, 28, 30]
    resultados = []

    for d in diametros:
        print(f"\n{'─'*70}")
        print(f"  Ø{d} mm" + ("   ← ADOTADO" if d == DIAMETRO_ADOTADO_MM else ""))
        print(f"{'─'*70}")

        r = analisar_diametro(d, f"Ø{d} mm")
        resultados.append(r)

        print("Tensões (com torque):")
        print(f"  σ_flexão:   {r['sigma_flexao_MPa']:6.1f} MPa")
        print(f"  τ_torção:   {r['tau_torcao_MPa']:6.1f} MPa")
        print(f"  σ_VM:       {r['sigma_VM_MPa']:6.1f} MPa")

        print("\nFatores de Segurança:")
        print(f"  FS escoamento: {r['FS_escoamento']:.2f}  {'✓' if r['FS_escoamento'] >= 1.3 else '✗'}")
        print(f"  FS fadiga:     {r['FS_fadiga_Kt2']:.2f}  {'✓' if r['FS_fadiga_Kt2'] >= 1.5 else '✗'}")

        print("\nCaso otimista (cubo absorve torque):")
        print(f"  σ_flex apenas: {r['sigma_flexao_MPa']:6.1f} MPa")
        print(f"  FS escoamento: {r['FS_cubo_longo']:.2f}  {'✓' if r['FS_cubo_longo'] >= 2.0 else '✗'}")

        rol = rolamentos[d]
        print("\nRolamento:")
        print(f"  Código: {rol['codigo']}  ({rol['dim']})")
        print(f"  Série comum no varejo: {'sim' if rol['comum'] else 'não: confirmar estoque'}")

        if r['adequado_pior_caso']:
            print("\n  ✅ Atende aos critérios no pior caso")
        elif r['adequado_cubo_longo']:
            print("\n  ⚠️  Atende apenas se o cubo absorver o torque")
        else:
            print("\n  ❌ FS insuficiente")

    # Tabela resumo
    print(f"\n{'='*70}")
    print("  TABELA RESUMO")
    print(f"{'='*70}\n")

    df = pd.DataFrame(resultados)
    df['rolamento'] = df['diametro_mm'].map(lambda d: rolamentos[d]['codigo'])
    df['rol_comum'] = df['diametro_mm'].map(lambda d: rolamentos[d]['comum'])

    print(df[['diametro_mm', 'sigma_VM_MPa', 'FS_escoamento', 'FS_fadiga_Kt2',
              'FS_cubo_longo', 'rolamento', 'rol_comum']].to_string(index=False))

    # Gráficos
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'Análise comparativa do eixo (adotado: Ø{DIAMETRO_ADOTADO_MM} mm)',
                 fontsize=14, fontweight='bold')

    d = df['diametro_mm'].values
    cores = ['tab:blue' if dd == DIAMETRO_ADOTADO_MM else
             ('green' if adeq else 'orange' if cubo else 'red')
             for dd, adeq, cubo in zip(df['diametro_mm'], df['adequado_pior_caso'],
                                       df['adequado_cubo_longo'])]

    ax = axes[0, 0]
    ax.bar(d - 0.6, df['sigma_flexao_MPa'], width=0.6, label='Flexão', alpha=0.7)
    ax.bar(d, df['tau_torcao_MPa'], width=0.6, label='Torção', alpha=0.7)
    ax.bar(d + 0.6, df['sigma_VM_MPa'], width=0.6, label='Von Mises', alpha=0.7)
    ax.axhline(Sy/1e6, color='r', linestyle='--', label='Sy = 310 MPa')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('Tensão (MPa)')
    ax.set_title('Tensões atuantes (pior caso)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.bar(d, df['FS_escoamento'], color=cores, alpha=0.7)
    ax.axhline(1.3, color='orange', linestyle='--', label='Mínimo aceitável')
    ax.axhline(2.0, color='g', linestyle='--', label='Desejável')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('FS')
    ax.set_title('FS escoamento (pior caso)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.bar(d, df['FS_fadiga_Kt2'], color=cores, alpha=0.7)
    ax.axhline(1.5, color='orange', linestyle='--', label='Mínimo')
    ax.axhline(2.0, color='g', linestyle='--', label='Desejável')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('FS')
    ax.set_title('FS fadiga (Kt = 2.0)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.bar(d, df['FS_cubo_longo'], color=cores, alpha=0.7)
    ax.axhline(2.0, color='g', linestyle='--', label='Mínimo')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('FS')
    ax.set_title('FS escoamento (cubo absorve torque)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('analise_comparativa_FINAL_28mm.png', dpi=300, bbox_inches='tight')
    print("\n→ Gráfico salvo: analise_comparativa_FINAL_28mm.png")

    df.to_csv('analise_comparativa_FINAL_28mm.csv', index=False)
    print("→ Dados salvos: analise_comparativa_FINAL_28mm.csv")

    # Verificação do diâmetro adotado
    print(f"\n{'='*70}")
    print(f"  VERIFICAÇÃO DO DIÂMETRO ADOTADO: Ø{DIAMETRO_ADOTADO_MM} mm")
    print(f"{'='*70}\n")

    adotado = df[df['diametro_mm'] == DIAMETRO_ADOTADO_MM].iloc[0]
    rol = rolamentos[DIAMETRO_ADOTADO_MM]
    M_reb, sigma_reb = secao_rebaixo()

    print(f"  • FS escoamento = {adotado['FS_escoamento']:.2f} (≥ 1.3: {'✓' if adotado['FS_escoamento'] >= 1.3 else '✗'})")
    print(f"  • FS fadiga     = {adotado['FS_fadiga_Kt2']:.2f} (≥ 1.5: {'✓' if adotado['FS_fadiga_Kt2'] >= 1.5 else '✗'})")
    print(f"  • Deflexão      = {adotado['deflexao_mm']:.2f} mm")
    print(f"  • Se o cubo absorver o torque: FS = {adotado['FS_cubo_longo']:.2f}")
    print(f"  • Rebaixo Ø{D_REBAIXO_MM}: M = {M_reb:.1f} N·m, σ nominal = {sigma_reb:.1f} MPa "
          f"(Kt do raio r ≥ 1,5 mm já coberto pelo Kt = 2,0 acima)")
    print(f"  • Rolamento {rol['codigo']} ({rol['dim']}): confirmar estoque; alternativa 63/28 (28×68×18)")

    print("\n" + "="*70)
    print("  COMPONENTES ENVOLVIDOS (Ø28 mm)")
    print("="*70 + "\n")
    print("  1. Eixo Ø28 × 400 mm, AISI 1045 normalizado, rosca M14×1,5")
    print("  2. Rolamentos 62/28 (28×58×16) — 2 unidades")
    print("  3. Cubo: furo/sedes para 62/28 (alojamento Ø58 H7); parede ≥ 8 mm")
    print("  4. Espaçador(es) Ø28 interno, apoiando só no anel interno")
    print("  5. Porca M14×1,5 autotravante + arruelas")
    print("  6. Mancal/ligação da balança no diâmetro Ø28")
    print("\n  Custos: sem cotação; ver RESUMO_EXECUTIVO_EIXO_28mm.md (estimativas)\n")
