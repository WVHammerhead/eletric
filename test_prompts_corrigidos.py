"""Regressões das correções dos prompts 1-6 (revisão que desmentiu o RELATORIO_CONCLUSAO_PROMPTS original)."""
import math
import unittest

import varredura_modulo_completo as v
from cabecote_pivo import geometria_caixa, verificar_passagem_perna_interna
from ensaios_sinteticos_modulo import gerar_ensaios_corrente, _elos_corrente_aberta, _diametro_primitivo
from frenagem_curva import desaceleracao_maxima, desaceleracao_maxima_em_curva, por_pneu
from percurso_um_ocupante import avaliar


class Varredura(unittest.TestCase):
    def test_folga_nao_e_dobrada(self):
        a, b = v.AABB('a', 0, 10, 0, 10, 0, 10), v.AABB('b', 20, 30, 0, 10, 0, 10)   # vão de 10 mm
        self.assertTrue(a.intercepta(b, 10.5))
        self.assertFalse(a.intercepta(b, 9.5))

    def test_balancim_tem_260_mm_entre_pivo_e_eixo(self):
        for lado in ('direito', 'esquerdo'):
            m = v.ModuloCompleto(0, 0, lado)
            bal = next(c for c in m.cilindros if c.nome.startswith('Balancim'))
            eixo = v.Ponto3D(v.X_EIXO, m.sinal_y*v.YR, v.Z_EIXO)
            self.assertAlmostEqual(bal.p1.distancia(eixo), v.BALANCIM['comprimento_pivo_eixo_mm'], places=3)

    def test_espelhamento_da_placa_do_tensor(self):
        d, e = v.ModuloCompleto(0, 0, 'direito'), v.ModuloCompleto(0, 0, 'esquerdo')
        pd = next(c for c in d.componentes if c.nome.startswith('Placa tensor'))
        pe = next(c for c in e.componentes if c.nome.startswith('Placa tensor'))
        self.assertAlmostEqual(pd.y_min, -pe.y_max)
        self.assertAlmostEqual(pd.y_max, -pe.y_min)

    def test_caixas_orientadas_giram_com_esterco(self):
        m = v.ModuloCompleto(25, 0, 'direito')
        motor = next(c for c in m.componentes if c.nome.startswith('Motor A'))
        self.assertAlmostEqual(motor.yaw, math.radians(25))

    def test_perna_interna_colide_no_nominal_e_tem_deslocamento_minimo(self):
        r = v.deslocamento_perna_interna_minimo()
        self.assertTrue(r['colide_no_nominal'])
        self.assertGreater(r['minimo_mm'], r['nominal_mm'])
        m = v.ModuloCompleto(0, 0, 'direito', deslocamento_perna_interna_mm=r['minimo_mm'])
        self.assertFalse([i for i in m.verificar_interferencias(10) if 'interna' in i['componente']
                          and i['tipo'] in ('colisao_garfo', 'folga_insuficiente_garfo')])


class Cabecote(unittest.TestCase):
    def test_geometria_da_caixa_fecha_sob_o_capo(self):
        g = geometria_caixa()
        self.assertTrue(g['ok'], g['verificacoes'])
        self.assertLessEqual(g['z_caixa_topo_mm'], v.Z_CAPO_MAX)
        self.assertEqual(g['comprimento_perna_mm'], 470.0)

    def test_passagem_da_perna_usa_modelo_3d(self):
        r = verificar_passagem_perna_interna()
        self.assertIn('AJUSTAR', r['status'])
        self.assertGreater(r['deslocamento_minimo_mm'], 175)


class Corrente(unittest.TestCase):
    def test_diametro_primitivo(self):
        self.assertAlmostEqual(_diametro_primitivo(12.7, 11), 45.1, delta=0.1)
        self.assertAlmostEqual(_diametro_primitivo(12.7, 60), 242.7, delta=0.1)

    def test_elos_plausiveis_e_sem_valores_absurdos(self):
        for e in gerar_ensaios_corrente():
            self.assertTrue(40 < e.elos_necessarios_a < 100 and 40 < e.elos_necessarios_b < 100)

    def test_sobreposicao_de_primitivos_e_sinalizada(self):
        por_curso = {e.curso_suspensao_mm: e for e in gerar_ensaios_corrente()}
        self.assertEqual(por_curso[0].fechamento_a, 'INVIAVEL')
        self.assertLess(por_curso[0].folga_dentes_a_mm, 0)
        self.assertGreater(por_curso[-40].folga_dentes_a_mm, 0)

    def test_formula_de_elos(self):
        # duas rodas iguais: N = 2L/p + Z
        self.assertAlmostEqual(_elos_corrente_aberta(254.0, 12.7, 20, 20), 2*254/12.7 + 20)


class Frenagem(unittest.TestCase):
    def test_api_antiga_preservada_e_atalho_equivalente(self):
        self.assertAlmostEqual(desaceleracao_maxima_em_curva(.8, 'proporcional', .4), desaceleracao_maxima(.8, 'proporcional', .4))

    def test_limite_mantem_pneu_traseiro_ate_1(self):
        a = desaceleracao_maxima(.8, 'proporcional', .6)
        self.assertLessEqual(por_pneu(a, .6, .8, 'proporcional')['pneus']['traseira']['utilizacao'], 1 + 1e-9)
        self.assertGreater(por_pneu(a + .02, .6, .8, 'proporcional')['pneus']['traseira']['utilizacao'], 1)

    def test_falha_unilateral_gera_guinada_com_sinais_opostos(self):
        e = por_pneu(.4, .0, .8, 'falha_esquerda')['momento_guinada_Nm']
        d = por_pneu(.4, .0, .8, 'falha_direita')['momento_guinada_Nm']
        self.assertGreater(abs(e), 0)
        self.assertAlmostEqual(e, -d, places=6)
        self.assertAlmostEqual(por_pneu(.4, .0, .8, 'igual_frente')['momento_guinada_Nm'], 0.0, places=6)


class Percurso(unittest.TestCase):
    def test_subida_acrescenta_pelo_menos_mgh(self):
        a, b = avaliar(acessorios_w=0), avaliar(acessorios_w=0, desnivel_subida_m=100)
        self.assertGreater(b['energia_viagem_wh'] - a['energia_viagem_wh'], a['massa_kg']*9.80665*100/3600)

    def test_acessorios_saem_do_orcamento_da_bateria(self):
        r = avaliar(tensao_bateria_v=50.0, limite_corrente_bateria_a=20.0)     # 1000 W
        self.assertAlmostEqual(r['limite_bateria']['disponivel_para_tracao_w'], 950.0)


if __name__ == '__main__':
    unittest.main()
