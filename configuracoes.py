"""Bases comparáveis do projeto: anterior (P0), reclinada na cunha (P1) e dorsal adotada (P2).

Cada base é um par (Hipoteses, inventário CSV). Os padrões de `Hipoteses` não mudam; as bases só
os sobrescrevem. A dorsal reflete a decisão do usuário após o P2: 80/90-17, bitola 1420 mm, eixo
traseiro em 2615 mm e inventário `inventario_dorsal.csv` (encosto 45°).
"""
from dataclasses import replace
from pathlib import Path

from estabilidade_massas import INVENTARIO_PADRAO, Hipoteses, cg_nominal

RAIZ = Path(__file__).parent
INVENTARIO_DORSAL = RAIZ / 'inventario_dorsal.csv'
THETA_DORSAL = 45.
BASES = {
    'p0_ereta_cunha': (Hipoteses(massa_pessoa=65., postura='ereta_legada'), INVENTARIO_PADRAO),
    'p1_reclinada_cunha': (Hipoteses(massa_pessoa=65., postura='reclinada', theta_encosto_graus=THETA_DORSAL), INVENTARIO_PADRAO),
    'p2_dorsal': (Hipoteses(massa_pessoa=65., postura='reclinada', theta_encosto_graus=THETA_DORSAL,
                            eixo_traseiro=2.615, bitola=1.420, indice_traseiro_kg=160.), INVENTARIO_DORSAL),
}
NOMES = tuple(BASES)


def base(nome):
    if nome not in BASES:
        raise ValueError(f'Base desconhecida: {nome}; use {", ".join(NOMES)}')
    return BASES[nome]


def cg_da_base(nome, h=None, inventario=None):
    h0, caminho = base(nome)
    return cg_nominal(inventario or caminho, h or h0)


def com_bitola(nome, bitola_m):
    h, caminho = base(nome)
    return replace(h, bitola=bitola_m), caminho
