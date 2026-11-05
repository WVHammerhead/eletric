"""Modelo histórico NÃO VALIDADO do balancim; ver VALIDACAO_GEOMETRIA_MODULO.md.

Calcula invasão da carroceria, tensão da corrente com tensor e folgas mínimas.
Compara com geometria atual (balança 400mm, esterço 6°).

Uso:
    python geometria_balancim.py
    python geometria_balancim.py --esterco_max 25
    python geometria_balancim.py --comprimento_balancim 240
"""
import argparse
import json
import math
import sys


# Geometria base (mm)
BITOLA = 1420.0
YR = BITOLA / 2.0                    # 710mm
X_EIXO = 600.0
X_PIVO = 520.0
Z_EIXO = 258.0                       # raio roda 80/100-14
RECUO_PINO = 89.0                    # pino de esterço recuado p/ dentro

# Carroceria
LARGURA_CARROCERIA = 1640.0
Y_MAX_CARROCERIA = LARGURA_CARROCERIA / 2.0   # 820mm

# Balança/balancim
AFASTAMENTO_BRACO = 60.0             # braço externo: yr + 60mm
COMPRIMENTO_BALANCA_ATUAL = 400.0    # Biz original
COMPRIMENTO_BALANCIM_PROPOSTO = 260.0

# Motores
MOTOR_DIAMETRO = 103.0
MOTOR_COMPRIMENTO = 190.0
FOLGA_PNEU = 25.0
Y_PLANO_CORRENTE = YR - FOLGA_PNEU   # 685mm

# Posições dos motores (pinhões no plano da corrente)
MOTOR_A = {'x': 650.0, 'z': 372.0, 'nome': 'Motor A (traseiro)'}
MOTOR_B = {'x': 530.0, 'z': 372.0, 'nome': 'Motor B (frente)'}

# Corrente
CORRENTE_ELOS = 64
CORRENTE_PASSO = 12.7  # #428
DENTES_PINHAO = 11
DENTES_COROA = 60


def pino_esterco():
    """Posição do pino de esterço (x, y) em mm."""
    return (X_EIXO, YR - RECUO_PINO)


def girar_ponto_2d(p, pino, angulo_rad):
    """Gira ponto (x, y) em torno do pino no plano xy."""
    dx, dy = p[0] - pino[0], p[1] - pino[1]
    c, s = math.cos(angulo_rad), math.sin(angulo_rad)
    return (pino[0] + c*dx - s*dy, pino[1] + s*dx + c*dy)


def geometria_balanca(comprimento_mm, afastamento_braco_mm, deslocamento_pivo_y=0.0):
    """Devolve função que calcula y_tip da balança em função do ângulo de esterço.
    
    Args:
        comprimento_mm: Distância pivô → eixo
        afastamento_braco_mm: Deslocamento lateral do braço (yr + afastamento)
        deslocamento_pivo_y: Deslocamento adicional do pivô em y (positivo = p/ fora)
    
    Returns:
        função(angulo_graus) -> {'y_tip': ..., 'y_pivo': ..., 'invasao_mm': ...}
    """
    pino = pino_esterco()
    # Pivô inicial (antes do esterço)
    pivo_base = (X_PIVO, YR + afastamento_braco_mm + deslocamento_pivo_y)
    # Tip da balança: extensão além do eixo (assumindo 80mm p/ fora)
    extensao_alem_eixo = 80.0
    
    def calcular(angulo_graus):
        ang = math.radians(angulo_graus)
        # Girar pivô em torno do pino
        pivo_rot = girar_ponto_2d(pivo_base, pino, ang)
        # Eixo após rotação (roda gira com módulo)
        eixo_rot = girar_ponto_2d((X_EIXO, YR), pino, ang)
        # Vetor pivô → eixo
        dx, dy = eixo_rot[0] - pivo_rot[0], eixo_rot[1] - pivo_rot[1]
        dist = math.hypot(dx, dy)
        # Normalizar para comprimento da balança
        if dist < 1e-6:
            tip_x, tip_y = eixo_rot[0], eixo_rot[1] + extensao_alem_eixo
        else:
            # Tip está além do eixo, na direção pivô → eixo
            fator = (comprimento_mm + extensao_alem_eixo) / dist
            tip_x = pivo_rot[0] + dx * fator
            tip_y = pivo_rot[1] + dy * fator
        
        invasao = max(0.0, abs(tip_y) - Y_MAX_CARROCERIA)
        
        return {
            'angulo_graus': angulo_graus,
            'y_pivo_mm': round(pivo_rot[1], 1),
            'y_eixo_mm': round(eixo_rot[1], 1),
            'y_tip_mm': round(tip_y, 1),
            'carroceria_mm': Y_MAX_CARROCERIA,
            'invasao_mm': round(invasao, 1),
            'ok': invasao < 0.5,
        }
    
    return calcular


