"""Baliza sintética em vaga longitudinal: dois arcos ideais, sem ensaio físico.

CSV separado por ponto e vírgula, decimais com ponto. Construção parte do
veículo estacionado e simula saída; a inversão da sequência é uma entrada em ré.
Modelo bicicleta, carro retangular conservador, sem movimento dos obstáculos.
"""
import argparse
import csv
import json
import math
from pathlib import Path


def retangulo(x, y, ang, traseira, dianteira, largura):
    c, s = math.cos(ang), math.sin(ang)
    return [(x+c*u-s*v, y+s*u+c*v) for u,v in
            ((-traseira,-largura/2), (dianteira,-largura/2),
             (dianteira,largura/2), (-traseira,largura/2))]


def sobrepoe(a, b):
    """Separação por eixos dos dois polígonos convexos; contato conta como colisão."""
    for pol in (a,b):
        for i in range(len(pol)):
            x1,y1=pol[i]; x2,y2=pol[(i+1)%len(pol)]
            eixo=(-(y2-y1),x2-x1)
            pa=[x*eixo[0]+y*eixo[1] for x,y in a]
            pb=[x*eixo[0]+y*eixo[1] for x,y in b]
            if max(pa)<min(pb) or max(pb)<min(pa): return False
    return True


def gerar(vao=4.5, comprimento=2.765, largura=1.64, entre_eixos=2.015,
          balanco_tras=.35, largura_carro=1.8, folga=.10, afastamento_faixa=.30,
          angulos=(6.,15.,30.), passo=.025):
    valores=(vao,comprimento,largura,entre_eixos,largura_carro,passo)
    if not all(math.isfinite(v) and v>0 for v in valores): raise ValueError('Dimensões e passo devem ser positivos e finitos')
    if not all(math.isfinite(v) and v>=0 for v in (balanco_tras,folga,afastamento_faixa)) or comprimento < entre_eixos+balanco_tras:
        raise ValueError('Balanços, folga ou comprimento incompatíveis')
    if not angulos or any(not math.isfinite(a) or a<=0 or a>=90 for a in angulos): raise ValueError('Ângulos devem ficar entre 0 e 90 graus')
    # Vaga x=0..vao; meio-fio y=0. Carros estáticos prolongam-se 5 m para fora da vaga.
    carros=[[(a,-folga),(b,-folga),(b,largura_carro+folga),(a,largura_carro+folga)]
            for a,b in ((-5-folga,-folga),(vao+folga,vao+5+folga))]
    traseira=balanco_tras; frente=comprimento-traseira
    x0=(vao-comprimento)/2+traseira; y0=largura/2+folga
    y_inicio=largura_carro+largura/2+afastamento_faixa
    deslocamento=y_inicio-y0
    if deslocamento <= 0: raise ValueError('Faixa inicial deve estar mais afastada do meio-fio que a posição estacionada')
    linhas=[]; resumo=[]
    for angulo in angulos:
        raio=entre_eixos/math.tan(math.radians(angulo))
        if deslocamento > 4*raio:
            resumo.append({'esterco_equivalente_graus':angulo,'status':'fora_do_dominio_dois_arcos','raio_m':raio})
            continue
        theta=math.acos(1-deslocamento/(2*raio)); comprimento_arco=raio*theta
        n=max(1,math.ceil(comprimento_arco/passo)); ds=comprimento_arco/n
        x,y,h=x0,y0,0.; poses=[]
        for i in range(2*n+1):
            p=retangulo(x,y,h,traseira,frente,largura)
            col=any(sobrepoe(p,c) for c in carros)
            meio_fio=min(v for _,v in p)<folga
            poses.append((x,y,h,col,meio_fio))
            if i==2*n: break
            k=(1 if i<n else -1)/raio
            novo=h+k*ds
            x+=(math.sin(novo)-math.sin(h))/k
            y+=(-math.cos(novo)+math.cos(h))/k
            h=novo
        colisoes=sum(p[3] for p in poses); viola=sum(p[4] for p in poses)
        valido=colisoes==0 and viola==0 and comprimento+2*folga<vao
        resumo.append({'esterco_equivalente_graus':angulo,'status':'trajetoria_livre_no_modelo' if valido else 'trajetoria_intercepta_obstaculo_ou_folga',
                       'raio_m':round(raio,3),'arco_graus':round(math.degrees(theta),2),'comprimento_manobra_m':round(2*comprimento_arco,3),
                       'amostras_com_colisao':colisoes,'amostras_fora_folga_meio_fio':viola,'alcance_lateral_maximo_m':round(max(v for x,y,h,_,_ in poses for _,v in retangulo(x,y,h,traseira,frente,largura)),3)})
        for j,(x,y,h,col,meio) in enumerate(reversed(poses)):
            linhas.append({'natureza':'SINTETICO','esterco_equivalente_graus':angulo,'amostra':j,
                           'distancia_percorrida_m':round(j*ds,4),'x_eixo_traseiro_m':round(x,4),'y_eixo_traseiro_m':round(y,4),
                           'orientacao_graus':round(math.degrees(h),3),'colisao_carro':col,'viola_folga_meio_fio':meio})
    return resumo,linhas


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vao',type=float,default=4.5);p.add_argument('--comprimento',type=float,default=2.765)
    p.add_argument('--largura',type=float,default=1.64);p.add_argument('--entre-eixos',type=float,default=2.015)
    p.add_argument('--balanco-tras',type=float,default=.35);p.add_argument('--largura-carro',type=float,default=1.8)
    p.add_argument('--folga',type=float,default=.1);p.add_argument('--afastamento-faixa',type=float,default=.3)
    p.add_argument('--angulos',type=float,nargs='+',default=[6,15,30]);p.add_argument('--passo',type=float,default=.025)
    p.add_argument('--saida',default='dados_sinteticos_estacionamento.csv')
    a=p.parse_args(); params=vars(a).copy(); destino=params.pop('saida')
    resumo,linhas=gerar(**params)
    if not linhas: p.error('Nenhuma trajetória no domínio: revise ângulos ou parâmetros')
    with open(destino,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=linhas[0],delimiter=';');w.writeheader();w.writerows(linhas)
    meta={'natureza':'SINTETICO','hipoteses':params,'resumo':resumo,
          'limites':'Bicicleta cinemática, dois arcos fixos e deslocamento lateral prescrito; esterço equivalente não é ângulo da roda interna. Carro retangular, obstáculos estacionários, sem tráfego, velocidade, atrito, pedestres, guias, espelhos ou piso. Amostragem pode perder colisões. Falha desta manobra não prova impossibilidade, sucesso não prova segurança.'}
    Path(destino).with_suffix('.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(resumo,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
