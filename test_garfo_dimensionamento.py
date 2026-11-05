import math, unittest
from garfo_dimensionamento import cargas_perna, casos, escolher, orelha, prop_tubo, tensao, SY


class TestGarfo(unittest.TestCase):
    def test_propriedades_tubo(self):
        A, I, W, J = prop_tubo(50.8, 3.0)
        self.assertAlmostEqual(A, 451, delta=2)
        self.assertAlmostEqual(W, 5086, delta=15)

    def test_momentos_h300(self):
        c = cargas_perna(0.30, 1, 0)
        self.assertAlmostEqual(c['M_ip'], 781, delta=3)
        self.assertAlmostEqual(cargas_perna(0.30, 0, 1)['M_op'], 574, delta=2)

    def test_tubo_adotado_h300(self):
        fs = min(SY / tensao(50.8, 3.0, c) for c in casos(0.30).values())
        self.assertAlmostEqual(fs, 2.21, delta=0.02)

    def test_tubo_minimo_cresce_com_h(self):
        a = escolher(0.25)[0][0]; b = escolher(0.35)[0][0]
        self.assertLessEqual(a, b)

    def test_orelha(self):
        o = orelha()
        self.assertAlmostEqual(o['pressao_furo_MPa'], 5.4, delta=0.1)
        self.assertAlmostEqual(o['pre_carga_min_axial_kN'], 6.4, delta=0.1)


if __name__ == '__main__':
    unittest.main()
