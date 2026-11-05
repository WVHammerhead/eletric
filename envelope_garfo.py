"""Triagem do garfo biapoiado no empacotamento P2; dimensões hipotéticas, em mm.

Não é CAD nem verificação de fabricação. A caixa da corrente envolve todo o laço
(e pode produzir falsos positivos). Não representa cubo, espelho, coroa em 3D,
travessa, capô ou suportes. Curso e esterço são amostrados, não contínuos.
"""
import copy
import json
import math
from cabecote_pivo import H, X_PERNA
from cinematica_dianteira import curso_modulo
from empacotamento_dianteiro import Caixa, Tubo, componentes_modulo_biz, tubo_x_caixa, _girar_em_torno_do_pino
from transmissao_dianteira import PADRAO_MODULO_BIZ, calcular_modulo_biz


def analisar(bitola=1420.0, altura_mm=H*1000, afastamento_mm=X_PERNA*1000,
             diametro_mm=63.5, largura_corrente_mm=16.8,
             angulos=range(-30, 31, 5), cursos=(-40, 0, 40, 80), config=None):
    valores = (bitola, altura_mm, afastamento_mm, diametro_mm, largura_corrente_mm)
    if any(not math.isfinite(v) or v <= 0 for v in valores):
        raise ValueError('Dimensões devem ser positivas e finitas')
    angulos, cursos = tuple(angulos), tuple(cursos)
    if not angulos or not cursos or not all(math.isfinite(v) for v in angulos+cursos):
        raise ValueError('Ângulos e cursos devem ser não vazios e finitos')
    comp = componentes_modulo_biz(bitola, config=config)
    geo = comp['geo']; x = geo.x_eixo_mm; y = bitola/2; z = geo.raio_roda_mm
    pernas = [Tubo('perna interna', 'garfo', (x,y-afastamento_mm,z), (x,y-afastamento_mm,z+altura_mm), diametro_mm/2),
              Tubo('perna externa', 'garfo', (x,y+afastamento_mm,z), (x,y+afastamento_mm,z+altura_mm), diametro_mm/2)]
    poly=comp['laco']; yp=comp['y_plano_corrente']; w=largura_corrente_mm/2
    corrente=Caixa('envelope do laço de corrente', 'corrente',
                   (min(p[0] for p in poly),max(p[0] for p in poly)), (yp-w,yp+w),
                   (min(p[1] for p in poly),max(p[1] for p in poly)))
    motores=[c for c in comp['caixas'] if c.grupo=='motor' and c.y[0]>=0]
    fixos=[c for c in comp['caixas'] if c.grupo in ('estrutura','ocupante')]
    internas=[]
    for perna in pernas:
        for obstaculo in motores+[corrente]:
            colisao=tubo_x_caixa(perna,obstaculo)
            if colisao: internas.append({'perna':perna.nome,'objeto':obstaculo.nome,**colisao})
    externas={}
    for curso in cursos:
        dx=curso_modulo(geo,curso)['variacao_eixo_mm']
        pino=(x+dx,y-geo.recuo_pino_mm)
        for angulo in angulos:
            for perna in pernas:
                def mover(p):
                    return _girar_em_torno_do_pino((p[0]+dx,p[1],p[2]+curso),pino,math.radians(angulo))
                t=Tubo(perna.nome,'garfo',mover(perna.a),mover(perna.b),perna.raio)
                for obstaculo in fixos:
                    hit=tubo_x_caixa(t,obstaculo)
                    if hit: externas.setdefault((perna.nome,obstaculo.nome),{'perna':perna.nome,'objeto':obstaculo.nome,'angulo_graus':angulo,'curso_mm':curso,**hit})
    return {'hipoteses': {'bitola_mm':bitola,'altura_pernas_mm':altura_mm,'apoios_mm':afastamento_mm,
                         'diametro_perna_mm':diametro_mm,'corrente_largura_mm':largura_corrente_mm,
                         'plano_corrente_y_mm':yp,'angulos_graus':angulos,'cursos_mm':cursos},
            'interferencias_internas':internas,'interferencias_estrutura':list(externas.values()),
            'limites':'Caixas e tubos hipotéticos; corrente como caixa envolvente conservadora, amostragem discreta e apenas lado direito. Sem cubo, espelho, coroa 3D, travessa, capô, suportes ou deformações; interseção da caixa de corrente exige verificação detalhada.'}


def analisar_ajuste_corrente(config=None, **opcoes):
    """Analisa a posição nominal e a posição após o ajuste estimado da corrente."""
    cfg = copy.deepcopy(PADRAO_MODULO_BIZ if config is None else config)
    ajuste = calcular_modulo_biz(cfg)['corrente']['ajuste']
    nominal = analisar(config=cfg, **opcoes)
    roda = next(r for r in cfg['corrente']['rodas'] if r['nome'] == ajuste['roda'])
    for eixo, componente in zip(('x', 'z'), ajuste['direcao']):
        roda[eixo] += componente * ajuste['deslocamento_montagem_mm']
    montado = analisar(config=cfg, **opcoes)
    return {'ajuste': ajuste, 'posicao_ajustada_mm': {'x': roda['x'], 'z': roda['z']},
            'nominal': nominal, 'ajustada': montado}

if __name__ == '__main__':
    print(json.dumps(analisar_ajuste_corrente(), ensure_ascii=True, indent=2))
