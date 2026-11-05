"""Balanço sintético de torque do freio: hipótese de transmissão ao eixo.

Não identifica a ligação existente nem dimensiona uma montagem real.
"""
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def avaliar(torque_nm, fracao_eixo, raio_ancoragem_m, momento_fletor_nm, diametro_mm):
    """Estator: torque da sapata divide-se entre ancoragem e eixo por hipótese.

    Uma fração é dada como entrada, não derivada da rigidez ou do atrito.
    Tensão considera torque na mesma seção que o momento fletor nominal.
    """
    if not all(math.isfinite(x) for x in (torque_nm, fracao_eixo, raio_ancoragem_m, momento_fletor_nm, diametro_mm)):
        raise ValueError('Entradas devem ser finitas')
    if torque_nm < 0 or momento_fletor_nm < 0 or not 0 <= fracao_eixo <= 1 or raio_ancoragem_m <= 0 or diametro_mm <= 0:
        raise ValueError('Geometria, cargas ou fração inválidas')
    eixo = torque_nm*fracao_eixo
    ancora = torque_nm-eixo
    d = diametro_mm/1000
    sigma = 32*momento_fletor_nm/(math.pi*d**3)/1e6
    tau = 16*eixo/(math.pi*d**3)/1e6
    return {'torque_freio_Nm': torque_nm, 'fracao_torque_eixo': fracao_eixo,
            'torque_eixo_Nm': eixo, 'torque_ancoragem_Nm': ancora,
            'braco_ancoragem_m': raio_ancoragem_m, 'forca_tangencial_ancora_N': ancora/raio_ancoragem_m,
            'momento_fletor_Nm': momento_fletor_nm, 'diametro_mm': diametro_mm,
            'flexao_nominal_MPa': sigma, 'cisalhamento_nominal_MPa': tau,
            'von_mises_nominal_MPa': math.hypot(sigma, math.sqrt(3)*tau)}


def main():
    torque = 180*9.81*1.2*.26
    linhas = [avaliar(torque, f, .1, 180*9.81*.3/4, d)
              for d in (25, 28) for f in (0., .5, 1.)]
    with (ROOT/'dados_torque_freio_sintetico.csv').open('w', encoding='utf-8', newline='') as arquivo:
        w = csv.DictWriter(arquivo, fieldnames=linhas[0].keys(), delimiter=';')
        w.writeheader(); w.writerows(linhas)
    for r in linhas:
        print(f"Ø{r['diametro_mm']} mm; eixo {r['fracao_torque_eixo']:.0%}; "
              f"T eixo {r['torque_eixo_Nm']:.1f} N.m; VM {r['von_mises_nominal_MPa']:.1f} MPa")


if __name__ == '__main__':
    main()
