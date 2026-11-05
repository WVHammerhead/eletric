"""Cobertura específica do projeto: dois ocupantes, baixa velocidade, estacionamento e manobra.

Os números de referência vêm dos próprios dados do projeto (PADRAO_MODULO_BIZ, bateria, base adotada).
Qualquer mudança que quebre um destes testes é uma mudança de requisito a revisar, não só de código.

Executar: python -B -m unittest -v test_dois_ocupantes_baixa_velocidade
"""
import copy
import math
import unittest
from dataclasses import replace

from cinematica_dianteira import GeometriaSuspensao, calcular_ackermann
from configuracoes import base, cg_da_base
from estabilidade_massas import (Hipoteses, estabilidade, ler_inventario, montar, ocupantes_sentados,
                                 preparar_itens)
from transmissao_dianteira import PADRAO_MODULO_BIZ, calcular_modulo_biz

G = 9.80665
MASSA_OCUPANTE_KG = 65.0
META_VELOCIDADE_KMH = 50.0          # meta de PICO (2026-11-05): 50 km/h só em pico
PROJETO_CONTINUO_KMH = 35.0         # velocidade contínua de projeto (2026-11-05)
LIMITE_VERIFICACAO_KMH = 40.0       # limite contínuo a verificar (modelos divergem por perdas)
POTENCIA_CONTINUA_W = 1500.0        # limite contínuo adotado da bateria/controladores
ENERGIA_BATERIA_WH = 25.6 * 100.0    # 2,56 kWh (ficha FLA24100-EU)


def _estado_da_base(nome='p2_dorsal', massa_ocupantes_kg=None):
    """Itens, referência e limiares estáticos da base, com a posição dos motores do módulo."""
    h, caminho = base(nome)
    if massa_ocupantes_kg is not None:
        h = replace(h, massa_pessoa=massa_ocupantes_kg)
    itens = preparar_itens(ler_inventario(caminho), h)
    return h, itens


def _resultado_estatico(h, itens):
    return estabilidade(montar(itens, 'sentado', ocupantes_sentados(h, h.distancia_nominal)), h)


def _potencia_bateria_w(v_kmh, massa_kg, cfg):
    """Potência drenada da bateria (W) para manter v_kmh em plano, com a cadeia de eficiências do projeto."""
    v = v_kmh / 3.6
    vei = cfg['veiculo']
    F = massa_kg * G * vei['rolamento'] + 0.5 * vei['densidade_ar'] * vei['cda_m2'] * v * v
    eta = vei['rendimento_corrente'] * vei['rendimento_juntas'] * vei['rendimento_controlador']
    return F * v / eta


