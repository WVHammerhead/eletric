"""Berço elevado da bateria dentro da cunha (D-10); anteprojeto, não libera fabricação.

Bateria Felicity FLA24100-EU deitada (345 × 430 × 195 mm, 26 kg) sob o capô,
acima das cabeças no modo leito. Quatro pernas de aço sobem das longarinas
80 × 80 × 3 nos vãos entre as barras 1–2 e 2–3 do piso; duas diagonais laterais
levam a carga longitudinal. Acelerações de cálculo são hipóteses quase-estáticas
a substituir pelo requisito aplicável à categoria. Coordenadas em metros.
"""
import argparse
import math

from modelo_estrutural import (
    GRAVIDADE, LONGARINA, PISO, Perfil, X_FRENTE_TRAP, barras_piso, largura_quadro,
)
from relatorio_visual import adicionar_saida, configurar_console, emitir

BATERIA = {'modelo': 'Felicity FLA24100-EU', 'massa_kg': 26.0,
           'comprimento_x_m': .345, 'largura_y_m': .430, 'altura_z_m': .195}
FOLGA_FACE = .020          # da face (plano dos faróis) à frente da bateria: lona, borracha e batente
BASE_BATERIA_Z = .590      # cabeças no leito: ≈ 270 mm livres sobre o piso até o berço
NEOPRENE = .003
ACO_KG_M3 = 7850

PERNA = Perfil('30 × 30 × 2', 'aço', 30, 30, 2)
DIAGONAL = Perfil('Ø 22,2 × 2', 'aço', 22.2, 22.2, 2, True)
BUCHA = Perfil('Ø 14 × 2', 'aço', 14, 14, 2, True)
CANTONEIRA = (30, 3)       # L 30 × 30 × 3: cesto e travessas do berço
CINTA = (25, 3)            # barra chata das duas cintas
CHAPA_BASE = (.040, .080, .00475)   # cabe no vão de ≈ 50 mm entre barras do piso

# Parafusos métricos classe 8.8: área resistente (mm²) e tensão de prova 600 MPa.
AREA_RESISTENTE = {'M8': 36.6, 'M10': 58.0}
PROVA_8_8 = 600.0
PARAFUSOS_POR_PE = 2

ACELERACOES_G = {'longitudinal': 20.0, 'lateral': 8.0, 'vertical': 8.0}


def kg_m_cantoneira(aba, espessura):
    return (2*aba - espessura)*espessura*ACO_KG_M3/1e6


def geometria(piso=.285):
    """Posições derivadas do piso comum, para acompanhar mudanças nas barras."""
    if not math.isfinite(piso) or piso <= 0:
        raise ValueError('Altura do piso deve ser positiva e finita')
    barras = barras_piso()
    vaos = [(a['x_mm'] + PISO.largura + b['x_mm'])/2000 for a, b in zip(barras, barras[1:])]
    x_pes = vaos[:2]                                   # entre as barras 1–2 e 2–3
    y_pes = [largura_quadro(x*1000)/2000 - LONGARINA.largura/2000 for x in x_pes]
    z_apoio = piso - PISO.altura/1000                  # face superior das longarinas
    x0 = X_FRENTE_TRAP/1000 + FOLGA_FACE
    base = BASE_BATERIA_Z
    z_berco = base - NEOPRENE - CANTONEIRA[1]/1000 - CANTONEIRA[0]/1000   # fundo das travessas
    if piso >= z_berco:
        raise ValueError('Piso intercepta o berço; rever alturas e espaço para ocupantes')
    return {'x_bateria_m': (x0, x0 + BATERIA['comprimento_x_m']),
            'z_bateria_m': (base, base + BATERIA['altura_z_m']),
            'cg_bateria_m': (x0 + BATERIA['comprimento_x_m']/2, base + BATERIA['altura_z_m']/2),
            'x_pes_m': x_pes, 'y_pes_m': y_pes, 'z_apoio_m': z_apoio, 'z_fundo_berco_m': z_berco,
            'altura_perna_m': z_berco - z_apoio,
            'altura_livre_sobre_piso_m': z_berco - piso,
            'folga_entre_barras_m': (barras[1]['x_mm'] - barras[0]['x_mm'] - PISO.largura)/1000}


