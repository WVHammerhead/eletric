"""Varredura exploratória das posições dos motores do módulo P2.

A corrente é recalculada e a posição de montagem é aplicada antes das
verificações. Não é otimização de projeto nem validação de fabricação.
"""
import copy
import json
from pathlib import Path
from empacotamento_dianteiro import componentes_modulo_biz, colisoes, varredura_esterco_modulo
from envelope_garfo import analisar_ajuste_corrente
from transmissao_dianteira import PADRAO_MODULO_BIZ, calcular_modulo_biz

CANDIDATOS = ((650,530), (700,450), (750,400), (780,420), (750,500), (800,450))


def avaliar(a, b):
    cfg=copy.deepcopy(PADRAO_MODULO_BIZ)
    motores=[r for r in cfg['corrente']['rodas'] if r['tipo']=='motor']
    motores[0]['x'],motores[1]['x']=a,b
    transmissao=calcular_modulo_biz(cfg)['corrente']
    analise=analisar_ajuste_corrente(cfg)
    motores[1].update(analise['posicao_ajustada_mm'])
    comp=componentes_modulo_biz(config=cfg)
    col=[{'peca':r['a'],'obstaculo':r['b']} for r in colisoes(comp) if r['a'].startswith('motor')]
    esterco=varredura_esterco_modulo(comp,esterco_max_graus=30,passo_graus=5)
    return {'x_motor_a_mm':a,'x_motor_b_nominal_mm':b,
            'motor_b_montado_mm':analise['posicao_ajustada_mm'],
            'elos':transmissao['elos_adotados'],
            'deslocamento_montagem_mm':round(analise['ajuste']['deslocamento_montagem_mm'],2),
            'curso_rasgo_estimado_mm':round(transmissao['ajuste']['curso_minimo_rasgo_mm'],2),
            'interferencias_garfo_nominal':analise['nominal']['interferencias_internas'],
            'interferencias_garfo_ajustada':analise['ajustada']['interferencias_internas'],
            'interferencias_garfo_estrutura_amostradas':analise['ajustada']['interferencias_estrutura'],
            'interferencias_motor_estaticas':col,
            'invasoes_esterco_modelo_anterior':esterco['invasoes']}


def main():
    resultados=[]
    for a,b in CANDIDATOS:
        try: resultados.append(avaliar(a,b))
        except ValueError as e: resultados.append({'x_motor_a_mm':a,'x_motor_b_nominal_mm':b,'erro':str(e)})
    saida={'natureza':'TRIAGEM_SINTETICA','base':'P2 dorsal, bitola 1420 mm',
           'limites':'Modelos aproximados distintos: duas pernas e suspensão amostrada na triagem de garfo, esterço amostrado no modelo antigo de balança e amortecedor, sem movimento combinado dos motores. Sem cubo, espelho, suportes, tensor, proteção, capô, carroceria 3D, tolerâncias, deformações ou dimensionamento estrutural. 25 mm de folga só na varredura antiga; interseção com caixa de corrente pode ser falso positivo. Lado direito, sem simetria comprovada. Não aprova geometria.',
           'resultados':resultados}
    Path('varredura_geometria_modulo.json').write_text(json.dumps(saida,indent=2,ensure_ascii=False),encoding='utf-8')
    for r in resultados:
        if 'erro' in r: print(r['x_motor_a_mm'],r['x_motor_b_nominal_mm'],'ERRO',r['erro']);continue
        print(r['x_motor_a_mm'],r['x_motor_b_nominal_mm'],'elos',r['elos'],'interferencias garfo',len(r['interferencias_garfo_ajustada']),
              'motor estático',len(r['interferencias_motor_estaticas']), 'invasoes esterço',[(v['peca'],v['obstaculo']) for v in r['invasoes_esterco_modelo_anterior']])
    print('Resultados: varredura_geometria_modulo.json; não significa validação.')

if __name__=='__main__': main()
