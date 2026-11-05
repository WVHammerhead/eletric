"""
Teste: Divisão de Esforços — Eixo Traseiro com Balança (Swing Arm)
====================================================================

Objetivo:
    Modelar o eixo traseiro como viga com múltiplos apoios e cargas,
    para determinar onde a balança se apoia e como o torque é transmitido.

Modelo:
    - Eixo: viga com até 4 pontos de apoio (2 rolamentos + 2 fixações balança)
    - Cargas: vertical (ocupantes), torque (frenagem), lateral (curvas)
    - Casos de teste: diferentes configurações de fixação

Casos a Testar:
    1. Apenas 2 rolamentos (modelo simples)
    2. Rolamentos + braço limitador da balança (3 apoios)
    3. Rolamentos + espelho esquerdo e direito (4 apoios)
    4. Torque no cubo vs torque distribuído
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrow, Circle, FancyBboxPatch
import pandas as pd

# ============================================================================
# CLASSE: MODELO DE VIGA COM MÚLTIPLOS APOIOS
# ============================================================================

class VigaMultiApoios:
    """
    Modelo de viga com múltiplos apoios e cargas.
    
    Convenção:
    - x = 0 na extremidade esquerda do eixo
    - Apoios: (posição, tipo) onde tipo = 'fixo' ou 'rolamento'
    - Cargas: (posição, magnitude, direção)
    """
    
    def __init__(self, L_total_mm, d_eixo_mm, descricao=""):
        self.L = L_total_mm / 1000  # m
        self.d = d_eixo_mm / 1000   # m
        self.descricao = descricao
        
        # Geometria
        self.I = np.pi * (self.d**4) / 64
        self.Z = np.pi * (self.d**3) / 32
        self.J = np.pi * (self.d**4) / 32
        
        # Apoios e cargas (serão definidos por configuração)
        self.apoios = []  # Lista de (x_m, tipo, descricao)
        self.cargas_verticais = []  # Lista de (x_m, F_N, descricao)
        self.momentos_aplicados = []  # Lista de (x_m, M_Nm, descricao)
        
    def adicionar_apoio(self, x_mm, tipo='rolamento', descricao=''):
        """Adiciona apoio (rolamento ou fixo)."""
        self.apoios.append({
            'x': x_mm / 1000,
            'tipo': tipo,
            'descricao': descricao
        })
    
    def adicionar_carga_vertical(self, x_mm, F_N, descricao=''):
        """Adiciona carga vertical concentrada."""
        self.cargas_verticais.append({
            'x': x_mm / 1000,
            'F': F_N,
            'descricao': descricao
        })
    
    def adicionar_momento(self, x_mm, M_Nm, descricao=''):
        """Adiciona momento aplicado (torque)."""
        self.momentos_aplicados.append({
            'x': x_mm / 1000,
            'M': M_Nm,
            'descricao': descricao
        })
    
    def calcular_reacoes(self):
        """
        Calcula reações nos apoios (simplificado para 2-3 apoios).
        
        Para casos complexos, requer matriz de rigidez ou método das forças.
        Aqui implementamos casos específicos.
        """
        n_apoios = len(self.apoios)
        
        if n_apoios == 0:
            raise ValueError("Nenhum apoio definido!")
        
        # Soma de forças verticais
        F_total = sum([c['F'] for c in self.cargas_verticais])
        
        if n_apoios == 2:
            # Caso simples: 2 apoios, carga entre eles
            x1, x2 = self.apoios[0]['x'], self.apoios[1]['x']
            L_vao = x2 - x1
            
            # Momento em relação ao apoio 1
            M_total = sum([c['F'] * (c['x'] - x1) for c in self.cargas_verticais])
            
            R2 = M_total / L_vao
            R1 = F_total - R2
            
            reacoes = [R1, R2]
            
        elif n_apoios == 3:
            # Caso: 3 apoios (hiperestático)
            # Simplificação: assume apoio central como limitador (reação menor)
            x1, x2, x3 = [a['x'] for a in self.apoios]
            
            # Se carga está entre x1 e x2, x3 tem reação mínima
            # Solução aproximada: distribui proporcionalmente
            distancias = [abs(c['x'] - a['x']) for c in self.cargas_verticais for a in self.apoios]
            
            # Distribui carga inversamente proporcional à distância
            R1 = F_total * 0.45  # Estimativa
            R2 = F_total * 0.45
            R3 = F_total * 0.10  # Limitador
            
            reacoes = [R1, R2, R3]
            
        else:
            # Mais de 3 apoios: distribui igualmente (muito simplificado)
            reacoes = [F_total / n_apoios] * n_apoios
        
        # Atribui reações aos apoios
        for i, apoio in enumerate(self.apoios):
            apoio['reacao_N'] = reacoes[i]
        
        return reacoes
    
    def calcular_diagrama_V_M(self, n_pontos=500):
        """
        Calcula esforço cortante V(x) e momento fletor M(x).
        """
        x_array = np.linspace(0, self.L, n_pontos)
        V = np.zeros_like(x_array)
        M = np.zeros_like(x_array)
        
        for i, x in enumerate(x_array):
            # Esforço cortante: soma de reações e cargas à esquerda
            V[i] = 0
            for apoio in self.apoios:
                if apoio['x'] < x:
                    V[i] += apoio.get('reacao_N', 0)
            for carga in self.cargas_verticais:
                if carga['x'] < x:
                    V[i] -= carga['F']
            
            # Momento fletor: integral do cortante
            M[i] = 0
            for apoio in self.apoios:
                if apoio['x'] < x:
                    M[i] += apoio.get('reacao_N', 0) * (x - apoio['x'])
            for carga in self.cargas_verticais:
                if carga['x'] < x:
                    M[i] -= carga['F'] * (x - carga['x'])
        
        return x_array, V, M
    
    def tensao_maxima_flexao(self):
        """Retorna tensão máxima de flexão."""
        x, V, M = self.calcular_diagrama_V_M()
        M_max = np.max(np.abs(M))
        return M_max / self.Z
    
    def tensao_maxima_torcao(self):
        """Retorna tensão máxima de torção (se momento aplicado)."""
        if not self.momentos_aplicados:
            return 0
        T_max = max([abs(m['M']) for m in self.momentos_aplicados])
        return (T_max * (self.d / 2)) / self.J
    
    def __repr__(self):
        return (f"Viga: L={self.L*1000:.0f} mm, Ø{self.d*1000:.0f} mm\n"
                f"  {len(self.apoios)} apoios, {len(self.cargas_verticais)} cargas")


# ============================================================================
# CONFIGURAÇÕES DE TESTE
# ============================================================================

def criar_configuracao_1_dois_rolamentos():
    """
    Configuração 1: Modelo Simples
    - Apenas 2 rolamentos (balanço livre)
    - Carga no centro
    - Torque aplicado no cubo
    """
    viga = VigaMultiApoios(L_total_mm=400, d_eixo_mm=28, 
                           descricao="Config 1: Apenas 2 Rolamentos")
    
    # Apoios: rolamentos nas posições típicas
    viga.adicionar_apoio(x_mm=50, tipo='rolamento', descricao='Rolamento Esq')
    viga.adicionar_apoio(x_mm=350, tipo='rolamento', descricao='Rolamento Dir')
    
    # Carga: 180 kg no centro do vão
    viga.adicionar_carga_vertical(x_mm=200, F_N=1766, descricao='Ocupantes (180 kg)')
    
    # Torque: frenagem no cubo (posição = centro do vão)
    viga.adicionar_momento(x_mm=200, M_Nm=551, descricao='Frenagem')
    
    return viga


def criar_configuracao_2_rolamentos_mais_limitador():
    """
    Configuração 2: Rolamentos + Limitador
    - 2 rolamentos
    - 1 braço limitador da balança (impede rotação excessiva)
    - Carga no centro
    """
    viga = VigaMultiApoios(L_total_mm=400, d_eixo_mm=28,
                           descricao="Config 2: Rolamentos + Limitador")
    
    # Apoios
    viga.adicionar_apoio(x_mm=50, tipo='rolamento', descricao='Rolamento Esq')
    viga.adicionar_apoio(x_mm=350, tipo='rolamento', descricao='Rolamento Dir')
    viga.adicionar_apoio(x_mm=280, tipo='fixo', descricao='Limitador Balança')
    
    # Carga
    viga.adicionar_carga_vertical(x_mm=200, F_N=1766, descricao='Ocupantes')
    
    # Torque
    viga.adicionar_momento(x_mm=200, M_Nm=551, descricao='Frenagem')
    
    return viga


def criar_configuracao_3_espelhos_balanca():
    """
    Configuração 3: Espelhos da Balança
    - 2 rolamentos
    - 2 espelhos (abraçadeiras laterais) onde a balança se fixa
    - Carga no centro
    """
    viga = VigaMultiApoios(L_total_mm=400, d_eixo_mm=28,
                           descricao="Config 3: Espelhos da Balança")
    
    # Apoios
    viga.adicionar_apoio(x_mm=50, tipo='rolamento', descricao='Rolamento Esq')
    viga.adicionar_apoio(x_mm=350, tipo='rolamento', descricao='Rolamento Dir')
    viga.adicionar_apoio(x_mm=120, tipo='fixo', descricao='Espelho Esq')
    viga.adicionar_apoio(x_mm=280, tipo='fixo', descricao='Espelho Dir')
    
    # Carga
    viga.adicionar_carga_vertical(x_mm=200, F_N=1766, descricao='Ocupantes')
    
    # Torque: pode ser absorvido pelos espelhos (momento reativo)
    viga.adicionar_momento(x_mm=200, M_Nm=551, descricao='Frenagem')
    
    return viga


def criar_configuracao_4_cubo_longo():
    """
    Configuração 4: Cubo Longo
    - 2 rolamentos
    - Cubo longo (80 mm) atua como apoio distribuído
    - Torque é absorvido pelo atrito cubo-eixo
    """
    viga = VigaMultiApoios(L_total_mm=400, d_eixo_mm=28,
                           descricao="Config 4: Cubo Longo (Atrito)")
    
    # Apoios
    viga.adicionar_apoio(x_mm=50, tipo='rolamento', descricao='Rolamento Esq')
    viga.adicionar_apoio(x_mm=350, tipo='rolamento', descricao='Rolamento Dir')
    
    # Cubo: apoio distribuído de 160 a 240 mm (simplificado como 2 pontos)
    viga.adicionar_apoio(x_mm=170, tipo='fixo', descricao='Cubo Esq')
    viga.adicionar_apoio(x_mm=230, tipo='fixo', descricao='Cubo Dir')
    
    # Carga
    viga.adicionar_carga_vertical(x_mm=200, F_N=1766, descricao='Ocupantes')
    
    # Torque: absorvido pelo cubo (não atua diretamente no eixo)
    # Não adiciona momento ao eixo, apenas ao cubo
    
    return viga


# ============================================================================
# VISUALIZAÇÃO
# ============================================================================

def plotar_configuracao(viga, ax=None):
    """Plota esquema da viga com apoios e cargas."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(14, 6))
    
    L_mm = viga.L * 1000
    d_mm = viga.d * 1000
    
    # Eixo
    ax.plot([0, L_mm], [0, 0], 'k-', linewidth=3, label='Eixo')
    ax.add_patch(Rectangle((0, -d_mm/2), L_mm, d_mm, 
                           facecolor='lightsteelblue', edgecolor='black', linewidth=1.5))
    
    # Apoios
    cores_apoio = {'rolamento': 'darkred', 'fixo': 'darkblue'}
    for apoio in viga.apoios:
        x_mm = apoio['x'] * 1000
        cor = cores_apoio.get(apoio['tipo'], 'gray')
        ax.plot(x_mm, 0, '^', markersize=15, color=cor)
        ax.text(x_mm, -d_mm/2 - 10, apoio['descricao'], 
                ha='center', va='top', fontsize=8, rotation=45, color=cor)
        
        # Reação (se calculada)
        if 'reacao_N' in apoio:
            R = apoio['reacao_N']
            ax.text(x_mm, d_mm/2 + 10, f'R={R:.0f}N',
                   ha='center', va='bottom', fontsize=7, color=cor, fontweight='bold')
    
    # Cargas verticais
    for carga in viga.cargas_verticais:
        x_mm = carga['x'] * 1000
        F = carga['F']
        ax.arrow(x_mm, d_mm/2 + 30, 0, -25, head_width=10, head_length=5,
                fc='red', ec='red', linewidth=2)
        ax.text(x_mm, d_mm/2 + 35, f"{carga['descricao']}\n{F:.0f}N",
               ha='center', va='bottom', fontsize=9, color='red', fontweight='bold')
    
    # Momentos
    for momento in viga.momentos_aplicados:
        x_mm = momento['x'] * 1000
        M = momento['M']
        # Desenha seta circular
        circle = Circle((x_mm, 0), radius=15, fill=False, edgecolor='purple', linewidth=2)
        ax.add_patch(circle)
        ax.text(x_mm, -d_mm/2 - 35, f"T={M:.0f}N·m",
               ha='center', va='top', fontsize=8, color='purple', fontweight='bold')
    
    ax.set_xlim(-20, L_mm + 20)
    ax.set_ylim(-60, 80)
    ax.set_aspect('equal')
    ax.set_xlabel('Posição (mm)', fontsize=10)
    ax.set_title(viga.descricao, fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color='k', linewidth=0.5, alpha=0.5)
    
    return ax


