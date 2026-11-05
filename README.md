# Hammerhead — ferramentas de estudo de um triciclo elétrico

O Hammerhead é um anteprojeto de triciclo elétrico com duas rodas direcionais dianteiras e uma roda traseira central. O conceito prevê quatro motores, banco removível para dois ocupantes em tandem, cobertura leve e uma prancha para descanso com o veículo estacionado. As laterais em alumínio formam W e V, com três hastes destacadas que lembram as brânquias de um tubarão-cabeça-de-martelo. Os programas desta pasta exploram geometria, transmissão, cargas, frenagem, estabilidade, montagem e manobras a partir de hipóteses e dados sintéticos. O projeto está em evolução: dimensões de peças, compatibilidade, segurança, conforto e desempenho precisam de medições, análise de engenharia e ensaios físicos. Resultados de scripts, desenhos e imagens não constituem aprovação para fabricação ou circulação.

## Sobre este repositório

Esta pasta reúne estudos desenvolvidos em etapas, com modelos de complexidade e datas diferentes. Os arquivos servem para **examinar hipóteses, reproduzir cálculos e localizar pendências**. Um número produzido por um script vale apenas para suas entradas e simplificações. Os programas não formam um único simulador integrado e não devem ser tratados como um pacote pronto para dimensionar um veículo.

Leia primeiro:

* `prompts.md`: roteiro dos problemas e correções estudados; contém também trechos históricos.
* `RELATORIO\_FINAL\_PRANCHA.md`: decisão sobre a prancha, hipóteses e limites da verificação em planta.
* `Balancim\_em\_U\_afastados\_x.md`: conceito de balancim em U e incompatibilidades a resolver.
* `fabricacao.md`: conceito de montagem, incluindo a proposta de banco removível; dados de fabricação devem ser revisados.
* `Hammerhead\_topo.svg`, `Hammerhead\_lateral.svg` e `Hammerhead\_frontal.svg`: vistas conceituais; algumas cotas do veículo ainda são históricas.

### Referências de projeto e limitações atuais

A base dorsal em `configuracoes.py` usa eixo dianteiro em **x = 600 mm**, eixo traseiro em **x = 2615 mm** e bitola de **1420 mm**; o entre-eixos correspondente é 2015 mm. A referência anterior de eixo traseiro x = 2515 mm ainda aparece em desenhos e modelos legados. As coordenadas são hipóteses, não medições de um veículo construído.

A prancha representada foi reduzida 47 mm por lateral: **906 mm na frente e 426 mm na extremidade estreita**. O polígono da vista histórica mede cerca de 1795 mm longitudinalmente. A medida útil para descanso e a acomodação de duas pessoas precisam ser verificadas na base dorsal e em maquete. O modelo estrutural ainda contém dimensões anteriores do quadro e piso; não presuma que a redução foi propagada a todos os programas.

No candidato de balancim em U, uma varredura em planta, com esterço zero e curso amostrado de −40 a +80 mm, não mostrou sobreposição de área entre a prancha reduzida e os corpos simplificados dos motores. No ponto crítico há **folga nominal de 0 mm**. Isso não demonstra folga tridimensional: esterço, tolerâncias, flange, corrente, proteção, estrutura, apoios e posições entre amostras precisam ser verificados. O modelo de pneu e as posições dos motores são hipóteses.

O banco é concebido como uma armação removível. Em cada lateral, as hastes W1, W3 e V1 têm dois pontos de fixação cada: seis por lado e 12 no conjunto. Os dois parafusos inferiores de V1, um por lado e já incluídos nesses 12, são propostos para liberar a armação do banco. Encaixes, apoio da cabine sem banco e retenção dos ocupantes ainda precisam de projeto.

## Preparação do ambiente

Use Python 3.10 ou posterior. O trabalho recente foi executado com Python 3.13; não foi feito um teste de compatibilidade em todas as versões. No Windows, por exemplo:

```powershell
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install numpy pandas matplotlib
```

Muitos programas usam apenas a biblioteca padrão. As análises numéricas e desenhos que importam `numpy`, `pandas` ou `matplotlib` exigem esses pacotes. Não há, nesta pasta, um arquivo de dependências com versões fixadas; para uma publicação reproduzível, registre as versões efetivamente usadas. `importar\_topo.py` e `inspecionar\_blend.py` exigem o Python do **Blender**, que fornece `bpy`; instalar `bpy` com `pip` não substitui automaticamente esse ambiente.