class BaixaVelocidade(unittest.TestCase):
    def test_curva_de_baixa_velocidade_fica_abaixo_do_tombamento(self):
        """20 km/h em curva de 8 m (dados do projeto) não pode passar do limiar lateral da base."""
        h, itens = _estado_da_base()
        limiar = _resultado_estatico(h, itens)['limite_tombamento_lateral_g']
        vei = PADRAO_MODULO_BIZ['veiculo']
        a_g = (vei['velocidade_curva_kmh'] / 3.6) ** 2 / (vei['raio_curva_m'] * G)
        self.assertLess(a_g, limiar)
        self.assertLess(a_g, 0.5 * limiar)      # margem: metade do limiar, para dinâmica e pneu não ideal

    @unittest.expectedFailure
    def test_pico_atinge_a_meta_de_50_kmh(self):
        """Lacuna conhecida: com a ficha de 2500 W, o pico modelado não chega a 50 km/h (ver Decisao_modulo_biz.md).
        Se passar a valer, o unittest acusa 'unexpected success' e a expectativa deve ser revisada."""
        t = calcular_modulo_biz()['torque']
        self.assertGreaterEqual(t['velocidade_max_plano_pico_kmh'], META_VELOCIDADE_KMH)

    def test_pico_modelado_fica_perto_da_meta_de_50_kmh(self):
        t = calcular_modulo_biz()['torque']
        self.assertGreater(t['velocidade_max_plano_pico_kmh'], 47.0)
        self.assertLess(t['velocidade_max_plano_pico_kmh'], META_VELOCIDADE_KMH)

    def test_velocidade_continua_fica_abaixo_da_meta_de_50_kmh(self):
        t = calcular_modulo_biz()['torque']
        self.assertLess(t['velocidade_max_plano_continua_kmh'], META_VELOCIDADE_KMH)

    def test_projeto_continuo_35_kmh_cabe_no_modelo_de_motor(self):
        t = calcular_modulo_biz()['torque']
        self.assertGreaterEqual(t['velocidade_max_plano_continua_kmh'], PROJETO_CONTINUO_KMH)

    def test_40_kmh_fica_no_limite_do_modelo_de_motor(self):
        """Modelo de motor e transmissão: limite contínuo abaixo de 40 km/h (perdas no motor)."""
        t = calcular_modulo_biz()['torque']
        self.assertLess(t['velocidade_max_plano_continua_kmh'], LIMITE_VERIFICACAO_KMH)

    def test_potencia_simples_em_35_kmh_e_40_kmh(self):
        """Modelo simples de energia: 35 km/h abaixo de 1500 W; 40 km/h perto do limite."""
        h, itens = _estado_da_base()
        massa = _resultado_estatico(h, itens)['massa_kg']
        self.assertLess(_potencia_bateria_w(35.0, massa, PADRAO_MODULO_BIZ), POTENCIA_CONTINUA_W)
        self.assertGreater(_potencia_bateria_w(40.0, massa, PADRAO_MODULO_BIZ), 1400.0)

    def test_45_e_50_kmh_excedem_1500_w_continuos(self):
        h, itens = _estado_da_base()
        massa = _resultado_estatico(h, itens)['massa_kg']
        self.assertGreater(_potencia_bateria_w(45.0, massa, PADRAO_MODULO_BIZ), POTENCIA_CONTINUA_W)
        self.assertGreater(_potencia_bateria_w(50.0, massa, PADRAO_MODULO_BIZ), POTENCIA_CONTINUA_W)

    def test_modelo_simples_superestima_o_limite_por_perdas_do_motor(self):
        """Na velocidade-limite do modelo de motor, o modelo simples ainda acusa folga: a diferença são perdas."""
        h, itens = _estado_da_base()
        massa = _resultado_estatico(h, itens)['massa_kg']
        v_motor = calcular_modulo_biz()['torque']['velocidade_max_plano_continua_kmh']
        self.assertLess(_potencia_bateria_w(v_motor, massa, PADRAO_MODULO_BIZ), POTENCIA_CONTINUA_W)

    def test_energia_em_35_kmh_deixa_margem_para_1_hora(self):
        h, itens = _estado_da_base()
        massa = _resultado_estatico(h, itens)['massa_kg']
        kwh_por_hora = _potencia_bateria_w(35.0, massa, PADRAO_MODULO_BIZ) / 1000.0
        self.assertLess(kwh_por_hora, ENERGIA_BATERIA_WH / 1000.0)

    def test_arrancada_nao_limitada_pela_aderencia_com_dois_ocupantes(self):
        t = calcular_modulo_biz()['torque']
        self.assertFalse(t['arrancada_limitada_pela_aderencia'])
        self.assertLess(t['forca_arrancada_N'], t['limite_aderencia_N'])

    def test_autonomia_em_25_kmh_na_ordem_de_grandeza(self):
        """Autonomia pela energia da ficha e pela potência em 25 km/h (dois ocupantes, massa da base)."""
        h, itens = _estado_da_base()
        massa = _resultado_estatico(h, itens)['massa_kg']
        p_bat = _potencia_bateria_w(25.0, massa, PADRAO_MODULO_BIZ)
        autonomia_km = ENERGIA_BATERIA_WH / p_bat * 25.0
        self.assertGreater(autonomia_km, 50.0)
        self.assertLess(autonomia_km, 300.0)

    def test_um_ocupante_a_menos_reduz_a_potencia_necessaria(self):
        """Sensibilidade: tirar o passageiro (65 kg) reduz a potência drenada em 25 km/h."""
        h, itens = _estado_da_base()
        massa_dois = _resultado_estatico(h, itens)['massa_kg']
        massa_um = massa_dois - MASSA_OCUPANTE_KG
        self.assertLess(_potencia_bateria_w(25.0, massa_um, PADRAO_MODULO_BIZ),
                        _potencia_bateria_w(25.0, massa_dois, PADRAO_MODULO_BIZ))

    def test_um_ocupante_a_menos_aumenta_a_velocidade_maxima(self):
        cfg_um = copy.deepcopy(PADRAO_MODULO_BIZ)
        h, itens = _estado_da_base()
        massa_dois = _resultado_estatico(h, itens)['massa_kg']
        cfg_um['veiculo']['massa_kg'] = massa_dois - MASSA_OCUPANTE_KG
        dois = calcular_modulo_biz()['torque']['velocidade_max_plano_pico_kmh']
        um = calcular_modulo_biz(cfg_um)['torque']['velocidade_max_plano_pico_kmh']
        self.assertGreaterEqual(um, dois)


