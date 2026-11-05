import unittest
from analise_interfaces_modulo import ComponenteAxial, configuracao_varredura, analisar_espacamento, verificar_montagem

class Interfaces(unittest.TestCase):
    def test_intervalo_contido_e_pares_nao_adjacentes(self):
        a=ComponenteAxial('a',0,100,'roda'); b=ComponenteAxial('b',0,8,'corrente'); c=ComponenteAxial('c',-10,2,'x')
        self.assertEqual(a.folga_para(b),-8)
        pares={(x['comp_a'],x['comp_b']) for x in analisar_espacamento([a,b,c])['interferencias']}
        self.assertTrue(any('a' in p and 'b' in p for p in pares))
    def test_referencia_de_varredura(self):
        r=analisar_espacamento(configuracao_varredura())
        pares={frozenset((x['comp_a'],x['comp_b'])):x['folga_mm'] for x in r['interferencias']}
        self.assertEqual(pares[frozenset(('Corrente #428','Espaçador do cubo'))],-8)
        self.assertEqual(pares[frozenset(('Tambor freio Ø130mm','Rolamento interno roda'))],-12.5)
        self.assertEqual(r['resumo']['dist_rolamentos_mm'],200)
        self.assertTrue(all('INDEFINIDO' in e['status'] for e in verificar_montagem(configuracao_varredura())['sequencia_montagem']))
if __name__=='__main__': unittest.main()
