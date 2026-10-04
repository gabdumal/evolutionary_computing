#import "../packages.typ": *
#import "../components.typ": *
#import "../template.typ": *


#title_slide(glossarium.gls-long("cso") + sym.space + emoji.cat)

== Origem

O #stress(gls("cso", link: false)) é um algoritmo bioinspirado criado por #cite_prose(<chu:2006:cat_swarm_optimization>) #footnote[
  #cite(<chu:2006:cat_swarm_optimization>, form: "full")
].
É motivado pelo #gls("pso") e pelo #gls("aco").

Seu mecanismo de inspiração é a movimentação de #stress[felinos] em caçadas:
- gatos passam a maior parte do tempo #strong[alertas], movendo-se pouco;
- #strong[observam] o ambiente à procura de presas;
- ao encontrar, se movem #strong[rapidamente] para o ataque.

#pagebreak()

== Representação

Cada #stress[solução] no espaço de busca é representada por um #strong[gato].
- Sua #strong[posição] é composta por $M$ dimensões.
- Guarda um vetor de #strong[velocidade] para cada dimensão.
- Salva o valor de #strong(get_term("fitness")) calculado.
- Identifica o modo de agir atual:
  - #strong(get_term("seeking")) (procura) ou
  - #strong(get_term("tracing")) (perseguição).

A #stress[melhor solução global] é armazenada durante a execução.\
Decide-se o tamanho da #strong[população] e o critério de #strong[parada].

#pagebreak()

== #get_term("seeking", capitalize: true)

=== Hiperparâmetros

#stress[`smp`:] #foreign_text[seeking memory pool].\ #h(leading)
Quantidade de pontos próximos que um gato avalia em cada iteração.

#stress[`srd`:] #foreign_text[seeking range of the selected dimension].\ #h(leading)
Comprimento da distância de até onde o gato pode observar.

#stress[`cdc`:] #foreign_text[counts of dimension to change].\ #h(leading)
Quantidade de dimensões que podem variar para amostrar os pontos.\ #h(leading)
No NiaPy, funciona como porcentagem.

#stress[`spc`:] #foreign_text[self-position considering].\ #h(leading)
Decide se o gato pode continuar parado no mesmo ponto.

=== Algoritmo

+ Faz `j = smp` #strong[cópias] da posição atual do gato.
+ Para cada, incrementa ou decrementa a #strong[posição] com `srd`.
+ Calcula a #strong(get_term("fitness")) de todas e converte em probabilidades de seleção.
+ Seleciona um ponto aleatoriamente e #strong[move] o gato para lá.

Esse modo favorece a #stress[busca local].

#pagebreak()

== #get_term("tracing", capitalize: true)

=== Hiperparâmetros

#stress[`max_velocity`:] #foreign_text[maximal velocity].\ #h(leading)
Velocidade máxima.

#stress[`c1`:] #foreign_text[tracing constant].\ #h(leading)
Coeficiente de ajuste da relevância do tracing.

#stress[`mixture_ratio`:] #foreign_text[mixture ratio].\ #h(leading)
Proporção de gatos que vão entrar em #get_term("tracing") a cada iteração.

#colbreak()

=== Algoritmo

Atualiza a #stress[posição] $x$ de um gato $k$ em todas as dimensões $d$ de acordo com os vetores de velocidade segundo:

#align(center)[
  $v_(k,d) = v_(k,d) + r_1 #math.times c_1 #math.times (#text(fill: theme_color)[$x_("best",d)$] - x_(k,d))$ \
  $x_(k,d) = x_(k,d) + v_(k,d)$
]

- $r_1$ é um valor #strong[aleatório] entre $[0,1]$.
- #text(fill: theme_color)[$x_("best",d)$] é a posição do gato #strong[melhor avaliado] até então.

Caminha na direção da #stress[melhor solução].

#pagebreak()

#title_slide("Funções de otimização")

== Rosenbrock

#grid(
  columns: 2,
  [
    #stress[Vale] de busca #strong[estreito] e curvo, que se estende de forma não-linear #footnote[
      Imagem: #link("https://commons.wikimedia.org/wiki/File%3ARosenbrock%27s_function_in_3D.pdf")
    ].

    - Avalia a capacidade de #strong[refinamento] e exploração #strong[direcionada] em regiões estreitas do espaço de busca.
  ],
  [
    #image("../assets/images/rosenbrock.jpg")

  ],
)

#pagebreak()

== Schwefel

#grid(
  columns: 2,
  [
    #stress[Multimodal], com diversos picos e vales (ótimos locais) #footnote[
      Imagem: #link("https://infinity77.net/global_optimization/test_functions_nd_S.html")
    ].

    - Avalia a capacidade de #strong[exploração global] e de evitar a #strong[convergência] prematura para um ótimo local.
  ],
  [
    #image("../assets/images/schwefel.png")

  ],
)

#pagebreak()

== HappyCat

#grid(
  columns: 2,
  [
    #stress[Não separável] e não linear, com região ótima relativamente plana #footnote[
      Imagem: #link("https://infinity77.net/go_2021/scipy_test_functions_nd_H.html")
    ].

    - Avalia a capacidade de lidar com #strong[interação entre variáveis] e com uma região de ótimo menos pronunciada.
  ],
  [
    #image("../assets/images/happy_cat.png")

  ],
)

#title_slide([Validação do #glossarium.gls-short("cso")])

== Protocolo

#grid(
  columns: 2,
  [
    #stress([#get_term("seed", plural: true, capitalize: true):]) 27, 32, 59.

    #stress[10_000] avaliações\ da função.

    #stress[Dimensões:] 10, 100

    #stress[Configurações:] 4_374

    #stress[Execuções:] 78_732
  ],
  [
    #table(
      columns: (auto, 1fr, 1fr, 1fr),

      table.header(strong[Parâmetro], table.cell(colspan: 3, strong[Possibilidades])),

      [population_size], [15], [30], [60],
      [smp], [2], [3], [5],
      [srd], [0.1], [0.2], [0.4],
      [cdc], [0.60], [0.85], [1.0],
      [spc], [], [True], [False],
      [max_velocity], [1.0], [1.9], [3.0],
      [c1], [1.05], [2.05], [3.05],
      [mixture_ratio], [0.1], [0.3], [0.5],
    )
  ],
)

#pagebreak()

== Métrica

Define-se uma #stress[configuração] ($c$): função de otimização ($f$) aplicada no tamanho de dimensão ($d$). Executa-a $s$ vezes, com #get_term("seed", plural: true) diferentes.

- $f_c$ : valores das #text(fill: theme_color)[soluções] encontradas na combinação $c$.
- $overline(f_c)$ : média de $f_c$, em todas as #get_term("seed", plural: true).

Fixa-se um #strong[hiperparâmetro] ($p$).\
Seleciona seu primeiro valor possível ($v$):
`population_size` = 15

- $f_v$ : valores das #text(fill: theme_color)[soluções] encontradas quando usado $v$.
- $overline(f_v)$ : média de $f_v$, em todas as #get_term("seed", plural: true).

