import unittest
from traseira_telescopica import (FZ_EST, FZ_2X, momento_haste, tensao_haste, l_exposto_max,
                                  rigidez_alvo, arco, pressao_bucha, SY_HASTE)


class TestTraseira(unittest.TestCase):
    def test_cargas(self):
        self.assertAlmostEqual(FZ_EST, 147 * 9.80665, places=6)
        self.assertAlmostEqual(FZ_2X, 2 * FZ_EST)

    def test_momento(self):
        f, m = momento_haste()
        self.assertAlmostEqual(f, 0.8 * FZ_2X / 2)
        self.assertAlmostEqual(m, 456, delta=1)

    def test_haste_oca_nao_passa_no_alavanca_395(self):
        _, m = momento_haste()
        for t in (2.0, 3.0, 4.0):
            self.assertLess(SY_HASTE / tensao_haste(m, parede_mm=t)[0], 1.3)
        self.assertGreater(SY_HASTE / tensao_haste(m)[0], 1.3 - 0.01)

    def test_exposto_max_cresce_com_parede(self):
        self.assertLess(l_exposto_max(3.0), l_exposto_max(4.0))
        self.assertAlmostEqual(l_exposto_max(3.0), 62, delta=2)

    def test_rigidez(self):
        r = rigidez_alvo()
        self.assertAlmostEqual(r['k_N_mm'], 30.0, delta=0.1)
        self.assertAlmostEqual(r['freq_Hz'], 2.27, delta=0.02)

    def test_arco_consistente(self):
        a = arco(20, 96, 1.0)
        k = 4 * 210e9 * (a['b_mm'] / 1000) * (a['h_mm'] / 1000)**3 / 1.0**3
        self.assertAlmostEqual(k, 20000, delta=20)
        self.assertAlmostEqual(a['F_max_N'], 1920)

    def test_bucha(self):
        self.assertAlmostEqual(pressao_bucha(1153)[1], 3.1, delta=0.1)


if __name__ == '__main__':
    unittest.main()
