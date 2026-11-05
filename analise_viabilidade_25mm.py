"""
Análise de Viabilidade Ø25 mm - Eixo Traseiro Hammerhead
==========================================================

Objetivo:
    Avaliar se Ø25 mm resiste a **todas** as solicitações reais:
    - Flexão vertical (dois ocupantes)
    - Momento lateral (curva)
    - Torque de frenagem
    - Fadiga (ciclos de uso)
    - Concentração de tensão (rebaixos, roscas)
    
Premissas:
    - Material: AISI 1045 normalizado (Sy ≈ 310 MPa, Su ≈ 565 MPa)
    - Vão livre entre apoios: 300 mm (estimado, requer medição)
    - Cargas: 180 kg vertical, 0.8g lateral, 1.2g frenagem
"""

import sys
import io
# Configure stdout encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================================
# PROPRIEDADES DO MATERIAL
# ============================================================================

class MaterialAISI1045:
    """AISI 1045 normalizado - valores conservadores."""
    Sy = 310e6  # Pa - Tensão de escoamento
    Su = 565e6  # Pa - Tensão última
    E = 200e9   # Pa - Módulo de Young
    Se_prime = 0.5 * Su  # Limite de fadiga não corrigido (viga rotativa)
    
    # Fatores de correção Marin para fadiga
    ka_surface = 0.8    # Acabamento usinado
    kb_size_20 = 0.85   # Ø20 mm
    kb_size_25 = 0.83   # Ø25 mm (penalidade por tamanho maior)
    kc_load = 1.0       # Flexão
    kd_temp = 1.0       # Ambiente
    ke_reliability = 0.868  # 95% confiabilidade
    
    @classmethod
    def Se(cls, diametro_mm):
        """Limite de fadiga corrigido."""
        kb = cls.kb_size_20 if diametro_mm <= 20 else cls.kb_size_25
        return cls.Se_prime * cls.ka_surface * kb * cls.kc_load * cls.kd_temp * cls.ke_reliability


# ============================================================================
# GEOMETRIA E CARGAS
# ============================================================================

class ConfiguracaoEixo:
    """Configuração geométrica e de carregamento."""
    
    def __init__(self, diametro_mm, vao_mm=300, massa_total_kg=180):
        self.d = diametro_mm / 1000  # m
        self.L = vao_mm / 1000       # m
        self.massa = massa_total_kg  # kg
        self.g = 9.81                # m/s²
        
        # Momentos de inércia
        self.I = np.pi * (self.d**4) / 64  # m^4
        self.Z = np.pi * (self.d**3) / 32  # m^3 - módulo de seção
        
        # Momento polar (torção)
        self.J = np.pi * (self.d**4) / 32  # m^4
        
    def __repr__(self):
        return f"Ø{self.d*1000:.0f} mm | L={self.L*1000:.0f} mm | m={self.massa:.0f} kg"


class CarregamentoCombinado:
    """Modelo de cargas reais sobre o eixo."""
    
    def __init__(self, config: ConfiguracaoEixo):
        self.cfg = config
        
    def carga_vertical(self):
        """Carga vertical estática (peso)."""
        return self.cfg.massa * self.cfg.g
    
    def carga_lateral_curva(self, aceleracao_lateral_g=0.8):
        """Força lateral em curva fechada."""
        return self.cfg.massa * self.cfg.g * aceleracao_lateral_g
    
    def momento_frenagem(self, raio_roda_m=0.26, desaceleracao_g=1.2):
        """Momento de torque na frenagem (transmitido pelo tambor)."""
        F_frenagem = self.cfg.massa * self.cfg.g * desaceleracao_g
        return F_frenagem * raio_roda_m
    
    def momento_fletor_vertical(self):
        """Momento máximo no centro do vão (viga bi-apoiada, carga concentrada)."""
        F = self.carga_vertical()  # N
        return (F * self.cfg.L) / 4
    
    def momento_fletor_lateral(self):
        """Momento lateral em curva."""
        F_lat = self.carga_lateral_curva()
        # Braço de momento = altura do CG (~0.6 m) até eixo
        h_cg = 0.6  # m (estimado)
        return F_lat * h_cg / 2  # Dividido entre dois lados
    
    def tensao_flexao_vertical(self):
        """Tensão de flexão vertical."""
        M = self.momento_fletor_vertical()
        return M / self.cfg.Z
    
    def tensao_flexao_lateral(self):
        """Tensão de flexão lateral."""
        M = self.momento_fletor_lateral()
        return M / self.cfg.Z
    
    def tensao_flexao_combinada(self):
        """Tensão de flexão resultante (vertical + lateral)."""
        sigma_v = self.tensao_flexao_vertical()
        sigma_l = self.tensao_flexao_lateral()
        return np.sqrt(sigma_v**2 + sigma_l**2)
    
    def tensao_torcao(self):
        """Tensão de cisalhamento por torção (frenagem)."""
        T = self.momento_frenagem()
        return (T * (self.cfg.d / 2)) / self.cfg.J
    
    def tensao_von_mises(self):
        """Tensão equivalente de Von Mises (flexão + torção)."""
        sigma = self.tensao_flexao_combinada()
        tau = self.tensao_torcao()
        return np.sqrt(sigma**2 + 3 * tau**2)


