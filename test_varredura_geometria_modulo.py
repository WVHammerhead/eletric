import unittest
from varredura_geometria_modulo import avaliar

class TriagemGeometria(unittest.TestCase):
    def test_arranjo_atual_e_candidato_se_diferenciam(self):
        atual=avaliar(650,530)
        candidato=avaliar(750,400)
        self.assertTrue(atual['interferencias_garfo_ajustada'])
        self.assertFalse(candidato['interferencias_garfo_ajustada'])
        self.assertNotEqual(atual['elos'],candidato['elos'])
        self.assertTrue(any(i['peca']=='balança' for i in candidato['invasoes_esterco_modelo_anterior']))

if __name__=='__main__': unittest.main()