Calcula-se o mesmo para os próximos $v$, e se forma $V$.

#colbreak()

#copy_last_heading()

Selecionam-se os valores de #text(fill: theme_color)[solução] mais baixo e mais alto em $V$.

Calcula-se o #stress[intervalo] entre eles.

- $G_p = limits(max)_(v)(overline(f_v)) - limits(min)_(v)(overline(f_v))$ : intervalo causado por $p$ nas soluções.

Normaliza-se pela média global daquela configuração.

- $E_p = bfrac(G_p, abs(overline(f_c)))$ : #stress[efeito] do parâmetro $p$ nas soluções.

#strong[Intuição:] o quanto $p$ fez a #stress[amplitude] da média variar.

#pagebreak()

#let cso_sensitivity = (
  rosenbrock: (
    d10: (
      effect: (
        c1: 17.82252397543381,
        cdc: 94.51824535313312,
        max_velocity: 144.29208082813855,
        mixture_ratio: 197.6221962083765,
        population_size: 70.2983353517607,
        smp: 3.5454303427508416,
        spc: 17.380606977510247,
        srd: 195.88463941396773,
      ),
      best_level: (
        c1: "1.05",
        cdc: "1.00",
        max_velocity: "1.0",
        mixture_ratio: "0.1",
        population_size: "15",
        smp: "5",
        spc: "False",
        srd: "0.4",
      ),
      selected_params: (
        c1: "1.05",
        cdc: "0.60",
        max_velocity: "1.0",
        mixture_ratio: "0.1",
        population_size: "60",
        smp: "3",
        spc: "True",
        srd: "0.1",
      ),
    ),
    d100: (
      effect: (
        c1: 18.280341056517354,
        cdc: 188.8391905023365,
        max_velocity: 223.15158235581748,
        mixture_ratio: 278.152681267128,
        population_size: 77.63716600718466,
        smp: 48.72529063446382,
        spc: 56.6665708052558,
        srd: 272.73942605123545,
      ),
      best_level: (
        c1: "3.05",
        cdc: "1.00",
        max_velocity: "1.0",
        mixture_ratio: "0.1",
        population_size: "15",
        smp: "5",
        spc: "False",
        srd: "0.4",
      ),
      selected_params: (
        c1: "1.05",
        cdc: "0.60",
        max_velocity: "1.9",
        mixture_ratio: "0.1",
        population_size: "15",
        smp: "5",
        spc: "True",
        srd: "0.1",
      ),
    ),
  ),
  schwefel: (
    d10: (
      effect: (
        c1: 0.7454157126034436,
        cdc: 16.19107099188538,
        max_velocity: 5.257996350767764,
        mixture_ratio: 6.823027607410362,
        population_size: 6.55638721904214,
        smp: 7.399112461043586,
        spc: 3.5721400558412277,
        srd: 30.85207412216593,
      ),
      best_level: (
        c1: "3.05",
        cdc: "0.60",
        max_velocity: "3.0",
        mixture_ratio: "0.5",
        population_size: "60",
        smp: "2",
        spc: "True",
        srd: "0.1",
      ),
      selected_params: (
        c1: "2.05",
        cdc: "0.60",
        max_velocity: "3.0",
        mixture_ratio: "0.3",
        population_size: "15",
        smp: "2",
        spc: "True",
        srd: "0.1",
      ),
    ),
    d100: (
      effect: (
        c1: 0.5029965519997607,
        cdc: 3.960549038343239,
        max_velocity: 1.9796295492822384,
        mixture_ratio: 2.963454494605499,
        population_size: 2.4538121523508534,
        smp: 4.012237848022155,
        spc: 2.8887438754641,
        srd: 8.588413596940908,
      ),
      best_level: (
        c1: "3.05",
        cdc: "0.60",
        max_velocity: "3.0",
        mixture_ratio: "0.5",
        population_size: "15",
        smp: "2",
        spc: "True",
        srd: "0.1",
      ),
      selected_params: (
        c1: "3.05",
        cdc: "0.60",
        max_velocity: "3.0",
        mixture_ratio: "0.5",
        population_size: "15",
        smp: "2",
        spc: "True",
        srd: "0.1",
      ),
    ),
  ),
  happy_cat: (
    d10: (
      effect: (
        c1: 0.32303632606498517,
        cdc: 8.629187267965802,
        max_velocity: 1.4518540695534585,
        mixture_ratio: 1.7852977408562416,
        population_size: 2.3323076716183015,
        smp: 2.911583426682747,
        spc: 1.2324506435195468,
        srd: 5.631585896610847,
      ),
      best_level: (
        c1: "3.05",
        cdc: "1.00",
        max_velocity: "1.9",
        mixture_ratio: "0.1",
        population_size: "15",
        smp: "2",
        spc: "False",
        srd: "0.4",
      ),
      selected_params: (
        c1: "1.05",
        cdc: "1.00",
        max_velocity: "1.9",
        mixture_ratio: "0.1",
        population_size: "15",
        smp: "2",
        spc: "False",
        srd: "0.4",
      ),
    ),
    d100: (
      effect: (
        c1: 0.14363977964549926,
        cdc: 12.05829222396496,
        max_velocity: 0.7144447560998489,
        mixture_ratio: 4.302734400985881,
        population_size: 4.3006479332537335,
        smp: 1.9965287811398478,
        spc: 4.541560570394624,
        srd: 11.634167893851057,
      ),
      best_level: (
        c1: "3.05",
        cdc: "1.0",
        max_velocity: "1.9",
        mixture_ratio: "0.5",
        population_size: "15",
        smp: "3.0",
        spc: "False",
        srd: "0.4",
      ),
      selected_params: (
        c1: "2.05",
        cdc: "1.00",
        max_velocity: "1.0",
        mixture_ratio: "0.3",
        population_size: "15",
        smp: "2",
        spc: "False",
        srd: "0.4",
      ),
    ),
  ),
)

== Rosenbrock

