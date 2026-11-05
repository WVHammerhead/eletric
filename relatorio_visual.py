"""Relatório HTML/SVG autônomo, gerado apenas com a biblioteca padrão.

Importar não cria arquivos nem modifica stdout. --html é sempre optativo.
"""
import json
import sys
from html import escape
from pathlib import Path

from modelo_estrutural import (
    ACO, ALUMINIO, INDEFINIDO, INTERFACE, AVISO, FONTE, HIERARQUIA,
    X_FRENTE_TRAP, X_EIXO_DIANT, X_EIXO_TRAS, BITOLA, PNEU_DIANT,
    PNEU_TRAS, diametro, geometria, largura_quadro, barras_piso, massas_parciais,
)


def configurar_console():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def adicionar_saida(parser):
    parser.add_argument("--html", type=Path, help="Salvar relatório visual HTML (arquivo novo)")


def planta_svg():
    """Planta nominal em escala uniforme; não representa detalhes de uniões."""
    s = .30
    def x(v):
        return 40 + v*s
    def y(v):
        return 290 + v*s
    partes = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 570" role="img" aria-labelledby="planta-titulo">',
              '<title id="planta-titulo">Planta nominal: duas longarinas, 14 barras e três rodas</title>',
              '<rect width="940" height="570" fill="#f6f8fb" rx="16"/>']
    for eixo in (X_EIXO_DIANT, X_EIXO_TRAS):
        partes.append(f'<path d="M{x(eixo)} 50 V 520" stroke="#a1aebd" stroke-dasharray="5 6"/>')
        partes.append(f'<text x="{x(eixo)}" y="40" text-anchor="middle">Eixo · {eixo} mm</text>')
    for eixo, lateral, pneu in ((X_EIXO_DIANT, -BITOLA/2, PNEU_DIANT),
                               (X_EIXO_DIANT, BITOLA/2, PNEU_DIANT), (X_EIXO_TRAS, 0, PNEU_TRAS)):
        d = diametro(*pneu[1:])
        partes.append(f'<rect x="{x(eixo-d/2)}" y="{y(lateral-pneu[2]/2)}" width="{d*s}" height="{pneu[2]*s}" rx="9" fill="#64748b" opacity=".65"/>')
    for sinal in (-1, 1):
        # Faces externas nominais; largura de 80 mm projetada transversalmente.
        pontos = [(X_FRENTE_TRAP, sinal*500), (X_EIXO_TRAS, sinal*largura_quadro(X_EIXO_TRAS)/2),
                  (X_EIXO_TRAS, sinal*(largura_quadro(X_EIXO_TRAS)/2-80)), (X_FRENTE_TRAP, sinal*420)]
        pts = ' '.join(f'{x(a)},{y(b)}' for a,b in pontos)
        partes.append(f'<polygon points="{pts}" fill="{ACO}"/>')
    for barra in barras_piso():
        pos, comp = barra["x_mm"], barra["comprimento_mm"]
        partes.append(f'<rect x="{x(pos)}" y="{y(-comp/2)}" width="24" height="{comp*s}" fill="{ALUMINIO}" opacity=".88"/>')
        partes.append(f'<text x="{x(pos+40)}" y="295" text-anchor="middle" fill="white" font-size="11">{barra["barra"]}</text>')
        for sinal in (-1, 1):
            partes.append(f'<circle cx="{x(pos+40)}" cy="{y(sinal*(comp/2-40))}" r="3" fill="white" stroke="{INTERFACE}" stroke-width="2"/>')
    g = geometria()
    partes.append(f'<rect x="{x(g["inicio_estatico_roda_mm"])}" y="{y(-260)}" width="{g["extensao_leve_mm"]*s}" height="156" fill="{ALUMINIO}" fill-opacity=".08" stroke="{ALUMINIO}" stroke-dasharray="7 5"/>')
    partes += ['<text x="460" y="540" text-anchor="middle">Frente à esquerda · extensão elevada em tracejado · medidas nominais</text>', '</svg>']
    return ''.join(partes)


def tabela_dados(valor):
    if isinstance(valor, dict):
        return '<dl>' + ''.join(f'<dt>{escape(str(k).replace("_", " "))}</dt><dd>{tabela_dados(v)}</dd>' for k,v in valor.items()) + '</dl>'
    if isinstance(valor, list):
        return '<ol>' + ''.join(f'<li>{tabela_dados(v)}</li>' for v in valor) + '</ol>'
    if isinstance(valor, bool):
        return 'Sim' if valor else 'Não'
    if isinstance(valor, float):
        return f'{valor:,.3f}'.replace(',', ' ').replace('.', ',')
    return escape(str(valor))


def documento(titulo, dados):
    massas = massas_parciais()
    cards = ''.join(f'<div class="card"><span>{label}</span><strong>{v:.1f} <small>{u}</small></strong></div>' for label,v,u in (
        ('Longarinas de aço', massas['duas_longarinas_kg'], 'kg'),
        ('14 barras de piso', massas['14_barras_piso_kg'], 'kg'),
        ('Subtotal parcial', massas['subtotal_quadro_e_piso_kg'], 'kg'),
        ('Corredor na ponta', (BITOLA-90)/2-500, 'mm')))
    linhas = ''.join(f'<tr><td><span class="nivel n{n}">{"?" if n == 0 else n}</span></td><td>{escape(ids)}<b>{escape(nome)}</b></td><td>{escape(perfil)} mm</td><td>{escape(nota)}</td></tr>' for n,ids,nome,perfil,nota in HIERARQUIA)
    return f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(titulo)} · Hammerhead</title>
