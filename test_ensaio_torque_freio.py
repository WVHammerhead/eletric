import math
import unittest
from ensaio_torque_freio import avaliar


class Equilibrio(unittest.TestCase):
    def test_torque_equilibrado_em_ambas_as_ligacoes(self):
        for f in (0, .5, 1):
            r = avaliar(551, f, .1, 132.4, 28)
            self.assertAlmostEqual(r['torque_eixo_Nm']+r['torque_ancoragem_Nm'], 551)
            self.assertAlmostEqual(r['forca_tangencial_ancora_N']*.1, r['torque_ancoragem_Nm'])

    def test_caminhos_extremos_e_diametro(self):
        livre = avaliar(551, 0, .1, 132.4, 28)
        preso = avaliar(551, 1, .1, 132.4, 28)
        maior = avaliar(551, 1, .1, 132.4, 25)
        self.assertEqual(livre['cisalhamento_nominal_MPa'], 0)
        self.assertGreater(preso['von_mises_nominal_MPa'], livre['von_mises_nominal_MPa'])
        self.assertAlmostEqual(preso['von_mises_nominal_MPa']/maior['von_mises_nominal_MPa'], (25/28)**3)

    def test_invalidos(self):
        for f in (-.1, 1.1, math.nan):
            with self.assertRaises(ValueError):
                avaliar(551, f, .1, 132.4, 28)


if __name__ == '__main__':
    unittest.main()