Mantenha os arquivos Python e os CSVs de entrada juntos. Em especial, `configuracoes.py` aponta para `inventario\_dorsal.csv` e `estabilidade\_massas.py` usa `inventario\_estimado.csv` por padrão. O formato dos inventários, suas unidades e procedência devem ser preservados. Consulte também `inventario\_dianteira.csv`, `inventario\_modulo\_biz.csv` e `inventario\_dorsal\_motores\_14kg.csv` conforme o estudo; nomes de componentes e massas podem representar versões anteriores.

### Dependências locais ausentes no conjunto atual

Antes de publicar apenas os arquivos `.py`, observe que **o conjunto da raiz não é autocontido**. A análise estática dos imports encontrou módulos usados por arquivos atuais que não estão na raiz:

|Módulo ausente|Usado diretamente por|
|-|-|
|`cinematica\_dianteira.py`|`envelope\_garfo.py`, `test\_dois\_ocupantes\_baixa\_velocidade.py`|
|`empacotamento\_dianteiro.py`|`envelope\_garfo.py`, `varredura\_geometria\_modulo.py`|
|`ensaio.py`|`gerador\_rolamentos.py`, `verificacao\_rolamento.py`|
|`frenagem\_curva.py`|`ensaio\_integrado.py`, `test\_prompts\_corrigidos.py`|



## Início rápido

Execute os comandos a partir da raiz do projeto. As opções efetivamente disponíveis podem ser consultadas com `--help` nos programas que usam `argparse`:

```powershell
python balancim\_em\_u.py --help
python avaliar\_decisoes\_modulo.py --help
python estacionamento\_sintetico.py --help
python varredura\_modulo\_completo.py --help
```

Para examinar o balancim com as hipóteses padrão e gerar uma lista de corte conceitual:

```powershell
python balancim\_em\_u.py --layout afastados\_x\_B\_a\_frente
python balancim\_em\_u.py --csv
```

`--csv` grava `balancim\_em\_u\_lista\_corte.csv`; essa lista **não é ordem de fabricação**. O parâmetro `--buscar` explora candidatos de layout conforme filtros do programa, que não incluem todas as verificações 3D. `--L` ajusta o comprimento do balancim e `--xs` a posição dos braços, ambos em milímetros.

Para comparar vínculos de motores e roda no plano longitudinal:

```powershell
python avaliar\_decisoes\_modulo.py --passo 5 --saida estudo\_decisoes\_modulo
```

O comando escreve `amostras.csv`, `resumo.csv` e `relatorio.md` no diretório de saída, substituindo arquivos com esses nomes. É uma triagem 2D, com raios de engrenagem estimados; ela não avalia o veículo completo.

Para explorar a baliza sintética em vão de 4,50 m:

```powershell
python estacionamento\_sintetico.py --vao 4.5 --saida minha\_baliza.csv
```

O programa usa um modelo geométrico idealizado; a manobra real depende de visibilidade, reação, folgas, esterço, pneus e dimensões medidas. Os números e unidades aceitos aparecem em `--help`.

**Arquivos gerados:** alguns scripts escrevem CSV, JSON, HTML, imagens ou listas de corte. Dependendo do programa, podem sobrescrever saídas existentes. Leia as opções e escolha uma pasta ou nome novo antes de executar; os exemplos não são ensaios físicos.

## Catálogo de ferramentas

### Configuração, massas e estrutura

|Arquivo|Função e limite|
|-|-|
|`configuracoes.py`|Define bases comparáveis e caminhos dos inventários, incluindo `p2\_dorsal`; fornece funções importadas por outros módulos.|
|`modelo\_estrutural.py`|Reúne hipóteses geométricas, perfis, massas e estrutura; conserva dimensões anteriores de quadro/piso.|
|`estabilidade\_massas.py`|Lê inventários, estima centro de gravidade, reações e estabilidade estática; aceita dados de pesagem e exportação. Não modela toda a dinâmica.|
|`revisar\_calculos.py`|Calcula reações idealizadas sobre três apoios; serve à revisão de hipóteses de carga.|
|`suporte\_bateria.py`|Estuda suportes e cargas da bateria; inclui hipóteses históricas da bateria na cunha. Verificar a posição dorsal antes de usar resultados.|
|`percurso\_um\_ocupante.py`|Estima consumo e percurso com um ocupante; não garante autonomia, desempenho ou vida da bateria.|
|`relatorio\_visual.py`|Funções auxiliares para relatórios HTML/SVG e saída de programas; é módulo de apoio.|

