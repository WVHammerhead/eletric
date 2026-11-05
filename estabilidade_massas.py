"""Centro de gravidade e estabilidade estática por configuração; anteprojeto.

Lê inventario_estimado.csv (ou outro CSV com as mesmas colunas), acrescenta as
duas pessoas pelo modelo de postura e varre a distância guidão → quadril do
piloto. Pesagens das três rodas substituem estimativas quando informadas.
Coordenadas em metros: x desde a frente, y positivo à direita, z desde o solo.
Não aprova pneus, estrutura, frenagem nem velocidade em curva.

Uso:
    python estabilidade_massas.py
    python estabilidade_massas.py --pesagem sentado=96,98,151 --html relatorio.html
    python estabilidade_massas.py --exportar-csv inventario.csv
"""
import argparse
import csv
import math
from dataclasses import dataclass, replace, asdict
from functools import lru_cache
from pathlib import Path

from modelo_estrutural import (
    X_EIXO_DIANT, X_EIXO_TRAS, X_FRENTE_TRAP, FOLGA_RODA, BITOLA, ASSENTO, PNEU_DIANT,
    PNEU_TRAS, LONGARINA, PISO, TETO, EVA_PISO_MM, ALTURA_SENTADO, diametro, geometria, barras_piso, massas_parciais,
)
from relatorio_visual import adicionar_saida, configurar_console, emitir
from suporte_bateria import massa_berco
from revisar_calculos import calcular_reacoes

RAIZ = Path(__file__).parent
INVENTARIO_PADRAO = RAIZ / 'inventario_estimado.csv'
COLUNAS = ('cenario', 'componente', 'massa_kg', 'x_m', 'y_m', 'z_m', 'estado', 'fonte')
# informado: massa de fornecedor ou referência, ainda não pesada neste veículo.
ESTADOS = ('medido', 'informado', 'estimado', 'modelo', 'pendente', 'ausente')
CENARIOS = ('sentado', 'leito')
POSTURAS = ('reclinada', 'ereta_legada')
THETAS_VARREDURA = (35., 40., 45., 48.)
# Modelo segmentar (hipótese): fração da massa e do comprimento em relação à estatura H, no estilo
# Winter/Dempster. Coeficientes lembrados de referência geral: A CONFIRMAR com a tabela original.
FRACAO_MASSA = {'cabeca_pescoco': .081, 'tronco': .497, 'bracos': .100, 'coxas': .200, 'pernas': .093, 'pes': .029}
COMPRIMENTO_TRONCO, COMPRIMENTO_CABECA, COMPRIMENTO_COXA, COMPRIMENTO_PERNA, ALTURA_TORNOZELO = (
    .288, .182, .245, .246, .039)       # × estatura
CENTRO_TRONCO, CENTRO_CABECA, CENTRO_COXA, CENTRO_PERNA = .5, .5, .433, .433   # fração do segmento
PE_AVANCO_M, PE_ABAIXO_M = .08, .03     # centro do pé em relação ao tornozelo (hipótese)
X_MAOS_PILOTO, Z_MAOS_PILOTO = .745, .90   # guidão nominal
AVISO = ('Estimativa de anteprojeto: massas não medidas, corpo rígido, piso plano e '
         'apoios nos centros das rodas. Limiares não são velocidade segura nem aprovação.')


@dataclass(frozen=True)
class Hipoteses:
    """Valores ilustrativos; cada um pode ser alterado pela linha de comando."""
    massa_pessoa: float = 65.0
    altura_pessoa: float = 1.75
    x_guidao: float = .745   # posição nominal do guidão, independente do deslocamento do eixo traseiro
    distancias_piloto: tuple = (.40, .45, .50, .55, .60)
    distancia_nominal: float = .60
    abraco: float = .30              # quadril do passageiro atrás do quadril do piloto
    piso: float = .285               # face superior, janela D-4 de 280–290 mm
    assento: float = ASSENTO / 1000  # fonte comum (modelo_estrutural.ASSENTO)
    cg_sentado: float = .22          # SÓ postura 'ereta_legada': CG acima do assento
    avanco_sentado: float = .07      # SÓ postura 'ereta_legada': CG à frente do quadril
    # --- Postura muito reclinada (requisito fixo). Todos os valores abaixo são HIPÓTESES. ---
    postura: str = 'reclinada'       # 'ereta_legada' reproduz os parâmetros anteriores
    theta_encosto_graus: float = 40.   # tronco em relação à vertical, para trás; varredura 35–48°
    angulo_coxa_graus: float = 5.      # coxa acima da horizontal, apontando à frente
    angulo_cabeca_graus: float = 20.   # cabeça fletida à frente do eixo do tronco (olhar à frente)
    espessura_capacete_m: float = .03  # coquinho aberto; varredura 0,025–0,035
    espessura_teto_m: float = .02      # face interna do teto abaixo do plano de 1560 mm
    compressao_assento_m: float = .02  # afundamento do quadril no estofado
    quadril_acima_assento_m: float = .06   # articulação do quadril acima da superfície do assento
    folga_minima_cabeca_m: float = .02
    raio_cabeca_m: float = .095
    meia_profundidade_torax_m: float = .11
    espessura_estofado_m: float = 0.
    cg_deitado: float = .12          # CG da pessoa deitada acima do piso
    fracao_cabeca: float = .43       # CG a 43 % da altura medido a partir da cabeça
    aderencia: float = .8            # aderência lateral de referência, em g
    indice_traseiro_kg: float = 132  # exemplo: índice 38; conferir o flanco
    indice_dianteiro_kg: float = 170  # exemplo: índice 46; conferir o flanco
    tensao_bateria: float = 25.6     # FLA24100-EU: LiFePO4 de oito células, "24 V"
    capacidade_bateria_ah: float = 100
    corrente_max_bateria_a: float = 100   # ficha FLA24100-EU (2026-11-05): corrente contínua de carga/descarga
    corrente_pico_bateria_a: float = 150  # ficha: pico de 150 A por 15 s
    potencia_max_bateria_w: float = 2500  # ficha: máx. de carga/descarga 2500 W (não diz se medida na bateria ou nos motores)
    potencia_recomendada_bateria_w: float = 1500
    potencia_motores_w: float = 4*745.7  # quatro motores de 1 HP nominal
    eixo_dianteiro: float = X_EIXO_DIANT / 1000
    eixo_traseiro: float = X_EIXO_TRAS / 1000
    bitola: float = BITOLA / 1000

    def validar(self):
        valores = [v for v in asdict(self).values() if not isinstance(v, (tuple, str))] + list(self.distancias_piloto)
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in valores):
            raise ValueError('Hipóteses devem ser números finitos')
        if min(self.massa_pessoa, self.altura_pessoa, self.bitola, self.aderencia, self.tensao_bateria,
               self.capacidade_bateria_ah, self.potencia_motores_w, self.corrente_max_bateria_a,
               self.potencia_max_bateria_w, self.potencia_recomendada_bateria_w) <= 0:
            raise ValueError('Massa, altura, bitola, aderência e dados elétricos devem ser positivos')
        if self.postura not in POSTURAS:
            raise ValueError(f'Postura deve ser uma de {", ".join(POSTURAS)}')
        if not (0 <= self.theta_encosto_graus < 80 and 0 <= self.angulo_coxa_graus < 60
                and 0 <= self.angulo_cabeca_graus < 80):
            raise ValueError('Ângulos de encosto (<80°), coxa (<60°) e cabeça (<80°) devem ser não negativos')
        if min(self.espessura_capacete_m, self.espessura_teto_m, self.compressao_assento_m,
               self.quadril_acima_assento_m, self.raio_cabeca_m, self.meia_profundidade_torax_m,
               self.espessura_estofado_m) < 0:
            raise ValueError('Espessuras e raios da postura não podem ser negativos')
        if not 0 <= self.eixo_dianteiro < self.eixo_traseiro:
            raise ValueError('Exige 0 ≤ eixo dianteiro < eixo traseiro')
        if not self.distancias_piloto or min(self.distancias_piloto) < 0:
            raise ValueError('Distâncias do piloto devem ser não negativas')
        return self