def posicao_motor_apos_esterco(motor, angulo_graus):
    """Posição do motor após esterço (centro da carcaça no plano xy)."""
    pino = pino_esterco()
    # Centro do motor: pinhão em (motor['x'], Y_PLANO_CORRENTE), carcaça p/ dentro (y menor)
    y_carcaca = Y_PLANO_CORRENTE - MOTOR_COMPRIMENTO
    centro = (motor['x'], y_carcaca)
    centro_rot = girar_ponto_2d(centro, pino, math.radians(angulo_graus))
    
    # Envelope do motor (cilindro)
    y_min = centro_rot[1] - MOTOR_DIAMETRO / 2
    y_max = centro_rot[1] + MOTOR_DIAMETRO / 2
    invasao = max(0.0, abs(y_max) - Y_MAX_CARROCERIA)
    
    return {
        'motor': motor['nome'],
        'angulo_graus': angulo_graus,
        'centro_y_mm': round(centro_rot[1], 1),
        'y_min_mm': round(y_min, 1),
        'y_max_mm': round(y_max, 1),
        'carroceria_mm': Y_MAX_CARROCERIA,
        'invasao_mm': round(invasao, 1),
        'ok': invasao < 0.5,
    }


def raio_giro(entre_eixos_mm, angulo_graus):
    """Raio de giro externo (m) para ângulo de esterço dado."""
    if abs(angulo_graus) < 0.1:
        return float('inf')
    ang = math.radians(angulo_graus)
    # Aproximação: R ≈ L / tan(δ) + bitola/2
    R_interno = entre_eixos_mm / math.tan(abs(ang))
    R_externo = math.hypot(R_interno + BITOLA/2, entre_eixos_mm)
    return R_externo / 1000.0  # converter para metros


def comprimento_corrente_triangulo(xa, za, xb, zb, xc, zc, dentes_a, dentes_b, dentes_c, passo_mm):
    """Comprimento teórico da corrente em laço de 3 rodas (2 pinhões + 1 coroa).
    
    Fórmula aproximada: soma de arcos engrenados + segmentos retos entre centros.
    """
    def raio_primitivo(dentes):
        return passo_mm * dentes / (2 * math.pi)
    
    ra, rb, rc = raio_primitivo(dentes_a), raio_primitivo(dentes_b), raio_primitivo(dentes_c)
    
    # Distâncias entre centros
    d_ab = math.hypot(xb - xa, zb - za)
    d_bc = math.hypot(xc - xb, zc - zb)
    d_ca = math.hypot(xa - xc, za - zc)
    
    # Ângulos de envolvimento (simplificado: arco completo menos envolvimento)
    # Para laço externo: cada roda tem ~π de envolvimento (metade do perímetro)
    L_arcos = math.pi * (ra + rb + rc)
    
    # Segmentos retos (aproximação: distâncias menos raios)
    L_retos = d_ab + d_bc + d_ca
    
    L_total = L_arcos + L_retos
    elos = L_total / passo_mm
    
    return {
        'comprimento_teorico_mm': round(L_total, 1),
        'elos_teoricos': round(elos, 1),
        'elos_adotados': int(elos) if elos - int(elos) < 0.5 else int(elos) + 1,
    }


