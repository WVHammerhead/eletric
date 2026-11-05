"""Varredura sintética de reações no cubo; não dimensiona nem aprova rolamentos.

Convenção: eixo dos rolamentos em y, contato no plano médio da roda, raio em z.
Suportes rígidos, dois apoios simétricos; força axial integralmente em um apoio.
Nenhum dado de catálogo ou geometria real é inferido. Ver RELATORIO_ROLAMENTOS.md.
"""
import argparse
import csv
import math
from pathlib import Path

from ensaio import Balanca, cargas_nas_rodas, referencia_veiculo
from modelo_estrutural import GRAVIDADE

RAIZ = Path(__file__).resolve().parent


def reacoes(fx, fy, fz, raio_m, espacamento_m):
    """Equilíbrio do cubo: reações radiais (x,z) e impulso axial (y).

    Momento devido à força lateral é resistido por par vertical; momento de
    frenagem em torno de y é transmitido ao freio, não por este modelo.
    Retorna módulos radiais dos apoios; não define qual recebe carga axial.
    """
    if espacamento_m <= 0 or raio_m <= 0:
        raise ValueError('Raio e espaçamento devem ser positivos')
    par = fy * raio_m / espacamento_m
    return tuple(math.hypot(fx / 2, fz / 2 + sinal * par) for sinal in (-1, 1))


def gerar(espacamentos=(40, 100, 150, 200, 250, 300)):
    h, ref = referencia_veiculo()
    b = Balanca()
    # 80/100-14 nominal; o raio real carregado e a posição do contato devem ser medidos.
    raio = (14 * 25.4 + 2 * 80) / 2000
    linhas = []
    for lateral in (0.0, 0.4, 0.6, 0.8, 0.9):
        for freio in (0.0, 0.4):
            for impacto in (1.0, 2.0):
                for lado, c in cargas_nas_rodas(lateral, freio, impacto, b, h, ref).items():
                    for espaco in espacamentos:
                        r = reacoes(c['Fx_N'], c['Fy_N'], c['Fz_N'], raio, espaco / 1000)
                        for axial_em in (0, 1):
                            # Coeficientes ilustrativos: NÃO são fatores de catálogo.
                            p0 = max(max(r), max(0.6*r[i] + 0.5*(abs(c['Fy_N']) if i == axial_em else 0) for i in (0, 1)))
                            linhas.append(dict(lateral_g=lateral, freio_g=freio, impacto_vertical=impacto,
                                roda=lado, espacamento_mm=espaco, apoio_axial=axial_em+1,
                                fx_N=c['Fx_N'], fy_N=c['Fy_N'], fz_N=c['Fz_N'],
                                radial_1_N=r[0], radial_2_N=r[1], axial_N=abs(c['Fy_N']),
                                uso_radial_referencia_500kgf=max(r)/(500*GRAVIDADE),
                                p0_ilustrativo_N=p0, c0_ilustrativo_2x_N=2*p0,
                                saturacao_pneu=c['pneu_satura'], tres_contatos=c['tres_contatos'],
                                excede_aderencia_global=c['excede_aderencia_global']))
    return ref, linhas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=RAIZ/'dados_sinteticos_rolamentos.csv')
    args = parser.parse_args()
    ref, linhas = gerar()
    with args.csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=linhas[0].keys(), delimiter=';')
        w.writeheader()
        w.writerows(linhas)
    print(f"Massa estimada: {ref['massa_kg']:.1f} kg. {len(linhas)} linhas: {args.csv}")
    for d in (40, 100, 150, 200, 250, 300):
        # Só cenários onde o modelo mantém os três contatos e não reporta saturação.
        ok = [x for x in linhas if x['espacamento_mm'] == d and x['tres_contatos']
              and not x['saturacao_pneu'] and not x['excede_aderencia_global']]
        if ok:
            p = max(ok, key=lambda x: x['p0_ilustrativo_N'])
            print(f"{d:3} mm: P0 ilustrativo {p['p0_ilustrativo_N']/1000:.2f} kN; "
                  f"C0 ilustrativo com fator 2: {p['c0_ilustrativo_2x_N']/1000:.2f} kN; "
                  f"caso {p['lateral_g']} g / freio {p['freio_g']} g / impacto {p['impacto_vertical']}x")
    print('Triagem sintética: coeficientes e fator ilustrativos, não selecionar peças por estes valores.')


if __name__ == '__main__':
    main()
