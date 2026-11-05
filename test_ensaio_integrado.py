import unittest
from ensaio_integrado import estado, veiculo, eixo, freio_reta, potencia_cruzeiro, aceleracao


class Integracao(unittest.TestCase):
    def test_base_dorsal_e_um_piloto(self):
        h, r, cfg, mot, v = veiculo(1)
        self.assertAlmostEqual(v.xr, 2.615)
        self.assertAlmostEqual(v.r, .2578)
        self.assertAlmostEqual(r['massa_kg'] + 65, estado(2)[1]['massa_kg'])

    def test_carga_vertical_produz_flexao(self):
        self.assertGreater(eixo(0, 3000, 20), 0)
        self.assertAlmostEqual(eixo(0, 3000, 20)/eixo(0, 3000, 25), (25/20)**3)

    def test_falha_unilateral_gera_guinada(self):
        h, r = estado(1)
        uso, momento = freio_reta(h, r, .3, .8, .5)
        uso_falha, momento_falha = freio_reta(h, r, .3, .8, 1.)
        self.assertAlmostEqual(momento, 0)
        self.assertGreater(momento_falha, 0)
        self.assertGreater(uso_falha, uso)

    def test_potencia_sobe_e_acessorios_somam(self):
        _, _, _, mot, v = veiculo(1)
        a = potencia_cruzeiro(v, mot, 35, 0)[0]
        self.assertAlmostEqual(potencia_cruzeiro(v, mot, 35, 50)[0]-a, 50)
        self.assertGreater(potencia_cruzeiro(v, mot, 40)[0], potencia_cruzeiro(v, mot, 35)[0])

    def test_pico_limitado_aumenta_tempo(self):
        _, _, _, _, v = veiculo(2)
        self.assertGreater(aceleracao(v, pico_s=15), aceleracao(v, pico_s=120))


if __name__ == '__main__':
    unittest.main()
