"""Estimativa exploratória para 50 km com piloto único, sem garantia de autonomia."""
import argparse
import json
import math

from configuracoes import base
from estabilidade_massas import estabilidade, ler_inventario, montar, ocupantes_sentados, preparar_itens
from transmissao_dianteira import PADRAO_MODULO_BIZ, constantes_motor

G = 9.80665


def avaliar(velocidade_kmh=25., distancia_km=50., massa_piloto_kg=65.,
            energia_wh=2560., fracao_util=.8, reserva_wh=256.,
            acessorios_w=50., desnivel_subida_m=0., fator_extra=1.,
            tensao_bateria_v=None, limite_corrente_bateria_a=None):
    valores = (velocidade_kmh, distancia_km, massa_piloto_kg, energia_wh, fracao_util,
               reserva_wh, acessorios_w, desnivel_subida_m, fator_extra)
    if not all(math.isfinite(x) for x in valores):
        raise ValueError('Entradas devem ser finitas')
    if min(velocidade_kmh, distancia_km, massa_piloto_kg, energia_wh, fator_extra) <= 0:
        raise ValueError('Velocidade, distância, massa, energia e fator devem ser positivos')
    if not 0 < fracao_util <= 1 or min(reserva_wh, acessorios_w, desnivel_subida_m) < 0:
        raise ValueError('Fração útil ou encargos inválidos')
    h, caminho = base('p2_dorsal')
    from dataclasses import replace
    h = replace(h, massa_pessoa=massa_piloto_kg)
    itens = preparar_itens(ler_inventario(caminho), h)
    piloto = ocupantes_sentados(h, h.distancia_nominal)[0]
    estado = estabilidade(montar(itens, 'sentado', [piloto]), h)
    v = velocidade_kmh/3.6
    cfg = PADRAO_MODULO_BIZ['veiculo']
    mot = constantes_motor(PADRAO_MODULO_BIZ)
    eta_transmissao = cfg['rendimento_corrente']*cfg['rendimento_juntas']
    eta_controlador = cfg['rendimento_controlador']
    from transmissao_dianteira import RAIO_RODA, DENTES_COROA_BIZ
    resistencia = estado['massa_kg']*G*cfg['rolamento'] + .5*cfg['densidade_ar']*cfg['cda_m2']*v*v
    # Potência mecânica na roda e no motor (antes da transmissão)
    potencia_mecanica = resistencia * v
    potencia_motor_mecanica = potencia_mecanica / eta_transmissao
    # Raio da roda e redução vêm do módulo de transmissão (mesma fonte do cálculo de torque)
    num_motores = 4
    reducao_media = DENTES_COROA_BIZ / 11
    raio_roda = RAIO_RODA / 1000 if RAIO_RODA > 10 else RAIO_RODA
    omega_motor = (v / raio_roda) * reducao_media
    corrente_por_motor = (potencia_motor_mecanica / num_motores) / (mot['ke'] * omega_motor)
    perdas_cobre_total = num_motores * corrente_por_motor**2 * mot['R']
    # Motores + perdas de cobre alimentados pelo controlador (eficiência do controlador sobre o total)
    potencia_tracao_bateria = (potencia_motor_mecanica + perdas_cobre_total) / eta_controlador
    # Subida: energia potencial passa pela transmissão e pelo controlador
    energia_subida_wh = estado['massa_kg']*G*desnivel_subida_m/3600/(eta_transmissao*eta_controlador)
    tempo_h = distancia_km/velocidade_kmh
    energia_tracao_wh = potencia_tracao_bateria*tempo_h*fator_extra + energia_subida_wh
    energia_acessorios_wh = acessorios_w*tempo_h
    potencia_tracao_media = energia_tracao_wh/tempo_h
    potencia_bateria = potencia_tracao_media + acessorios_w
    # Limite de corrente da bateria: acessórios saem do orçamento antes de comparar com a tração
    if tensao_bateria_v and limite_corrente_bateria_a:
        potencia_max_bateria = tensao_bateria_v*limite_corrente_bateria_a
        disponivel_tracao = potencia_max_bateria - acessorios_w
        limite_bateria = {'potencia_max_w': potencia_max_bateria, 'disponivel_para_tracao_w': disponivel_tracao,
                          'tracao_dentro_do_limite': potencia_tracao_media <= disponivel_tracao}
    else:
        limite_bateria = None
    tracao_wh = energia_tracao_wh + energia_acessorios_wh
    energia_viagem = tracao_wh
    disponivel = energia_wh*fracao_util
    return {'massa_kg': estado['massa_kg'], 'cg_x_m': estado['cg_x_m'], 'cg_z_m': estado['cg_z_m'],
            'reacoes_kgf': estado['reacoes_kgf'], 'limite_lateral_g': estado['limite_tombamento_lateral_g'],
            'velocidade_kmh': velocidade_kmh, 'distancia_km': distancia_km, 'tempo_h': tempo_h,
            'energia_viagem_wh': energia_viagem, 'consumo_wh_km': energia_viagem/distancia_km,
            'energia_disponivel_wh': disponivel, 'reserva_wh': reserva_wh,
            'saldo_apos_reserva_wh': disponivel-energia_viagem-reserva_wh,
            'potencia_media_wh_h': energia_viagem/tempo_h,
            'potencia_tracao_media_w': potencia_tracao_media,
            'potencia_mecanica_roda_w': potencia_mecanica,
            'energia_subida_wh': energia_subida_wh,
            'limite_bateria': limite_bateria,
            'potencia_bateria_w': potencia_bateria,
            'perdas_cobre_motores_w': perdas_cobre_total,
            'acessorios_w': acessorios_w,
            'potencia_continua_referencia_w': cfg['potencia_continua_W'],
            'hipoteses': 'regime constante, perdas de cobre dos motores e eficiência do controlador sobre a tração; acessórios deduzidos do orçamento da bateria antes de comparar com o limite de corrente'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--piloto-kg', type=float, default=65.)
    p.add_argument('--velocidade-kmh', type=float, default=25.)
    p.add_argument('--subida-m', type=float, default=0.)
    p.add_argument('--fator-extra', type=float, default=1.)
    a = p.parse_args()
    print(json.dumps(avaliar(massa_piloto_kg=a.piloto_kg, velocidade_kmh=a.velocidade_kmh,
                             desnivel_subida_m=a.subida_m, fator_extra=a.fator_extra), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