def plotar_diagramas(viga, ax_V=None, ax_M=None):
    """Plota diagramas de V(x) e M(x)."""
    x, V, M = viga.calcular_diagrama_V_M()
    x_mm = x * 1000
    
    if ax_V is None or ax_M is None:
        fig, (ax_V, ax_M) = plt.subplots(2, 1, figsize=(14, 8))
    
    # Esforço cortante
    ax_V.plot(x_mm, V, 'b-', linewidth=2)
    ax_V.fill_between(x_mm, V, alpha=0.3)
    ax_V.axhline(0, color='k', linewidth=0.8, linestyle='--', alpha=0.5)
    ax_V.set_ylabel('Esforço Cortante V(x) [N]', fontsize=10, fontweight='bold')
    ax_V.set_title(viga.descricao, fontsize=11)
    ax_V.grid(True, alpha=0.3)
    V_max = np.max(np.abs(V))
    ax_V.text(0.02, 0.95, f'V_max = {V_max:.1f} N', transform=ax_V.transAxes,
             fontsize=9, va='top', bbox=dict(boxstyle='round', facecolor='wheat'))
    
    # Momento fletor
    ax_M.plot(x_mm, M, 'g-', linewidth=2)
    ax_M.fill_between(x_mm, M, alpha=0.3, color='green')
    ax_M.axhline(0, color='k', linewidth=0.8, linestyle='--', alpha=0.5)
    ax_M.set_ylabel('Momento Fletor M(x) [N·m]', fontsize=10, fontweight='bold')
    ax_M.set_xlabel('Posição (mm)', fontsize=10)
    ax_M.grid(True, alpha=0.3)
    M_max = np.max(np.abs(M))
    sigma_max = viga.tensao_maxima_flexao() / 1e6
    ax_M.text(0.02, 0.95, f'M_max = {M_max:.2f} N·m\nσ_max = {sigma_max:.1f} MPa',
             transform=ax_M.transAxes, fontsize=9, va='top',
             bbox=dict(boxstyle='round', facecolor='lightgreen'))
    
    return ax_V, ax_M


