import unittest
from braco_reacao_freio import braco, torque_projeto


class TestBraco(unittest.TestCase):
    def test_torque(self):
        self.assertAlmostEqual(torque_projeto(), 0.8 * 2393 * 0.2578, places=6)
        self.assertAlmostEqual(torque_projeto(), 494, delta=1)

    def test_forca_igual_torque_sobre_raio(self):
        r = braco(150, 100, 30, 6)
        self.assertAlmostEqual(r['F_N'], torque_projeto() / 0.150, places=6)

    def test_conceito_adotado_ok(self):
        r = braco(150, 100, 30, 6)
        self.assertTrue(r['ok'])
        self.assertAlmostEqual(r['F_N'], 3290, delta=5)
        self.assertGreater(r['FS_tracao'], 9)

    def test_raio_menor_aumenta_forca(self):
        self.assertGreater(braco(100, 100, 30, 6)['F_N'], braco(200, 100, 30, 6)['F_N'])

    def test_folga_pos_falha_dobra_fator(self):
        # um braço de dois: cada um com ~50% -> metade da força
        self.assertAlmostEqual(braco(150, 100, 30, 6, fator_folga=.5)['F_N'] * 2,
                               braco(150, 100, 30, 6)['F_N'], places=6)


if __name__ == '__main__':
    unittest.main()