def numero(texto, n, campo):
    texto = (texto or '').strip().replace(',', '.')
    if not texto:
        return None
    try:
        valor = float(texto)
    except ValueError as exc:
        raise ValueError(f'Linha {n}: {campo} deve ser número') from exc
    if not math.isfinite(valor):
        raise ValueError(f'Linha {n}: {campo} deve ser finito')
    return valor


def itens_do_modelo():
    """Massa e posição derivadas da geometria comum, para não duplicar números."""
    g, m = geometria(), massas_parciais()
    barras = barras_piso()
    total = sum(b['comprimento_mm'] for b in barras)
    x_barras = sum(b['comprimento_mm']*(b['x_mm'] + PISO.largura/2) for b in barras) / total
    z_long = -(PISO.altura + LONGARINA.altura/2) / 1000   # relativo à face do piso
    m_berco, x_berco, z_berco = massa_berco()
    return {
        'berço da bateria': (m_berco, x_berco, z_berco - Hipoteses.piso),
        'longarinas de aço': (m['duas_longarinas_kg'], (X_FRENTE_TRAP + X_EIXO_TRAS)/2000, z_long),
        '14 barras do piso': (m['14_barras_piso_kg'], x_barras/1000, -PISO.altura/2000),
        'longarinas da extensão': (m['duas_longarinas_extensao_kg'],
                                   (g['inicio_estatico_roda_mm'] + g['fim_leito_hipotetico_mm'])/2000, None),
    }


def ler_inventario(caminho):
    with Path(caminho).open(encoding='utf-8-sig', newline='') as f:
        leitor = csv.DictReader(f, delimiter=';')
        faltam = set(COLUNAS) - set(leitor.fieldnames or [])
        if faltam:
            raise ValueError(f'CSV sem as colunas: {", ".join(sorted(faltam))}')
        return list(leitor)


def preparar_itens(linhas, h):
    """Normaliza linhas; posições vazias de 'modelo' vêm da geometria comum."""
    modelo, itens = itens_do_modelo(), []
    for n, linha in enumerate(linhas, 2):
        cenario = (linha.get('cenario') or '').strip().lower()
        nome = (linha.get('componente') or '').strip()
        estado = (linha.get('estado') or '').strip().lower()
        if cenario not in ('todos',) + CENARIOS or not nome or estado not in ESTADOS:
            raise ValueError(f'Linha {n}: cenário (todos, sentado, leito), componente e estado válidos são obrigatórios')
        massa, x, y, z = (numero(linha.get(c), n, c) for c in ('massa_kg', 'x_m', 'y_m', 'z_m'))
        if estado == 'modelo':
            if nome not in modelo or massa is not None:
                raise ValueError(f'Linha {n}: estado "modelo" só vale para {", ".join(modelo)}, com massa vazia')
            massa, x_mod, z_rel = modelo[nome]
            x = x_mod if x is None else x
            z = (h.piso + z_rel if z_rel is not None else None) if z is None else z
        if estado in ('pendente', 'ausente'):
            itens.append(dict(cenario=cenario, componente=nome, estado=estado, fonte=linha.get('fonte', '')))
            continue
        if massa is None or massa <= 0 or z is None or z < 0 or (x is not None and x < 0):
            raise ValueError(f'Linha {n}: massa positiva e z não negativo são obrigatórios')
        if x is None and cenario != 'sentado':
            raise ValueError(f'Linha {n}: x vazio só é aceito no cenário sentado (acompanha o banco)')
        itens.append(dict(cenario=cenario, componente=nome, massa_kg=massa, x_m=x, y_m=y or 0.0,
                          z_m=z, estado=estado, fonte=(linha.get('fonte') or '').strip()))
    return itens