# ============================================================================
# ANÁLISE COMPARATIVA
# ============================================================================

def analisar_todas_configuracoes():
    """Compara todas as configurações."""
    
    configs = [
        criar_configuracao_1_dois_rolamentos(),
        criar_configuracao_2_rolamentos_mais_limitador(),
        criar_configuracao_3_espelhos_balanca(),
        criar_configuracao_4_cubo_longo(),
    ]
    
    resultados = []
    
    print("\n" + "="*70)
    print("  ANÁLISE COMPARATIVA: DIVISÃO DE ESFORÇOS")
    print("="*70)
    
    for i, viga in enumerate(configs, 1):
        print(f"\n[{i}] {viga.descricao}")
        print("-" * 70)
        
        # Calcular reações
        try:
            reacoes = viga.calcular_reacoes()
            
            print(f"Apoios ({len(viga.apoios)}):")
            for j, apoio in enumerate(viga.apoios):
                R = apoio.get('reacao_N', 0)
                print(f"  {apoio['descricao']:20s}: x={apoio['x']*1000:5.0f} mm | R={R:6.0f} N")
            
            # Tensões
            sigma_flex = viga.tensao_maxima_flexao() / 1e6
            tau_torc = viga.tensao_maxima_torcao() / 1e6
            sigma_vm = np.sqrt(sigma_flex**2 + 3 * tau_torc**2)
            
            print(f"\nTensões:")
            print(f"  Flexão:     {sigma_flex:6.1f} MPa")
            print(f"  Torção:     {tau_torc:6.1f} MPa")
            print(f"  Von Mises:  {sigma_vm:6.1f} MPa")
            
            # Fator de segurança
            Sy = 310  # MPa (AISI 1045)
            FS = Sy / sigma_vm if sigma_vm > 0 else np.inf
            adequado = FS >= 2.0
            
            print(f"\nFator de Segurança:")
            print(f"  FS = {FS:.2f}  {'✓ ADEQUADO' if adequado else '✗ INSUFICIENTE'}")
            
            resultados.append({
                'config': i,
                'descricao': viga.descricao.replace("Config ", "").replace(": ", "\n"),
                'n_apoios': len(viga.apoios),
                'sigma_flexao_MPa': sigma_flex,
                'tau_torcao_MPa': tau_torc,
                'sigma_VM_MPa': sigma_vm,
                'FS': FS,
                'adequado': adequado
            })
            
        except Exception as e:
            print(f"  ERRO: {str(e)}")
            resultados.append({
                'config': i,
                'descricao': viga.descricao,
                'n_apoios': len(viga.apoios),
                'sigma_flexao_MPa': np.nan,
                'tau_torcao_MPa': np.nan,
                'sigma_VM_MPa': np.nan,
                'FS': np.nan,
                'adequado': False
            })
    
    # Tabela resumo
    print("\n" + "="*70)
    print("  RESUMO COMPARATIVO")
    print("="*70 + "\n")
    
    df = pd.DataFrame(resultados)
    print(df.to_string(index=False))
    
    return configs, df


