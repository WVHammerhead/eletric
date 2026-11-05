import copy
import unittest
from envelope_garfo import analisar, analisar_ajuste_corrente
from transmissao_dianteira import PADRAO_MODULO_BIZ

class EnvelopeGarfo(unittest.TestCase):
    def test_ajuste_corrente_pode_reintroduzir_interferencia(self):
        cfg = copy.deepcopy(PADRAO_MODULO_BIZ)
        cfg['corrente']['rodas'][0]['x'] = 700
        cfg['corrente']['rodas'][1]['x'] = 500
        r = analisar_ajuste_corrente(cfg, angulos=(0,), cursos=(0,))
        self.assertEqual(r['nominal']['interferencias_internas'], [])
        self.assertIn(('perna interna', 'motor B'),
                      {(x['perna'], x['objeto']) for x in r['ajustada']['interferencias_internas']})
        self.assertEqual(cfg['corrente']['rodas'][1]['x'], 500)
    def test_interferencia_perna_interna_motores_hipoteticos(self):
        r = analisar(angulos=(0,), cursos=(0,))
        pares={(c['perna'],c['objeto']) for c in r['interferencias_internas']}
        self.assertIn(('perna interna','motor A'),pares)
        self.assertIn(('perna interna','motor B'),pares)

    def test_geometria_parametrizada_altera_resultado(self):
        r=analisar(afastamento_mm=300,angulos=(0,),cursos=(0,))
        self.assertFalse([x for x in r['interferencias_internas'] if x['perna']=='perna interna'])

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError): analisar(diametro_mm=0)
        with self.assertRaises(ValueError): analisar(angulos=())
        with self.assertRaises(ValueError): analisar(cursos=(400,))

if __name__ == '__main__': unittest.main()
