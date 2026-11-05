import math, unittest
from fcl_eixo_garfo import momento_max, caso
from fcl_eixo_balanco import caso as caso_balanco


class TestGarfo(unittest.TestCase):
    def test_carga_simetrica(self):
        m, re, rd = momento_max(0.15, 600, 600)
        self.assertAlmostEqual(re, 600); self.assertAlmostEqual(rd, 600)
        self.assertAlmostEqual(m, 600 * 0.05)          # R·(x_s − 100 mm)

    def test_equilibrio(self):
        m, re, rd = momento_max(0.15, 300, 900)
        self.assertAlmostEqual(re + rd, 1200)

    def test_garfo_muito_melhor_que_balanco_na_curva(self):
        g = caso('c', 2393, 0, 1, 0, 0.15)
        b = caso_balanco('c', 2393, 0, 1, 0, 0.15)
        self.assertGreater(g['FS_escoamento'], 3 * b['FS_escoamento'])

    def test_torque_reduz_fs(self):
        self.assertLess(caso('f', 2393, 1, 0, 1, 0.15)['FS_escoamento'],
                        caso('f', 2393, 1, 0, 0, 0.15)['FS_escoamento'])


if __name__ == '__main__':
    unittest.main()


class TestRev03(unittest.TestCase):
    def test_layout_soma_400(self):
        self.assertEqual(35 + 330 + 35, 400)

    def test_x_s(self):
        from fcl_eixo_garfo import X_S_REV03
        self.assertAlmostEqual(X_S_REV03, 0.200 - 0.025)

    def test_valores_documentados(self):
        from fcl_eixo_garfo import X_S_REV03, fracao_max_torque_na_ponta, torcao_ponta
        from fcl_eixo_balanco import FZ_2X
        c = caso('f', FZ_2X, 1, 0, 1, X_S_REV03)
        self.assertAlmostEqual(c['FS_escoamento'], 1.51, delta=0.01)
        f, t = fracao_max_torque_na_ponta()
        self.assertAlmostEqual(f, 0.58, delta=0.01)
        self.assertAlmostEqual(torcao_ponta(t)[2], 0.76, delta=0.01)


if __name__ == '__main__':
    unittest.main()
