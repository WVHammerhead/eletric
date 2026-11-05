import unittest
from estacionamento_sintetico import gerar,sobrepoe,retangulo

class Estacionamento(unittest.TestCase):
    def test_contato_e_separacao(self):
        a=retangulo(0,0,0,1,1,2)
        self.assertTrue(sobrepoe(a,retangulo(2,0,0,1,1,2)))
        self.assertFalse(sobrepoe(a,retangulo(2.1,0,0,1,1,2)))
    def test_trajetoria_termina_na_vaga(self):
        resumo,linhas=gerar(angulos=(30,))
        fim=linhas[-1]
        self.assertAlmostEqual(fim['x_eixo_traseiro_m'],(4.5-2.765)/2+.35,places=4)
        self.assertAlmostEqual(fim['y_eixo_traseiro_m'],.92,places=4)
        self.assertEqual(fim['orientacao_graus'],0)
        self.assertGreater(resumo[0]['amostras_com_colisao'],0)
    def test_parametros_invalidos(self):
        for kwargs in ({'passo':0},{'angulos':(0,)},{'comprimento':1}):
            with self.assertRaises(ValueError): gerar(**kwargs)
if __name__=='__main__': unittest.main()
