"""Cenários exploratórios de 50 km; passagem dos testes não valida autonomia real."""
import unittest
from percurso_um_ocupante import avaliar
from configuracoes import base
from estabilidade_massas import estabilidade, ler_inventario, montar, ocupantes_sentados, preparar_itens
from transmissao_dianteira import calcular_modulo_biz


class UmOcupante(unittest.TestCase):
    def test_modelos_usam_mesma_massa_e_separam_acessorios(self):
        r = avaliar(velocidade_kmh=40, distancia_km=35)
        self.assertAlmostEqual(r['potencia_media_wh_h'] - r['potencia_tracao_media_w'], 50)
        cfg = {'veiculo': {'massa_kg': r['massa_kg'], 'cg_x_mm': r['cg_x_m']*1000,
                           'cg_z_mm': r['cg_z_m']*1000}}
        velocidade = calcular_modulo_biz(cfg)['torque']['velocidade_max_plano_continua_kmh']
        self.assertGreater(velocidade, 39)
        self.assertLess(velocidade, 40)
        # Com perdas de cobre e controlador, 40 km/h excede a potência contínua (coerente com vmax < 40 km/h acima):
        # o cenário NÃO é sustentável em regime contínuo.
        self.assertGreater(r['potencia_tracao_media_w'], 1500)

    def test_massa_cg_e_reacoes_incluem_so_piloto(self):
        h, caminho = base('p2_dorsal')
        itens = preparar_itens(ler_inventario(caminho), h)
        dois = estabilidade(montar(itens, 'sentado', ocupantes_sentados(h, h.distancia_nominal)), h)
        um = avaliar()
        self.assertAlmostEqual(dois['massa_kg'] - um['massa_kg'], h.massa_pessoa)
        self.assertLess(um['cg_x_m'], dois['cg_x_m'])
        self.assertAlmostEqual(sum(um['reacoes_kgf'].values()), um['massa_kg'])

    def test_percurso_e_reserva_sao_contabilizados(self):
        r = avaliar()
        self.assertEqual(r['distancia_km'], 50)
        self.assertAlmostEqual(r['tempo_h'], 2)
        self.assertAlmostEqual(r['saldo_apos_reserva_wh'], 2048-r['energia_viagem_wh']-256)

    def test_subida_e_consumo_extra_reduzem_saldo(self):
        plano = avaliar()
        exigente = avaliar(velocidade_kmh=35, desnivel_subida_m=300, fator_extra=1.3)
        self.assertLess(exigente['saldo_apos_reserva_wh'], plano['saldo_apos_reserva_wh'])
        self.assertLess(exigente['saldo_apos_reserva_wh'], 0)

    def test_desnivel_acrescenta_energia_potencial(self):
        a = avaliar(desnivel_subida_m=0, acessorios_w=0)
        b = avaliar(desnivel_subida_m=100, acessorios_w=0)
        # Pelo menos mgh: o rendimento deve elevar a energia solicitada à bateria.
        self.assertGreater(b['energia_viagem_wh']-a['energia_viagem_wh'], a['massa_kg']*9.80665*100/3600)

    def test_percurso_dobrado_dobra_energia_no_plano(self):
        a, b = avaliar(distancia_km=25), avaliar(distancia_km=50)
        self.assertAlmostEqual(b['energia_viagem_wh'], 2*a['energia_viagem_wh'])

    def test_limites_invalidos(self):
        for kw in ({'velocidade_kmh': 0}, {'fracao_util': 1.1}, {'reserva_wh': -1}, {'fator_extra': 0}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                avaliar(**kw)


if __name__ == '__main__':
    unittest.main()
