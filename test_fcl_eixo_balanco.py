import math
import unittest
from fcl_eixo_balanco import caso, FZ_ESTATICO, R, MU


class TestFCLBalanco(unittest.TestCase):
    def test_vertical_momento_no_engaste(self):
        c = caso('v', FZ_ESTATICO, 0, 0, 0, 0.13)
        self.assertAlmostEqual(c['M_engaste_Nm'], FZ_ESTATICO * 0.13, places=6)

    def test_curva_soma_overturning(self):
        c = caso('c', 1000, 0, 1, 0, 0.13)
        self.assertAlmostEqual(c['M_engaste_Nm'], 1000 * 0.13 + MU * 1000 * R, places=6)

    def test_torque_nao_altera_flexao(self):
        a = caso('f', 1000, 1, 0, 0, 0.13)
        b = caso('f', 1000, 1, 0, 1, 0.13)
        self.assertAlmostEqual(a['sigma_flexao_MPa'], b['sigma_flexao_MPa'])
        self.assertLess(b['FS_escoamento'], a['FS_escoamento'])

    def test_equilibrio_rolamentos(self):
        # sem lateral/freio: cada rolamento leva Fz/2
        c = caso('v', 1200, 0, 0, 0, 0.13)
        self.assertAlmostEqual(c['rolamento_max_N'], 600, places=6)

    def test_maior_balanco_piora(self):
        self.assertLess(caso('c', 1200, 0, 1, 0, 0.2)['FS_escoamento'],
                        caso('c', 1200, 0, 1, 0, 0.11)['FS_escoamento'])


if __name__ == '__main__':
    unittest.main()