### Direção, suspensão e empacotamento dianteiro

|Arquivo|Função e limite|
|-|-|
|`cabecote\_pivo.py`|Estuda caixa, rolamentos, travessa e passagem da perna interna; resultados são preliminares e dependem da geometria adotada.|
|`garfo\_dimensionamento.py`|Avalia esforços e perfis de um garfo de duas pernas; não substitui análise de fadiga e ligações.|
|`envelope\_garfo.py`|Triagem de empacotamento do garfo; depende dos módulos locais de cinemática e empacotamento atualmente ausentes na raiz.|
|`geometria\_balancim.py`|Modelo **histórico não validado**; contém hipóteses antigas e não deve prevalecer sobre a revisão atual.|
|`balancim\_em\_u.py`|Explora geometria, folgas estimadas, movimento, tubos, soldas e candidatos de um balancim em U; continua sendo conceito.|
|`avaliar\_decisoes\_modulo.py`|Compara layouts e vínculos de motores/coroa em 2D ao longo do curso; gera relatório e CSVs em uma pasta escolhida.|
|`varredura\_geometria\_modulo.py`|Varre posições de componentes do módulo; requer `empacotamento\_dianteiro.py`, ausente na raiz.|
|`varredura\_modulo\_completo.py`|Monta volumes simplificados e varre esterço e suspensão; volumes e vínculos são aproximações e devem ser auditados.|
|`analise\_interfaces\_modulo.py`|Examina interfaces axiais e propõe configurações; `--proposta varredura` usa a referência da varredura. Sobreposição axial isolada não prova colisão radial.|
|`ensaios\_sinteticos\_modulo.py`|Gera dados sintéticos de incompatibilidades, esterço, corrente e montagem, em formatos disponíveis no CLI. São hipóteses, não ensaios medidos.|

### Eixos, freios e rolamentos

|Arquivo|Função e limite|
|-|-|
|`fcl\_eixo\_balanco.py`|Diagrama de corpo livre e cargas idealizadas para eixo dianteiro em balanço.|
|`fcl\_eixo\_garfo.py`|Estuda o eixo dianteiro com apoio nos dois lados; é uma arquitetura distinta do eixo em balanço.|
|`braco\_reacao\_freio.py`|Conceito do braço de reação do freio, com forças e tensões simplificadas.|
|`ensaio\_torque\_freio.py`|Balanço sintético de torque do freio e hipóteses de transmissão de carga.|
|`gerador\_rolamentos.py`|Gera cenários sintéticos de reações; depende de `ensaio.py`, ausente na raiz, e não aprova rolamentos.|
|`verificacao\_rolamento.py`|Estuda exigências de carga e vida de rolamentos; depende de `ensaio.py` e de dados reais do componente.|
|`analise\_viabilidade\_25mm.py`|Análise exploratória de eixo traseiro Ø25 mm, com bibliotecas numéricas e gráficas.|
|`analise\_viabilidade\_25mm\_CORRIGIDA.py`|Revisão da análise anterior; leia hipóteses antes de comparar os resultados.|
|`analise\_comparativa\_FINAL\_28mm.py`|Compara diâmetros de eixo em hipóteses específicas; o nome do arquivo não significa aprovação.|
|`desenho\_corte\_eixo\_traseiro.py`|Gera ilustração de corte do eixo traseiro, usando NumPy e Matplotlib; não é desenho final de usinagem.|

### Transmissão, manobras e integração

|Arquivo|Função e limite|
|-|-|
|`transmissao\_dianteira.py`|Estuda laços de corrente, motores, torque e desempenho, além de modelos de suspensão e esterço. Possui arranjos diferentes: conferir `--arranjo` e suas hipóteses.|
|`estacionamento\_sintetico.py`|Gera cenários de baliza longitudinal por arcos ideais; produz dados sintéticos em CSV.|
|`ensaio\_integrado.py`|Triagem sintética integrada; depende de `frenagem\_curva.py`, ausente na raiz.|
|`traseira\_telescopica.py`|Examina o conceito de suspensão traseira com duas hastes telescópicas e uma roda central.|
|`reforco\_haste.py`|Compara conceitos de reforço da haste traseira por tensões nominais, sem avaliação completa de fadiga.|
|`auditoria\_completa\_projeto.py`|Reúne verificações de projeto e dados; depende de NumPy/Pandas. Uma auditoria automática não valida hipóteses físicas.|
|`verificacao\_prompt4.py`|Verifica aspectos associados ao Prompt 4, como base e balanço de energia; confira suas dependências e a versão dos modelos usados.|