def pecas(g):
    """Massa de cada grupo do berço, com o centro de massa aproximado."""
    x0, x1 = g['x_bateria_m']
    z_cesto = g['z_bateria_m'][0] - NEOPRENE
    cant = kg_m_cantoneira(*CANTONEIRA)
    perimetro = 2*(BATERIA['comprimento_x_m'] + BATERIA['largura_y_m'] + .02)
    travessas = 2*sum(g['y_pes_m'])
    pernas = 4*g['altura_perna_m']
    dx = g['x_pes_m'][1] - x0
    diag = math.hypot(dx, g['altura_perna_m'])
    cinta = BATERIA['largura_y_m'] + 2*BATERIA['altura_z_m'] + .05
    chapa = CHAPA_BASE[0]*CHAPA_BASE[1]*CHAPA_BASE[2]*ACO_KG_M3
    xm = (x0 + x1)/2
    lista = [
        ('cesto em cantoneira 30 × 30 × 3', perimetro*cant, xm, z_cesto),
        ('duas travessas do berço em cantoneira 30 × 30 × 3', travessas*cant, sum(g['x_pes_m'])/2, g['z_fundo_berco_m'] + .015),
        ('quatro pernas 30 × 30 × 2', pernas*PERNA.kg_m, sum(g['x_pes_m'])/2, g['z_apoio_m'] + g['altura_perna_m']/2),
        ('duas diagonais Ø 22,2 × 2', 2*diag*DIAGONAL.kg_m, (x0 + g['x_pes_m'][1])/2, g['z_apoio_m'] + g['altura_perna_m']/2),
        ('duas cintas 25 × 3 e dois batentes dianteiros', 2*cinta*CINTA[0]*CINTA[1]*ACO_KG_M3/1e6 + .36, xm, z_cesto + .1),
        ('quatro chapas de base e quatro contraplacas 4,75 mm', 8*chapa, sum(g['x_pes_m'])/2, g['z_apoio_m'] - .04),
        ('8 × M10 8.8, 8 buchas Ø 14 × 2 e 4 tirantes M8 8.8', 8*.08 + 8*.08*BUCHA.kg_m + 4*.12, sum(g['x_pes_m'])/2, g['z_apoio_m']),
    ]
    return [{'peca': n, 'massa_kg': m, 'x_m': x, 'z_m': z} for n, m, x, z in lista]


def massa_berco(piso=.285):
    """Massa, x e z do berço, para o inventário (estado 'modelo')."""
    lista = pecas(geometria(piso))
    m = sum(p['massa_kg'] for p in lista)
    return m, sum(p['massa_kg']*p['x_m'] for p in lista)/m, sum(p['massa_kg']*p['z_m'] for p in lista)/m


def parafuso(tracao, corte, bitola):
    area = AREA_RESISTENTE[bitola]
    sigma, tau = tracao/area, corte/area
    eq = math.hypot(sigma, math.sqrt(3)*tau)
    return {'tracao_N': tracao, 'corte_N': corte, 'tensao_equivalente_MPa': eq,
            'uso_da_prova_pct': 100*eq/PROVA_8_8}


