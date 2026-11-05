"""Fonte comum das hipóteses D-4 a D-7 e da hierarquia de bitolas.

Unidades geométricas em mm, massas em kg. Seções ideais, sem raios de
canto, furos ou tolerâncias. Candidatos não constituem dimensionamento.
"""
from dataclasses import dataclass
import math

FONTE = "bitolas_e_hierarquia_estrutural.md"
ACO, ALUMINIO, INDEFINIDO, INTERFACE = "#1F4E8C", "#3FA34D", "#F2C230", "#D32F2F"
GRAVIDADE = 9.80665
PNEU_DIANT = ("90/90-14", 14, 90, 90)
PNEU_TRAS = ("70/90-17", 17, 70, 90)
X_EIXO_DIANT, X_EIXO_TRAS, X_FRENTE_TRAP = 600, 2515, 441
FIM_LEITO, FOLGA_RODA, L_TRAP_MIN = 2565, 25, 1750
MARGEM_NOMINAL_PISO_MM, TOLERANCIA_EXECUCAO_ASSUMIDA_MM = 20, 8
PISO_ESTRUTURAL_Z_MM, EVA_PISO_MM = 285, 10
Z_SUPERFICIE_UTIL_MM = PISO_ESTRUTURAL_Z_MM + EVA_PISO_MM
LARGURA_CARROCERIA_DIANTEIRA = 1640  # D-11, sem retrovisores; não é bitola
BITOLA = 1338
TETO, ASSENTO, ALTURA_SENTADO = 1560, 327.495493, 910
CURSO_MIN, CURSO_MAX, FOLGA_PNEU_MIN, FOLGA_PNEU_MAX = 80, 100, 30, 50
AVISO = ("Anteprojeto: geometria nominal e perfis candidatos, sem liberação de corte "
         "ou comprovação de resistência. Massas parciais não incluem uniões, "
         "travessas, suspensão, motores, bateria ou ocupantes.")


def diametro(aro, secao, perfil):
    return aro * 25.4 + 2 * secao * perfil / 100


@dataclass(frozen=True)
class Perfil:
    nome: str
    material: str
    largura: float
    altura: float
    parede: float
    redondo: bool = False

    def __post_init__(self):
        medidas = (self.largura, self.altura, self.parede)
        if not all(math.isfinite(v) and v > 0 for v in medidas):
            raise ValueError("Dimensões do perfil devem ser positivas e finitas")
        if 2 * self.parede >= min(self.largura, self.altura):
            raise ValueError("Parede deve preservar o vazio interno")
        if self.material not in ("aço", "alumínio"):
            raise ValueError("Material sem densidade cadastrada")
        if self.redondo and self.largura != self.altura:
            raise ValueError("Perfil redondo exige diâmetros iguais")

    @property
    def area_mm2(self):
        b, h, t = self.largura, self.altura, self.parede
        if self.redondo:
            return math.pi * (b**2 - (b - 2*t)**2) / 4
        return b*h - (b - 2*t)*(h - 2*t)

    @property
    def inercia_mm4(self):
        b, h, t = self.largura, self.altura, self.parede
        if self.redondo:
            return math.pi * (b**4 - (b - 2*t)**4) / 64
        return (b*h**3 - (b - 2*t)*(h - 2*t)**3) / 12

    @property
    def kg_m(self):
        return self.area_mm2 * (7850 if self.material == "aço" else 2700) / 1e6


LONGARINA = Perfil("80 × 80 × 3", "aço", 80, 80, 3)
PISO = Perfil("80 × 40 × 2", "alumínio", 80, 40, 2)
CABINE = Perfil("30 × 30 × 2", "alumínio", 30, 30, 2)
DIAGONAL_ACO = Perfil("Ø 22,2 × 1,5", "aço", 22.2, 22.2, 1.5, True)
DIAGONAL_AL = Perfil("Ø 22,2 × 1,5", "alumínio", 22.2, 22.2, 1.5, True)