# ============================================================================
# ANÁLISE DE FADIGA
# ============================================================================

class AnaliseFadiga:
    """Critério de Goodman modificado."""
    
    def __init__(self, config: ConfiguracaoEixo, material=MaterialAISI1045):
        self.cfg = config
        self.mat = material
        self.Se = material.Se(config.d * 1000)
        
    def tensao_media_alternada(self, sigma_max, sigma_min):
        """Componentes média e alternada de um ciclo."""
        sigma_m = (sigma_max + sigma_min) / 2
        sigma_a = (sigma_max - sigma_min) / 2
        return sigma_m, sigma_a
    
    def fator_seguranca_goodman(self, sigma_a, sigma_m):
        """Fator de segurança segundo Goodman."""
        # 1/n = sigma_a/Se + sigma_m/Su
        if sigma_a == 0 and sigma_m == 0:
            return np.inf
        inv_n = sigma_a / self.Se + sigma_m / self.mat.Su
        return 1 / inv_n if inv_n > 0 else np.inf
    
    def avaliar_fadiga_flexao(self, sigma_max):
        """
        Ciclo de flexão: assume tensão mínima = 0 (sempre tração em um lado).
        Pior caso: carga pulsante (0 → sigma_max).
        """
        sigma_m, sigma_a = self.tensao_media_alternada(sigma_max, 0)
        return self.fator_seguranca_goodman(sigma_a, sigma_m)


# ============================================================================
# CONCENTRAÇÃO DE TENSÃO (REBAIXOS E ROSCAS)
# ============================================================================

class ConcentracaoTensao:
    """Estimativa de Kt para rebaixos e roscas."""
    
    @staticmethod
    def kt_rebaixo_filete(r_mm, d_mm, D_mm):
        """
        Fator de concentração para rebaixo com raio de concordância.
        r: raio do filete (mm)
        d: diâmetro menor (mm)
        D: diâmetro maior (mm)
        
        Aproximação: Kt ≈ 1 + 2*sqrt(D/r - 1) para flexão
        """
        if r_mm <= 0:
            return 4.0  # Rebaixo vivo (muito severo)
        ratio = D_mm / d_mm
        return 1.0 + 0.9 * np.sqrt((ratio - 1) * d_mm / r_mm)
    
    @staticmethod
    def kt_rosca_metrica(tipo="laminada"):
        """
        Fator de concentração para rosca métrica.
        - Laminada (melhor): Kt ≈ 2.2
        - Usinada (pior): Kt ≈ 2.8
        """
        return 2.2 if tipo == "laminada" else 2.8
    
    @staticmethod
    def kf_fadiga(kt, sensibilidade_entalhe_q=0.85):
        """Fator de fadiga Kf = 1 + q(Kt - 1)."""
        return 1 + sensibilidade_entalhe_q * (kt - 1)


# ============================================================================
# ANÁLISE COMPARATIVA
# ============================================================================