def avaliar_geometria(comprimento_balancim_mm, deslocamento_pivo_y_mm, esterco_max_graus,
                      entre_eixos_mm=2015.0, passo_angulo=2.0):
    """Avalia geometria completa: balança, motores, raio de giro e corrente."""
    
    calc_balanca = geometria_balanca(comprimento_balancim_mm, AFASTAMENTO_BRACO, deslocamento_pivo_y_mm)
    
    angulos = []
    n = int(esterco_max_graus / passo_angulo) + 1
    for i in range(n + 1):
        ang = i * passo_angulo
        if ang > esterco_max_graus:
            ang = esterco_max_graus
        angulos.append(ang)
    
    resultados = []
    for ang in sorted(set(angulos)):
        bal = calc_balanca(ang)
        mot_a = posicao_motor_apos_esterco(MOTOR_A, ang)
        mot_b = posicao_motor_apos_esterco(MOTOR_B, ang)
        R = raio_giro(entre_eixos_mm, ang)
        
        ok_geral = bal['ok'] and mot_a['ok'] and mot_b['ok']
        
        resultados.append({
            'angulo_graus': ang,
            'balanca': bal,
            'motor_a': mot_a,
            'motor_b': mot_b,
            'raio_giro_externo_m': round(R, 2) if R < 1000 else None,
            'ok': ok_geral,
        })
    
    # Encontrar ângulo máximo viável
    ang_max_viavel = max((r['angulo_graus'] for r in resultados if r['ok']), default=0.0)
    
    # Comprimento da corrente (posição inicial, sem tensor)
    corrente = comprimento_corrente_triangulo(
        MOTOR_A['x'], MOTOR_A['z'],
        MOTOR_B['x'], MOTOR_B['z'],
        X_EIXO, Z_EIXO,
        DENTES_PINHAO, DENTES_PINHAO, DENTES_COROA,
        CORRENTE_PASSO
    )
    
    return {
        'configuracao': {
            'comprimento_balancim_mm': comprimento_balancim_mm,
            'deslocamento_pivo_y_mm': deslocamento_pivo_y_mm,
            'esterco_maximo_testado_graus': esterco_max_graus,
            'entre_eixos_mm': entre_eixos_mm,
        },
        'resultados_por_angulo': resultados,
        'angulo_maximo_viavel_graus': ang_max_viavel,
        'raio_giro_minimo_m': round(raio_giro(entre_eixos_mm, ang_max_viavel), 2) if ang_max_viavel > 0 else None,
        'corrente': corrente,
        'conclusao': (
            f"Esterço viável até {ang_max_viavel}° (raio {round(raio_giro(entre_eixos_mm, ang_max_viavel), 1)}m). "
            f"Corrente: {corrente['elos_adotados']} elos, {corrente['comprimento_teorico_mm']}mm."
            if ang_max_viavel > 0 else
            "Nenhum ângulo viável — geometria inválida."
        )
    }