class DoisOcupantes(unittest.TestCase):
    def test_massa_de_ocupantes_entra_no_total(self):
        h, itens = _estado_da_base()
        r = _resultado_estatico(h, itens)
        sem_ocupantes = sum(i['massa_kg'] for i in itens if i['estado'] not in ('pendente', 'ausente')
                            and i['cenario'] in ('todos', 'sentado'))
        self.assertAlmostEqual(r['massa_kg'] - sem_ocupantes, 2 * MASSA_OCUPANTE_KG, delta=0.5)

    def test_reacao_traseira_estatica_cabe_no_pneu_80_90_17(self):
        """Índice 44 do 80/90-17 = 160 kg. Dois ocupantes na base adotada."""
        h, itens = _estado_da_base()
        traseira = _resultado_estatico(h, itens)['reacoes_kgf']['traseira']
        self.assertLess(traseira, 160.0)

    def test_traseira_nao_levanta_em_rampa_de_descida_20_pct(self):
        h, itens = _estado_da_base()
        r = _resultado_estatico(h, itens)
        self.assertGreater(r['traseira_rampa_20pct_nariz_baixo_kgf'], 0.0)

    def test_freio_so_traseiro_retem_rampa_de_20_pct_so_com_mu_07(self):
        """Registro do modelo: freio só na traseira retém 12,7° com μ = 0,7 (acima dos 11,3° da rampa de 20 %).
        Com μ menor o resultado muda; o projeto mantém freio nas dianteiras por essa dependência (Configuracao_atual.md)."""
        h, itens = _estado_da_base()
        retencao = _resultado_estatico(h, itens)['retencao_freio_so_traseiro_graus_mu07']
        self.assertGreater(retencao, math.degrees(math.atan(0.2)))
        self.assertLess(retencao, 20.0)

    def test_passageiro_desloca_o_cg_para_tras_do_piloto(self):
        h, itens = _estado_da_base()
        r = _resultado_estatico(h, itens)
        piloto, passageiro = ocupantes_sentados(h, h.distancia_nominal)
        self.assertGreater(passageiro['x_m'], piloto['x_m'])


class Manobra(unittest.TestCase):
    def test_raio_externo_com_6_graus_de_esterco_registrado(self):
        """Consequência registrada do limite de 6° (Decisao_modulo_biz.md): raio externo entre 18 e 23 m."""
        a = calcular_ackermann(GeometriaSuspensao(bitola_mm=1420.0, x_traseiro_mm=2615.0), 6.0)
        self.assertGreater(a['raio_giro_minimo_externo_m'], 18.0)
        self.assertLess(a['raio_giro_minimo_externo_m'], 23.0)

    def test_esterco_interno_maior_que_externo_em_ackermann(self):
        a = calcular_ackermann(GeometriaSuspensao(bitola_mm=1420.0, x_traseiro_mm=2615.0), 6.0)
        self.assertLess(a['esterco_roda_externa_ackermann_graus'], a['esterco_roda_interna_graus'])


class Base(unittest.TestCase):
    def test_base_p2_cg_e_massa_coerentes_com_o_cadastro(self):
        ref = cg_da_base('p2_dorsal')
        self.assertGreater(ref['massa_kg'], 350.0)
        self.assertLess(ref['massa_kg'], 450.0)
        self.assertGreater(ref['cg_x_m'], 1.0)
        self.assertLess(ref['cg_z_m'], 0.7)


if __name__ == '__main__':
    unittest.main()
