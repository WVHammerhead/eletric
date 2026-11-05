"""
Análise de Viabilidade Ø25 mm - VERSÃO CORRIGIDA
=================================================

CORREÇÕES APLICADAS:
1. Momento fletor vertical: M = (F*L)/4 (carga concentrada)
2. Momento lateral: REMOVIDO temporariamente (h_cg não validado)
3. Análise isolada de flexão vertical (conservadora)

Objetivo:
    Avaliar viabilidade estrutural de Ø25 mm vs Ø20 mm
    sob carga vertical APENAS (dois ocupantes, 180 kg).
    
Premissas:
    - Material: AISI 1045 normalizado (Sy ≈ 310 MPa, Su ≈ 565 MPa)
    - Vão entre apoios: 300 mm (estimado — MEDIR)
    - Carga: 180 kg concentrada no centro do vão
    - Modelo: Viga bi-apoiada, carga concentrada
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================================
# PROPRIEDADES DO MATERIAL
# ============================================================================

class MaterialAISI1045:
    """AISI 1045 normalizado - valores conservadores."""
    Sy = 310e6  # Pa - Tensão de escoamento
    Su = 565e6  # Pa - Tensão última
    E = 200e9   # Pa - Módulo de Young
    Se_prime = 0.5 * Su  # Limite de fadiga não corrigido
    
    # Fatores de correção Marin
    ka_surface = 0.8    # Usinado
    kb_size_20 = 0.85   # Ø20 mm
    kb_size_25 = 0.83   # Ø25 mm
    kc_load = 1.0       # Flexão
    kd_temp = 1.0       # Ambiente
    ke_reliability = 0.868  # 95% confiabilidade
    
    @classmethod
    def Se(cls, diametro_mm):
        """Limite de fadiga corrigido."""
        kb = cls.kb_size_20 if diametro_mm <= 20 else cls.kb_size_25
        return cls.Se_prime * cls.ka_surface * kb * cls.kc_load * cls.kd_temp * cls.ke_reliability

# ============================================================================
# GEOMETRIA E CARREGAMENTO
# ============================================================================

class ConfiguracaoEixo:
    """Configuração geométrica."""
    
    def __init__(self, diametro_mm, vao_mm=300, massa_total_kg=180):
        self.d = diametro_mm / 1000  # m
        self.L = vao_mm / 1000       # m
        self.F = massa_total_kg * 9.81  # N (carga concentrada)
        
        # Geometria da seção
        self.I = np.pi * (self.d**4) / 64  # m^4 - momento de inércia
        self.Z = np.pi * (self.d**3) / 32  # m^3 - módulo de seção
        self.J = np.pi * (self.d**4) / 32  # m^4 - momento polar
    
    def __repr__(self):
        return f"Ø{self.d*1000:.0f} mm | L={self.L*1000:.0f} mm | F={self.F:.0f} N"

class CarregamentoVertical:
    """Modelo de carga vertical (carga concentrada no centro)."""
    
    def __init__(self, config: ConfiguracaoEixo):
        self.cfg = config
    
    def momento_fletor_maximo(self):
        """
        Momento máximo para viga bi-apoiada com carga concentrada no centro.
        
        Fórmula: M_max = (F * L) / 4
        
        Derivação:
            Reações nos apoios: R_A = R_B = F/2
            Momento no centro: M = R_A * (L/2) = (F/2) * (L/2) = F*L/4
        """
        return (self.cfg.F * self.cfg.L) / 4
    
    def tensao_flexao(self):
        """Tensão de flexão: σ = M / Z"""
        M = self.momento_fletor_maximo()
        return M / self.cfg.Z
    
    def deflexao_centro(self):
        """Deflexão no centro: δ = (F*L³)/(48*E*I)"""
        return (self.cfg.F * self.cfg.L**3) / (48 * MaterialAISI1045.E * self.cfg.I)

class CarregamentoTorcao:
    """Modelo simplificado de torção (frenagem)."""
    
    def __init__(self, config: ConfiguracaoEixo):
        self.cfg = config
    
    def momento_torcao_frenagem(self, raio_roda_m=0.26, desaceleracao_g=1.2):
        """Torque transmitido pelo tambor durante frenagem."""
        F_frenagem = (self.cfg.F / 9.81) * 9.81 * desaceleracao_g  # N
        return F_frenagem * raio_roda_m
    
    def tensao_cisalhamento(self):
        """Tensão de cisalhamento: τ = (T*r)/J"""
        T = self.momento_torcao_frenagem()
        return (T * (self.cfg.d / 2)) / self.cfg.J

class TensaoEquivalente:
    """Critério de Von Mises para flexão + torção."""
    
    @staticmethod
    def von_mises(sigma_flexao, tau_torcao):
        """σ_eq = sqrt(σ² + 3τ²)"""
        return np.sqrt(sigma_flexao**2 + 3 * tau_torcao**2)

# ============================================================================
# ANÁLISE DE FADIGA
# ============================================================================

class AnaliseFadiga:
    """Critério de Goodman modificado."""
    
    def __init__(self, config: ConfiguracaoEixo):
        self.cfg = config
        self.Se = MaterialAISI1045.Se(config.d * 1000)
    
    def fator_seguranca_goodman(self, sigma_max, sigma_min=0):
        """
        FS segundo Goodman para carga pulsante.
        
        σ_m = (σ_max + σ_min) / 2
        σ_a = (σ_max - σ_min) / 2
        1/FS = σ_a/Se + σ_m/Su
        """
        sigma_m = (sigma_max + sigma_min) / 2
        sigma_a = (sigma_max - sigma_min) / 2
        
        if sigma_a == 0 and sigma_m == 0:
            return np.inf
        
        inv_n = sigma_a / self.Se + sigma_m / MaterialAISI1045.Su
        return 1 / inv_n if inv_n > 0 else np.inf

class ConcentracaoTensao:
    """Fatores de concentração de tensão."""
    
    @staticmethod
    def kt_rebaixo(r_mm=1.0, d_mm=20, D_mm=22):
        """Kt para rebaixo com raio de concordância."""
        if r_mm <= 0:
            return 4.0
        ratio = D_mm / d_mm
        return 1.0 + 0.9 * np.sqrt((ratio - 1) * d_mm / r_mm)
    
    @staticmethod
    def kt_rosca(tipo="laminada"):
        """Kt para rosca métrica."""
        return 2.2 if tipo == "laminada" else 2.8
    
    @staticmethod
    def kf(kt, q=0.85):
        """Kf = 1 + q(Kt - 1)"""
        return 1 + q * (kt - 1)

# ============================================================================
# ANÁLISE COMPARATIVA
# ============================================================================

def analisar_configuracao(diametro_mm, descricao):
    """Análise completa para um diâmetro."""
    print(f"\n{'='*70}")
    print(f"  {descricao}")
    print(f"{'='*70}")
    
    cfg = ConfiguracaoEixo(diametro_mm)
    vert = CarregamentoVertical(cfg)
    torc = CarregamentoTorcao(cfg)
    fadiga = AnaliseFadiga(cfg)
    
    print(f"\nGeometria: {cfg}")
    print(f"  Z = {cfg.Z*1e6:.2f} cm³")
    print(f"  I = {cfg.I*1e8:.2f} cm⁴")
    
    # Cargas
    M = vert.momento_fletor_maximo()
    T = torc.momento_torcao_frenagem()
    
    print(f"\nMomentos:")
    print(f"  Fletor (vertical): {M:.2f} N·m")
    print(f"  Torção (frenagem): {T:.2f} N·m")
    
    # Tensões
    sigma = vert.tensao_flexao()
    tau = torc.tensao_cisalhamento()
    sigma_vm = TensaoEquivalente.von_mises(sigma, tau)
    
    print(f"\nTensões Nominais:")
    print(f"  Flexão:     {sigma/1e6:>6.1f} MPa")
    print(f"  Torção:     {tau/1e6:>6.1f} MPa")
    print(f"  Von Mises:  {sigma_vm/1e6:>6.1f} MPa")
    
    # FS Escoamento
    fs_esc = MaterialAISI1045.Sy / sigma_vm
    print(f"\nFator de Segurança (Escoamento):")
    print(f"  FS = {fs_esc:.2f}  {'✓ ADEQUADO' if fs_esc >= 2.0 else '✗ INSUFICIENTE'}")
    
    # Fadiga (nominal)
    fs_fad_nom = fadiga.fator_seguranca_goodman(sigma)
    print(f"\nFadiga (nominal, sem Kt):")
    print(f"  Se = {fadiga.Se/1e6:.1f} MPa")
    print(f"  FS = {fs_fad_nom:.2f}  {'✓ ADEQUADO' if fs_fad_nom >= 1.5 else '✗ INSUFICIENTE'}")
    
    # Concentração de tensão
    kt_reb = ConcentracaoTensao.kt_rebaixo(r_mm=1.0, d_mm=diametro_mm-2, D_mm=diametro_mm)
    kf_reb = ConcentracaoTensao.kf(kt_reb)
    print(f"\nConcentração (rebaixo rolamento):")
    print(f"  Kt = {kt_reb:.2f}, Kf = {kf_reb:.2f}")
    
    # Fadiga com Kt
    sigma_conc = sigma * kf_reb
    fs_fad_real = fadiga.fator_seguranca_goodman(sigma_conc)
    print(f"\nFadiga (com Kt):")
    print(f"  σ concentrada: {sigma_conc/1e6:.1f} MPa")
    print(f"  FS = {fs_fad_real:.2f}  {'✓ ADEQUADO' if fs_fad_real >= 1.5 else '⚠ MARGINAL' if fs_fad_real >= 1.2 else '✗ INSUFICIENTE'}")
    
    # Deflexão
    deflexao = vert.deflexao_centro() * 1000  # mm
    print(f"\nDeflexão no centro:")
    print(f"  δ = {deflexao:.2f} mm  {'✓ OK' if deflexao < 5 else '⚠ ALTA'}")
    
    return {
        'diametro_mm': diametro_mm,
        'descricao': descricao,
        'M_Nm': M,
        'sigma_flexao_MPa': sigma / 1e6,
        'sigma_von_mises_MPa': sigma_vm / 1e6,
        'FS_escoamento': fs_esc,
        'FS_fadiga_nominal': fs_fad_nom,
        'FS_fadiga_com_Kt': fs_fad_real,
        'deflexao_mm': deflexao,
        'adequado': fs_esc >= 2.0 and fs_fad_real >= 1.5,
    }

# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  ANÁLISE CORRIGIDA: Ø25 mm vs Ø20 mm")
    print("  Carga Vertical Concentrada (180 kg, dois ocupantes)")
    print("="*70)
    
    print("\n⚠️  PREMISSAS:")
    print("  - Vão entre apoios: 300 mm (ESTIMADO — requer medição)")
    print("  - Carga: 180 kg concentrada no centro")
    print("  - Modelo: Viga bi-apoiada, M = F*L/4")
    print("  - Momento lateral NÃO INCLUÍDO (h_cg não validado)\n")
    
    resultados = []
    
    r20 = analisar_configuracao(20, "Ø20 mm - ATUAL")
    resultados.append(r20)
    
    r25 = analisar_configuracao(25, "Ø25 mm - PROPOSTA")
    resultados.append(r25)
    
    # Comparação
    print(f"\n{'='*70}")
    print("  COMPARAÇÃO FINAL")
    print(f"{'='*70}\n")
    
    df = pd.DataFrame(resultados)
    print(df[['diametro_mm', 'sigma_flexao_MPa', 'FS_escoamento', 
              'FS_fadiga_com_Kt', 'deflexao_mm', 'adequado']].to_string(index=False))
    
    # Gráfico
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Análise Corrigida: Ø20 mm vs Ø25 mm (Carga Vertical)', 
                 fontsize=14, fontweight='bold')
    
    d = df['diametro_mm'].values
    
    # Tensões
    ax = axes[0, 0]
    ax.bar(d, df['sigma_flexao_MPa'], width=2, alpha=0.7, label='Flexão')
    ax.bar(d, df['sigma_von_mises_MPa'], width=2, alpha=0.7, label='Von Mises')
    ax.axhline(MaterialAISI1045.Sy/1e6, color='r', linestyle='--', label='Sy')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('Tensão (MPa)')
    ax.set_title('Tensões Atuantes')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # FS Escoamento
    ax = axes[0, 1]
    ax.bar(d, df['FS_escoamento'], width=2, color='steelblue', alpha=0.7)
    ax.axhline(2.0, color='g', linestyle='--', label='Mínimo')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('FS')
    ax.set_title('FS Escoamento')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # FS Fadiga
    ax = axes[1, 0]
    ax.bar(d - 0.5, df['FS_fadiga_nominal'], width=1, alpha=0.7, label='Nominal')
    ax.bar(d + 0.5, df['FS_fadiga_com_Kt'], width=1, alpha=0.7, label='Com Kt')
    ax.axhline(1.5, color='g', linestyle='--', label='Mínimo')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('FS')
    ax.set_title('FS Fadiga')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Deflexão
    ax = axes[1, 1]
    ax.bar(d, df['deflexao_mm'], width=2, color='orange', alpha=0.7)
    ax.axhline(5.0, color='orange', linestyle='--', label='Limite sugerido')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('Deflexão (mm)')
    ax.set_title('Deflexão no Centro')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('analise_viabilidade_25mm_CORRIGIDA.png', dpi=300, bbox_inches='tight')
    print("\n→ Gráfico: analise_viabilidade_25mm_CORRIGIDA.png")
    
    df.to_csv('analise_viabilidade_25mm_CORRIGIDA.csv', index=False)
    print("→ Dados: analise_viabilidade_25mm_CORRIGIDA.csv")
    
    # Conclusão
    print(f"\n{'='*70}")
    print("  CONCLUSÃO (Carga Vertical Isolada)")
    print(f"{'='*70}\n")
    
    if r25['adequado']:
        print("✓ Ø25 mm é ADEQUADO para carga vertical (180 kg).")
        print(f"  FS escoamento = {r25['FS_escoamento']:.2f}")
        print(f"  FS fadiga (com Kt) = {r25['FS_fadiga_com_Kt']:.2f}")
    else:
        print("✗ Ø25 mm NÃO É ADEQUADO.")
    
    print("\n⚠️  PENDÊNCIAS:")
    print("  1. Medir vão real entre rolamentos")
    print("  2. Avaliar momento lateral (requer modelo de suspensão)")
    print("  3. Confirmar tipo de rosca (laminada/usinada)")
    print("  4. Validar com medições de deformação (strain gauges)\n")
