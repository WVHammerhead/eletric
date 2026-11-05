import unittest
from reforco_haste import haste_sozinha, com_borracha, com_camisa


class TestReforco(unittest.TestCase):
    def test_haste_sozinha_reprova(self):
        self.assertAlmostEqual(haste_sozinha(1.5)['FS'], 0.51, delta=0.01)
        self.assertLess(haste_sozinha(2.0)['FS'], 1.0)

    def test_borracha_nao_reforca(self):
        for e in (3, 6):
            self.assertLess(com_borracha(2.0, e)['ganho_EI_pct'], 0.1)

    def test_camisa_acoplada_passa(self):
        self.assertAlmostEqual(com_camisa(1.5, 34, 3)['FS'], 1.99, delta=0.02)
        self.assertGreater(com_camisa(1.5, 32, 3)['FS'], 1.3)

    def test_camisa_sem_acoplamento_nao_ajuda(self):
        self.assertAlmostEqual(com_camisa(1.5, 34, 3, acoplada=False)['FS'], haste_sozinha(1.5)['FS'], places=6)


if __name__ == '__main__':
    unittest.main()


class TestAdotado(unittest.TestCase):
    def test_valores(self):
        from reforco_haste import adotado
        a = adotado(1.5)
        self.assertAlmostEqual(a['M_grampo_Nm'], 490, delta=1)
        self.assertAlmostEqual(a['FS_camisa'], 1.85, delta=0.02)
        self.assertAlmostEqual(a['pressao_bucha_MPa'], 2.4, delta=0.1)
        self.assertGreater(adotado(2.0)['FS_camisa'], adotado(1.5)['FS_camisa'])
        self.assertAlmostEqual(a['comprimento_camisa_reforco_mm'], 295)


if __name__ == '__main__':
    unittest.main()