### Blender

|Arquivo|Função|
|-|-|
|`importar\_topo.py`|Importa `Hammerhead\_topo.svg` em uma cena Blender e pode gravar uma cópia. Requer Blender e `bpy`.|
|`inspecionar\_blend.py`|Lista coleções e objetos da cena aberta no Blender.|

Exemplo de chamada, ajustando o executável e o nome do arquivo existente:

```powershell
blender --background arquivo\_de\_entrada.blend --python importar\_topo.py -- arquivo\_de\_saida.blend
```

O `.blend` anteriormente descrito no relatório continha uma vista superior importada em Grease Pencil, não um modelo tridimensional completo. **Confira se o arquivo de entrada está incluído na publicação**: ele não foi encontrado na raiz durante a elaboração deste README.

## Testes

Os arquivos `test\_\*.py` cobrem partes dos modelos. A maioria usa `unittest`; alguns estudos também importam bibliotecas numéricas ou módulos locais ausentes. Uma execução direcionada é:

```powershell
python -m unittest test\_balancim\_em\_u
```

A execução de toda a pasta pode ser feita com `python -m unittest discover`, mas o conjunto atualmente pode falhar na coleta enquanto os módulos ausentes não forem restaurados e conciliados. Um teste aprovado só verifica os casos e asserções implementados; não comprova que a hipótese corresponde ao veículo real. Alguns testes com nomes históricos podem incluir cálculos ou geração de saídas: leia o arquivo antes de executá-lo em uma cópia de trabalho com dados importantes.

Arquivos de teste presentes na raiz:

* **Geometria e módulos:** `test\_analise\_interfaces\_modulo.py`, `test\_balancim\_em\_u.py`, `test\_cabecote\_pivo.py`, `test\_envelope\_garfo.py`, `test\_garfo\_dimensionamento.py`, `test\_varredura\_geometria\_modulo.py`.
* **Eixos, freios e rolamentos:** `test\_braco\_reacao\_freio.py`, `test\_divisao\_esforcos\_balanca.py`, `test\_eixo\_28mm.py`, `test\_ensaio\_torque\_freio.py`, `test\_fcl\_eixo\_balanco.py`, `test\_fcl\_eixo\_garfo.py`, `test\_gerador\_rolamentos.py`, `test\_verificacao\_rolamento.py`.
* **Uso e integração:** `test\_corrections.py`, `test\_dois\_ocupantes\_baixa\_velocidade.py`, `test\_ensaio\_integrado.py`, `test\_estacionamento\_sintetico.py`, `test\_prompts\_corrigidos.py`, `test\_um\_ocupante\_50km.py`.
* **Traseira:** `test\_reforco\_haste.py`, `test\_traseira\_telescopica.py`.

## Convenções e leitura dos resultados

* Geometria do módulo geralmente usa **mm** e o veículo tem x longitudinal, y transversal e z vertical. Alguns cálculos de dinâmica e massas usam **m**, kg, N e N·m; confira a unidade de cada função e saída.
* No sistema lateral, as posições podem ser espelhadas por sinal de y. Confirme a origem e o lado antes de comparar arquivos.
* Valores de CSV e relatórios são estimativas ou dados sintéticos, salvo identificação de medição. Nomes como “corrigida” ou “final” indicam revisões locais, não certificação.
* Os modelos podem usar arquiteturas incompatíveis, como eixo em balanço versus eixo biapoiado, ou baterias e geometrias de versões diferentes. Compare premissas antes de combinar números.
* A verificação por caixas, perfis estimados ou projeções identifica possíveis conflitos; não substitui geometria real, folga tridimensional, tolerâncias e verificação em todo o curso.
* Cargas quase-estáticas, tensões nominais e parâmetros estimados não avaliam por si só fadiga, soldas, impactos, estabilidade dinâmica, homologação ou segurança dos ocupantes.

## 

