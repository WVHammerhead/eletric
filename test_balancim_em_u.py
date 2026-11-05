import math
import unittest

import balancim_em_u as b


class BalancimEmU(unittest.TestCase):
    def test_comprimento_260_encosta_no_pneu_e_315_nao(self):
        self.assertLess(b.geometria_u(L=260.0)['folga_tubo_pivo_pneu_mm'], 0)       # tubo de pivô dentro do pneu
        g = b.geometria_u(L=315.0)
        self.assertGreaterEqual(g['folga_tubo_pivo_pneu_mm'], b.FOLGA_PNEU_ESTRUTURA)
        self.assertGreaterEqual(g['folga_perna_pneu_mm'], b.FOLGA_PNEU_ESTRUTURA - 1e-9)

    def test_apoio_respeita_rolamento(self):
        self.assertGreaterEqual(b.geometria_u(x_s=140.0)['folga_apoio_rolamento_mm'], 0)
        self.assertLess(b.geometria_u(x_s=110.0)['folga_apoio_rolamento_mm'], 0)

    def test_rotacao_preserva_distancias_entre_motores_e_coroa(self):
        # rotação rígida em torno do pivô: a distância motor–pivô não muda
        L = 315.0
        xp = b.X_EIXO - L
        for (x, z) in b.LAYOUTS['afastados_x']:
            d0 = math.hypot(x - xp, z - b.Z_EIXO)
            for c in (-40.0, 80.0):
                xr, zr = b._girar(x, z, c, L)
                self.assertAlmostEqual(math.hypot(xr - xp, zr - b.Z_EIXO), d0, places=6)
        self.assertAlmostEqual(b._girar(b.X_EIXO, b.Z_EIXO, 80.0, L)[1] - b.Z_EIXO, 80.0, places=6)

    def test_afastados_x_invade_piso_em_extensao_e_sobe_na_compressao(self):
        e = b.excursao_motores(b.LAYOUTS['afastados_x'])
        self.assertGreater(e['invasao_piso_mm'], 0)
        self.assertGreater(e['z_max_corpo_mm'], 500)

    def test_motor_interfere_com_pneu_sem_ajuste_e_ajuste_resolve(self):
        lay = b.LAYOUTS['afastados_x']
        self.assertLess(b.folga_motor_pneu(lay, 0)['menor_mm'], 0)
        d = b.deslocamento_interno_minimo(lay)
        self.assertGreater(d, 0)
        self.assertGreaterEqual(b.folga_motor_pneu(lay, d)['menor_mm'], b.FOLGA_MIN)

    def test_secoes_atendem_fs_e_parede_minima(self):
        p = b.projeto()
        self.assertGreaterEqual(p['braco']['FS'], b.FS_BRACO)
        self.assertGreaterEqual(p['tubo_pivo']['FS'], b.FS_BRACO)
        self.assertGreaterEqual(p['braco']['esp'], b.PAREDE_MIN_MM)
        self.assertGreaterEqual(b.solda_junta(p['braco']['D'], p['cargas']['M_junta_max_Nm'], p['solda_junta_braco']['perna_recomendada_mm'])['FS'], 1.5)

    def test_braco_interno_passa_sob_motor_b(self):
        p = b.projeto()
        self.assertGreater(p['folga_braco_interno_motor_mm'], b.FOLGA_MIN)

    def test_buscar_layouts_respeita_piso(self):
        r = b.buscar_layouts(passo_grade=40, zmin_piso=b.Z_PISO + b.FOLGA_MIN)
        self.assertTrue(r)
        for x in r[:5]:
            self.assertGreaterEqual(b.excursao_motores((x['A'], x['B']))['z_min_corpo_mm'], b.Z_PISO + b.FOLGA_MIN - 1e-6)

    def test_reducao_da_prancha_elimina_sobreposicao_amostrada(self):
        layout = b.LAYOUTS['afastados_x_B_a_frente']
        movido = tuple(b._girar(x, z, -40.0, 315.0) for x, z in layout)
        self.assertAlmostEqual(b.invasao_leito(movido, 42.0)['por_motor_mm'][1], 0.0)
        self.assertEqual(b.invasao_leito_curso(layout, 42.0)['max_mm'], 0.0)


if __name__ == '__main__':
    unittest.main()
