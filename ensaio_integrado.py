"""Triagem sintética integrada. Não é dimensionamento nem aprovação para uso."""
import csv
import json
import math
from pathlib import Path

from configuracoes import base
from estabilidade_massas import estabilidade, ler_inventario, montar, ocupantes_sentados, preparar_itens
from frenagem_curva import avaliar as reacoes
from transmissao_dianteira import (PADRAO_MODULO_BIZ, mesclar, constantes_motor,
                                   calcular_corrente, Veiculo)

ROOT = Path(__file__).resolve().parent
G = 9.80665


def estado(n):
    h, arquivo = base('p2_dorsal')
    itens = preparar_itens(ler_inventario(arquivo), h)
    pessoas = ocupantes_sentados(h, h.distancia_nominal)[:n]
    return h, estabilidade(montar(itens, 'sentado', pessoas), h)


def veiculo(n):
    h, r = estado(n)
    cfg = mesclar(PADRAO_MODULO_BIZ, {'veiculo': {'massa_kg': r['massa_kg'],
        'cg_x_mm': r['cg_x_m']*1000, 'cg_z_mm': r['cg_z_m']*1000}})
    mot = constantes_motor(cfg)
    v = Veiculo(cfg, mot, calcular_corrente(cfg, mot))
    # Sobrescreve explicitamente as constantes históricas da classe com a base adotada.
    v.xf, v.xr = h.eixo_dianteiro, h.eixo_traseiro
    v.L = v.xr-v.xf
    v.r = (14*25.4+2*80)/2000  # nominal 80/100-14
    return h, r, cfg, mot, v


def potencia_cruzeiro(v, mot, velocidade, acessorios=50):
    """Motor CC idealizado: quatro motores iguais, I²R e controlador; W bateria."""
    vel = velocidade/3.6
    f = v.resistencia(vel)
    i = f*v.r/(2*v.eta*sum(mot['ke']*k for k in v.i))
    w = vel/v.r*v.i[0]
    tensao = mot['ke']*w + mot['R']*i
    potencia = 4*(mot['ke']*w*i + mot['R']*i*i)/v.v['rendimento_controlador'] + acessorios
    return potencia, i, tensao


def aceleracao(v, alvo=30, dt=.005, pico_s=15, acessorios=50):
    velocidade = tempo = 0.
    while velocidade < alvo/3.6 and tempo < 120:
        limite = (2500 if tempo < pico_s else 1500)-acessorios
        a = (v.forca(max(velocidade, .05), limite)-v.resistencia(velocidade))/(v.m*v.v['fator_inercia'])
        if a <= 0:
            return None
        passo = min(dt, pico_s-tempo) if tempo < pico_s else dt
        velocidade += a*passo
        tempo += passo
    return tempo if velocidade >= alvo/3.6 else None


def eixo(fx, fz, diametro_mm, balanco_mm=50):
    """Somente flexão Fz/Fx aplicada no plano médio a 50 mm do engaste.

    Não inclui momento de cambagem, axial, torque de freio, entalhes ou fadiga.
    É cenário simplificado, não limite superior nem projeto de eixo.
    """
    if diametro_mm <= 0 or balanco_mm <= 0:
        raise ValueError('Dimensões devem ser positivas')
    momento = math.hypot(fx, fz)*balanco_mm
    return 32*momento/(math.pi*diametro_mm**3)


def freio_reta(h, ref, desacel_g, fracao_frente, fracao_esquerda, mu=.7):
    """Demanda imposta, não capacidade do freio; guinada inicial sem contracorreção."""
    r = reacoes(desacel_g, 0, mu, ref, h)
    total = ref['massa_kg']*G*desacel_g
    esquerda = total*fracao_frente*fracao_esquerda
    direita = total*fracao_frente*(1-fracao_esquerda)
    traseira = total*(1-fracao_frente)
    demandas = [esquerda, direita, traseira]
    normais = [r[k]*G for k in ('esquerda_kgf', 'direita_kgf', 'traseira_kgf')]
    usos = [d/(mu*n) if n > 0 else float('inf') for d,n in zip(demandas,normais)]
    return max(usos), abs(direita-esquerda)*h.bitola/2


def gerar():
    linhas = []
    for n in (1, 2):
        h, ref, cfg, mot, v = veiculo(n)
        for velocidade in (25, 30, 35, 40, 45, 50):
            p, i, tensao = potencia_cruzeiro(v, mot, velocidade)
            linhas.append(dict(tipo='cruzeiro', ocupantes=n, caso=f'{velocidade} km/h',
                massa_kg=ref['massa_kg'], valor=p, unidade='W bateria', auxiliar=i,
                auxiliar_nome='corrente motor A', observacao=f'tensao motor {tensao:.1f} V; hipótese motor CC'))
        for dia in (20, 25, 28, 30):
            # 2× reação vertical estática em uma roda, não impacto validado.
            fz=ref['reacoes_kgf']['dianteira_esquerda']*G*2
            linhas.append(dict(tipo='eixo_vertical', ocupantes=n, caso=f'diametro {dia} mm',
                massa_kg=ref['massa_kg'], valor=eixo(0,fz,dia), unidade='MPa', auxiliar=fz,
                auxiliar_nome='Fz N', observacao='50 mm; somente flexao vertical; nao dimensiona'))
        for nome, frac in (('iguais', .5), ('um freio dianteiro falho', 1.0)):
            uso, yaw = freio_reta(h, ref, .3, .8, frac)
            linhas.append(dict(tipo='freio', ocupantes=n, caso=nome, massa_kg=ref['massa_kg'],
                valor=uso, unidade='demanda/aderencia', auxiliar=yaw, auxiliar_nome='guinada N m',
                observacao='0,3 g; 80% frente; mu 0,7; nao modelo de controle'))
        linhas.append(dict(tipo='aceleracao', ocupantes=n, caso='0-30 km/h', massa_kg=ref['massa_kg'],
            valor=aceleracao(v), unidade='s', auxiliar=15, auxiliar_nome='pico s',
            observacao='pico 2500 W ate 15 s; acessorios 50 W; depois 1500 W'))
    return linhas


def main():
    linhas = gerar()
    with (ROOT/'dados_ensaio_integrado.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=linhas[0].keys(), delimiter=';')
        w.writeheader(); w.writerows(linhas)
    print(json.dumps(linhas, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
