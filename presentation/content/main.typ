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

== Happy Cat

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
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.srd)],
    [#cso_sensitivity.rosenbrock.d100.best_level.srd],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.srd)],

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
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d10.effect.mixture_ratio)],
    [#cso_sensitivity.rosenbrock.d100.best_level.mixture_ratio],
    [#strfmt("{:.2}", cso_sensitivity.rosenbrock.d100.effect.mixture_ratio)],
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
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.smp)],

    [srd],
    [#cso_sensitivity.schwefel.d10.best_level.srd],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.srd)],
    [#cso_sensitivity.schwefel.d100.best_level.srd],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d100.effect.srd)],

    [cdc],
    [#cso_sensitivity.schwefel.d10.best_level.cdc],
    [#strfmt("{:.2}", cso_sensitivity.schwefel.d10.effect.cdc)],
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
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.srd)],
    [#cso_sensitivity.happy_cat.d100.best_level.srd],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.srd)],

    [cdc],
    [#cso_sensitivity.happy_cat.d10.best_level.cdc],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d10.effect.cdc)],
    [#cso_sensitivity.happy_cat.d100.best_level.cdc],
    [#strfmt("{:.2}", cso_sensitivity.happy_cat.d100.effect.cdc)],

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

== Comparação

#align(center + horizon)[
  #set text(size: 20pt)
  #table(
    columns: (auto, auto, auto, 1fr, auto, auto),

    table.header(strong[A], strong[Função], strong[Di.], strong[Valor], strong[Iter.], strong[Tempo (s)]),

    table.cell(rowspan: 6)[#rotate(-90deg, reflow: true)[CSO]],

    table.cell(rowspan: 2)[Rosenbrock],
    [10],
    [6.335050 #text(fill: gray)[± 4.402024]],
    [88],
    [0.559221 #text(fill: gray)[± 0.003166]],
    [100],
    [98.197302 #text(fill: gray)[± 0.520711]],
    [176],
    [0.486966 #text(fill: gray)[± 0.006750]],

    table.cell(rowspan: 2)[Schwefel],
    [10],
    [726.226428 #text(fill: gray)[± 147.870686]],
    [666],
    [0.613979 #text(fill: gray)[± 0.002793]],
    [100],
    [17,961.928481 #text(fill: gray)[± 1291.813387]],
    [666],
    [0.565550 #text(fill: gray)[± 0.001530]],

    table.cell(rowspan: 2)[HappyCat],
    [10],
    [7.818743 #text(fill: gray)[± 0.581813]],
    [345],
    [0.581429 #text(fill: gray)[± 0.001142]],
    [100],
    [129.035375 #text(fill: gray)[± 8.112539]],
    [385],
    [0.606574 #text(fill: gray)[± 0.001208]],
  )
]

#pagebreak()

#align(center + horizon)[
  #set text(size: 20pt)
  #table(
    columns: (auto, auto, auto, 1fr, auto, auto),

    table.header(strong[A], strong[Função], strong[Di.], strong[Valor], strong[Iter.], strong[Tempo (s)]),

    table.cell(rowspan: 6)[#rotate(-90deg, reflow: true)[ZO-AdaMM]],

    table.cell(rowspan: 2)[Rosenbrock],
    [10],
    [4,192,874.631919 #text(fill: gray)[± 931,426.132825]],
    [5000],
    [0.313871 #text(fill: gray)[± 0.112952]],
    [100],
    [266,982,516.859546 #text(fill: gray)[± 32,520,603.452682]],
    [5000],
    [0.435070 #text(fill: gray)[± 0.009591]],

    table.cell(rowspan: 2)[Schwefel],
    [10],
    [2,103.521697 #text(fill: gray)[± 206.474611]],
    [5000],
    [0.230122 #text(fill: gray)[± 0.015229]],
    [100],
    [35,302.975872 #text(fill: gray)[± 2,080.079750]],
    [5000],
    [0.298172 #text(fill: gray)[± 0.077311]],

    table.cell(rowspan: 2)[HappyCat],
    [10],
    [568.712977 #text(fill: gray)[± 187.351809]],
    [5000],
    [0.395836 #text(fill: gray)[± 0.098610]],
    [100],
    [1,215.770331 #text(fill: gray)[± 52.405470]],
    [5000],
    [0.274836 #text(fill: gray)[± 0.003551]],
  )
]

#title_slide([Validação do #get_term("za")])


== Protocolo

#grid(
  columns: 2,
  [
    #stress([#get_term("seed", plural: true, capitalize: true):]) 27, 32, 59.

    #stress[10 000] avaliações\ da função.

    #stress[Dimensões:] 10, 100.
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
