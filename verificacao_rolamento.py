"""Exigências de verificação do rolamento do cubo: carga radial e axial combinadas, capacidade estática e vida.

Não escolhe rolamento. Calcula o que o catálogo do rolamento precisa atender, para cada espaçamento entre
apoios. Os coeficientes X, Y, X0, Y0 e o expoente de vida são de REFERÊNCIA e devem ser trocados pelos do
fabricante; a vida-alvo, a rotação média e o fator estático S0 são decisões de projeto a confirmar.

Convenção: eixo dos rolamentos em y; contato no plano médio da roda; força lateral Fy axial no cubo; momento
Fy·R no plano x–z resistido por um par vertical nos apoios. Cada apoio recebe Fr = hypot(Fx/2, Fz/2 ± Fy·R/d);
a força axial Fy é atribuída inteira a um apoio por vez (envelope).

Uso:
    python verificacao_rolamento.py
    python verificacao_rolamento.py --espacamentos 200 300
"""
import argparse
import json
import math

from ensaio import Balanca, cargas_nas_rodas, referencia_veiculo
from modelo_estrutural import GRAVIDADE

# Raio sob carga da roda 80/100-14 nominal (257,8 mm); o raio carregado precisa ser medido.
RAIO_CUBO_M = (14 * 25.4 + 2 * 80) / 2000
# REFERÊNCIA (a trocar pelos coeficientes do fabricante do rolamento escolhido).
X_DIN, Y_DIN = 0.56, 1.5          # carga dinâmica equivalente P = X·Fr + Y·Fa
X_EST, Y_EST = 0.6, 0.5           # carga estática equivalente P0 = X0·Fr + Y0·Fa
EXPOENTE_VIDA = 3.0               # esferas (3); rolos cônicos usam 10/3
LIMITE_AXIAL_E = 0.3              # referência: Fa/Fr acima deste valor usa Y (rolamento de referência)
# DECISÕES DE PROJETO A CONFIRMAR
VIDA_ALVO_H = 2000.0              # horas de operação
VELOCIDADE_MEDIA_KMH = 25.0       # média do ciclo de uso
S0_OPCOES = (1.0, 1.5, 2.0)       # fator de segurança estático sobre o pico de impacto
ESPACAMENTOS_MM = (200.0, 250.0, 300.0, 350.0, 400.0)
LATERAIS_G = (0.0, 0.4, 0.6, 0.8, 0.9)
FRENAGENS_G = (0.0, 0.4)
IMPACTOS = (1.0, 2.0)             # impacto 2× só entra na verificação estática


def rotacao_media_rpm(v_kmh=VELOCIDADE_MEDIA_KMH):
    """Rotação média do cubo (rpm) para a velocidade média do ciclo e o raio carregado."""
    return 60.0 * (v_kmh / 3.6) / (2 * math.pi * RAIO_CUBO_M)


def carga_equivalente(Fr, Fa):
    """Carga dinâmica e estática equivalentes (N). Sem carga axial relevante, P = Fr; P0 nunca abaixo de Fr."""
    if Fa <= LIMITE_AXIAL_E * Fr:
        P = Fr
    else:
        P = max(Fr, X_DIN * Fr + Y_DIN * Fa)
    P0 = max(Fr, X_EST * Fr + Y_EST * Fa)
    return P, P0


def cargas_apoios(lateral, freio, impacto, espacamento_mm, b, h, ref):
    """Registros (Fr, Fa, P, P0) de cada apoio para cada atribuição da força axial. Só casos com três contatos."""
    d = espacamento_mm / 1000.0
    registros = []
    for lado, c in cargas_nas_rodas(lateral, freio, impacto, b, h, ref).items():
        if not (c['tres_contatos'] and not c['pneu_satura'] and not c['excede_aderencia_global']):
            continue
        par = c['Fy_N'] * RAIO_CUBO_M / d
        Fa_total = abs(c['Fy_N'])
        for apoio, sinal in ((1, 1.0), (2, -1.0)):
            Fr = math.hypot(c['Fx_N'] / 2, c['Fz_N'] / 2 + sinal * par)
            for recebe_axial in (1, 2):
                Fa = Fa_total if recebe_axial == apoio else 0.0
                P, P0 = carga_equivalente(Fr, Fa)
                registros.append({'roda': lado, 'lateral_g': lateral, 'freio_g': freio, 'impacto': impacto,
                                  'apoio': apoio, 'axial_no_apoio': recebe_axial,
                                  'Fr_N': Fr, 'Fa_N': Fa, 'P_N': P, 'P0_N': P0})
    return registros


def requisitos(espacamento_mm, base_b=None):
    """Exigências para o rolamento com o espaçamento dado: estática (pico) e vida (curva normal)."""
    if not math.isfinite(espacamento_mm) or espacamento_mm <= 0:
        raise ValueError('Espaçamento deve ser positivo e finito')
    h, ref = referencia_veiculo()
    b = base_b or Balanca()
    estatico, dinamico = [], []
    pior = None
    for lateral in LATERAIS_G:
        for freio in FRENAGENS_G:
            for impacto in IMPACTOS:
                for r in cargas_apoios(lateral, freio, impacto, espacamento_mm, b, h, ref):
                    estatico.append(r['P0_N'])
                    if impacto == 1.0:
                        dinamico.append(r['P_N'])
                        if pior is None or r['P_N'] > pior['P_N']:
                            pior = r
    if not estatico or not dinamico:
        raise ValueError('Nenhum caso com três contatos para este espaçamento')
    P0_max = max(estatico)
    P_medio = (sum(p ** EXPOENTE_VIDA for p in dinamico) / len(dinamico)) ** (1 / EXPOENTE_VIDA)
    n = rotacao_media_rpm()
    C_vida = P_medio * (VIDA_ALVO_H * 60.0 * n / 1e6) ** (1 / EXPOENTE_VIDA)
    C0 = {f'S0={s0:g}': s0 * P0_max for s0 in S0_OPCOES}
    return {
        'espacamento_mm': espacamento_mm,
        'P0_pico_impacto_N': P0_max,
        'P0_pico_impacto_kgf': P0_max / GRAVIDADE,
        'C0_minimo_N': C0,
        'C0_minimo_kgf': {k: v / GRAVIDADE for k, v in C0.items()},
        'P_dinamico_medio_N': P_medio,
        'P_dinamico_pior_curva_normal_N': pior['P_N'] if pior else None,
        'rotacao_media_rpm': n,
        'vida_alvo_h': VIDA_ALVO_H,
        'C_minimo_vida_N': C_vida,
        'C_minimo_vida_kgf': C_vida / GRAVIDADE,
        'coeficientes_referencia': {'X_din': X_DIN, 'Y_din': Y_DIN, 'X0': X_EST, 'Y0': Y_EST, 'p': EXPOENTE_VIDA, 'e': LIMITE_AXIAL_E},
        'nota': ('Coeficientes e vida-alvo são de referência: substituir pelos do catálogo e pela decisão de projeto. '
                 'A força axial entra inteira num apoio por vez (envelope). Impacto 2× só na verificação estática.'),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--espacamentos', type=float, nargs='+', default=list(ESPACAMENTOS_MM),
                   help='Espaçamentos entre rolamentos em mm')
    args = p.parse_args(argv)
    try:
        dados = [requisitos(e) for e in args.espacamentos]
    except ValueError as exc:
        p.error(str(exc))
    # ASCII é um subconjunto de UTF-8 e evita depender da página de código
    # do console Windows quando a saída JSON é capturada por outro processo.
    print(json.dumps(dados, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