def plotar_comparacao_completa(configs, df):
    """Gera visualização completa de todas as configurações."""
    
    n_configs = len(configs)
    fig = plt.figure(figsize=(18, 12))
    
    # Grid: 3 colunas (esquema, V(x), M(x)) x N linhas (configs)
    for i, viga in enumerate(configs):
        # Esquema
        ax_esquema = plt.subplot(n_configs, 3, 3*i + 1)
        plotar_configuracao(viga, ax=ax_esquema)
        
        # Diagramas V e M
        ax_V = plt.subplot(n_configs, 3, 3*i + 2)
        ax_M = plt.subplot(n_configs, 3, 3*i + 3)
        
        try:
            plotar_diagramas(viga, ax_V=ax_V, ax_M=ax_M)
        except:
            ax_V.text(0.5, 0.5, 'Erro no cálculo', ha='center', va='center', transform=ax_V.transAxes)
            ax_M.text(0.5, 0.5, 'Erro no cálculo', ha='center', va='center', transform=ax_M.transAxes)
    
    plt.tight_layout()
    plt.savefig('comparacao_configuracoes_balanca.png', dpi=300, bbox_inches='tight')
    print("\n→ Gráfico salvo: comparacao_configuracoes_balanca.png")
    
    # Gráfico de barras comparativo
    fig2, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Tensões
    ax = axes[0]
    x = df['config'].values
    width = 0.25
    ax.bar(x - width, df['sigma_flexao_MPa'], width, label='Flexão', alpha=0.7)
    ax.bar(x, df['tau_torcao_MPa'], width, label='Torção', alpha=0.7)
    ax.bar(x + width, df['sigma_VM_MPa'], width, label='Von Mises', alpha=0.7)
    ax.axhline(310, color='r', linestyle='--', label='Sy = 310 MPa')
    ax.set_xlabel('Configuração')
    ax.set_ylabel('Tensão (MPa)')
    ax.set_title('Comparação de Tensões')
    ax.set_xticks(x)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # FS
    ax = axes[1]
    cores = ['red' if not adeq else 'green' for adeq in df['adequado']]
    ax.bar(x, df['FS'], color=cores, alpha=0.7)
    ax.axhline(2.0, color='g', linestyle='--', label='FS mínimo = 2.0')
    ax.set_xlabel('Configuração')
    ax.set_ylabel('Fator de Segurança')
    ax.set_title('Fator de Segurança ao Escoamento')
    ax.set_xticks(x)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('comparacao_FS_configuracoes.png', dpi=300, bbox_inches='tight')
    print("→ Gráfico salvo: comparacao_FS_configuracoes.png")


# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  TESTE: DIVISÃO DE ESFORÇOS — EIXO TRASEIRO COM BALANÇA")
    print("="*70)
    print("\nObjetivo:")
    print("  Testar diferentes configurações de apoios da balança no eixo")
    print("  para identificar como o torque de frenagem é transmitido.\n")
    
    # Análise comparativa
    configs, df = analisar_todas_configuracoes()
    
    # Visualização
    plotar_comparacao_completa(configs, df)
    
    # Salvar resultados
    df.to_csv('divisao_esforcos_balanca.csv', index=False)
    print("→ Dados salvos: divisao_esforcos_balanca.csv")
    
    # Recomendação
    print("\n" + "="*70)
    print("  RECOMENDAÇÃO")
    print("="*70 + "\n")
    
    config_adequadas = df[df['adequado'] == True]
    
    if not config_adequadas.empty:
        melhor = config_adequadas.loc[config_adequadas['FS'].idxmax()]
        print(f"✓ Configuração {int(melhor['config'])} é a MAIS ADEQUADA:")
        print(f"  {melhor['descricao']}")
        print(f"  FS = {melhor['FS']:.2f}")
        print(f"  σ_VM = {melhor['sigma_VM_MPa']:.1f} MPa")
    else:
        print("✗ NENHUMA configuração testada atende FS ≥ 2.0 com Ø28 mm.")
        print("\nOpções:")
        print("  1. Aumentar diâmetro (Ø30 mm, rolamento 6206)")
        print("  2. Tratar termicamente AISI 1045 (Sy → 450 MPa)")
        print("  3. Reduzir vão entre apoios (medir valor real!)")
    
    print("\n⚠️  PRÓXIMO PASSO:")
    print("  → Medir fisicamente onde a balança se apoia no eixo")
    print("  → Identificar se há espelhos, limitador, ou apenas rolamentos")
    print("  → Recalcular com geometria real\n")
