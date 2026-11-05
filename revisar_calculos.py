"""Reações idealizadas de três apoios; não dimensiona estrutura ou freios.

Entradas omitidas vêm do inventário estimado (estabilidade_massas.py) e do modelo
geométrico comum. Coordenadas em metros, massa em kg.
"""
import argparse
import math

from modelo_estrutural import AVISO, FONTE, GRAVIDADE, X_EIXO_DIANT, X_EIXO_TRAS, BITOLA, corredor
from relatorio_visual import adicionar_saida, configurar_console, emitir


def valor_positivo(texto):
    try:
        valor = float(texto)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Informe um número') from exc
    if not math.isfinite(valor) or valor <= 0:
        raise argparse.ArgumentTypeError('Informe valor positivo e finito')
    return valor


def calcular_reacoes(massa, eixo_dianteiro, eixo_traseiro, cg_x, cg_altura, bitola):
    valores = (massa, eixo_dianteiro, eixo_traseiro, cg_x, cg_altura, bitola)
    if not all(math.isfinite(v) for v in valores) or min(massa, cg_altura, bitola) <= 0:
        raise ValueError('Entradas devem ser finitas; massa, altura e bitola positivas')
    if not 0 <= eixo_dianteiro < cg_x < eixo_traseiro:
        raise ValueError('Exige 0 ≤ eixo dianteiro < CG < eixo traseiro')
    comprimento = eixo_traseiro-eixo_dianteiro
    d = cg_x-eixo_dianteiro
    tolerancia = massa * 1e-12  # Resíduo de ponto flutuante não representa contato.
    resultados = {}
    for nome, kx, ky in [('estatico', 0, 0), ('acelera_0_2g', .2, 0), ('freia_0_8g', -.8, 0),
                         ('curva_0_5g', 0, .5), ('freia_0_8g_e_curva_0_5g', -.8, .5)]:
        traseira = massa*(d+cg_altura*kx)/comprimento
        dianteira = massa-traseira
        delta = massa*cg_altura*ky/bitola
        reacoes = {'dianteira_interna': dianteira/2-delta,
                   'dianteira_externa': dianteira/2+delta, 'traseira': traseira}
        resultados[nome] = {
            'reacoes_kgf': reacoes,
            'reacoes_N': {k: v*GRAVIDADE for k,v in reacoes.items()},
            'tolerancia_numerica_kgf': tolerancia,
            'todas_rodas_em_contato_no_modelo': all(v > tolerancia for v in reacoes.values()),
            'rodas_sem_carga_positiva': [k for k,v in reacoes.items() if v <= tolerancia],
        }
    return resultados


def main(argv=None):
    configurar_console()
    parser = argparse.ArgumentParser(description=__doc__)
    for nome, ajuda in [('massa', 'massa total em kg'), ('eixo-dianteiro', 'x dianteiro em m'),
                        ('eixo-traseiro', 'x traseiro em m'), ('cg-x', 'x do CG em m'),
                        ('cg-altura', 'altura do CG em m'), ('bitola', 'bitola dianteira em m')]:
        parser.add_argument('--'+nome, type=float if nome in ('eixo-dianteiro', 'cg-x') else valor_positivo,
                            help=ajuda + ' (padrão: inventário estimado ou modelo comum)')
    adicionar_saida(parser)
    args = parser.parse_args(argv)
    entradas = {k: v for k,v in vars(args).items() if k != 'html'}
    origem = 'argumentos'
    try:
        for chave, valor in (('eixo_dianteiro', X_EIXO_DIANT/1000), ('eixo_traseiro', X_EIXO_TRAS/1000),
                             ('bitola', BITOLA/1000)):
            if entradas[chave] is None:
                entradas[chave] = valor
        if None in (entradas['massa'], entradas['cg_x'], entradas['cg_altura']):
            from estabilidade_massas import cg_nominal  # importação tardia evita ciclo
            ref = cg_nominal()
            origem = ref['origem']
            for chave, campo in (('massa', 'massa_kg'), ('cg_x', 'cg_x_m'), ('cg_altura', 'cg_z_m')):
                if entradas[chave] is None:
                    entradas[chave] = ref[campo]
        resultados = calcular_reacoes(**entradas)
        alertas = [f"{nome}: apoio sem carga positiva ({', '.join(res['rodas_sem_carga_positiva'])}); limite ou perda de contato."
                   for nome,res in resultados.items() if not res['todas_rodas_em_contato_no_modelo']]
        alertas.append('Modelo rígido quase-estático: não inclui aderência, vento, impacto, suspensão ou transitórios.')
        emitir({'aviso': AVISO, 'fonte_bitolas': FONTE, 'entradas': entradas, 'origem_massa_e_cg': origem,
                'cenarios': resultados, 'alertas': alertas,
                'corredor_referencia_quadro_nominal': corredor(entradas['bitola']*1000, entradas['eixo_dianteiro']*1000),
                'caminhos_de_carga': {
                    'nivel_1': 'Mangas, freios, pivôs, suportes traseiros e ancoragens → longarinas de aço.',
                    'nivel_2': 'Braços e torres triangulados; berços dos motores e bateria em aço leve.',
                    'nivel_3': 'Piso e extensão em alumínio; não substituem ancoragens de retenção.',
                    'nivel_4': 'Cabine e lona leves; não são ROPS nem recebem cargas da suspensão.'}},
               'Reações e caminhos de carga', args.html)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