def calcular(piso=.285, aceleracoes=None):
    if aceleracoes and set(aceleracoes)-set(ACELERACOES_G):
        raise ValueError('Direção de aceleração desconhecida')
    a = dict(ACELERACOES_G, **(aceleracoes or {}))
    if not all(math.isfinite(v) and v > 0 for v in a.values()):
        raise ValueError('Acelerações devem ser positivas e finitas')
    g = geometria(piso)
    if g['folga_entre_barras_m'] < CHAPA_BASE[0]:
        raise ValueError('Chapa de base não cabe no vão entre as barras do piso')
    lista = pecas(g)
    massas = [(BATERIA['massa_kg'], g['cg_bateria_m'][1])] + [
        (p['massa_kg'], p['z_m']) for p in lista if p['z_m'] > g['z_apoio_m']]
    M = sum(m for m, _ in massas)
    momento_por_g = sum(m*GRAVIDADE*(z - g['z_apoio_m']) for m, z in massas)
    s = g['x_pes_m'][1] - g['x_pes_m'][0]
    b = sum(g['y_pes_m'])
    casos = {}
    for direcao, braco in (('longitudinal', s), ('lateral', b)):
        F = M*GRAVIDADE*a[direcao]
        T = momento_por_g*a[direcao]/braco/2 - M*GRAVIDADE/4   # arrancamento por pé, descontado o peso
        V = F/4
        casos[direcao] = {'forca_total_N': F, 'arrancamento_por_pe_N': T, 'corte_por_pe_N': V,
                          'parafuso_M10': parafuso(max(T, 0)/PARAFUSOS_POR_PE, V/PARAFUSOS_POR_PE, 'M10')}
    # Lateral: pórticos sem diagonal transversal (o leito passa sob o berço).
    V = casos['lateral']['corte_por_pe_N']
    flexao = V*g['altura_perna_m']/2*1000/(PERNA.inercia_mm4/(PERNA.altura/2))
    # Longitudinal: diagonal tracionada leva a força para o pé traseiro.
    dx = g['x_pes_m'][1] - g['x_bateria_m'][0]
    angulo = math.atan2(g['altura_perna_m'], dx)
    tracao_diag = casos['longitudinal']['forca_total_N']/2/math.cos(angulo)
    compressao_perna = M*GRAVIDADE*a['vertical']/4
    L = g['altura_perna_m']*1000
    euler = math.pi**2*210000*PERNA.inercia_mm4/(L**2)          # biarticulada, conservador
    # Cintas: vertical para cima e tombamento sobre o batente dianteiro.
    cima = BATERIA['massa_kg']*GRAVIDADE*(a['vertical'] - 1)/4
    giro = (BATERIA['massa_kg']*GRAVIDADE*a['longitudinal']*(BATERIA['altura_z_m']/2 - .04)
            / BATERIA['comprimento_x_m']/2)
    return {
        'aviso': ('Anteprojeto quase-estático: acelerações hipotéticas, aço S235/S275 presumido, '
                  'sem fadiga, sem verificação local da parede da longarina nem das soldas. Não libera fabricação.'),
        'bateria': BATERIA, 'aceleracoes_g': a, 'geometria': g, 'pecas': lista,
        'massa_berco_kg': sum(p['massa_kg'] for p in lista), 'massa_suspensa_nos_pes_kg': M,
        'pes': {'espacamento_longitudinal_m': s, 'espacamento_transversal_m': b, 'parafusos_por_pe': PARAFUSOS_POR_PE},
        'casos': casos,
        'pernas': {'perfil': PERNA.nome, 'tensao_flexao_lateral_MPa': flexao,
                   'compressao_vertical_N': compressao_perna, 'carga_critica_euler_N': euler},
        'diagonais': {'perfil': DIAGONAL.nome, 'tracao_N': tracao_diag,
                      'tensao_MPa': tracao_diag/DIAGONAL.area_mm2, 'angulo_graus': math.degrees(angulo)},
        'tirantes_M8_das_cintas': {'vertical_para_cima': parafuso(cima, 0, 'M8'),
                                   'tombamento_sobre_batente': parafuso(giro, 0, 'M8')},
        'especificacao': [
            'Cesto em cantoneira de aço 30 × 30 × 3 com abas para cima, 5 mm de folga e neoprene de 3 mm em todo o contorno.',
            'Dois batentes dianteiros em chapa 4,75 mm, 80 mm de altura, contra a face de 430 × 195 mm da bateria.',
            'Duas cintas transversais em barra chata 25 × 3 sobre a bateria, com 4 tirantes M8 classe 8.8 em orelhas de chapa 4,75 soldadas ao cesto; porcas autotravantes.',
            'Quatro pernas em tubo 30 × 30 × 2 nos vãos entre as barras 1–2 e 2–3 do piso, soldadas às travessas do berço.',
            'Duas diagonais Ø 22,2 × 2, uma por lado, do pé traseiro ao canto dianteiro do cesto, tracionadas no impacto frontal.',
            'Cada pé: chapa de base 40 × 80 × 4,75 soldada à perna, contraplaca igual sob a longarina e 2 parafusos M10 classe 8.8 atravessando a longarina com bucha anti-esmagamento Ø 14 × 2 soldada por dentro; porcas autotravantes e torque pela tabela do fornecedor.',
            'Ligações aço-aço soldadas; nenhuma carga da bateria nas barras de alumínio do piso, na lona ou no capô.',
            'Caixa estanque leve (nível 4) em volta da bateria com respiro em labirinto e dreno; a face da cunha continua sem grade.',
            'Corta-corrente e fusível junto ao terminal; cabos curtos até os controladores perto dos motores.',
        ],
        'pendencias': [
            'Confirmar com a Felicity o uso deitada, a vibração admitida e a posição dos terminais.',
            'Confirmar a altura livre de ≈ 270 mm para as cabeças no leito com colchão e travesseiro reais.',
            'Compatibilizar com coluna de direção, guidão, mãos e joelhos do piloto (bateria até x ≈ 0,81 m).',
            'Substituir as acelerações hipotéticas pelo requisito de retenção aplicável e verificar a parede da longarina.',
        ],
    }