# Uma linha por função: C01, C09 e C11 contêm mais de um nível.
HIERARQUIA = (
    (1, "C01/C02 · P4", "Longarinas contínuas", "Aço 80 × 80 × 3", "Estoque; duas peças inteiras"),
    (1, "C01 · P4", "Travessas principais", "Aço 60 × 40 × 2,65 ou 50 × 50 × 3", "80 × 80 apenas em segmento curto de nó crítico"),
    (1, "C03/C07 · P5/P11", "Mangas, pivôs, freios e batentes", "Aço: chapas 4,75–6,35; buchas ≥ 3", "Batente amortecido; cisalhamento duplo"),
    (1, "C05 · P1", "Suportes das duas hastes traseiras", "Aço: paredes 4,75–6,35; reforços 3–4,75", "Verificar flexão lateral, torção e fadiga"),
    (1, "C10/C11 · P2/P2b/P10", "Retenção de banco, cintos e bateria", "Aço: chapas 3–4,75", "Cargas diretamente no quadro de aço"),
    (2, "C03 · P5", "Braços superiores / inferiores", "Aço Ø 22,2 × 2 / Ø 25,4 × 2,65", "Pivôs sob/dentro do quadro; verificar curso e esterço"),
    (2, "C04 · P5", "Torres dos quatro amortecedores", "Aço Ø 25,4 × 2; orelhas 3–4,75", "Trianguladas; olhais em cisalhamento duplo"),
    (2, "C06 · P3", "Berços dos quatro motores", "Aço 25 × 25 × 2 ou chapa U 2,65–3", "Motores na massa suspensa; dois circuitos de corrente"),
    (2, "C01", "Travessas intermediárias", "Aço 40 × 40 × 2 ou Ø 31,8 × 2", "Sob o piso; não apoiam a bateria"),
    (2, "C11 · P10 · D-10", "Berço elevado da bateria na cunha", "Aço: pernas 30 × 30 × 2, cesto L 30 × 30 × 3, diagonais Ø 22,2 × 2", "Pés com 2 × M10 8.8 e bucha; 2 cintas 25 × 3 com 4 × M8 8.8"),
    (2, "C12/C13 · P6", "Bases da cabine e nós de lona", "Aço: luvas 2–2,65 e bases 3", "Nós ligados ao quadro; interfaces isoladas"),
    (3, "C08 · P8", "14 barras de piso", "Alumínio 80 × 40 × 2 deitado", "Buchas internas, arruelas largas e isolamento"),
    (3, "C09 · P8", "Longarinas da extensão elevada", "Alumínio 80 × 40 × 2", "Duas sobras do piso; apoios ainda a dimensionar"),
    (4, "C09 · D-4", "Travessas da extensão / parede reta", "Alumínio 30 × 30 × 2 / 25 × 25 × 1,5", "Chapa 1,2–1,5 e EVA na parede; sem rampa"),
    (4, "C12 · P6", "Quatro colunas, teto e molduras", "Alumínio 30 × 30 × 2 ou 40 × 20 × 2", "Alternativa Ø 28,6 × 2; cobertura não é ROPS"),
    (4, "C13 · P6", "Duas barras traseiras de lona", "Alumínio Ø 25,4 × 2 ou 30 × 30 × 2", "x = 2615; comprimento ainda a definir"),
    (4, "C14 · P7/P9", "Capô, luzes e suportes de tecido", "Alumínio Ø 12–16 × 1,5 ou chata 20 × 3", "Suporte leve; lentes não recebem carga de lona"),
    (0, "A definir", "Diagonal superior separada", "Aço ou alumínio Ø 22,2 × 1,5", "Escolha depende da função; não usar 80 × 80 por padrão"),
)


def largura_quadro(x):
    comprimento = X_EIXO_TRAS - diametro(*PNEU_TRAS[1:])/2 - X_FRENTE_TRAP
    return 1000 - 480 * (x - X_FRENTE_TRAP) / comprimento


def geometria():
    inicio_roda = X_EIXO_TRAS - diametro(*PNEU_TRAS[1:])/2
    comprimento = inicio_roda - X_FRENTE_TRAP
    util = comprimento - FOLGA_RODA
    declive = 240 / comprimento
    return {
        "inicio_piso_mm": X_FRENTE_TRAP,
        "eixo_traseiro_hipotetico_mm": X_EIXO_TRAS,
        "inicio_estatico_roda_mm": inicio_roda,
        "comprimento_trecho_trapezoidal_mm": comprimento,
        "comprimento_util_com_folga_mm": util,
        "margem_sobre_o_minimo_mm": util - L_TRAP_MIN,
        "margem_apos_tolerancia_assumida_mm": util - L_TRAP_MIN - TOLERANCIA_EXECUCAO_ASSUMIDA_MM,
        "piso_estrutural_z_mm": PISO_ESTRUTURAL_Z_MM,
        "eva_piso_mm": EVA_PISO_MM,
        "superficie_util_z_mm": Z_SUPERFICIE_UTIL_MM,
        "area_util_eva_m2": ((1000 + 1000 - 480 * util / comprimento) / 2) * util / 1e6,
        "bordas_trecho_trapezoidal_mm": [1000, 520],
        "fim_leito_hipotetico_mm": FIM_LEITO,
        "extensao_leve_mm": FIM_LEITO - inicio_roda,
        "comprimento_total_leito_mm": FIM_LEITO - X_FRENTE_TRAP,
        "borda_geometrica_mm": math.hypot(comprimento, 240),
        "angulo_planta_graus": math.degrees(math.atan(declive)),
        "largura_externa_prolongada_no_eixo_mm": largura_quadro(X_EIXO_TRAS),
        "longarina_prolongada_mm": math.hypot(X_EIXO_TRAS-X_FRENTE_TRAP, declive*(X_EIXO_TRAS-X_FRENTE_TRAP)),
        "espacamento_livre_piso_mm": (util - 14 * PISO.largura)/13,
    }


def barras_piso():
    passo = PISO.largura + geometria()["espacamento_livre_piso_mm"]
    return [{"barra": i+1, "x_mm": X_FRENTE_TRAP+i*passo,
             "comprimento_mm": largura_quadro(X_FRENTE_TRAP+i*passo)} for i in range(14)]


def massas_parciais():
    g = geometria()
    aco = 2*g["longarina_prolongada_mm"]/1000*LONGARINA.kg_m
    piso = sum(b["comprimento_mm"] for b in barras_piso())/1000*PISO.kg_m
    return {"duas_longarinas_kg": aco, "14_barras_piso_kg": piso,
            "subtotal_quadro_e_piso_kg": aco+piso,
            "duas_longarinas_extensao_kg": 2*g["extensao_leve_mm"]/1000*PISO.kg_m}


def corredor(bitola_mm=BITOLA, eixo_mm=X_EIXO_DIANT):
    if not math.isfinite(bitola_mm) or bitola_mm <= 0 or not math.isfinite(eixo_mm):
        raise ValueError("Bitola deve ser positiva e coordenada deve ser finita")
    face_interna = (bitola_mm-PNEU_DIANT[2])/2
    return {"bitola_mm": bitola_mm, "corredor_na_ponta_mm": face_interna-500,
            "corredor_no_eixo_mm": face_interna-largura_quadro(eixo_mm)/2,
            "observacao": "Pneu reto em planta; não comprova espaço para suspensão, freio ou esterço."}
