import unittest

from gerador_rolamentos import gerar, reacoes


class Reacoes(unittest.TestCase):
    def test_vertical_e_momento_somam_em_um_apoio(self):
        a, b = reacoes(0, 1000, 2000, .25, .20)
        self.assertAlmostEqual(a, 250)
        self.assertAlmostEqual(b, 2250)

    def test_inverter_curva_troca_apoios(self):
        a = reacoes(500, 1000, 2000, .25, .20)
        b = reacoes(500, -1000, 2000, .25, .20)
        self.assertEqual(a, b[::-1])

    def test_grade_inclui_impacto_e_caso_adotado(self):
        _, linhas = gerar((200,))
        self.assertTrue(any(x['impacto_vertical'] == 2 and x['lateral_g'] == .8 for x in linhas))
        self.assertEqual({x['apoio_axial'] for x in linhas}, {1, 2})
        self.assertTrue(all(x['espacamento_mm'] == 200 for x in linhas))

    def test_espacamento_invalido(self):
        with self.assertRaises(ValueError):
            reacoes(0, 1, 1, .25, 0)


if __name__ == '__main__':
    unittest.main()
