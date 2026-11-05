#!/usr/bin/env python3
"""Compara hipóteses de vínculos e posicionamento dos motores no módulo dianteiro.

Modelo 2D no plano x-z, sem tensor, esterço, carroceria, estruturas ou cargas.
Um resultado favorável é triagem geométrica, não liberação para fabricação.
"""
import argparse
import csv
import math
import sys
from pathlib import Path
import varredura_modulo_completo as v
import transmissao_dianteira as td

CURSOS = (-40.0, 80.0)
MARGEM_MM = 10.0


def pontos(curso, layout, vinculo):
    """No repouso usa constantes da varredura; para rotação o pivô é fixo em x-z."""
    x0, z0 = v.X_EIXO, v.Z_EIXO
    afastamento = v.BALANCIM['y_afastamento_mm'] + v.BALANCIM['deslocamento_pivo_y_mm']
    comprimento = v.BALANCIM['comprimento_pivo_eixo_mm']
    raio = math.sqrt(comprimento**2 - afastamento**2)
    xp = x0 - raio
    if abs(curso) >= raio:
        raise ValueError('Curso excede o raio projetado do balancim')
    theta = math.asin(curso / raio)
    def rodar(x, z):
        dx, dz = x - xp, z - z0
        return (xp + dx*math.cos(theta) - dz*math.sin(theta),
                z0 + dx*math.sin(theta) + dz*math.cos(theta))
    eixo = rodar(x0, z0) if vinculo != 'translacao_conjunta' else (x0, z0 + curso)
    motores = []
    for x, z in layout:
        if vinculo == 'translacao_conjunta':
            motores.append((x, z + curso))
        elif vinculo == 'rotacao_conjunta':
            motores.append(rodar(x, z))
        else:
            motores.append((x, z))
    zp, zc = v.CORRENTE['dentes_pinhao'], v.CORRENTE['dentes_coroa']
    return [{'nome': 'motor A', 'dentes': zp, 'x': motores[0][0], 'z': motores[0][1]},
            {'nome': 'motor B', 'dentes': zp, 'x': motores[1][0], 'z': motores[1][1]},
            {'nome': 'coroa', 'dentes': zc, 'x': eixo[0], 'z': eixo[1]}]


