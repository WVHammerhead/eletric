import unittest
from cabecote_pivo import reacoes_pivo, haste, rolamento, travessa, Z_TRAVESSA, F_H
from garfo_dimensionamento import prop_tubo, tensao, casos, SY


class TestCabecote(unittest.TestCase):
    def test_altura_travessa(self):
        self.assertAlmostEqual(Z_TRAVESSA, 0.7278, places=4)

    def test_equilibrio_pivo(self):
        r = reacoes_pivo()
        self.assertAlmostEqual(r['R_inf_N'] - r['R_sup_N'], F_H, places=6)
        self.assertAlmostEqual(r['R_sup_N'], 14024, delta=5)

    def test_haste_45(self):
        s, fs = haste(45, reacoes_pivo()['M_haste_Nm'])
        self.assertAlmostEqual(fs, 1.65, delta=0.02)
        self.assertLess(haste(40, reacoes_pivo()['M_haste_Nm'])[1], 1.3)

    def test_espacamento_maior_reduz_reacao(self):
        self.assertLess(reacoes_pivo(0.15)['R_sup_N'], reacoes_pivo(0.09)['R_sup_N'])

    def test_rolamento_30209(self):
        r = reacoes_pivo()
        self.assertAlmostEqual(rolamento(r['R_inf_N'], r['Fa_N'])[1], 4.0, delta=0.1)

    def test_travessa_e_perna_adotadas(self):
        self.assertAlmostEqual(travessa(63.5, 4.0, 'curva')['FS'], 2.27, delta=0.02)
        fs = min(SY / tensao(63.5, 4.0, c) for c in casos(0.47).values())
        self.assertAlmostEqual(fs, 2.4, delta=0.02)

    def test_tubo_26_nao_serve_como_perna(self):
        for t in (2.0, 3.0, 4.0):
            self.assertLess(min(SY / tensao(26, t, c) for c in casos(0.47).values()), 1.0)


if __name__ == '__main__':
    unittest.main()