<style>
:root{{--ink:#172638;--muted:#536477;--paper:#f1f4f8}}*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 'Segoe UI',Arial,sans-serif}}
header{{background:#142a40;color:white;padding:44px max(24px,calc((100vw - 1120px)/2))}}
.eyebrow{{font-size:12px;letter-spacing:3px;color:#a8c6e2}}h1{{font-size:38px;line-height:1.15;margin:12px 0}}header p{{max-width:780px;color:#d0deeb}}
main{{max-width:1168px;padding:28px 24px;margin:auto}}section{{background:white;border:1px solid #dce3eb;border-radius:16px;padding:24px;margin:24px 0}}
h2{{font-size:22px;margin:0 0 8px}}.muted{{color:var(--muted)}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.card{{background:white;border-radius:12px;padding:20px;border-top:4px solid {ACO}}}.card span{{display:block;color:var(--muted);font-size:13px}}strong{{display:block;font-size:30px}}small{{font-size:15px;font-weight:400}}
svg{{display:block;width:100%;height:auto;font-family:'Segoe UI',Arial,sans-serif;font-size:13px}}
.legend{{display:flex;flex-wrap:wrap;gap:20px;margin:16px 0}}.legend i{{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:7px}}
.table-wrap{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:700px;text-align:left}}th{{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}}td,th{{padding:14px 10px;border-bottom:1px solid #e5eaf0;vertical-align:top}}td b{{display:block}}td:nth-child(2){{min-width:220px}}
.nivel{{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:8px;color:white;background:{ACO}}}.n2{{background:{ACO};border:3px double white}}.n3,.n4{{background:{ALUMINIO};color:#102c17}}.n4{{border:3px double white}}.n0{{background:{INDEFINIDO};color:#253041}}
dl{{display:grid;grid-template-columns:minmax(160px,1fr) minmax(0,2fr);margin:0}}dt,dd{{margin:0;padding:8px;border-bottom:1px solid #e5eaf0;overflow-wrap:anywhere}}dt{{color:var(--muted)}}dd dl{{display:block}}dd dl dt{{font-size:12px}}ol{{padding-left:20px}}li{{margin-bottom:12px}}summary{{cursor:pointer;font-weight:600}}.notice{{border-left:4px solid #d29b21;background:#fff7e6;padding:16px}}footer{{color:var(--muted);font-size:12px;padding:8px 0 28px}}
@media(max-width:650px){{.cards{{grid-template-columns:repeat(2,1fr)}}h1{{font-size:29px}}section{{padding:16px}}dl{{display:block}}}}
@media print{{header{{background:white;color:#172638;padding:12px}}header p{{color:#536477}}main{{padding:0}}section{{break-inside:avoid}}}}
</style><header><div class="eyebrow">HAMMERHEAD / ESTUDO ESTRUTURAL</div><h1>{escape(titulo)}</h1><p>Quatro níveis de bitolas. Geometria coerente. Massa concentrada nos caminhos críticos de carga.</p></header>
<main><p class="notice">{escape(AVISO)}</p><p class="muted">Referência nominal comum abaixo: eixos 600 / 2515 mm, bitola 1338 mm. Cenários específicos constam nos resultados ao final.</p><div class="cards">{cards}</div>
<section><h2>Geometria do quadro e do piso</h2><p class="muted">Planta de estudo. Suspensão, travessas e uniões ainda não dimensionadas.</p>{planta_svg()}
<div class="legend"><span><i style="background:{ACO}"></i>Aço · níveis 1 e 2</span><span><i style="background:{ALUMINIO}"></i>Alumínio · níveis 3 e 4</span><span><i style="background:{INDEFINIDO}"></i>A definir</span><span><i style="background:{INTERFACE}"></i>Interface isolada</span></div>
<p class="notice">Piso útil: {geometria()['comprimento_util_com_folga_mm']:.1f} mm; margem nominal {geometria()['margem_sobre_o_minimo_mm']:.1f} mm, com {geometria()['margem_apos_tolerancia_assumida_mm']:.1f} mm após a reserva de oficina assumida. EVA de 10 mm eleva a superfície de uso para z = 295 mm. Folgas dinâmicas ainda precisam de confirmação.</p></section>
<section><h2>Hierarquia por função</h2><p class="muted">N1: nós críticos e longarinas · N2: aço tubular leve · N3: piso e extensão · N4: superestrutura leve.</p><div class="table-wrap"><table><thead><tr><th>Nível</th><th>Componente</th><th>Perfil candidato</th><th>Critério</th></tr></thead><tbody>{linhas}</tbody></table></div></section>
<section><h2>Resultados desta execução</h2>{tabela_dados(dados)}</section><footer>Fonte: {FONTE}. Perfis ideais; aço 7850 kg/m³ e alumínio 2700 kg/m³. Cobertura não é gaiola de capotamento.</footer></main></html>'''


def salvar_html(caminho, titulo, dados):
    # Não substituir documentos ou artefatos existentes por engano.
    caminho = Path(caminho)
    if caminho.suffix.lower() != '.html':
        raise ValueError("O relatório visual exige extensão .html")
    with caminho.open('x', encoding='utf-8') as arquivo:
        arquivo.write(documento(titulo, dados))
    return caminho.resolve()


def emitir(dados, titulo, html=None):
    configurar_console()
    if html:
        caminho = salvar_html(html, titulo, dados)
        print(f"Relatório visual: {caminho}", file=sys.stderr)
    print(json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False))
