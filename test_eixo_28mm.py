"""
Testes Unitários — Eixo Ø28 mm
===============================

Valida o cálculo estrutural simplificado e a coerência dos números
registrados nos documentos da decisão de Ø28 mm.
Não valida geometria real nem substitui o diagrama de corpo livre.
"""

import unittest
import numpy as np

from analise_comparativa_FINAL_28mm import (
    DIAMETRO_ADOTADO_MM, analisar_diametro, secao_rebaixo, rolamentos,
)

# ============================================================================
# CONSTANTES (independentes do módulo, para conferência cruzada)
# ============================================================================

DIAMETRO_MM = 28
SY_MPA = 310
F_VERTICAL_N = 1766
VAO_M = 0.3
T_FRENAGEM_NM = 551


def calcular_tensoes(d_mm, F_N, L_m, T_Nm):
    d = d_mm / 1000
    Z = np.pi * d**3 / 32
    J = np.pi * d**4 / 32
    M = F_N * L_m / 4
    sigma = M / Z
    tau = T_Nm * (d / 2) / J
    return {
        'M_Nm': M,
        'sigma_flexao_MPa': sigma / 1e6,
        'tau_torcao_MPa': tau / 1e6,
        'sigma_VM_MPa': np.sqrt(sigma**2 + 3 * tau**2) / 1e6,
    }


class TestEixo28mm(unittest.TestCase):

    def test_diametro_adotado(self):
        self.assertEqual(DIAMETRO_ADOTADO_MM, DIAMETRO_MM)

    def test_fs_escoamento_adequado(self):
        """FS escoamento ≥ 1.3 no pior caso (torque todo no eixo)."""
        t = calcular_tensoes(28, F_VERTICAL_N, VAO_M, T_FRENAGEM_NM)
        self.assertGreaterEqual(SY_MPA / t['sigma_VM_MPa'], 1.3)

    def test_numeros_documentados(self):
        """Valores citados em DECISAO_FINAL_EIXO_28mm.md e RESUMO_EXECUTIVO_EIXO_28mm.md."""
        r = analisar_diametro(28)
        self.assertAlmostEqual(r['M_Nm'], 132.45, places=2)
        self.assertAlmostEqual(r['sigma_flexao_MPa'], 61.5, delta=0.1)
        self.assertAlmostEqual(r['tau_torcao_MPa'], 127.8, delta=0.1)
        self.assertAlmostEqual(r['sigma_VM_MPa'], 229.8, delta=0.1)
        self.assertAlmostEqual(r['FS_escoamento'], 1.35, delta=0.01)
        self.assertAlmostEqual(r['FS_fadiga_Kt2'], 2.03, delta=0.01)
        self.assertAlmostEqual(r['deflexao_mm'], 0.16, delta=0.01)
        self.assertAlmostEqual(r['FS_cubo_longo'], 5.04, delta=0.01)
        self.assertTrue(r['adequado_pior_caso'])

    def test_analise_coincide_com_calculo_independente(self):
        r = analisar_diametro(28)
        t = calcular_tensoes(28, F_VERTICAL_N, VAO_M, T_FRENAGEM_NM)
        self.assertAlmostEqual(r['sigma_VM_MPa'], t['sigma_VM_MPa'], places=6)

    def test_melhor_que_25mm(self):
        t28 = calcular_tensoes(28, F_VERTICAL_N, VAO_M, T_FRENAGEM_NM)
        t25 = calcular_tensoes(25, F_VERTICAL_N, VAO_M, T_FRENAGEM_NM)
        self.assertLess(t28['sigma_VM_MPa'], t25['sigma_VM_MPa'])

    def test_25mm_nao_atende(self):
        """Justifica não ficar em Ø25: pior caso reprova."""
        self.assertFalse(analisar_diametro(25)['adequado_pior_caso'])

    def test_rolamento_furo_28(self):
        """Furo do rolamento = diâmetro do eixo; 62/28 = 28×58×16 (ISO 15)."""
        rol = rolamentos[28]
        self.assertEqual(rol['codigo'], '62/28')
        self.assertTrue(rol['dim'].startswith('28×'))

    def test_secao_rebaixo(self):
        """Rebaixo Ø26 no fim da seção C (x = 165 mm, apoio em 50 mm)."""
        M, sigma = secao_rebaixo()
        self.assertAlmostEqual(M, 101.5, delta=0.2)
        self.assertAlmostEqual(sigma, 58.9, delta=0.3)

    def test_cotas_do_eixo_somam_400(self):
        """A 15 + B 120 + C 30 + D 120 + E 90 + F 25 (DESENHO_TECNICO_EIXO_28mm.md)."""
        self.assertEqual(15 + 120 + 30 + 120 + 90 + 25, 400)


if __name__ == '__main__':
    unittest.main(verbosity=2)
