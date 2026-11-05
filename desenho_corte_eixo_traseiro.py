"""
Desenho em Corte — Eixo Traseiro Hammerhead
============================================

Gera desenho técnico esquemático mostrando:
- Eixo (Ø20 mm atual presumido ou Ø28 mm adotado)
- Dois rolamentos nos pontos de fixação à balança
- Cubo da roda (comprimento e Ø interno)
- Tambor de freio
- Pontos de aplicação de carga

Objetivo: permitir entrada de medidas reais e gerar diagramas de esforços.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle, FancyBboxPatch, Circle, FancyArrowPatch
import numpy as np

def desenhar_corte_eixo_traseiro(
    L_total=400,           # Comprimento total do eixo (mm)
    L_vao=300,             # Vão entre rolamentos (mm)
    d_eixo=28,             # Diâmetro do eixo (mm)
    d_cubo_int=28,         # Diâmetro interno do cubo (mm)
    d_cubo_ext=75,         # Diâmetro externo do cubo (mm); >= ~75 para sede Ø58 (62/28) com parede >= 8
    L_cubo=80,             # Comprimento do cubo (mm)
    pos_rolamento_esq=50,  # Posição do rolamento esquerdo desde a ponta (mm)
    pos_rolamento_dir=None, # Posição do rolamento direito (calculado se None)
    L_rosca=25,            # Comprimento da rosca M14x1,5 (mm)
    d_rosca=14,            # Diâmetro da rosca (mm)
    mostrar_cargas=True,
    titulo="Eixo Traseiro — Configuração Atual"
):
    """
    Desenha corte esquemático do conjunto eixo traseiro.
    
    Convenção:
    - Origem (x=0) na extremidade esquerda do eixo
    - Rolamentos = pontos de fixação à balança (apoios)
    - Cubo = região onde a roda se fixa ao eixo
    - Tambor = fixado ao cubo (representado simplificado)
    """
    
    if pos_rolamento_dir is None:
        pos_rolamento_dir = pos_rolamento_esq + L_vao
    
    # ========================================================================
    # SETUP DO PLOT
    # ========================================================================
    fig, ax = plt.subplots(figsize=(16, 8))
    ax.set_xlim(-20, L_total + 40)
    ax.set_ylim(-80, 120)
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Linha de centro
    ax.plot([0, L_total], [0, 0], 'k--', linewidth=0.5, alpha=0.3, label='Linha de centro')
    
    # ========================================================================
    # EIXO PRINCIPAL
    # ========================================================================
    
    # Corpo principal do eixo
    eixo_corpo = Rectangle(
        (0, -d_eixo/2), L_total, d_eixo,
        facecolor='lightsteelblue', edgecolor='black', linewidth=2,
        label=f'Eixo Ø{d_eixo} mm'
    )
    ax.add_patch(eixo_corpo)
    
    # Rosca M14 na extremidade direita
    rosca_x = L_total - L_rosca
    rosca = Rectangle(
        (rosca_x, -d_rosca/2), L_rosca, d_rosca,
        facecolor='gold', edgecolor='darkorange', linewidth=1.5,
        hatch='///', alpha=0.8, label=f'Rosca M{d_rosca}'
    )
    ax.add_patch(rosca)
    
    # ========================================================================
    # ROLAMENTOS (APOIOS)
    # ========================================================================
    
    largura_rolamento = 12  # mm (simplificado)
    altura_rolamento = d_eixo + 10
    
    for i, pos in enumerate([pos_rolamento_esq, pos_rolamento_dir], start=1):
        # Rolamento (retângulo cinza)
        rolamento = Rectangle(
            (pos - largura_rolamento/2, -altura_rolamento/2),
            largura_rolamento, altura_rolamento,
            facecolor='dimgray', edgecolor='black', linewidth=1.5,
            alpha=0.7
        )
        ax.add_patch(rolamento)
        
        # Seta de fixação à balança (para baixo)
        ax.annotate(
            '', xy=(pos, -altura_rolamento/2 - 5), xytext=(pos, -altura_rolamento/2 - 25),
            arrowprops=dict(arrowstyle='->', lw=2.5, color='darkred')
        )
        ax.text(pos, -altura_rolamento/2 - 30, f'Balança\nApoio {i}',
                ha='center', va='top', fontsize=9, fontweight='bold', color='darkred')
        
        # Cota de posição
        ax.text(pos, altura_rolamento/2 + 8, f'x = {pos:.0f} mm',
                ha='center', va='bottom', fontsize=8, color='darkblue')
    
    if i == 2:  # Adiciona label apenas uma vez
        ax.add_patch(Rectangle((0, 0), 0, 0, facecolor='dimgray', edgecolor='black',
                               label='Rolamentos (apoios)'))
    
    # ========================================================================
    # CUBO DA RODA
    # ========================================================================
    
    # Posição do cubo: centralizado entre os rolamentos
    pos_cubo_centro = (pos_rolamento_esq + pos_rolamento_dir) / 2
    pos_cubo_x = pos_cubo_centro - L_cubo / 2
    
    cubo = FancyBboxPatch(
        (pos_cubo_x, -d_cubo_ext/2), L_cubo, d_cubo_ext,
        boxstyle="round,pad=2", facecolor='silver', edgecolor='black',
        linewidth=2, alpha=0.6, label='Cubo da roda'
    )
    ax.add_patch(cubo)
    
    # Furo interno do cubo (sobre o eixo)
    ax.add_patch(Rectangle(
        (pos_cubo_x, -d_cubo_int/2), L_cubo, d_cubo_int,
        facecolor='white', edgecolor='gray', linewidth=1, linestyle='--'
    ))
    
    # Texto do cubo
    ax.text(pos_cubo_centro, d_cubo_ext/2 + 8,
            f'Cubo: Ø{d_cubo_int}/{d_cubo_ext} mm\nL = {L_cubo} mm',
            ha='center', va='bottom', fontsize=9, fontweight='bold', color='black')
    
    # ========================================================================
    # TAMBOR DE FREIO (simplificado)
    # ========================================================================
    
    tambor_x = pos_cubo_x - 15
    tambor_largura = 25
    tambor_altura = d_cubo_ext + 20
    
    tambor = Rectangle(
        (tambor_x, -tambor_altura/2), tambor_largura, tambor_altura,
        facecolor='lightcoral', edgecolor='darkred', linewidth=2,
        alpha=0.5, label='Tambor de freio'
    )
    ax.add_patch(tambor)
    
    ax.text(tambor_x + tambor_largura/2, -tambor_altura/2 - 8,
            'Tambor', ha='center', va='top', fontsize=8, color='darkred')
    
    # ========================================================================
    # CARGAS APLICADAS
    # ========================================================================
    
    if mostrar_cargas:
        # Carga vertical (no centro do vão)
        pos_carga_v = pos_cubo_centro
        ax.annotate(
            '', xy=(pos_carga_v, d_cubo_ext/2 + 5), xytext=(pos_carga_v, d_cubo_ext/2 + 35),
            arrowprops=dict(arrowstyle='->', lw=4, color='red')
        )
        ax.text(pos_carga_v, d_cubo_ext/2 + 40, 'Fv = 1766 N\n(180 kg × g)',
                ha='center', va='bottom', fontsize=10, fontweight='bold', color='red')
        
        # Força lateral (curva)
        pos_carga_h = pos_cubo_centro
        ax.annotate(
            '', xy=(pos_carga_h + 50, 0), xytext=(pos_carga_h + 5, 0),
            arrowprops=dict(arrowstyle='->', lw=3, color='orange')
        )
        ax.text(pos_carga_h + 55, 0, 'Flat = 1413 N\n(0.8g lateral)',
                ha='left', va='center', fontsize=9, fontweight='bold', color='orange')
        
        # Momento de frenagem (no tambor)
        ax.annotate(
            '', xy=(tambor_x + tambor_largura/2, tambor_altura/2 - 5),
            xytext=(tambor_x + tambor_largura/2, tambor_altura/2 - 15),
            arrowprops=dict(arrowstyle='->', lw=2.5, color='purple', connectionstyle="arc3,rad=.3")
        )
        ax.text(tambor_x - 20, tambor_altura/2 + 5, 'Tfren = 551 N·m',
                ha='right', va='bottom', fontsize=9, fontweight='bold', color='purple')
    
    # ========================================================================
    # COTAS GERAIS
    # ========================================================================
    
    # Vão entre apoios
    y_cota = -50
    ax.plot([pos_rolamento_esq, pos_rolamento_dir], [y_cota, y_cota],
            'k-', linewidth=1.5)
    ax.plot([pos_rolamento_esq, pos_rolamento_esq], [y_cota-3, y_cota+3], 'k-', linewidth=1.5)
    ax.plot([pos_rolamento_dir, pos_rolamento_dir], [y_cota-3, y_cota+3], 'k-', linewidth=1.5)
    ax.text((pos_rolamento_esq + pos_rolamento_dir)/2, y_cota - 8,
            f'Vão livre = {L_vao:.0f} mm',
            ha='center', va='top', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7))
    
    # Comprimento total
    y_cota2 = -65
    ax.plot([0, L_total], [y_cota2, y_cota2], 'k-', linewidth=1)
    ax.plot([0, 0], [y_cota2-2, y_cota2+2], 'k-', linewidth=1)
    ax.plot([L_total, L_total], [y_cota2-2, y_cota2+2], 'k-', linewidth=1)
    ax.text(L_total/2, y_cota2 - 5,
            f'L total = {L_total:.0f} mm',
            ha='center', va='top', fontsize=9, color='gray')
    
    # ========================================================================
    # TÍTULO E LEGENDA
    # ========================================================================
    
    ax.set_title(titulo, fontsize=14, fontweight='bold', pad=20)
    ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
    
    # Grid de referência
    ax.grid(True, alpha=0.2, linestyle=':', linewidth=0.5)
    
    plt.tight_layout()
    return fig, ax


# ============================================================================
# VARIAÇÕES PARA COMPARAÇÃO
# ============================================================================

def gerar_comparativo():
    """Gera três variações do desenho para análise."""
    
    configs = [
        {
            'titulo': 'Configuração A: Ø20 mm (atual presumido)',
            'd_eixo': 20,
            'd_cubo_int': 20,
            'd_cubo_ext': 55,
            'L_cubo': 75,
            'pos_rolamento_esq': 50,
            'L_vao': 300,
            'filename': 'corte_eixo_config_A_20mm.png'
        },
        {
            'titulo': 'Configuração B: Ø28 mm (adotada)',
            'd_eixo': 28,
            'd_cubo_int': 28,
            'd_cubo_ext': 75,
            'L_cubo': 80,
            'pos_rolamento_esq': 50,
            'L_vao': 300,
            'filename': 'corte_eixo_config_B_28mm.png'
        },
        {
            'titulo': 'Configuração C: Medidas Reais (PREENCHER)',
            'd_eixo': 28,  # ← MEDIR
            'd_cubo_int': 28,  # ← MEDIR
            'd_cubo_ext': 75,  # ← MEDIR
            'L_cubo': 80,  # ← MEDIR
            'pos_rolamento_esq': 50,  # ← MEDIR
            'L_vao': 320,  # ← MEDIR (crítico!)
            'filename': 'corte_eixo_config_C_real.png'
        }
    ]
    
    for cfg in configs:
        fig, ax = desenhar_corte_eixo_traseiro(
            L_total=400,
            L_vao=cfg['L_vao'],
            d_eixo=cfg['d_eixo'],
            d_cubo_int=cfg['d_cubo_int'],
            d_cubo_ext=cfg['d_cubo_ext'],
            L_cubo=cfg['L_cubo'],
            pos_rolamento_esq=cfg['pos_rolamento_esq'],
            titulo=cfg['titulo']
        )
        plt.savefig(cfg['filename'], dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Salvo: {cfg['filename']}")
        plt.close()


# ============================================================================
# DIAGRAMA DE ESFORÇOS
# ============================================================================

def diagrama_esforcos(
    L_vao=300,             # mm
    pos_rolamento_esq=50,  # mm desde a ponta esquerda
    F_vertical=1766,       # N
    F_lateral=1413,        # N
    d_eixo=28,             # mm
    titulo="Diagramas de Esforço Cortante e Momento Fletor"
):
    """
    Gera diagramas de V(x) e M(x) para viga bi-apoiada com carga concentrada no centro.
    
    Modelo:
    - Viga bi-apoiada nas posições dos rolamentos
    - Carga vertical concentrada no centro do vão
    - Momento lateral aplicado no centro (aproximação)
    """
    
    L = L_vao / 1000  # converter para metros
    pos_esq = pos_rolamento_esq / 1000
    pos_dir = pos_esq + L
    pos_carga = (pos_esq + pos_dir) / 2
    
    # Reações de apoio (simetria)
    R_esq = F_vertical / 2
    R_dir = F_vertical / 2
    
    # Domínio x (ao longo do eixo)
    x = np.linspace(0, (pos_rolamento_esq + L_vao + 50) / 1000, 500)
    
    # Esforço cortante V(x)
    V = np.zeros_like(x)
    for i, xi in enumerate(x):
        if xi < pos_esq:
            V[i] = 0
        elif xi < pos_carga:
            V[i] = R_esq
        elif xi < pos_dir:
            V[i] = R_esq - F_vertical
        else:
            V[i] = 0
    
    # Momento fletor M(x) - vertical
    M_vert = np.zeros_like(x)
    for i, xi in enumerate(x):
        if xi < pos_esq:
            M_vert[i] = 0
        elif xi < pos_carga:
            M_vert[i] = R_esq * (xi - pos_esq)
        elif xi < pos_dir:
            M_vert[i] = R_esq * (xi - pos_esq) - F_vertical * (xi - pos_carga)
        else:
            M_vert[i] = 0
    
    # Momento fletor máximo
    M_max = np.max(M_vert)
    
    # Tensão de flexão
    Z = np.pi * (d_eixo/1000)**3 / 32  # m³
    sigma_vert = M_max / Z / 1e6  # MPa
    
    # ========================================================================
    # PLOT
    # ========================================================================
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle(titulo, fontsize=14, fontweight='bold')
    
    # (1) Esquema da viga
    ax = axes[0]
    ax.plot([0, x[-1]], [0, 0], 'k-', linewidth=3, label='Eixo')
    
    # Apoios
    ax.plot(pos_esq, 0, '^', markersize=15, color='darkred', label='Apoio esquerdo')
    ax.plot(pos_dir, 0, '^', markersize=15, color='darkred', label='Apoio direito')
    
    # Carga
    ax.arrow(pos_carga, 0.05, 0, -0.04, head_width=0.01, head_length=0.005,
             fc='red', ec='red', linewidth=2)
    ax.text(pos_carga, 0.06, f'F = {F_vertical:.0f} N', ha='center', va='bottom',
            fontsize=10, fontweight='bold', color='red')
    
    ax.set_xlim([0, x[-1]])
    ax.set_ylim([-0.02, 0.08])
    ax.set_ylabel('Carregamento', fontsize=10)
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xticklabels([])
    
    # (2) Esforço cortante
    ax = axes[1]
    ax.plot(x, V, 'b-', linewidth=2.5)
    ax.axhline(0, color='k', linewidth=0.8, linestyle='--', alpha=0.5)
    ax.fill_between(x, V, alpha=0.3)
    ax.set_ylabel('Esforço Cortante V(x) [N]', fontsize=10, fontweight='bold')
    ax.set_xlim([0, x[-1]])
    ax.grid(True, alpha=0.3)
    ax.set_xticklabels([])
    
    V_max = np.max(np.abs(V))
    ax.text(0.02, 0.95, f'V_max = {V_max:.1f} N', transform=ax.transAxes,
            fontsize=10, va='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # (3) Momento fletor
    ax = axes[2]
    ax.plot(x, M_vert, 'g-', linewidth=2.5)
    ax.axhline(0, color='k', linewidth=0.8, linestyle='--', alpha=0.5)
    ax.fill_between(x, M_vert, alpha=0.3, color='green')
    ax.set_ylabel('Momento Fletor M(x) [N·m]', fontsize=10, fontweight='bold')
    ax.set_xlabel('Posição ao longo do eixo [m]', fontsize=10)
    ax.set_xlim([0, x[-1]])
    ax.grid(True, alpha=0.3)
    
    ax.text(0.02, 0.95, f'M_max = {M_max:.2f} N·m\nσ_flex = {sigma_vert:.1f} MPa (Ø{d_eixo} mm)',
            transform=ax.transAxes, fontsize=10, va='top',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
    
    plt.tight_layout()
    return fig, M_max, sigma_vert


def comparar_diagramas():
    """Compara diagramas para Ø20 mm (atual presumido) e Ø28 mm (adotado)."""
    
    configs = [
        {'d': 20, 'L_vao': 300, 'pos_esq': 50, 'arquivo': 'diagramas_esforcos_20mm.png'},
        {'d': 28, 'L_vao': 300, 'pos_esq': 50, 'arquivo': 'diagramas_esforcos_28mm.png'},
        {'d': 28, 'L_vao': 320, 'pos_esq': 50, 'arquivo': 'diagramas_esforcos_28mm_vao320.png'},  # Se vão for maior
    ]
    
    print("\n" + "="*70)
    print("  DIAGRAMAS DE ESFORÇO CORTANTE E MOMENTO FLETOR")
    print("="*70 + "\n")
    
    for cfg in configs:
        fig, M_max, sigma = diagrama_esforcos(
            L_vao=cfg['L_vao'],
            pos_rolamento_esq=cfg['pos_esq'],
            F_vertical=1766,
            d_eixo=cfg['d'],
            titulo=f"Ø{cfg['d']} mm | Vão {cfg['L_vao']} mm — Carga Vertical Apenas"
        )
        plt.savefig(cfg['arquivo'], dpi=300, bbox_inches='tight')
        print(f"✓ {cfg['arquivo']}")
        print(f"  M_max = {M_max:.2f} N·m | σ_flex = {sigma:.1f} MPa\n")
        plt.close()


# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  DESENHO EM CORTE — EIXO TRASEIRO HAMMERHEAD")
    print("="*70 + "\n")
    
    print("Gerando desenhos em corte (3 configurações)...\n")
    gerar_comparativo()
    
    print("\n" + "="*70)
    print("  DIAGRAMAS DE ESFORÇOS")
    print("="*70 + "\n")
    
    comparar_diagramas()
    
    print("\n" + "="*70)
    print("  INSTRUÇÕES PARA USO")
    print("="*70 + "\n")
    print("1. Abra os arquivos PNG gerados:")
    print("   - corte_eixo_config_A_20mm.png (configuração presumida atual)")
    print("   - corte_eixo_config_B_28mm.png (adotada)")
    print("   - corte_eixo_config_C_real.png (PREENCHER COM MEDIDAS REAIS)")
    print("")
    print("2. Meça na peça física:")
    print("   a) Distância entre centros dos rolamentos (vão livre)")
    print("   b) Diâmetro interno do cubo")
    print("   c) Comprimento do cubo")
    print("   d) Posição dos rolamentos desde a ponta do eixo")
    print("")
    print("3. Edite este script, seção 'Configuração C', e insira as medidas reais.")
    print("")
    print("4. Execute novamente para gerar diagramas com geometria correta.")
    print("")
    print("5. Abra os diagramas de esforços:")
    print("   - diagramas_esforcos_20mm.png")
    print("   - diagramas_esforcos_28mm.png")
    print("   - diagramas_esforcos_28mm_vao320.png (se vão for maior)")
    print("")
    print("="*70 + "\n")