def analisar(curso, layout, vinculo):
    rodas = pontos(curso, layout, vinculo)
    passo = v.CORRENTE['passo_mm']
    pares = []
    for i, a in enumerate(rodas):
        for b in rodas[i+1:]:
            distancia = math.hypot(a['x']-b['x'], a['z']-b['z'])
            folga = distancia - td.raio_externo(passo, a['dentes']) - td.raio_externo(passo, b['dentes'])
            pares.append((folga, a['nome'] + ' / ' + b['nome']))
    minimo, par = min(pares)
    linha = {'curso_mm': curso, 'menor_folga_estimada_mm': round(minimo, 3), 'par_critico': par,
             'comprimento_laco_mm': None, 'elos_teoricos': None, 'menor_dentes_pinhao': None,
             'estado': '', 'motivo': ''}
    if minimo < 0:
        linha.update(estado='SOBREPOSICAO', motivo='Raios externos estimados se sobrepõem')
        return linha
    try:
        resultado = td.laco(rodas, passo)
    except ValueError as exc:
        linha.update(estado='LACO_INVALIDO', motivo=str(exc))
        return linha
    linha.update(comprimento_laco_mm=round(resultado['comprimento_mm'], 3),
                 elos_teoricos=round(resultado['elos'], 4),
                 menor_dentes_pinhao=round(min(r['dentes_engrenados'] for r in resultado['rodas'] if r['nome'].startswith('motor')), 3),
                 estado='FOLGA_MENOR_10' if minimo < MARGEM_MM else 'GEOMETRIA_2D_SEM_BLOQUEIO')
    return linha


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--passo', type=float, default=5, help='Passo do curso de suspensão, em mm (padrão: 5)')
    ap.add_argument('--saida', type=Path, default=Path('estudo_decisoes_modulo'), help='Pasta dos resultados')
    args = ap.parse_args()
    if not math.isfinite(args.passo) or args.passo <= 0 or args.passo > 120:
        ap.error('--passo deve ser maior que 0 e no máximo 120 mm')
    cursos = [CURSOS[0]]
    while cursos[-1] + args.passo < CURSOS[1] - 1e-9:
        cursos.append(cursos[-1] + args.passo)
    cursos.append(CURSOS[1])
    nominal = v.MOTOR['posicoes_pinhao']
    layouts = {'original': (nominal['A'], nominal['B']),
               'pinhoes_490': ((nominal['A'][0], 490.0), (nominal['B'][0], 490.0)),
               'afastados_x': ((757.0, nominal['A'][1]), (443.0, nominal['B'][1]))}
    vinculos = ('motores_fixos', 'translacao_conjunta', 'rotacao_conjunta')
    linhas, resumo = [], []
    for nome, layout in layouts.items():
        for vinculo in vinculos:
            grupo = []
            for curso in cursos:
                linha = {'layout': nome, 'vinculo': vinculo, **analisar(curso, layout, vinculo)}
                grupo.append(linha)
                linhas.append(linha)
            validas = [x for x in grupo if x['comprimento_laco_mm'] is not None]
            comprimentos = [x['comprimento_laco_mm'] for x in validas]
            delta = max(comprimentos)-min(comprimentos) if comprimentos else None
            resumo.append({'layout': nome, 'vinculo': vinculo, 'amostras': len(grupo),
                           'laco_valido': len(validas), 'com_folga_10': sum(x['estado']=='GEOMETRIA_2D_SEM_BLOQUEIO' for x in grupo),
                           'menor_folga_mm': min(x['menor_folga_estimada_mm'] for x in grupo),
                           'menor_dentes_pinhao': min((x['menor_dentes_pinhao'] for x in validas), default=None),
                           'variacao_laco_valido_mm': round(delta, 3) if delta is not None else None})
    args.saida.mkdir(parents=True, exist_ok=True)
    for arquivo, dados in [('amostras.csv', linhas), ('resumo.csv', resumo)]:
        with (args.saida / arquivo).open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(dados[0])); w.writeheader(); w.writerows(dados)
    leg = v.deslocamento_perna_interna_minimo()
    caixa_z = v.CAIXA_DIRECAO['z_topo_max_mm'] - v.CAIXA_DIRECAO['altura_mm']
    wheel_out = v.YR + v.GARFO['deslocamento_pernas_mm'] + v.GARFO['diametro_perna_mm']/2
    texto = ['# Triagem paramétrica do módulo dianteiro', '',
        'Modelo de estudo, não validação ou projeto de fabricação. Dimensões em mm.', '',
        f'Curso amostrado: {CURSOS[0]:g} a +{CURSOS[1]:g} mm, passo {args.passo:g} mm, incluindo os extremos. Pinhões e coroa #428: constantes atuais da varredura. A geometria do laço usa transmissao_dianteira.laco, depois de rejeitar sobreposição dos raios externos estimados.', '',
        'Vínculos: motores_fixos mantém pinhões no referencial esterçante e gira o eixo em torno do pivô; translacao_conjunta move ambos verticalmente; rotacao_conjunta gira ambos em torno do pivô. Somente repouso de esterço e vista 2D x-z. O pivô tem afastamento lateral e seu raio projetado é derivado dos 260 mm em 3D.', '',
        '| Layout | Vínculo | Laço calculável | Folga ≥ 10 | Menor folga (mm) | Variação do laço calculável (mm) | Menor nº estimado de dentes engajados |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in resumo:
        delta = '—' if r['variacao_laco_valido_mm'] is None else f"{r['variacao_laco_valido_mm']:.1f}"
        dentes = '—' if r['menor_dentes_pinhao'] is None else f"{r['menor_dentes_pinhao']:.1f}"
        texto.append(f"| {r['layout']} | {r['vinculo']} | {r['laco_valido']}/{r['amostras']} | {r['com_folga_10']}/{r['amostras']} | {r['menor_folga_mm']:.1f} | {delta} | {dentes} |")
    texto += ['', 'A variação e o engajamento estimado são calculados apenas nas amostras com laço geometricamente calculável; se não cobrir todas as amostras, não representa o curso inteiro. O engajamento é uma estimativa idealizada de envolvimento, não valida capacidade de transmissão. Folga positiva usa raios externos estimados, não perfil medido dos dentes. Ajuste de tensor depende do percurso e da direção de trabalho, portanto seu deslocamento ±8 mm não é diretamente a capacidade de absorção do comprimento de corrente.', '',
        f"A função existente encontra {leg['minimo_mm']} mm para a perna interna e vão de {leg['vao_entre_pernas_mm']} mm na configuração examinada. É uma triagem de repouso baseada em caixas e no envelope aproximado da corrente, não uma prova para todo o curso e esterço.", '',
        f"Perna externa nominal: centro em y={v.YR + v.GARFO['deslocamento_pernas_mm']:.1f}, raio {v.GARFO['diametro_perna_mm']/2:.2f}; extremo em y={wheel_out:.2f}, ou {wheel_out-v.Y_MAX_CARROCERIA:.2f} mm além de y={v.Y_MAX_CARROCERIA:.1f}, na geometria nominal. A solução depende do envelope permitido e da representação da carroceria.", '',
        f"Caixa: base z={caixa_z:.1f} e topo z={v.CAIXA_DIRECAO['z_topo_max_mm']:.1f}; a folga de roda comprimida é uma comparação vertical simplificada, sem demonstrar separação 3D entre caixa e pneu ou compatibilidade da travessa com as sedes.", '',
        'O ensaio de corrente existente move apenas a coroa, enquanto a varredura move motores, coroa e pivô verticalmente. Esta ferramenta separa as hipóteses, mas não corrige a cinemática da varredura. A alternativa de braço único previamente registrada e o eixo biapoiado precisam ser conciliados antes de escolher a solução.', '',
        'Próximas verificações: geometria real e percurso da corrente e tensor; volumes de motores, flanges e proteções; amortecedor, batentes, travessa, carroceria e piso em 3D para ambos os lados, esterço e curso; cargas, rigidez, fadiga e montagem.', '']
    (args.saida / 'relatorio.md').write_text('\n'.join(texto), encoding='utf-8')
    print('\n'.join(texto))
    print('Arquivos:', args.saida.resolve())

if __name__ == '__main__':
    main()
