"""Regressões das exigências do rolamento (carga combinada, estática e vida).

Executar: python -B -m unittest -v test_verificacao_rolamento
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from verificacao_rolamento import carga_equivalente, requisitos, rotacao_media_rpm

RAIZ = Path(__file__).resolve().parent


class CargaEquivalente(unittest.TestCase):
    def test_radial_puro_nao_reduz_a_carga(self):
        self.assertEqual(carga_equivalente(1000.0, 0.0), (1000.0, 1000.0))

    def test_axial_aumenta_a_carga(self):
        P, _ = carga_equivalente(1000.0, 800.0)
        self.assertGreater(P, 1000.0)
        _, P0 = carga_equivalente(1000.0, 1000.0)
        self.assertGreater(P0, 1000.0)

    def test_p0_nunca_abaixo_de_fr(self):
        for fr, fa in ((500.0, 0.0), (500.0, 10.0), (500.0, 400.0)):
            self.assertGreaterEqual(carga_equivalente(fr, fa)[1], fr)


class Exigencias(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r200 = requisitos(200.0)
        cls.r300 = requisitos(300.0)

    def test_pico_estatico_200_mm_bate_com_o_gerador_do_gpt(self):
        # GPT: 4,92 kN (≈ 502 kgf) para 200 mm, 0,8 g, impacto 2×. Conferência independente.
        self.assertAlmostEqual(self.r200['P0_pico_impacto_kgf'], 502.0, delta=10.0)

    def test_mais_espaco_reduz_as_exigencias(self):
        self.assertLess(self.r300['P0_pico_impacto_kgf'], self.r200['P0_pico_impacto_kgf'])
        self.assertLess(self.r300['C_minimo_vida_kgf'], self.r200['C_minimo_vida_kgf'])
        self.assertLess(self.r300['P_dinamico_medio_N'], self.r200['P_dinamico_medio_N'])

    def test_c0_escala_linearmente_com_s0(self):
        c0 = self.r200['C0_minimo_N']
        self.assertAlmostEqual(c0['S0=2'], 2*c0['S0=1'], places=6)
        self.assertAlmostEqual(c0['S0=1.5'], 1.5*c0['S0=1'], places=6)

    def test_rotacao_media_e_coerente_com_25_kmh(self):
        self.assertAlmostEqual(rotacao_media_rpm(25.0), 257, delta=2)

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            requisitos(0.0)

    def test_cli_imprime_um_registro_por_espacamento(self):
        p = subprocess.run([sys.executable, '-B', str(RAIZ/'verificacao_rolamento.py'), '--espacamentos', '200', '300'],
                           capture_output=True, encoding='utf-8')
        self.assertEqual(p.returncode, 0, p.stderr)
        dados = json.loads(p.stdout)
        self.assertEqual([d['espacamento_mm'] for d in dados], [200.0, 300.0])


if __name__ == '__main__':
    unittest.main()