# --- Configuração 'dorsal' (D-10 Revisada, em avaliação): bateria atrás do encosto do passageiro ---
ENCOSTO_ESPESSURA_M = .04    # hipótese: estofado + chapa do encosto
FOLGA_NORMAL_M = .01         # hipótese: folga entre o encosto e a bateria
COLCHAO_M = .03              # hipótese
ORIENTACOES = {'A': (.430, .345), 'B': (.345, .430)}   # (dimensão ao longo do encosto, dimensão em Y)
# Espessura vertical de cada trecho do corpo deitado, hipótese a confirmar (m): coxa, perna, pé.
ESPESSURA_DEITADO_M = {'coxa': .20, 'perna': .14, 'pe': .12}


def geometria_dorsal(quadril_passageiro, theta_graus, s0_m, orientacao='A', espessura_tronco_m=.11):
    """Caixa da bateria encostada atrás do encosto, no plano x–z (x cresce para trás).

    `quadril_passageiro` = (x, z) do quadril; `s0_m` = distância, ao longo do encosto, do quadril à aresta
    inferior da bateria. Devolve centro, cantos do retângulo (x, z), extremos e dimensão em Y.
    """
    if orientacao not in ORIENTACOES:
        raise ValueError('Orientação deve ser A (Y = 345 mm) ou B (Y = 430 mm)')
    if not 0 <= theta_graus < 80 or not math.isfinite(s0_m):
        raise ValueError('Ângulo do encosto em [0, 80)° e s0 finito são obrigatórios')
    th = math.radians(theta_graus)
    u, n = (math.sin(th), math.cos(th)), (math.cos(th), -math.sin(th))
    lu, ly = ORIENTACOES[orientacao]
    t = BATERIA['altura_z_m']                 # 195 mm: perpendicular ao encosto
    d0 = espessura_tronco_m + ENCOSTO_ESPESSURA_M + FOLGA_NORMAL_M
    centro = (quadril_passageiro[0] + (s0_m + lu/2)*u[0] + (d0 + t/2)*n[0],
              quadril_passageiro[1] + (s0_m + lu/2)*u[1] + (d0 + t/2)*n[1])
    cantos = [(centro[0] + a*lu/2*u[0] + b*t/2*n[0], centro[1] + a*lu/2*u[1] + b*t/2*n[1])
              for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    xs, zs = [c[0] for c in cantos], [c[1] for c in cantos]
    return {'centro_m': centro, 'cantos_m': cantos, 'x_m': (min(xs), max(xs)), 'z_m': (min(zs), max(zs)),
            'y_dimensao_m': ly, 'ao_longo_encosto_m': lu, 'espessura_m': t, 'distancia_normal_ao_eixo_m': d0,
            'u': u, 'n': n}


def z_inferior(cantos, x):
    """Cota z da face inferior do retângulo no abscissa x (None fora do polígono)."""
    zs = []
    for (x0, z0), (x1, z1) in zip(cantos, cantos[1:] + cantos[:1]):
        if x0 == x1:
            if abs(x - x0) < 1e-12:
                zs += [z0, z1]
        elif min(x0, x1) <= x <= max(x0, x1):
            zs.append(z0 + (z1 - z0)*(x - x0)/(x1 - x0))
    return min(zs) if zs else None


def folga_leito(cantos, superficie_m, x_frente_leito_m, altura_pessoa=1.75, passos=60):
    """Menor folga (m) entre a face inferior da bateria e o corpo deitado (cabeças em x_frente_leito_m).

    Trechos (coxa, perna, pé) pelas proporções de estabilidade_massas; espessuras em ESPESSURA_DEITADO_M.
    Devolve (folga mínima, x onde ocorre); +inf se a bateria não se sobrepõe ao corpo em x.
    """
    quadril = x_frente_leito_m + .47*altura_pessoa
    joelho = quadril + .245*altura_pessoa
    tornozelo = joelho + .246*altura_pessoa
    trechos = ((quadril, joelho, 'coxa'), (joelho, tornozelo, 'perna'), (tornozelo, x_frente_leito_m + altura_pessoa, 'pe'))
    x0, x1 = min(c[0] for c in cantos), max(c[0] for c in cantos)
    pior, onde = math.inf, None
    for i in range(passos + 1):
        x = x0 + (x1 - x0)*i/passos
        zb = z_inferior(cantos, x)
        for a, b, nome in trechos:
            if zb is not None and a <= x <= b:
                f = zb - superficie_m - ESPESSURA_DEITADO_M[nome]
                if f < pior:
                    pior, onde = f, x
    return pior, onde


def berco_dorsal(g, z_apoio_m, x_pes_m, y_pes_m):
    """Peças e massa do berço dorsal pelo mesmo gabarito do berço da cunha (inclinação ignorada).

    ESTIMATIVA de anteprojeto: a inclinação do cesto não é modelada nem verificada em resistência.
    """
    x0, x1 = g['x_m']
    base = g['z_m'][0]
    z_berco = base - NEOPRENE - CANTONEIRA[1]/1000 - CANTONEIRA[0]/1000
    if z_apoio_m >= z_berco:
        raise ValueError('Apoio nas longarinas acima do fundo do berço dorsal')
    gd = {'x_bateria_m': (x0, x1), 'z_bateria_m': (base, g['z_m'][1]), 'z_apoio_m': z_apoio_m,
          'z_fundo_berco_m': z_berco, 'altura_perna_m': z_berco - z_apoio_m,
          'x_pes_m': list(x_pes_m), 'y_pes_m': list(y_pes_m)}
    lista = pecas(gd)
    m = sum(p['massa_kg'] for p in lista)
    return {'massa_kg': m, 'x_m': sum(p['massa_kg']*p['x_m'] for p in lista)/m,
            'z_m': sum(p['massa_kg']*p['z_m'] for p in lista)/m, 'altura_perna_m': gd['altura_perna_m'], 'pecas': lista}


def main(argv=None):
    configurar_console()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--piso', type=float, default=.285, help='Face superior do piso em m')
    for nome, valor in ACELERACOES_G.items():
        p.add_argument('--a-' + nome, type=float, default=valor, help=f'Aceleração {nome} em g (hipótese)')
    adicionar_saida(p)
    args = p.parse_args(argv)
    try:
        emitir(calcular(args.piso, {k: getattr(args, 'a_' + k) for k in ACELERACOES_G}),
               'Berço da bateria na cunha', args.html)
    except (ValueError, OSError) as exc:
        p.error(str(exc))


if __name__ == '__main__':
    main()