def analisar_configuracao(diametro_mm, descricao):
    """Executa análise completa para um diâmetro."""
    print(f"\n{'='*70}")
    print(f"  {descricao}")
    print(f"{'='*70}")
    
    cfg = ConfiguracaoEixo(diametro_mm)
    cargas = CarregamentoCombinado(cfg)
    fadiga = AnaliseFadiga(cfg)
    
    print(f"\nGeometria: {cfg}")
    print(f"  Módulo de seção Z = {cfg.Z*1e6:.2f} cm³")
    print(f"  Momento de inércia I = {cfg.I*1e8:.2f} cm⁴")
    
    # Cargas
    print(f"\nCargas:")
    print(f"  Vertical: {cargas.carga_vertical():.0f} N")
    print(f"  Lateral (0.8g): {cargas.carga_lateral_curva():.0f} N")
    print(f"  Momento frenagem: {cargas.momento_frenagem():.1f} N·m")
    
    # Tensões
    sigma_v = cargas.tensao_flexao_vertical()
    sigma_l = cargas.tensao_flexao_lateral()
    sigma_comb = cargas.tensao_flexao_combinada()
    tau = cargas.tensao_torcao()
    sigma_vm = cargas.tensao_von_mises()
    
    print(f"\nTensões Nominais:")
    print(f"  Flexão vertical:     {sigma_v/1e6:>6.1f} MPa")
    print(f"  Flexão lateral:      {sigma_l/1e6:>6.1f} MPa")
    print(f"  Flexão combinada:    {sigma_comb/1e6:>6.1f} MPa")
    print(f"  Cisalhamento torção: {tau/1e6:>6.1f} MPa")
    print(f"  Von Mises:           {sigma_vm/1e6:>6.1f} MPa")
    
    # Fatores de segurança estático
    fs_escoamento = MaterialAISI1045.Sy / sigma_vm
    print(f"\nFator de Segurança (Escoamento):")
    print(f"  FS = {fs_escoamento:.2f}  {'✓ ADEQUADO' if fs_escoamento >= 2.0 else '✗ INSUFICIENTE'}")
    
    # Fadiga (sem concentração)
    fs_fadiga_nominal = fadiga.avaliar_fadiga_flexao(sigma_comb)
    print(f"\nFadiga (tensão nominal, sem concentração):")
    print(f"  Se' = {fadiga.Se/1e6:.1f} MPa")
    print(f"  FS_fadiga = {fs_fadiga_nominal:.2f}  {'✓ ADEQUADO' if fs_fadiga_nominal >= 1.5 else '✗ INSUFICIENTE'}")
    
    # Concentração de tensão
    print(f"\nConcentração de Tensão:")
    
    # Rebaixo típico para rolamento (r=1mm, D=diametro+2mm)
    kt_rebaixo = ConcentracaoTensao.kt_rebaixo_filete(r_mm=1.0, d_mm=diametro_mm-2, D_mm=diametro_mm)
    kf_rebaixo = ConcentracaoTensao.kf_fadiga(kt_rebaixo)
    print(f"  Rebaixo rolamento: Kt={kt_rebaixo:.2f}, Kf={kf_rebaixo:.2f}")
    
    # Rosca
    kt_rosca = ConcentracaoTensao.kt_rosca_metrica("laminada")
    kf_rosca = ConcentracaoTensao.kf_fadiga(kt_rosca)
    print(f"  Rosca laminada: Kt={kt_rosca:.2f}, Kf={kf_rosca:.2f}")
    
    # Pior caso: concentração no rebaixo
    sigma_concentrada = sigma_comb * kf_rebaixo
    fs_fadiga_real = fadiga.avaliar_fadiga_flexao(sigma_concentrada)
    print(f"\nFadiga (com concentração no rebaixo):")
    print(f"  Tensão concentrada: {sigma_concentrada/1e6:.1f} MPa")
    print(f"  FS_fadiga = {fs_fadiga_real:.2f}  {'✓ ADEQUADO' if fs_fadiga_real >= 1.5 else '✗ MARGINAL' if fs_fadiga_real >= 1.2 else '✗ INSUFICIENTE'}")
    
    # Resumo
    resultado = {
        'diametro_mm': diametro_mm,
        'descricao': descricao,
        'sigma_flexao_MPa': sigma_comb / 1e6,
        'sigma_von_mises_MPa': sigma_vm / 1e6,
        'FS_escoamento': fs_escoamento,
        'FS_fadiga_nominal': fs_fadiga_nominal,
        'FS_fadiga_com_concentracao': fs_fadiga_real,
        'adequado_estatico': fs_escoamento >= 2.0,
        'adequado_fadiga': fs_fadiga_real >= 1.5,
    }
    
    return resultado


# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    print("ATENÇÃO: estudo hipotético NÃO VALIDADO; o braço lateral de 0,6 m não foi demonstrado, e os fatores de segurança não aprovam nem reprovam o eixo real.")
    print("\n" + "="*70)
    print("  ANÁLISE DE VIABILIDADE: Ø25 mm vs Ø20 mm")
    print("  Eixo Traseiro Hammerhead - Cenário Completo")
    print("="*70)
    
    resultados = []
    
    # Ø20 mm (referência atual)
    r20 = analisar_configuracao(20, "Ø20 mm - CONFIGURAÇÃO ATUAL")
    resultados.append(r20)
    
    # Ø25 mm (proposta)
    r25 = analisar_configuracao(25, "Ø25 mm - PROPOSTA")
    resultados.append(r25)
    
    # Comparação final
    print(f"\n{'='*70}")
    print("  COMPARAÇÃO FINAL")
    print(f"{'='*70}\n")
    
    df = pd.DataFrame(resultados)
    print(df.to_string(index=False))
    
    # Gráfico comparativo
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Comparação Ø20 mm vs Ø25 mm - Eixo Traseiro', fontsize=14, fontweight='bold')
    
    diametros = df['diametro_mm'].values
    
    # Tensões
    ax = axes[0, 0]
    ax.bar(diametros - 0.5, df['sigma_flexao_MPa'], width=1, label='Flexão combinada', alpha=0.7)
    ax.bar(diametros + 0.5, df['sigma_von_mises_MPa'], width=1, label='Von Mises', alpha=0.7)
    ax.axhline(MaterialAISI1045.Sy/1e6, color='r', linestyle='--', label='Sy (310 MPa)')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('Tensão (MPa)')
    ax.set_title('Tensões Atuantes')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # FS Escoamento
    ax = axes[0, 1]
    ax.bar(diametros, df['FS_escoamento'], width=2, color='steelblue', alpha=0.7)
    ax.axhline(2.0, color='g', linestyle='--', label='Mínimo (FS=2.0)')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('Fator de Segurança')
    ax.set_title('FS Escoamento')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # FS Fadiga (nominal)
    ax = axes[1, 0]
    ax.bar(diametros, df['FS_fadiga_nominal'], width=2, color='orange', alpha=0.7, label='Nominal')
    ax.axhline(1.5, color='g', linestyle='--', label='Mínimo (FS=1.5)')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('Fator de Segurança')
    ax.set_title('FS Fadiga (sem concentração)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # FS Fadiga (com concentração)
    ax = axes[1, 1]
    ax.bar(diametros, df['FS_fadiga_com_concentracao'], width=2, color='crimson', alpha=0.7, label='Com Kt')
    ax.axhline(1.5, color='g', linestyle='--', label='Mínimo (FS=1.5)')
    ax.axhline(1.2, color='orange', linestyle='--', label='Marginal (FS=1.2)')
    ax.set_xlabel('Diâmetro (mm)')
    ax.set_ylabel('Fator de Segurança')
    ax.set_title('FS Fadiga (com concentração de tensão)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('analise_viabilidade_25mm.png', dpi=300, bbox_inches='tight')
    print("\n→ Gráfico salvo: analise_viabilidade_25mm.png")
    
    # Salvar dados
    df.to_csv('analise_viabilidade_25mm.csv', index=False)
    print("→ Dados salvos: analise_viabilidade_25mm.csv")
    
    # Conclusão
    print(f"\n{'='*70}")
    print("  CONCLUSÃO")
    print(f"{'='*70}\n")
    
    if r25['adequado_estatico'] and r25['adequado_fadiga']:
        print("✓ Ø25 mm é VIÁVEL do ponto de vista estrutural.")
        print("  Atende aos critérios de escoamento e fadiga com concentração de tensão.")
    elif r25['adequado_estatico']:
        print("⚠ Ø25 mm é MARGINAL.")
        print("  Atende ao escoamento, mas está no limite para fadiga.")
        print("  Recomenda-se validação experimental ou aumento de diâmetro.")
    else:
        print("✗ Ø25 mm NÃO É ADEQUADO.")
        print("  Não atende aos critérios mínimos de segurança.")
    
    print("\nPendências para validação final:")
    print("  1. Medir geometria real: vão entre apoios, posição de rebaixos")
    print("  2. Confirmar rosca M12: comprimento, posição, tipo (laminada/usinada)")
    print("  3. Medir cubo da roda: diâmetro interno, comprimento, rolamentos")
    print("  4. Verificar integração tambor de freio com cubo Ø25 mm")
    print("  5. Considerar tratamento térmico localizado se FS < 1.5")
    print("\n")