def comparar_geometrias(esterco_max_graus=25.0):
    """Compara geometria atual (400mm, 6°) com proposta (260mm, até 25°)."""
    
    print("=" * 80)
    print("COMPARAÇÃO DE GEOMETRIAS — Módulo Dianteiro Hammerhead")
    print("=" * 80)
    print()
    
    # Geometria atual
    print("1. GEOMETRIA ATUAL (Baseline)")
    print("-" * 80)
    atual = avaliar_geometria(COMPRIMENTO_BALANCA_ATUAL, 0.0, 6.0)
    print(f"   Balança: {COMPRIMENTO_BALANCA_ATUAL}mm (Biz original)")
    print(f"   Esterço máximo adotado: 6°")
    print(f"   Esterço máximo viável: {atual['angulo_maximo_viavel_graus']}°")
    print(f"   Raio de giro: {atual['raio_giro_minimo_m']}m")
    print(f"   Corrente: {atual['corrente']['elos_adotados']} elos")
    
    # Verificar invasão a 30° (meta original)
    teste_30 = [r for r in atual['resultados_por_angulo'] if abs(r['angulo_graus'] - 30.0) < 0.1]
    if teste_30:
        r = teste_30[0]
        print(f"   A 30° (meta D-12): balança invade {r['balanca']['invasao_mm']}mm")
    print()
    
    # Geometria proposta (balancim sem deslocamento)
    print("2. PROPOSTA A: Balancim 260mm (sem deslocamento pivô)")
    print("-" * 80)
    prop_a = avaliar_geometria(COMPRIMENTO_BALANCIM_PROPOSTO, 0.0, esterco_max_graus)
    print(f"   Balancim: {COMPRIMENTO_BALANCIM_PROPOSTO}mm (custom)")
    print(f"   Deslocamento pivô: 0mm")
    print(f"   Esterço máximo viável: {prop_a['angulo_maximo_viavel_graus']}°")
    print(f"   Raio de giro: {prop_a['raio_giro_minimo_m']}m")
    print(f"   Corrente: {prop_a['corrente']['elos_adotados']} elos")
    print()
    
    # Geometria proposta com pivô deslocado
    print("3. PROPOSTA B: Balancim 260mm + Pivô deslocado +20mm")
    print("-" * 80)
    prop_b = avaliar_geometria(COMPRIMENTO_BALANCIM_PROPOSTO, 20.0, esterco_max_graus)
    print(f"   Balancim: {COMPRIMENTO_BALANCIM_PROPOSTO}mm (custom)")
    print(f"   Deslocamento pivô: +20mm (p/ fora)")
    print(f"   Esterço máximo viável: {prop_b['angulo_maximo_viavel_graus']}°")
    print(f"   Raio de giro: {prop_b['raio_giro_minimo_m']}m")
    print(f"   Corrente: {prop_b['corrente']['elos_adotados']} elos")
    print()
    
    # Resumo comparativo
    print("=" * 80)
    print("RESUMO COMPARATIVO")
    print("=" * 80)
    print()
    print(f"{'Critério':<30} {'Atual':<15} {'Proposta A':<15} {'Proposta B':<15}")
    print("-" * 80)
    print(f"{'Comprimento balança/balancim':<30} {COMPRIMENTO_BALANCA_ATUAL:<15.0f} {COMPRIMENTO_BALANCIM_PROPOSTO:<15.0f} {COMPRIMENTO_BALANCIM_PROPOSTO:<15.0f}")
    print(f"{'Deslocamento pivô (mm)':<30} {'0':<15} {'0':<15} {'+20':<15}")
    print(f"{'Esterço máximo viável (°)':<30} {atual['angulo_maximo_viavel_graus']:<15.0f} {prop_a['angulo_maximo_viavel_graus']:<15.0f} {prop_b['angulo_maximo_viavel_graus']:<15.0f}")
    print(f"{'Raio de giro mínimo (m)':<30} {atual['raio_giro_minimo_m']:<15.1f} {prop_a['raio_giro_minimo_m']:<15.1f} {prop_b['raio_giro_minimo_m']:<15.1f}")
    print(f"{'Elos corrente':<30} {atual['corrente']['elos_adotados']:<15} {prop_a['corrente']['elos_adotados']:<15} {prop_b['corrente']['elos_adotados']:<15}")
    print()
    
    print("=" * 80)
    print("RECOMENDAÇÃO")
    print("=" * 80)
    melhor = max([atual, prop_a, prop_b], key=lambda g: g['angulo_maximo_viavel_graus'])
    if melhor is prop_b:
        print("✅ PROPOSTA B (Balancim 260mm + Pivô +20mm)")
        print(f"   • Esterço viável: {prop_b['angulo_maximo_viavel_graus']}° (vs. meta 30°)")
        print(f"   • Raio de giro: {prop_b['raio_giro_minimo_m']}m (funcional para urbano)")
        print(f"   • Sem alteração de corrente (mesmo número de elos)")
    elif melhor is prop_a:
        print("✅ PROPOSTA A (Balancim 260mm sem deslocamento)")
        print(f"   • Esterço viável: {prop_a['angulo_maximo_viavel_graus']}°")
        print(f"   • Raio de giro: {prop_a['raio_giro_minimo_m']}m")
    else:
        print("⚠️ Geometria atual (6°) é a única viável")
        print("   • Considerar paralama mais largo ou esterço limitado")
    print()
    
    return {
        'atual': atual,
        'proposta_a': prop_a,
        'proposta_b': prop_b,
    }


def main():
    print('ATENÇÃO: modelo não validado; não demonstra geometria nem segurança. '
          'Consulte VALIDACAO_GEOMETRIA_MODULO.md.', file=sys.stderr)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--comprimento_balancim', type=float, default=260.0,
                        help='Comprimento do balancim em mm (default: 260)')
    parser.add_argument('--deslocamento_pivo', type=float, default=20.0,
                        help='Deslocamento do pivô em mm, positivo p/ fora (default: 20)')
    parser.add_argument('--esterco_max', type=float, default=25.0,
                        help='Ângulo máximo de esterço a testar em graus (default: 25)')
    parser.add_argument('--comparar', action='store_true',
                        help='Comparar geometrias (atual vs. propostas)')
    parser.add_argument('--json', action='store_true',
                        help='Saída em JSON')
    
    args = parser.parse_args()
    
    if args.comparar:
        resultados = comparar_geometrias(args.esterco_max)
        if args.json:
            print(json.dumps(resultados, ensure_ascii=False, indent=2))
    else:
        resultado = avaliar_geometria(args.comprimento_balancim, args.deslocamento_pivo, args.esterco_max)
        if args.json:
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        else:
            print(f"Comprimento balancim: {args.comprimento_balancim}mm")
            print(f"Deslocamento pivô: {args.deslocamento_pivo:+.1f}mm")
            print(f"Esterço máximo viável: {resultado['angulo_maximo_viavel_graus']}°")
            print(f"Raio de giro: {resultado['raio_giro_minimo_m']}m")
            print()
            print(resultado['conclusao'])


if __name__ == '__main__':
    main()