#align(center + horizon)[
  #table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Dimensões = 10]],
      table.cell(colspan: 2)[#strong[Dimensões = 100]],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
    ),

    [population_size],
    [#cso_sensitivity.rosenbrock.d10.best_level.population_size],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.population_size)],
    [#cso_sensitivity.rosenbrock.d100.best_level.population_size],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.population_size)],

    [smp],
    [#cso_sensitivity.rosenbrock.d10.best_level.smp],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.smp)],
    [#cso_sensitivity.rosenbrock.d100.best_level.smp],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.smp)],

    [srd],
    [#cso_sensitivity.rosenbrock.d10.best_level.srd],
    strong[#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.srd)],
    [#cso_sensitivity.rosenbrock.d100.best_level.srd],
    strong[#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.srd)],

    [cdc],
    [#cso_sensitivity.rosenbrock.d10.best_level.cdc],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.cdc)],
    [#cso_sensitivity.rosenbrock.d100.best_level.cdc],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.cdc)],

    [spc],
    [#cso_sensitivity.rosenbrock.d10.best_level.spc],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.spc)],
    [#cso_sensitivity.rosenbrock.d100.best_level.spc],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.spc)],

    [max_velocity],
    [#cso_sensitivity.rosenbrock.d10.best_level.max_velocity],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.max_velocity)],
    [#cso_sensitivity.rosenbrock.d100.best_level.max_velocity],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.max_velocity)],

    [c1],
    [#cso_sensitivity.rosenbrock.d10.best_level.c1],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.c1)],
    [#cso_sensitivity.rosenbrock.d100.best_level.c1],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.c1)],

    [mixture_ratio],
    [#cso_sensitivity.rosenbrock.d10.best_level.mixture_ratio],
    stress[#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.mixture_ratio)],
    [#cso_sensitivity.rosenbrock.d100.best_level.mixture_ratio],
    stress[#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.mixture_ratio)],
  )
]

#pagebreak()

== Schwefel

#align(center + horizon)[
  #table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Dimensões = 10]],
      table.cell(colspan: 2)[#strong[Dimensões = 100]],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
    ),

    [population_size],
    [#cso_sensitivity.schwefel.d10.best_level.population_size],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.population_size)],
    [#cso_sensitivity.schwefel.d100.best_level.population_size],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.population_size)],

    [smp],
    [#cso_sensitivity.schwefel.d10.best_level.smp],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.smp)],
    [#cso_sensitivity.schwefel.d100.best_level.smp],
    strong[#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.smp)],

    [srd],
    [#cso_sensitivity.schwefel.d10.best_level.srd],
    stress[#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.srd)],
    [#cso_sensitivity.schwefel.d100.best_level.srd],
    stress[#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.srd)],

    [cdc],
    [#cso_sensitivity.schwefel.d10.best_level.cdc],
    strong[#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.cdc)],
    [#cso_sensitivity.schwefel.d100.best_level.cdc],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.cdc)],

    [spc],
    [#cso_sensitivity.schwefel.d10.best_level.spc],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.spc)],
    [#cso_sensitivity.schwefel.d100.best_level.spc],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.spc)],

    [max_velocity],
    [#cso_sensitivity.schwefel.d10.best_level.max_velocity],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.max_velocity)],
    [#cso_sensitivity.schwefel.d100.best_level.max_velocity],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.max_velocity)],

    [c1],
    [#cso_sensitivity.schwefel.d10.best_level.c1],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.c1)],
    [#cso_sensitivity.schwefel.d100.best_level.c1],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.c1)],

    [mixture_ratio],
    [#cso_sensitivity.schwefel.d10.best_level.mixture_ratio],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.mixture_ratio)],
    [#cso_sensitivity.schwefel.d100.best_level.mixture_ratio],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.mixture_ratio)],
  )
]

#pagebreak()

== HappyCat #emoji.cat.face.smile

#align(center + horizon)[
  #table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Dimensões = 10]],
      table.cell(colspan: 2)[#strong[Dimensões = 100]],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
    ),

    [population_size],
    [#cso_sensitivity.happy_cat.d10.best_level.population_size],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.population_size)],
    [#cso_sensitivity.happy_cat.d100.best_level.population_size],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.population_size)],

    [smp],
    [#cso_sensitivity.happy_cat.d10.best_level.smp],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.smp)],
    [#cso_sensitivity.happy_cat.d100.best_level.smp],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.smp)],

    [srd],
    [#cso_sensitivity.happy_cat.d10.best_level.srd],
    strong[#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.srd)],
    [#cso_sensitivity.happy_cat.d100.best_level.srd],
    strong[#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.srd)],

    [cdc],
    [#cso_sensitivity.happy_cat.d10.best_level.cdc],
    stress[#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.cdc)],
    [#cso_sensitivity.happy_cat.d100.best_level.cdc],
    stress[#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.cdc)],

    [spc],
    [#cso_sensitivity.happy_cat.d10.best_level.spc],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.spc)],
    [#cso_sensitivity.happy_cat.d100.best_level.spc],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.spc)],

    [max_velocity],
    [#cso_sensitivity.happy_cat.d10.best_level.max_velocity],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.max_velocity)],
    [#cso_sensitivity.happy_cat.d100.best_level.max_velocity],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.max_velocity)],

    [c1],
    [#cso_sensitivity.happy_cat.d10.best_level.c1],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.c1)],
    [#cso_sensitivity.happy_cat.d100.best_level.c1],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.c1)],

    [mixture_ratio],
    [#cso_sensitivity.happy_cat.d10.best_level.mixture_ratio],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.mixture_ratio)],
    [#cso_sensitivity.happy_cat.d100.best_level.mixture_ratio],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.mixture_ratio)],
  )
]

#pagebreak()

== Parâmetros selecionados

#align(center + horizon)[
  #table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Rosenbrock]],
      table.cell(colspan: 2)[#strong[Schwefel]],
      table.cell(colspan: 2)[#strong[HappyCat]],
      strong[D=10], strong[D=100], strong[D=10], strong[D=100], strong[D=10], strong[D=100],
    ),

    [population_size],
    [#cso_sensitivity.rosenbrock.d10.selected_params.population_size],
    [#cso_sensitivity.rosenbrock.d100.selected_params.population_size],
    [#cso_sensitivity.schwefel.d10.selected_params.population_size],
    [#cso_sensitivity.schwefel.d100.selected_params.population_size],
    [#cso_sensitivity.happy_cat.d10.selected_params.population_size],
    [#cso_sensitivity.happy_cat.d100.selected_params.population_size],

    [smp],
    [#cso_sensitivity.rosenbrock.d10.selected_params.smp],
    [#cso_sensitivity.rosenbrock.d100.selected_params.smp],
    [#cso_sensitivity.schwefel.d10.selected_params.smp],
    [#cso_sensitivity.schwefel.d100.selected_params.smp],
    [#cso_sensitivity.happy_cat.d10.selected_params.smp],
    [#cso_sensitivity.happy_cat.d100.selected_params.smp],

    [srd],
    [#cso_sensitivity.rosenbrock.d10.selected_params.srd],
    [#cso_sensitivity.rosenbrock.d100.selected_params.srd],
    [#cso_sensitivity.schwefel.d10.selected_params.srd],
    [#cso_sensitivity.schwefel.d100.selected_params.srd],
    [#cso_sensitivity.happy_cat.d10.selected_params.srd],
    [#cso_sensitivity.happy_cat.d100.selected_params.srd],

    [cdc],
    [#cso_sensitivity.rosenbrock.d10.selected_params.cdc],
    [#cso_sensitivity.rosenbrock.d100.selected_params.cdc],
    [#cso_sensitivity.schwefel.d10.selected_params.cdc],
    [#cso_sensitivity.schwefel.d100.selected_params.cdc],
    [#cso_sensitivity.happy_cat.d10.selected_params.cdc],
    [#cso_sensitivity.happy_cat.d100.selected_params.cdc],

    [spc],
    [#cso_sensitivity.rosenbrock.d10.selected_params.spc],
    [#cso_sensitivity.rosenbrock.d100.selected_params.spc],
    [#cso_sensitivity.schwefel.d10.selected_params.spc],
    [#cso_sensitivity.schwefel.d100.selected_params.spc],
    [#cso_sensitivity.happy_cat.d10.selected_params.spc],
    [#cso_sensitivity.happy_cat.d100.selected_params.spc],

    [max_velocity],
    [#cso_sensitivity.rosenbrock.d10.selected_params.max_velocity],
    [#cso_sensitivity.rosenbrock.d100.selected_params.max_velocity],
    [#cso_sensitivity.schwefel.d10.selected_params.max_velocity],
    [#cso_sensitivity.schwefel.d100.selected_params.max_velocity],
    [#cso_sensitivity.happy_cat.d10.selected_params.max_velocity],
    [#cso_sensitivity.happy_cat.d100.selected_params.max_velocity],

    [c1],
    [#cso_sensitivity.rosenbrock.d10.selected_params.c1],
    [#cso_sensitivity.rosenbrock.d100.selected_params.c1],
    [#cso_sensitivity.schwefel.d10.selected_params.c1],
    [#cso_sensitivity.schwefel.d100.selected_params.c1],
    [#cso_sensitivity.happy_cat.d10.selected_params.c1],
    [#cso_sensitivity.happy_cat.d100.selected_params.c1],

    [mixture_ratio],
    [#cso_sensitivity.rosenbrock.d10.selected_params.mixture_ratio],
    [#cso_sensitivity.rosenbrock.d100.selected_params.mixture_ratio],
    [#cso_sensitivity.schwefel.d10.selected_params.mixture_ratio],
    [#cso_sensitivity.schwefel.d100.selected_params.mixture_ratio],
    [#cso_sensitivity.happy_cat.d10.selected_params.mixture_ratio],
    [#cso_sensitivity.happy_cat.d100.selected_params.mixture_ratio],
  )
]

#pagebreak()

== Comparação

#let cso_comparison = (
  rosenbrock: (
    d10: (
      value_mean: 6.3350496956147,
      value_std: 4.40202427888666,
      iterations: 88,
      cpu_time: 0.5555250073333203,
    ),
    d100: (
      value_mean: 98.19730234218265,
      value_std: 0.5207109922675295,
      iterations: 176,
      cpu_time: 0.48221419066666255,
    ),
  ),
  schwefel: (
    d10: (
      value_mean: 726.2264277266696,
      value_std: 147.87068627250898,
      iterations: 666,
      cpu_time: 0.6101315730000275,
    ),
    d100: (
      value_mean: 17961.92848083907,
      value_std: 1291.813387001493,
      iterations: 666,
      cpu_time: 0.5618326273333878,
    ),
  ),
  happy_cat: (
    d10: (
      value_mean: 7.8187429767516115,
      value_std: 0.5818132610836718,
      iterations: 345,
      cpu_time: 0.5772075963333331,
    ),
    d100: (
      value_mean: 129.03537510984057,
      value_std: 8.11253918223638,
      iterations: 385,
      cpu_time: 0.6025498613333866,
    ),
  ),
)

#align(center + horizon)[
  #set text(size: 22pt)
  #table(
    columns: (auto, auto, auto, 1fr, auto, auto, auto),

    table.header(
      strong[A],
      strong[Função],
      strong[Dim.],
      table.cell(colspan: 1)[#strong[Valor]], strong[Desvio],
      strong[Iterações],
      strong[Tempo (ms)],
    ),

    table.cell(rowspan: 6)[#rotate(-90deg, reflow: true)[CSO]],

    table.cell(rowspan: 2)[Rosenbrock],
    [10],
    [#strfmt("{:.4}", cso_comparison.rosenbrock.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.rosenbrock.d10.value_std)]],
    [#cso_comparison.rosenbrock.d10.iterations],
    [#strfmt("{:.4}", cso_comparison.rosenbrock.d10.cpu_time * 1000)],
    [100],
    [#strfmt("{:.4}", cso_comparison.rosenbrock.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.rosenbrock.d100.value_std)]],
    [#cso_comparison.rosenbrock.d100.iterations],
    [#strfmt("{:.4}", cso_comparison.rosenbrock.d100.cpu_time * 1000)],

    table.cell(rowspan: 2)[Schwefel],
    [10],
    [#strfmt("{:.4}", cso_comparison.schwefel.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.schwefel.d10.value_std)]],
    [#cso_comparison.schwefel.d10.iterations],
    [#strfmt("{:.4}", cso_comparison.schwefel.d10.cpu_time * 1000)],
    [100],
    [#strfmt("{:.4}", cso_comparison.schwefel.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.schwefel.d100.value_std)]],
    [#cso_comparison.schwefel.d100.iterations],
    [#strfmt("{:.4}", cso_comparison.schwefel.d100.cpu_time * 1000)],

    table.cell(rowspan: 2)[HappyCat],
    [10],
    [#strfmt("{:.4}", cso_comparison.happy_cat.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.happy_cat.d10.value_std)]],
    [#cso_comparison.happy_cat.d10.iterations],
    [#strfmt("{:.4}", cso_comparison.happy_cat.d10.cpu_time * 1000)],
    [100],
    [#strfmt("{:.4}", cso_comparison.happy_cat.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.happy_cat.d100.value_std)]],
    [#cso_comparison.happy_cat.d100.iterations],
    [#strfmt("{:.4}", cso_comparison.happy_cat.d100.cpu_time * 1000)],
  )
]

#pagebreak()

#title_slide([#get_term("zoadamm")])

== Ideia

O #stress[ZO-AdaMM] #cite(<chen:2019:zoadamm>) #footnote[
  #cite(<chen:2019:zoadamm>, form: "full")
] é um método de #strong[ordem zero]: usa apenas valores de $f$, sem gradiente analítico.

Une duas ideias:
- #strong[estimar] o gradiente por diferenças finitas, em direções aleatórias;
- #strong[usar] a estimativa em um passo adaptativo, no estilo #foreign_text[Adam] (momento e escala por dimensão).

Mantém #stress[um único ponto] $x$, que se move a cada iteração.

#pagebreak()

== Hiperparâmetros

#stress[`learning_rate`]: $#math.alpha$.\ #h(leading)
Tamanho base do passo. Decai com $1 slash sqrt(t)$.

#stress[`beta1`]: $#(math.beta) _1$.\ #h(leading)
Peso do momento: quanto da direção anterior é mantida.\ #h(leading)
Com 0, não há momento.

#stress[`beta2`]: $#(math.beta) _2$.\ #h(leading)
Memória da escala do gradiente.\ #h(leading)
Janela efetiva de $approx 1 slash (1 - #(math.beta) _2)$ iterações.

#stress[`q`]: $q$.\ #h(leading)
Direções por estimativa. Reduz a variância do gradiente,\ #h(leading)mas
diminui o número de iterações no orçamento.

#stress[`mu`]: $#math.mu$.\ #h(leading)
Raio de suavização da diferença finita.\ #h(leading)
#strong[Fixo] em $10^(-3)$: não variou significativamente em testes exploratórios.

#stress[`epsilon`]: $#math.epsilon$.\ #h(leading)
Evita divisão por zero.\ #h(leading)
#strong[Fixo] em $10^(-12)$.

#pagebreak()

== Algoritmo

A cada iteração $t$:

+ Sorteia $q$ #strong[direções] unitárias $u_i$.
+ #strong[Estima o gradiente:]\
  $hat(g) = d / (#math.mu q) sum_(i=1)^q [f(x + #math.mu u_i) - f(x)] u_i$
+ #strong[Atualiza] momento e escala:\
  $m = #(math.beta) _1 m + (1 - #(math.beta) _1) hat(g)$\
  $v = #(math.beta) _2 v + (1 - #(math.beta) _2) hat(g)^2$
+ #strong[Move:]\
  $x = x - #math.alpha _t dot m / (sqrt(v) + #math.epsilon)$, com $#math.alpha _t = #math.alpha slash sqrt(t)$

Cada iteração custa #stress[$q + 1$] avaliações de $f$.

#pagebreak()

== Diferenças na busca

#align(center + horizon)[
  #table(
    columns: (auto, 1fr, 1fr),
    table.header([], strong[CSO], strong[#get_term("zoadamm")]),

    [Estado], [População de gatos], [Um único ponto],
    [Informação], [Amostragem direta e melhor global], [Gradiente estimado e momento],
    [Exploração], [Global, aleatória\ (seeking e tracing)], [Local, direcionada],
    [Custo por iteração], [Depende de `smp` e `spc`], [$q + 1$],
  )
]

#pagebreak()

== Protocolo

#grid(
  columns: 2,
  [
    #stress([#get_term("seed", plural: true, capitalize: true):]) 27, 32, 59.

    #stress[10_000] avaliações\ da função.

    #stress[Dimensões:] 10, 100

    #stress[Configurações:] 1_050

    #stress[Execuções:] 18_900
  ],
  [
    #table(
      columns: (auto, 1fr),

      table.header(strong[Par.], table.cell(colspan: 1, strong[Possibilidades])),

      [$#(math.beta) _1$], [0.00, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99],
      [$#(math.beta) _2$], [0.9999, 0.99999, 0.999999, 0.9999999, 0.99999999, 0.999999999],
      [$#math.alpha$], [0.7, 1.0, 1.5, 2.0, 3.0],
      [$q$], [5, 10, 20, 30, 40],
      [$#math.mu$], [1e-3],
      [$#math.epsilon$], [1e-12],
    )
  ],
)

#pagebreak()

#let zoadamm_sensitivity = (
  rosenbrock: (
    d10: (
      effect: (
        beta1: 250.29929456350737,
        beta2: 531.0261640961406,
        learning_rate: 192.53720541403706,
        q: 220.62104935077417,
      ),
      best_level: (
        beta1: "0.95",
        beta2: "0.999_9",
        learning_rate: "0.7",
        q: "5",
      ),
      selected_params: (
        beta1: "0.9",
        beta2: "0.999_999_9",
        learning_rate: "2.0",
        q: "30",
      ),
    ),
    d100: (
      effect: (
        beta1: 72.99680878671425,
        beta2: 400.07329000731715,
        learning_rate: 96.70602727559206,
        q: 101.15061112486296,
      ),
      best_level: (
        beta1: "0.0",
        beta2: "0.999_99",
        learning_rate: "0.7",
        q: "5",
      ),
      selected_params: (
        beta1: "0.0",
        beta2: "0.999_999_99",
        learning_rate: "1.5",
        q: "5",
      ),
    ),
  ),
  schwefel: (
    d10: (
      effect: (
        beta1: 15.766194055661467,
        beta2: 18.882174618851366,
        learning_rate: 6.494324332077948,
        q: 7.443990832617832,
      ),
      best_level: (
        beta1: "0.99",
        beta2: "0.999_9",
        learning_rate: "0.7",
        q: "5",
      ),
      selected_params: (
        beta1: "0.95",
        beta2: "0.999_999_9",
        learning_rate: "2.0",
        q: "40",
      ),
    ),
    d100: (
      effect: (
        beta1: 5.388010338894154,
        beta2: 51.42347261178604,
        learning_rate: 10.84135896557368,
        q: 10.255289026092553,
      ),
      best_level: (
        beta1: "0.0",
        beta2: "0.999_99",
        learning_rate: "0.7",
        q: "5",
      ),
      selected_params: (
        beta1: "0.0",
        beta2: "0.999_999",
        learning_rate: "0.7",
        q: "10",
      ),
    ),
  ),
  happy_cat: (
    d10: (
      effect: (
        beta1: 285.8244860475796,
        beta2: 532.2661002906051,
        learning_rate: 260.5790184563551,
        q: 260.10161675495857,
      ),
      best_level: (
        beta1: "0.9",
        beta2: "0.999_99",
        learning_rate: "0.7",
        q: "5",
      ),
      selected_params: (
        beta1: "0.9",
        beta2: "0.999_99",
        learning_rate: "0.7",
        q: "5",
      ),
    ),
    d100: (
      effect: (
        beta1: 189.2848255737706,
        beta2: 509.5442055553196,
        learning_rate: 187.0251819782218,
        q: 188.95044915740533,
      ),
      best_level: (
        beta1: "0.25",
        beta2: "0.999_99",
        learning_rate: "0.7",
        q: "5",
      ),
      selected_params: (
        beta1: "0.99",
        beta2: "0.999_9",
        learning_rate: "1.5",
        q: "5",
      ),
    ),
  ),
)

== Parâmetros selecionados

#align(center + horizon)[
  #set text(size: 21pt)
  #table(
    columns: (1fr, auto, auto, auto, auto, auto, auto),

    table.header(
      table.cell(rowspan: 2)[#strong[P.]],
      table.cell(colspan: 2)[#strong[Rosenbrock]],
      table.cell(colspan: 2)[#strong[Schwefel]],
      table.cell(colspan: 2)[#strong[HappyCat]],
      strong[D=10], strong[D=100], strong[D=10], strong[D=100], strong[D=10], strong[D=100],
    ),

    [$#(math.beta) _1$],
    [#zoadamm_sensitivity.rosenbrock.d10.selected_params.beta1],
    [#zoadamm_sensitivity.rosenbrock.d100.selected_params.beta1],
    [#zoadamm_sensitivity.schwefel.d10.selected_params.beta1],
    [#zoadamm_sensitivity.schwefel.d100.selected_params.beta1],
    [#zoadamm_sensitivity.happy_cat.d10.selected_params.beta1],
    [#zoadamm_sensitivity.happy_cat.d100.selected_params.beta1],

    [$#(math.beta) _2$],
    [#zoadamm_sensitivity.rosenbrock.d10.selected_params.beta2],
    [#zoadamm_sensitivity.rosenbrock.d100.selected_params.beta2],
    [#zoadamm_sensitivity.schwefel.d10.selected_params.beta2],
    [#zoadamm_sensitivity.schwefel.d100.selected_params.beta2],
    [#zoadamm_sensitivity.happy_cat.d10.selected_params.beta2],
    [#zoadamm_sensitivity.happy_cat.d100.selected_params.beta2],

    [$#math.alpha$],
    [#zoadamm_sensitivity.rosenbrock.d10.selected_params.learning_rate],
    [#zoadamm_sensitivity.rosenbrock.d100.selected_params.learning_rate],
    [#zoadamm_sensitivity.schwefel.d10.selected_params.learning_rate],
    [#zoadamm_sensitivity.schwefel.d100.selected_params.learning_rate],
    [#zoadamm_sensitivity.happy_cat.d10.selected_params.learning_rate],
    [#zoadamm_sensitivity.happy_cat.d100.selected_params.learning_rate],

    [$q$],
    [#zoadamm_sensitivity.rosenbrock.d10.selected_params.q],
    [#zoadamm_sensitivity.rosenbrock.d100.selected_params.q],
    [#zoadamm_sensitivity.schwefel.d10.selected_params.q],
    [#zoadamm_sensitivity.schwefel.d100.selected_params.q],
    [#zoadamm_sensitivity.happy_cat.d10.selected_params.q],
    [#zoadamm_sensitivity.happy_cat.d100.selected_params.q],
  )
]

== Rosenbrock

#align(center + horizon)[
  #table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Dimensões = 10]],
      table.cell(colspan: 2)[#strong[Dimensões = 100]],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
    ),

    [$#(math.beta) _1$],
    [#zoadamm_sensitivity.rosenbrock.d10.best_level.beta1],
    [#strfmt("{:.2}", zoadamm_sensitivity.rosenbrock.d10.effect.beta1)],
    [#zoadamm_sensitivity.rosenbrock.d100.best_level.beta1],
    [#strfmt("{:.2}", zoadamm_sensitivity.rosenbrock.d100.effect.beta1)],

    [$#(math.beta) _2$],
    [#zoadamm_sensitivity.rosenbrock.d10.best_level.beta2],
    [#strfmt("{:.2}", zoadamm_sensitivity.rosenbrock.d10.effect.beta2)],
    [#zoadamm_sensitivity.rosenbrock.d100.best_level.beta2],
    [#strfmt("{:.2}", zoadamm_sensitivity.rosenbrock.d100.effect.beta2)],

    [$#math.alpha$],
    [#zoadamm_sensitivity.rosenbrock.d10.best_level.learning_rate],
    [#strfmt("{:.2}", zoadamm_sensitivity.rosenbrock.d10.effect.learning_rate)],
    [#zoadamm_sensitivity.rosenbrock.d100.best_level.learning_rate],
    [#strfmt("{:.2}", zoadamm_sensitivity.rosenbrock.d100.effect.learning_rate)],

    [$q$],
    [#zoadamm_sensitivity.rosenbrock.d10.best_level.q],
    [#strfmt("{:.2}", zoadamm_sensitivity.rosenbrock.d10.effect.q)],
    [#zoadamm_sensitivity.rosenbrock.d100.best_level.q],
    [#strfmt("{:.2}", zoadamm_sensitivity.rosenbrock.d100.effect.q)],
  )
]

#pagebreak()

== Schwefel

#align(center + horizon)[
  #table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Dimensões = 10]],
      table.cell(colspan: 2)[#strong[Dimensões = 100]],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
    ),

    [$#(math.beta) _1$],
    [#zoadamm_sensitivity.schwefel.d10.best_level.beta1],
    [#strfmt("{:.2}", zoadamm_sensitivity.schwefel.d10.effect.beta1)],
    [#zoadamm_sensitivity.schwefel.d100.best_level.beta1],
    [#strfmt("{:.2}", zoadamm_sensitivity.schwefel.d100.effect.beta1)],

    [$#(math.beta) _2$],
    [#zoadamm_sensitivity.schwefel.d10.best_level.beta2],
    [#strfmt("{:.2}", zoadamm_sensitivity.schwefel.d10.effect.beta2)],
    [#zoadamm_sensitivity.schwefel.d100.best_level.beta2],
    [#strfmt("{:.2}", zoadamm_sensitivity.schwefel.d100.effect.beta2)],

    [$#math.alpha$],
    [#zoadamm_sensitivity.schwefel.d10.best_level.learning_rate],
    [#strfmt("{:.2}", zoadamm_sensitivity.schwefel.d10.effect.learning_rate)],
    [#zoadamm_sensitivity.schwefel.d100.best_level.learning_rate],
    [#strfmt("{:.2}", zoadamm_sensitivity.schwefel.d100.effect.learning_rate)],

    [$q$],
    [#zoadamm_sensitivity.schwefel.d10.best_level.q],
    [#strfmt("{:.2}", zoadamm_sensitivity.schwefel.d10.effect.q)],
    [#zoadamm_sensitivity.schwefel.d100.best_level.q],
    [#strfmt("{:.2}", zoadamm_sensitivity.schwefel.d100.effect.q)],
  )
]

#pagebreak()

== HappyCat #emoji.cat.face

#align(center + horizon)[
  #table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Dimensões = 10]],
      table.cell(colspan: 2)[#strong[Dimensões = 100]],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
      strong[#get_term("best", capitalize: true)], strong[Efeito (%)],
    ),

    [$#(math.beta) _1$],
    [#zoadamm_sensitivity.happy_cat.d10.best_level.beta1],
    [#strfmt("{:.2}", zoadamm_sensitivity.happy_cat.d10.effect.beta1)],
    [#zoadamm_sensitivity.happy_cat.d100.best_level.beta1],
    [#strfmt("{:.2}", zoadamm_sensitivity.happy_cat.d100.effect.beta1)],

    [$#(math.beta) _2$],
    [#zoadamm_sensitivity.happy_cat.d10.best_level.beta2],
    [#strfmt("{:.2}", zoadamm_sensitivity.happy_cat.d10.effect.beta2)],
    [#zoadamm_sensitivity.happy_cat.d100.best_level.beta2],
    [#strfmt("{:.2}", zoadamm_sensitivity.happy_cat.d100.effect.beta2)],

    [$#math.alpha$],
    [#zoadamm_sensitivity.happy_cat.d10.best_level.learning_rate],
    [#strfmt("{:.2}", zoadamm_sensitivity.happy_cat.d10.effect.learning_rate)],
    [#zoadamm_sensitivity.happy_cat.d100.best_level.learning_rate],
    [#strfmt("{:.2}", zoadamm_sensitivity.happy_cat.d100.effect.learning_rate)],

    [$q$],
    [#zoadamm_sensitivity.happy_cat.d10.best_level.q],
    [#strfmt("{:.2}", zoadamm_sensitivity.happy_cat.d10.effect.q)],
    [#zoadamm_sensitivity.happy_cat.d100.best_level.q],
    [#strfmt("{:.2}", zoadamm_sensitivity.happy_cat.d100.effect.q)],
  )
]

#pagebreak()

== Comparação

#let zoadamm_comparison = (
  rosenbrock: (
    d10: (
      value_mean: 250.53806692661234,
      value_std: 156.21981154024473,
      iterations: 323,
      cpu_time: 0.2223013216666724,
    ),
    d100: (
      value_mean: 213740.62322976338,
      value_std: 30094.796596907032,
      iterations: 1667,
      cpu_time: 0.3203681493333382,
    ),
  ),
  schwefel: (
    d10: (
      value_mean: 1130.6785365440953,
      value_std: 440.29028120680283,
      iterations: 244,
      cpu_time: 0.17454021566665764,
    ),
    d100: (
      value_mean: 15529.968298235704,
      value_std: 1805.6428291596274,
      iterations: 909,
      cpu_time: 0.23968857599999982,
    ),
  ),
  happy_cat: (
    d10: (
      value_mean: 0.2749897416218396,
      value_std: 0.04387987513874953,
      iterations: 1667,
      cpu_time: 0.2752931750000016,
    ),
    d100: (
      value_mean: 0.7705258363991104,
      value_std: 0.18092135257377365,
      iterations: 1667,
      cpu_time: 0.29675053500000104,
    ),
  ),
)

#align(center + horizon)[
  #set text(size: 22pt)
  #table(
    columns: (auto, auto, auto, 1fr, auto, auto, auto),

    table.header(
      strong[A],
      strong[Função],
      strong[Dim.],
      table.cell(colspan: 1)[#strong[Valor]], strong[Desvio],
      strong[Iterações],
      strong[Tempo (ms)],
    ),

    table.cell(rowspan: 6)[#rotate(-90deg, reflow: true)[#get_term("zoadamm")]],

    table.cell(rowspan: 2)[Rosenbrock],
    [10],
    [#strfmt("{:.4}", zoadamm_comparison.rosenbrock.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.rosenbrock.d10.value_std)]],
    [#zoadamm_comparison.rosenbrock.d10.iterations],
    [#strfmt("{:.4}", zoadamm_comparison.rosenbrock.d10.cpu_time * 1000)],
    [100],
    [#strfmt("{:.4}", zoadamm_comparison.rosenbrock.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.rosenbrock.d100.value_std)]],
    [#zoadamm_comparison.rosenbrock.d100.iterations],
    [#strfmt("{:.4}", zoadamm_comparison.rosenbrock.d100.cpu_time * 1000)],

    table.cell(rowspan: 2)[Schwefel],
    [10],
    [#strfmt("{:.4}", zoadamm_comparison.schwefel.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.schwefel.d10.value_std)]],
    [#zoadamm_comparison.schwefel.d10.iterations],
    [#strfmt("{:.4}", zoadamm_comparison.schwefel.d10.cpu_time * 1000)],
    [100],
    [#strfmt("{:.4}", zoadamm_comparison.schwefel.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.schwefel.d100.value_std)]],
    [#zoadamm_comparison.schwefel.d100.iterations],
    [#strfmt("{:.4}", zoadamm_comparison.schwefel.d100.cpu_time * 1000)],

    table.cell(rowspan: 2)[HappyCat],
    [10],
    [#strfmt("{:.4}", zoadamm_comparison.happy_cat.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.happy_cat.d10.value_std)]],
    [#zoadamm_comparison.happy_cat.d10.iterations],
    [#strfmt("{:.4}", zoadamm_comparison.happy_cat.d10.cpu_time * 1000)],
    [100],
    [#strfmt("{:.4}", zoadamm_comparison.happy_cat.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.happy_cat.d100.value_std)]],
    [#zoadamm_comparison.happy_cat.d100.iterations],
    [#strfmt("{:.4}", zoadamm_comparison.happy_cat.d100.cpu_time * 1000)],
  )
]

#pagebreak()

#title_slide([Híbrido])

#let hybrid_comparison = (
  rosenbrock: (
    d10: (
      value_mean: 9.00501371539914,
      value_std: 0.0501536363013417,
      iterations: 135,
      cpu_time: 0.488025706666667,
    ),
    d100: (
      value_mean: 98.5520766306534,
      value_std: 0.251213151404096,
      iterations: 475,
      cpu_time: 0.286003306,
    ),
  ),
  schwefel: (
    d10: (
      value_mean: 805.923238563305,
      value_std: 279.009274937572,
      iterations: 582,
      cpu_time: 0.518799715666667,
    ),
    d100: (
      value_mean: 18129.9863837226,
      value_std: 968.110290432428,
      iterations: 715,
      cpu_time: 0.324616516666667,
    ),
  ),
  happy_cat: (
    d10: (
      value_mean: 0.843977215864632,
      value_std: 0.0735834797464164,
      iterations: 610,
      cpu_time: 0.522269088,
    ),
    d100: (
      value_mean: 5.68671016963337,
      value_std: 0.710975710110626,
      iterations: 642,
      cpu_time: 0.513981183333333,
    ),
  ),
)

== Comparação

#align(center + horizon)[
  #set text(size: 22pt)
  #table(
    columns: (auto, auto, auto, 1fr, auto, auto, auto),

    table.header(
      strong[A],
      strong[Função],
      strong[Dim.],
      table.cell(colspan: 1)[#strong[Valor]], strong[Desvio],
      strong[Iterações],
      strong[Tempo (ms)],
    ),

    table.cell(rowspan: 6)[#rotate(-90deg, reflow: true)[Híbrido]],

    table.cell(rowspan: 2)[Rosenbrock],
    [10],
    [#strfmt("{:.4}", hybrid_comparison.rosenbrock.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.rosenbrock.d10.value_std)]],
    [#hybrid_comparison.rosenbrock.d10.iterations],
    [#strfmt("{:.4}", hybrid_comparison.rosenbrock.d10.cpu_time * 1000)],
    [100],
    [#strfmt("{:.4}", hybrid_comparison.rosenbrock.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.rosenbrock.d100.value_std)]],
    [#hybrid_comparison.rosenbrock.d100.iterations],
    [#strfmt("{:.4}", hybrid_comparison.rosenbrock.d100.cpu_time * 1000)],

    table.cell(rowspan: 2)[Schwefel],
    [10],
    [#strfmt("{:.4}", hybrid_comparison.schwefel.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.schwefel.d10.value_std)]],
    [#hybrid_comparison.schwefel.d10.iterations],
    [#strfmt("{:.4}", hybrid_comparison.schwefel.d10.cpu_time * 1000)],
    [100],
    [#strfmt("{:.4}", hybrid_comparison.schwefel.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.schwefel.d100.value_std)]],
    [#hybrid_comparison.schwefel.d100.iterations],
    [#strfmt("{:.4}", hybrid_comparison.schwefel.d100.cpu_time * 1000)],

    table.cell(rowspan: 2)[HappyCat],
    [10],
    [#strfmt("{:.4}", hybrid_comparison.happy_cat.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.happy_cat.d10.value_std)]],
    [#hybrid_comparison.happy_cat.d10.iterations],
    [#strfmt("{:.4}", hybrid_comparison.happy_cat.d10.cpu_time * 1000)],
    [100],
    [#strfmt("{:.4}", hybrid_comparison.happy_cat.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.happy_cat.d100.value_std)]],
    [#hybrid_comparison.happy_cat.d100.iterations],
    [#strfmt("{:.4}", hybrid_comparison.happy_cat.d100.cpu_time * 1000)],
  )
]

#pagebreak()

#align(center + horizon)[
  #set text(size: 17pt)
  #table(
    columns: (auto, auto, auto, 1fr, auto, auto, auto),
    inset: (x: 5pt, y: 4pt),

    table.header(
      strong[Função],
      strong[Dimensões],
      strong[Algoritmo],
      table.cell(colspan: 1)[#strong[Valor]], strong[Desvio],
      strong[Iterações],
      strong[Tempo (ms)],
    ),

    table.hline(stroke: 2pt),

    table.cell(rowspan: 6)[Rosenbrock],

    table.cell(rowspan: 3)[10],
    [CSO],
    strong[#strfmt("{:.4}", cso_comparison.rosenbrock.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.rosenbrock.d10.value_std)]],
    [#cso_comparison.rosenbrock.d10.iterations],
    [#strfmt("{:.4}", cso_comparison.rosenbrock.d10.cpu_time * 1000)],
    [#get_term("zoadamm")],
    [#strfmt("{:.4}", zoadamm_comparison.rosenbrock.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.rosenbrock.d10.value_std)]],
    [#zoadamm_comparison.rosenbrock.d10.iterations],
    strong[#strfmt("{:.4}", zoadamm_comparison.rosenbrock.d10.cpu_time * 1000)],
    [Híbrido],
    [#strfmt("{:.4}", hybrid_comparison.rosenbrock.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.rosenbrock.d10.value_std)]],
    [#hybrid_comparison.rosenbrock.d10.iterations],
    [#strfmt("{:.4}", hybrid_comparison.rosenbrock.d10.cpu_time * 1000)],

    table.hline(stroke: 1.5pt),

    table.cell(rowspan: 3)[100],
    [CSO],
    strong[#strfmt("{:.4}", cso_comparison.rosenbrock.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.rosenbrock.d100.value_std)]],
    [#cso_comparison.rosenbrock.d100.iterations],
    [#strfmt("{:.4}", cso_comparison.rosenbrock.d100.cpu_time * 1000)],
    [#get_term("zoadamm")],
    [#strfmt("{:.4}", zoadamm_comparison.rosenbrock.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.rosenbrock.d100.value_std)]],
    [#zoadamm_comparison.rosenbrock.d100.iterations],
    [#strfmt("{:.4}", zoadamm_comparison.rosenbrock.d100.cpu_time * 1000)],
    [Híbrido],
    [#strfmt("{:.4}", hybrid_comparison.rosenbrock.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.rosenbrock.d100.value_std)]],
    [#hybrid_comparison.rosenbrock.d100.iterations],
    strong[#strfmt("{:.4}", hybrid_comparison.rosenbrock.d100.cpu_time * 1000)],

    table.hline(stroke: 2pt),

    table.cell(rowspan: 6)[Schwefel],

    table.cell(rowspan: 3)[10],
    [CSO],
    strong[#strfmt("{:.4}", cso_comparison.schwefel.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.schwefel.d10.value_std)]],
    [#cso_comparison.schwefel.d10.iterations],
    [#strfmt("{:.4}", cso_comparison.schwefel.d10.cpu_time * 1000)],
    [#get_term("zoadamm")],
    [#strfmt("{:.4}", zoadamm_comparison.schwefel.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.schwefel.d10.value_std)]],
    [#zoadamm_comparison.schwefel.d10.iterations],
    strong[#strfmt("{:.4}", zoadamm_comparison.schwefel.d10.cpu_time * 1000)],
    [Híbrido],
    [#strfmt("{:.4}", hybrid_comparison.schwefel.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.schwefel.d10.value_std)]],
    [#hybrid_comparison.schwefel.d10.iterations],
    [#strfmt("{:.4}", hybrid_comparison.schwefel.d10.cpu_time * 1000)],

    table.hline(stroke: 1.5pt),

    table.cell(rowspan: 3)[100],
    [CSO],
    [#strfmt("{:.4}", cso_comparison.schwefel.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.schwefel.d100.value_std)]],
    [#cso_comparison.schwefel.d100.iterations],
    [#strfmt("{:.4}", cso_comparison.schwefel.d100.cpu_time * 1000)],
    [#get_term("zoadamm")],
    strong[#strfmt("{:.4}", zoadamm_comparison.schwefel.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.schwefel.d100.value_std)]],
    [#zoadamm_comparison.schwefel.d100.iterations],
    strong[#strfmt("{:.4}", zoadamm_comparison.schwefel.d100.cpu_time * 1000)],
    [Híbrido],
    [#strfmt("{:.4}", hybrid_comparison.schwefel.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.schwefel.d100.value_std)]],
    [#hybrid_comparison.schwefel.d100.iterations],
    [#strfmt("{:.4}", hybrid_comparison.schwefel.d100.cpu_time * 1000)],

    table.hline(stroke: 2pt),

    table.cell(rowspan: 6)[HappyCat],

    table.cell(rowspan: 3)[10],
    [CSO],
    [#strfmt("{:.4}", cso_comparison.happy_cat.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.happy_cat.d10.value_std)]],
    [#cso_comparison.happy_cat.d10.iterations],
    [#strfmt("{:.4}", cso_comparison.happy_cat.d10.cpu_time * 1000)],
    [#get_term("zoadamm")],
    strong[#strfmt("{:.4}", zoadamm_comparison.happy_cat.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.happy_cat.d10.value_std)]],
    [#zoadamm_comparison.happy_cat.d10.iterations],
    strong[#strfmt("{:.4}", zoadamm_comparison.happy_cat.d10.cpu_time * 1000)],
    [Híbrido],
    [#strfmt("{:.4}", hybrid_comparison.happy_cat.d10.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.happy_cat.d10.value_std)]],
    [#hybrid_comparison.happy_cat.d10.iterations],
    [#strfmt("{:.4}", hybrid_comparison.happy_cat.d10.cpu_time * 1000)],

    table.hline(stroke: 1.5pt),

    table.cell(rowspan: 3)[100],
    [CSO],
    [#strfmt("{:.4}", cso_comparison.happy_cat.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", cso_comparison.happy_cat.d100.value_std)]],
    [#cso_comparison.happy_cat.d100.iterations],
    [#strfmt("{:.4}", cso_comparison.happy_cat.d100.cpu_time * 1000)],
    [#get_term("zoadamm")],
    strong[#strfmt("{:.4}", zoadamm_comparison.happy_cat.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", zoadamm_comparison.happy_cat.d100.value_std)]],
    [#zoadamm_comparison.happy_cat.d100.iterations],
    strong[#strfmt("{:.4}", zoadamm_comparison.happy_cat.d100.cpu_time * 1000)],
    [Híbrido],
    [#strfmt("{:.4}", hybrid_comparison.happy_cat.d100.value_mean)],
    [#text(fill: gray.darken(20%))[± #strfmt("{:.4}", hybrid_comparison.happy_cat.d100.value_std)]],
    [#hybrid_comparison.happy_cat.d100.iterations],
    [#strfmt("{:.4}", hybrid_comparison.happy_cat.d100.cpu_time * 1000)],
  )
]