def _soma(a, b, k=1.):
    return (a[0] + k*b[0], a[1] + k*b[1])


def pessoa_reclinada(h, quadril_x, maos):
    """Modelo segmentar no plano x–z (x cresce para trás; a pessoa olha para x decrescente).

    `maos` = (x, z) do ponto onde os braços se apoiam (guidão ou cintura do piloto).
    Devolve o CG e os pontos usados nas verificações de cabeça e de tandem.
    """
    H, th = h.altura_pessoa, math.radians(h.theta_encosto_graus)
    u = (math.sin(th), math.cos(th))
    quadril = (quadril_x, h.piso + h.assento - h.compressao_assento_m + h.quadril_acima_assento_m)
    ombro = _soma(quadril, u, COMPRIMENTO_TRONCO*H)
    th_cab = th - math.radians(h.angulo_cabeca_graus)
    uc = (math.sin(th_cab), math.cos(th_cab))
    topo_cranio = _soma(ombro, uc, COMPRIMENTO_CABECA*H)
    centro_cabeca = _soma(topo_cranio, uc, -h.raio_cabeca_m)
    a = math.radians(h.angulo_coxa_graus)
    joelho = _soma(quadril, (-math.cos(a), math.sin(a)), COMPRIMENTO_COXA*H)
    z_tornozelo = h.piso + EVA_PISO_MM/1000 + ALTURA_TORNOZELO*H
    dz, perna = joelho[1] - z_tornozelo, COMPRIMENTO_PERNA*H
    if not 0 <= dz <= perna:
        raise ValueError(f'Pés não alcançam o piso com a coxa a {h.angulo_coxa_graus:.0f}° '
                         f'(joelho {dz*1000:.0f} mm acima do tornozelo; perna {perna*1000:.0f} mm)')
    tornozelo = (joelho[0] - math.sqrt(perna**2 - dz**2), z_tornozelo)
    segmentos = [
        ('cabeca_pescoco', _soma(ombro, uc, CENTRO_CABECA*COMPRIMENTO_CABECA*H)),
        ('tronco', _soma(quadril, u, CENTRO_TRONCO*COMPRIMENTO_TRONCO*H)),
        ('bracos', ((ombro[0] + maos[0])/2, (ombro[1] + maos[1])/2)),
        ('coxas', _soma(quadril, (joelho[0] - quadril[0], joelho[1] - quadril[1]), CENTRO_COXA)),
        ('pernas', _soma(joelho, (tornozelo[0] - joelho[0], tornozelo[1] - joelho[1]), CENTRO_PERNA)),
        ('pes', (tornozelo[0] - PE_AVANCO_M, tornozelo[1] - PE_ABAIXO_M)),
    ]
    cg = tuple(sum(FRACAO_MASSA[n]*p[i] for n, p in segmentos) for i in (0, 1))
    return {'cg_x_m': cg[0], 'cg_z_m': cg[1], 'quadril': quadril, 'ombro': ombro, 'topo_cranio': topo_cranio,
            'centro_cabeca': centro_cabeca, 'joelho': joelho, 'tornozelo': tornozelo}


def _par_reclinado(h, quadril_piloto_x):
    th = math.radians(h.theta_encosto_graus)
    piloto = pessoa_reclinada(h, quadril_piloto_x, (X_MAOS_PILOTO, Z_MAOS_PILOTO))
    cintura = _soma(piloto['quadril'], (math.sin(th), math.cos(th)), .5*COMPRIMENTO_TRONCO*h.altura_pessoa)
    return piloto, pessoa_reclinada(h, quadril_piloto_x + h.abraco, cintura)


def folga_cabeca(h, distancia=None):
    """Folga vertical do topo do capacete à face interna do teto, de piloto e passageiro (mm)."""
    piloto, passageiro = _par_reclinado(h, h.x_guidao + (h.distancia_nominal if distancia is None else distancia))
    teto = TETO/1000 - h.espessura_teto_m
    resultado = {'teto_interno_m': teto}
    for nome, p in (('piloto', piloto), ('passageiro', passageiro)):
        topo = p['topo_cranio'][1] + h.espessura_capacete_m
        resultado[nome] = {'topo_capacete_z_m': topo, 'folga_mm': 1000*(teto - topo),
                           'atende': teto - topo >= h.folga_minima_cabeca_m}
    return resultado


def _distancia_ponto_segmento(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    t = max(0., min(1., ((p[0] - a[0])*ab[0] + (p[1] - a[1])*ab[1])/(ab[0]**2 + ab[1]**2)))
    return math.hypot(p[0] - a[0] - t*ab[0], p[1] - a[1] - t*ab[1])


def interferencia_tandem(h, distancia=None):
    """Folga entre a cabeça (com capacete) do piloto e o tórax e a cabeça do passageiro (mm).

    Negativo = sobreposição geométrica. Não conclui conforto: o contato piloto–passageiro
    "abraçado" pode ser intencional; serve para dimensionar encosto escalonado e capacete.
    """
    piloto, passageiro = _par_reclinado(h, h.x_guidao + (h.distancia_nominal if distancia is None else distancia))
    r = h.raio_cabeca_m + h.espessura_capacete_m
    torax = _distancia_ponto_segmento(piloto['centro_cabeca'], passageiro['quadril'], passageiro['ombro']) \
        - r - h.meia_profundidade_torax_m - h.espessura_estofado_m
    cabecas = math.hypot(piloto['centro_cabeca'][0] - passageiro['centro_cabeca'][0],
                         piloto['centro_cabeca'][1] - passageiro['centro_cabeca'][1]) - 2*r
    return {'folga_torax_mm': 1000*torax, 'folga_cabecas_mm': 1000*cabecas,
            'sobrepoe': min(torax, cabecas) < 0}


def ocupantes_sentados(h, distancia):
    """Tandem abraçado, como numa Biz: passageiro colado às costas do piloto."""
    if h.postura == 'reclinada':
        quadril = h.x_guidao + distancia
        piloto, passageiro = _par_reclinado(h, quadril)
        return [dict(componente='piloto reclinado', massa_kg=h.massa_pessoa, x_m=piloto['cg_x_m'], y_m=0.0,
                     z_m=piloto['cg_z_m'], estado='hipótese', quadril_x_m=quadril),
                dict(componente='passageiro abraçado reclinado', massa_kg=h.massa_pessoa, x_m=passageiro['cg_x_m'],
                     y_m=0.0, z_m=passageiro['cg_z_m'], estado='hipótese', quadril_x_m=quadril + h.abraco)]
    z = h.piso + h.assento + h.cg_sentado
    quadril = h.x_guidao + distancia
    return [dict(componente='piloto sentado', massa_kg=h.massa_pessoa, x_m=quadril - h.avanco_sentado,
                 y_m=0.0, z_m=z, estado='hipótese', quadril_x_m=quadril),
            dict(componente='passageiro abraçado', massa_kg=h.massa_pessoa,
                 x_m=quadril + h.abraco - h.avanco_sentado, y_m=0.0, z_m=z, estado='hipótese',
                 quadril_x_m=quadril + h.abraco)]


def ocupantes_deitados(h, arranjo):
    """Cabeça junto ao guidão (início do piso) ou junto à parede reta."""
    frente = X_FRENTE_TRAP / 1000
    parede = (geometria()['inicio_estatico_roda_mm'] - FOLGA_RODA) / 1000
    d_cabeca = h.fracao_cabeca * h.altura_pessoa
    z = h.piso + h.cg_deitado
    passageiro = frente + d_cabeca if arranjo == 'mesmo_sentido' else parede - d_cabeca
    return [dict(componente='piloto deitado, cabeça ao guidão', massa_kg=h.massa_pessoa,
                 x_m=frente + d_cabeca, y_m=-.2, z_m=z, estado='hipótese'),
            dict(componente='passageiro deitado, cabeça ' + ('ao guidão' if arranjo == 'mesmo_sentido' else 'à traseira'),
                 massa_kg=h.massa_pessoa, x_m=passageiro, y_m=.2, z_m=z, estado='hipótese')]


def montar(itens, cenario, ocupantes):
    escolhidos = [dict(i) for i in itens
                  if i['cenario'] in ('todos', cenario) and i['estado'] not in ('pendente', 'ausente')]
    if cenario == 'sentado':
        banco = sum(o['quadril_x_m'] for o in ocupantes) / len(ocupantes)
        for item in escolhidos:
            if item['x_m'] is None:
                item['x_m'] = banco
    return escolhidos + ocupantes


def estabilidade(itens, h):
    """CG, reações estáticas e limiares quase-estáticos do triângulo de apoio."""
    m = sum(i['massa_kg'] for i in itens)
    x, y, z = (sum(i['massa_kg']*i[c] for i in itens)/m for c in ('x_m', 'y_m', 'z_m'))
    xf, xr, b = h.eixo_dianteiro, h.eixo_traseiro, h.bitola
    if not xf < x < xr:
        raise ValueError(f'CG em x = {x:.3f} m fora do entre-eixos; o triângulo de apoio não sustenta o veículo')
    L = xr - xf
    traseira = m*(x - xf)/L
    dianteira = m - traseira
    diferenca = 2*m*y/b                     # momento em torno do eixo longitudinal
    meia_largura = b/2*(xr - x)/L            # do eixo de tombamento até a linha central, no x do CG
    limite = min(meia_largura - y, meia_largura + y)/z
    frente = dianteira/m
    return {
        'massa_kg': m, 'cg_x_m': x, 'cg_y_m': y, 'cg_z_m': z,
        'reacoes_kgf': {'dianteira_esquerda': (dianteira - diferenca)/2,
                        'dianteira_direita': (dianteira + diferenca)/2, 'traseira': traseira},
        'frente_pct': 100*frente,
        'limite_tombamento_lateral_g': limite,
        'tomba_antes_de_derrapar': limite < h.aderencia,
        'bitola_para_igualar_aderencia_m': 2*z*h.aderencia/frente,
        'altura_cg_maxima_para_aderencia_m': frente*b/(2*h.aderencia),
        'desaceleracao_que_alivia_traseira_g': (x - xf)/z,
        'traseira_na_frenagem_0_8g_pct': 100*(x - xf - .8*z)/L,
        'tomba_para_frente_graus': math.degrees(math.atan((x - xf)/z)),
        'tomba_para_tras_graus': math.degrees(math.atan((xr - x)/z)),
        'traseira_rampa_20pct_nariz_baixo_kgf': m*((x - xf)*math.cos(math.atan(.2)) - z*math.sin(math.atan(.2)))/L,
        'retencao_freio_so_traseiro_graus_mu07': math.degrees(math.atan(
            .7*(m*((x - xf)*math.cos(math.atan(.2)) - z*math.sin(math.atan(.2)))/L)/(m*math.cos(math.atan(.2))))),
        'uso_indice_traseiro_pct': 100*traseira/h.indice_traseiro_kg,
        'uso_indice_dianteiro_pct': 100*max(dianteira - diferenca, dianteira + diferenca)/2/h.indice_dianteiro_kg,
    }


@lru_cache(maxsize=8)
def cg_nominal(caminho=INVENTARIO_PADRAO, h=Hipoteses()):
    """Massa e CG sentado na distância nominal: referência comum dos demais scripts."""
    itens = preparar_itens(ler_inventario(caminho), h.validar())
    nominal = montar(itens, 'sentado', ocupantes_sentados(h, h.distancia_nominal))
    r = estabilidade(nominal, h)
    veiculo = [i for i in nominal if i['estado'] != 'hipótese']
    estimada = sum(i['massa_kg'] for i in veiculo if i['estado'] == 'estimado')
    informada = sum(i['massa_kg'] for i in veiculo if i['estado'] == 'informado')
    total = sum(i['massa_kg'] for i in veiculo)
    return {'massa_kg': r['massa_kg'], 'cg_x_m': r['cg_x_m'], 'cg_z_m': r['cg_z_m'],
            'origem': (f"{Path(caminho).name}: sentado, piloto a {h.distancia_nominal*100:.0f} cm do guidão, "
                       f"{h.massa_pessoa:.0f} kg por pessoa; "
                       f"{100*estimada/total:.0f} % da massa do veículo estimada e {100*informada/total:.0f} % informada")}


def cg_por_pesagem(esquerda, direita, traseira, h):
    valores = (esquerda, direita, traseira)
    if not all(math.isfinite(v) and v >= 0 for v in valores) or sum(valores) <= 0:
        raise ValueError('Pesagens devem ser finitas, não negativas e com soma positiva')
    m = sum(valores)
    return {'massa_kg': m,
            'cg_x_m': h.eixo_dianteiro + (h.eixo_traseiro - h.eixo_dianteiro)*traseira/m,
            'cg_y_m': (direita - esquerda)/m*h.bitola/2}


def altura_por_inclinacao(nivelada, inclinada, elevacao, h):
    """Traseira erguida `elevacao` m com suspensão travada: Δdianteira = m·h'·tanθ/L."""
    L = h.eixo_traseiro - h.eixo_dianteiro
    if not math.isfinite(elevacao) or not 0 < elevacao < L:
        raise ValueError('Elevação da traseira deve ser positiva e menor que o entre-eixos')
    base = cg_por_pesagem(*nivelada, h)
    m = base['massa_kg']
    cg_por_pesagem(*inclinada, h)  # Mesma validação física das cargas da pesagem nivelada.
    if abs(sum(inclinada) - m) > .02*m:
        raise ValueError('Pesagem inclinada difere da nivelada em mais de 2 %; repetir')
    tan = math.tan(math.asin(elevacao/L))
    delta = (inclinada[0] + inclinada[1]) - (nivelada[0] + nivelada[1])
    raio_d, raio_t = diametro(*PNEU_DIANT[1:])/2000, diametro(*PNEU_TRAS[1:])/2000
    frac = (base['cg_x_m'] - h.eixo_dianteiro)/L
    return L*delta/(m*tan) + raio_d + (raio_t - raio_d)*frac


def varredura_postura(itens, h, thetas=THETAS_VARREDURA):
    """Legado (ereto) e cada ângulo de encosto: CG, reações, tombamento, cabeça × teto, tandem."""
    linhas = []
    legado = replace(h, postura='ereta_legada')
    r = estabilidade(montar(itens, 'sentado', ocupantes_sentados(legado, h.distancia_nominal)), legado)
    linhas.append({'postura': 'ereta_legada', 'theta_encosto_graus': None, 'cg_x_m': r['cg_x_m'], 'cg_z_m': r['cg_z_m'],
                   'reacoes_kgf': r['reacoes_kgf'], 'limite_tombamento_lateral_g': r['limite_tombamento_lateral_g'],
                   'desaceleracao_que_alivia_traseira_g': r['desaceleracao_que_alivia_traseira_g'],
                   'uso_indice_traseiro_pct': r['uso_indice_traseiro_pct'],
                   'folga_cabeca_mm': {'piloto': 1000*(TETO/1000 - h.piso - h.assento - ALTURA_SENTADO/1000)},
                   'nota': 'folga aritmética antiga: sem capacete, teto real nem postura'})
    for t in thetas:
        ht = replace(h, postura='reclinada', theta_encosto_graus=t)
        try:
            r = estabilidade(montar(itens, 'sentado', ocupantes_sentados(ht, h.distancia_nominal)), ht)
            fc, tandem = folga_cabeca(ht, h.distancia_nominal), interferencia_tandem(ht, h.distancia_nominal)
        except ValueError as exc:
            linhas.append({'postura': 'reclinada', 'theta_encosto_graus': t, 'erro': str(exc)})
            continue
        linhas.append({'postura': 'reclinada', 'theta_encosto_graus': t, 'cg_x_m': r['cg_x_m'], 'cg_z_m': r['cg_z_m'],
                       'reacoes_kgf': r['reacoes_kgf'], 'limite_tombamento_lateral_g': r['limite_tombamento_lateral_g'],
                       'desaceleracao_que_alivia_traseira_g': r['desaceleracao_que_alivia_traseira_g'],
                       'uso_indice_traseiro_pct': r['uso_indice_traseiro_pct'],
                       'folga_cabeca_mm': {n: fc[n]['folga_mm'] for n in ('piloto', 'passageiro')},
                       'atende_folga_minima': all(fc[n]['atende'] for n in ('piloto', 'passageiro')),
                       'tandem': tandem})
    return linhas


def calcular(itens, h, pesagens=None, inclinadas=None, modulos_bateria=(1, 2)):
    h.validar()
    pendencias = [f"{i['cenario']}: {i['componente']}" for i in itens if i['estado'] == 'pendente']
    sentado = []
    for d in h.distancias_piloto:
        ocup = ocupantes_sentados(h, d)
        res = estabilidade(montar(itens, 'sentado', ocup), h)
        sentado.append({'distancia_guidao_quadril_m': d, 'quadril_piloto_x_m': ocup[0]['quadril_x_m'], **res})
    nominal_itens = montar(itens, 'sentado', ocupantes_sentados(h, h.distancia_nominal))
    nominal = estabilidade(nominal_itens, h)
    leito = {a: estabilidade(montar(itens, 'leito', ocupantes_deitados(h, a)), h)
             for a in ('mesmo_sentido', 'invertido')}
    veiculo = [i for i in nominal_itens if i['estado'] != 'hipótese']
    massa_veiculo = sum(i['massa_kg'] for i in veiculo)
    estimada = sum(i['massa_kg'] for i in veiculo if i['estado'] == 'estimado')
    informada = sum(i['massa_kg'] for i in veiculo if i['estado'] == 'informado')
    bateria = next((i for i in nominal_itens if i['componente'].startswith('bateria')), None)
    banco_x = h.x_guidao + h.distancia_nominal + h.abraco/2
    sens = []
    if bateria:
        # FLA24100: só ligação em paralelo; a tensão não muda, somam-se corrente e energia.
        for modulos in modulos_bateria:
            massa = bateria['massa_kg']*modulos
            for local, x, z in (('inventário', bateria['x_m'], bateria['z_m']),
                                ('bloco traseiro', 2.30, .50),
                                ('sob o banco', banco_x, h.piso + .1)):
                variante = [dict(i, massa_kg=massa, x_m=x, z_m=z) if i is bateria else i for i in nominal_itens]
                r = estabilidade(variante, h)
                sens.append({'modulos': modulos, 'tensao_nominal_v': h.tensao_bateria,
                             'bateria_kg': massa, 'local': local, 'cg_x_m': r['cg_x_m'], 'cg_z_m': r['cg_z_m'],
                             'traseira_kgf': r['reacoes_kgf']['traseira'],
                             'limite_tombamento_lateral_g': r['limite_tombamento_lateral_g']})
    dados = {
        'aviso': AVISO,
        'hipoteses': {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(h).items()},
        'inventario': {'massa_veiculo_sem_pessoas_kg': massa_veiculo,
                       'parcela_estimada_pct': 100*estimada/massa_veiculo,
                       'parcela_informada_pct': 100*informada/massa_veiculo,
                       'resultado_parcial': bool(pendencias), 'pendencias': pendencias,
                       'itens_sentado_nominal': nominal_itens},
        'sentado_varredura_40_60_cm': sentado,
        'sentado_nominal': nominal,
        'postura_varredura_theta': varredura_postura(itens, h),
        'sentado_nominal_cenarios_dinamicos_kgf': {
            nome: r['reacoes_kgf'] for nome, r in calcular_reacoes(
                nominal['massa_kg'], h.eixo_dianteiro, h.eixo_traseiro,
                nominal['cg_x_m'], nominal['cg_z_m'], h.bitola).items()},
        'leito_estacionado': leito,
        'sensibilidade_bateria': sens,
        'comandos_coerentes': {
            'revisar_calculos': (f"python revisar_calculos.py --massa {nominal['massa_kg']:.0f} --eixo-dianteiro {h.eixo_dianteiro} "
                                 f"--eixo-traseiro {h.eixo_traseiro} --cg-x {nominal['cg_x_m']:.3f} "
                                 f"--cg-altura {nominal['cg_z_m']:.3f} --bitola {h.bitola}"),
            'avaliar_eixos': (f"python avaliar_eixos.py --massa {nominal['massa_kg']:.0f} --cg {nominal['cg_x_m']:.3f} "
                              f"--altura-cg {nominal['cg_z_m']:.3f}"),
            'observacao': ('Sem esses argumentos, os dois scripts já usam o inventário padrão; '
                           'o antigo cenário de 300 kg, CG 1,35 m e 0,60 m ficou só como histórico.')},
    }
    if bateria:
        dados['eletrica'] = {
            'tensao_nominal_v': h.tensao_bateria, 'energia_kwh': h.tensao_bateria*h.capacidade_bateria_ah/1000,
            'corrente_nominal_a': h.potencia_motores_w/h.tensao_bateria,
            'modulos_paralelo_para_potencia_nominal': math.ceil(h.potencia_motores_w/h.potencia_max_bateria_w),
            'modulos_paralelo_na_potencia_recomendada': math.ceil(h.potencia_motores_w/h.potencia_recomendada_bateria_w),
            # D-9: um módulo; controladores limitados à potência recomendada, picos até o máximo.
            'limite_continuo_controladores_w': h.potencia_recomendada_bateria_w,
            'limite_pico_controladores_w': h.potencia_max_bateria_w,
            'corrente_continua_limitada_a': h.potencia_recomendada_bateria_w/h.tensao_bateria,
            'corrente_pico_limitada_a': h.potencia_max_bateria_w/h.tensao_bateria,
            'potencia_continua_por_motor_w': h.potencia_recomendada_bateria_w/4,
            'fracao_da_potencia_nominal_pct': 100*h.potencia_recomendada_bateria_w/h.potencia_motores_w,
            'potencia_motores_cabe_em_um_modulo': (h.potencia_motores_w <= h.potencia_max_bateria_w
                                                   and h.potencia_motores_w/h.tensao_bateria <= h.corrente_max_bateria_a),
            'observacao': 'Potência nominal somada dos motores; picos, perdas e corrente do BMS não verificados.'}
    if pesagens:
        dados['pesagem'] = {}
        for cenario, valores in pesagens.items():
            medido = cg_por_pesagem(*valores, h)
            ref = nominal if cenario == 'sentado' else leito['mesmo_sentido']
            medido.update(diferenca_massa_kg=medido['massa_kg'] - ref['massa_kg'],
                          diferenca_cg_x_mm=1000*(medido['cg_x_m'] - ref['cg_x_m']),
                          inventario_coerente=abs(medido['massa_kg'] - ref['massa_kg']) <= .05*ref['massa_kg']
                          and abs(medido['cg_x_m'] - ref['cg_x_m']) <= .03)
            if inclinadas and cenario in inclinadas:
                *roda, elevacao = inclinadas[cenario]
                medido['cg_z_m'] = altura_por_inclinacao(valores, roda, elevacao, h)
                medido['diferenca_cg_z_mm'] = 1000*(medido['cg_z_m'] - ref['cg_z_m'])
            dados['pesagem'][cenario] = medido
    dados['conclusoes'] = conclusoes(dados, h)
    return dados


def conclusoes(dados, h):
    def f(valor, casas=2):
        return f'{valor:.{casas}f}'.replace('.', ',')

    def faixa(chave, casas=2, fator=1):
        valores = [r[chave]*fator for r in s] if isinstance(chave, str) else [chave(r) for r in s]
        menor, maior = f(min(valores), casas), f(max(valores), casas)
        return menor if menor == maior else f'{menor}–{maior}'

    s = sorted(dados['sentado_varredura_40_60_cm'], key=lambda r: r['distancia_guidao_quadril_m'])
    perto, longe = s[0], s[-1]
    passo = (perto['limite_tombamento_lateral_g'] - longe['limite_tombamento_lateral_g']) / max(
        longe['distancia_guidao_quadril_m'] - perto['distancia_guidao_quadril_m'], 1e-9) / 10
    texto = [
        f"Sentado, piloto de {faixa('distancia_guidao_quadril_m', 0, 100)} cm do guidão: CG x = {faixa('cg_x_m', 3)} m, "
        f"altura {faixa('cg_z_m', 3)} m; tombamento lateral em {faixa('limite_tombamento_lateral_g')} g "
        f"(cada 10 cm do piloto para trás custa ≈ {f(passo, 3)} g).",
    ]
    n = dados['sentado_nominal']
    linhas = [r for r in dados['postura_varredura_theta'] if 'erro' not in r]
    legado = linhas[0]
    recl = [r for r in linhas if r['theta_encosto_graus'] is not None]
    if recl:
        texto.append(f"Postura '{h.postura}' (encosto a {f(h.theta_encosto_graus, 0)}° nominal): comparado com a ereta, o CG fica em "
                     f"x = {f(n['cg_x_m'], 3)} m e z = {f(n['cg_z_m'], 3)} m (ereta: {f(legado['cg_x_m'], 3)} e {f(legado['cg_z_m'], 3)}). "
                     f"Para encostos de {f(recl[0]['theta_encosto_graus'], 0)}–{f(recl[-1]['theta_encosto_graus'], 0)}°, a folga "
                     f"cabeça–teto (hipóteses de capacete e teto) vai de {f(min(r['folga_cabeca_mm']['piloto'] for r in recl), 0)} a "
                     f"{f(max(r['folga_cabeca_mm']['piloto'] for r in recl), 0)} mm. Hipóteses antropométricas, sem medição.")
    if all(r['tomba_antes_de_derrapar'] for r in s):
        texto.append(f"Em toda a faixa o limiar fica abaixo da aderência de referência ({f(h.aderencia, 1)} g): o modelo "
                     f"tomba antes de derrapar. A posição do piloto pouco resolve; para igualar seria preciso bitola ≈ "
                     f"{f(n['bitola_para_igualar_aderencia_m'])} m ou CG a ≤ {f(n['altura_cg_maxima_para_aderencia_m'], 3)} m do solo.")
    texto.append(f"Frenagem: a traseira descarrega a {faixa('desaceleracao_que_alivia_traseira_g')} g, o menor valor com o piloto "
                 "mais à frente; ganhar estabilidade lateral avançando o piloto reduz essa reserva.")
    pior = max(s, key=lambda r: r['uso_indice_traseiro_pct'])
    acima = [r['distancia_guidao_quadril_m'] for r in s if r['uso_indice_traseiro_pct'] > 100]
    texto.append(f"Roda traseira sentado: {faixa(lambda r: r['reacoes_kgf']['traseira'], 0)} kgf estáticos, até "
                 f"{f(pior['uso_indice_traseiro_pct'], 0)} % do índice de exemplo de {f(h.indice_traseiro_kg, 0)} kg"
                 + (f"; acima dele a partir de {f(min(acima)*100, 0)} cm." if acima else '.'))
    l = dados['leito_estacionado']
    leito = [l[a]['reacoes_kgf']['traseira'] for a in ('mesmo_sentido', 'invertido')]
    texto.append(f"Leito (estacionado): traseira {f(leito[0], 0)} kgf com as duas cabeças ao guidão e {f(leito[1], 0)} kgf "
                 "com o passageiro invertido" + ('; abaixo do pior caso sentado.' if max(leito) < pior['reacoes_kgf']['traseira']
                                               else '; atenção: supera o pior caso sentado.'))
    bateria = dados['sensibilidade_bateria']
    if bateria:
        e = dados['eletrica']
        texto.append(f"Bateria de {f(e['tensao_nominal_v'], 1)} V e {f(e['energia_kwh'])} kWh: os motores somam "
                     f"{f(h.potencia_motores_w/1000)} kW nominais, ≈ {f(e['corrente_nominal_a'], 0)} A antes de perdas, contra "
                     f"{f(h.corrente_max_bateria_a, 0)} A e {f(h.potencia_max_bateria_w, 0)} W máximos por módulo "
                     f"({f(h.potencia_recomendada_bateria_w, 0)} W recomendados). "
                     + ('Um módulo basta na potência nominal.' if e['potencia_motores_cabe_em_um_modulo'] else
                        f"Decisão D-9: um módulo, com controladores limitados a {f(e['limite_continuo_controladores_w'], 0)} W "
                        f"contínuos (≈ {f(e['corrente_continua_limitada_a'], 0)} A, {f(e['potencia_continua_por_motor_w'], 0)} W por motor, "
                        f"{f(e['fracao_da_potencia_nominal_pct'], 0)} % do nominal) e {f(e['limite_pico_controladores_w'], 0)} W de pico "
                        f"(≈ {f(e['corrente_pico_limitada_a'], 0)} A) (ficha: pico de 150 A por 15 s)."))
        um = {r['local']: r for r in bateria if r['modulos'] == 1}
        texto.append("Posição da bateria (1 módulo): " + '; '.join(
            f"{nome} {f(um[nome]['limite_tombamento_lateral_g'])} g e {f(um[nome]['traseira_kgf'], 0)} kgf atrás"
            for nome in ('inventário', 'sob o banco', 'bloco traseiro') if nome in um)
            + ". Massa e posição da bateria pesam mais que os 20 cm do piloto.")
        n = dados['sentado_nominal']
        texto.append(f"Inclinação (posição do inventário): tomba para a frente a {f(n['tomba_para_frente_graus'], 0)}° e para trás a "
                     f"{f(n['tomba_para_tras_graus'], 0)}°; numa rampa de 20 % de nariz para baixo a roda traseira fica com "
                     f"{f(n['traseira_rampa_20pct_nariz_baixo_kgf'], 0)} kgf e um freio de estacionamento só traseiro retém ≈ "
                     f"{f(n['retencao_freio_so_traseiro_graus_mu07'], 0)}° (rampa de 11,3°; atrito 0,7). "
                     "Estacionamento deve atuar também nas rodas dianteiras.")
    inv = dados['inventario']
    texto.append(f"Da massa do veículo ({f(inv['massa_veiculo_sem_pessoas_kg'], 0)} kg), {f(inv['parcela_estimada_pct'], 0)} % é estimativa "
                 f"e {f(inv['parcela_informada_pct'], 0)} % é dado informado, ainda não pesado; pesar as três rodas antes de "
                 "usar estes números em projeto.")
    return texto


def exportar_csv(caminho, dados):
    """Formato de inventario_massas.py (cenário sentado na distância nominal)."""
    with Path(caminho).open('x', encoding='utf-8', newline='') as f:
        escritor = csv.writer(f, delimiter=';')
        escritor.writerow(['cenario', 'componente', 'massa_kg', 'x_m', 'estado'])
        for i in dados['inventario']['itens_sentado_nominal']:
            # inventario_massas.py não tem 'informado': sem pesagem, conta como estimativa.
            estado = 'medido' if i['estado'] == 'medido' else 'estimado'
            escritor.writerow(['sentado', i['componente'], f"{i['massa_kg']:.4f}", f"{i['x_m']:.4f}", estado])


def ler_pesagem(textos, partes):
    resultado = {}
    for texto in textos or []:
        cenario, _, valores = texto.partition('=')
        cenario = cenario.strip().lower()
        try:
            numeros = [float(v.replace(',', '.')) for v in valores.split(';' if ';' in valores else ',')]
        except ValueError as exc:
            raise ValueError(f'Pesagem inválida: {texto}') from exc
        if cenario not in CENARIOS or len(numeros) != partes:
            raise ValueError(f'Pesagem deve ser cenário=valores com {partes} números: {texto}')
        resultado[cenario] = numeros
    return resultado


def main(argv=None):
    configurar_console()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('inventario', nargs='?', type=Path, default=INVENTARIO_PADRAO)
    padrao = Hipoteses()
    for nome in ('massa_pessoa', 'altura_pessoa', 'x_guidao', 'distancia_nominal', 'abraco', 'piso',
                 'assento', 'aderencia', 'indice_traseiro_kg', 'indice_dianteiro_kg',
                 'eixo_dianteiro', 'eixo_traseiro', 'bitola', 'tensao_bateria', 'capacidade_bateria_ah',
                 'potencia_motores_w', 'corrente_max_bateria_a', 'potencia_max_bateria_w',
                 'potencia_recomendada_bateria_w', 'theta_encosto_graus', 'angulo_coxa_graus', 'angulo_cabeca_graus',
                 'espessura_capacete_m', 'espessura_teto_m', 'compressao_assento_m', 'quadril_acima_assento_m',
                 'folga_minima_cabeca_m', 'raio_cabeca_m', 'meia_profundidade_torax_m', 'espessura_estofado_m'):
        p.add_argument('--' + nome.replace('_', '-'), type=float, default=getattr(padrao, nome))
    p.add_argument('--theta', dest='theta_encosto_graus', type=float, default=padrao.theta_encosto_graus,
                   help='Ângulo do encosto/tronco em relação à vertical, para trás (alias de --theta-encosto-graus)')
    p.add_argument('--postura', choices=POSTURAS, default=padrao.postura,
                   help="'ereta_legada' reproduz os parâmetros anteriores à revisão reclinada")
    p.add_argument('--distancias', type=float, nargs='+', default=list(padrao.distancias_piloto),
                   help='Distâncias guidão → quadril do piloto em m (padrão 0,40 a 0,60)')
    p.add_argument('--pesagem', action='append', metavar='CENARIO=E,D,T',
                   help='Balanças sob dianteira esquerda, direita e traseira, em kg')
    p.add_argument('--pesagem-inclinada', action='append', metavar='CENARIO=E,D,T,ELEVACAO_M',
                   help='Mesma pesagem com a traseira erguida; estima a altura do CG')
    p.add_argument('--exportar-csv', type=Path, help='Gravar inventário nominal no formato de inventario_massas.py')
    adicionar_saida(p)
    args = p.parse_args(argv)
    campos = {k: v for k, v in vars(args).items() if k in Hipoteses.__dataclass_fields__}
    try:
        h = replace(padrao, **campos, distancias_piloto=tuple(args.distancias)).validar()
        pesagens = ler_pesagem(args.pesagem, 3)
        inclinadas = ler_pesagem(args.pesagem_inclinada, 4)
        if set(inclinadas) - set(pesagens):
            raise ValueError('Pesagem inclinada exige a pesagem nivelada do mesmo cenário')
        dados = calcular(preparar_itens(ler_inventario(args.inventario), h), h, pesagens, inclinadas)
        if args.exportar_csv:
            exportar_csv(args.exportar_csv, dados)
        emitir(dados, 'Centro de gravidade e estabilidade', args.html)
    except (OSError, ValueError, csv.Error) as exc:
        p.error(str(exc))


if __name__ == '__main__':
    main()
