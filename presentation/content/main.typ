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

== Rosenbrock

#align(center + horizon)[
  #set text(size: 21pt)
  #table(
    columns: (auto, auto, auto, auto, auto),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Intervalo de efeito]],
      table.cell(colspan: 2)[#strong[Melhor param.]],
      strong[D=10], strong[D=100],
      strong[D=10], strong[D=100],
    ),

    [population_size], [0.014971 #text(fill: gray)[± 0.007576]], [0.006271 #text(fill: gray)[± 0.003174]], [15], [15],
    [smp], [0.000755 #text(fill: gray)[± 0.000404]], [0.003936 #text(fill: gray)[± 0.002204]], [5], [5],
    [srd], [0.041717 #text(fill: gray)[± 0.022712]], [0.022032 #text(fill: gray)[± 0.012366]], [0.4], [0.4],
    [cdc], [0.020129 #text(fill: gray)[± 0.010301]], [0.015254 #text(fill: gray)[± 0.008229]], [0.10], [1.00],
    [spc], [0.003702 #text(fill: gray)[± 0.002617]], [0.004577 #text(fill: gray)[± 0.003237]], [False], [False],
    [max_velocity], [0.030730 #text(fill: gray)[± 0.015957]], [0.018026 #text(fill: gray)[± 0.009564]], [1.0], [1.0],
    [c1], [0.003796 #text(fill: gray)[± 0.001902]], [0.001477 #text(fill: gray)[± 0.000739]], [1.05], [3.05],
    [mixture_ratio], [0.042087 #text(fill: gray)[± 0.023027]], [0.022469 #text(fill: gray)[± 0.012720]], [0.1], [0.1],
  )
]

#pagebreak()

== Schwefel

#align(center + horizon)[
  #set text(size: 21pt)
  #table(
    columns: (auto, auto, auto, auto, auto),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Intervalo de efeito]],
      table.cell(colspan: 2)[#strong[Melhor param.]],
      strong[D=10], strong[D=100],
      strong[D=10], strong[D=100],
    ),

    [population_size], [0.055211 #text(fill: gray)[± 0.029898]], [0.042154 #text(fill: gray)[± 0.021077]], [60], [15],
    [smp], [0.062307 #text(fill: gray)[± 0.033537]], [0.068927 #text(fill: gray)[± 0.036307]], [2], [2],
    [srd], [0.259802 #text(fill: gray)[± 0.130771]], [0.147541 #text(fill: gray)[± 0.073855]], [0.1], [0.1],
    [cdc], [0.136344 #text(fill: gray)[± 0.072124]], [0.068039 #text(fill: gray)[± 0.036858]], [0.60], [0.60],
    [spc], [0.030081 #text(fill: gray)[± 0.021270]], [0.049626 #text(fill: gray)[± 0.035091]], [True], [True],
    [max_velocity], [0.044277 #text(fill: gray)[± 0.022142]], [0.034008 #text(fill: gray)[± 0.017026]], [3.0], [3.0],
    [c1], [0.006277 #text(fill: gray)[± 0.003320]], [0.008641 #text(fill: gray)[± 0.004350]], [3.05], [3.05],
    [mixture_ratio], [0.057456 #text(fill: gray)[± 0.029749]], [0.050910 #text(fill: gray)[± 0.025500]], [0.5], [0.5],
  )
]

#pagebreak()

== HappyCat

#align(center + horizon)[
  #set text(size: 21pt)
  #table(
    columns: (auto, auto, auto, auto, auto),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Intervalo de efeito]],
      table.cell(colspan: 2)[#strong[Melhor param.]],
      strong[D=10], strong[D=100],
      strong[D=10], strong[D=100],
    ),

    [population_size], [0.034065 #text(fill: gray)[± 0.017413]], [0.065646 #text(fill: gray)[± 0.033309]], [15], [15],
    [smp], [0.042525 #text(fill: gray)[± 0.022932]], [0.030476 #text(fill: gray)[± 0.015276]], [2], [3],
    [srd], [0.082253 #text(fill: gray)[± 0.041264]], [0.177588 #text(fill: gray)[± 0.091153]], [0.4], [0.4],
    [cdc], [0.126034 #text(fill: gray)[± 0.068111]], [0.184061 #text(fill: gray)[± 0.095695]], [1.00], [1.00],
    [spc], [0.018001 #text(fill: gray)[± 0.012728]], [0.069324 #text(fill: gray)[± 0.049019]], [False], [False],
    [max_velocity], [0.021205 #text(fill: gray)[± 0.012169]], [0.010906 #text(fill: gray)[± 0.005453]], [1.9], [1.9],
    [c1], [0.004718 #text(fill: gray)[± 0.002362]], [0.002193 #text(fill: gray)[± 0.001187]], [3.05], [3.05],
    [mixture_ratio], [0.026075 #text(fill: gray)[± 0.013843]], [0.065678 #text(fill: gray)[± 0.035794]], [0.1], [0.5],
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

    [population_size], [15], [15], [60], [15], [15], [15],
    [smp], [5], [5], [2], [2], [2], [3],
    [srd], [0.4], [0.4], [0.1], [0.1], [0.4], [0.4],
    [cdc], [1.0], [1.0], [0.6], [0.6], [1.0], [1.0],
    [spc], [False], [False], [True], [True], [False], [False],
    [max_velocity], [1.0], [1.0], [3.0], [3.0], [1.9], [1.9],
    [c1], [1.05], [3.05], [3.05], [3.05], [3.05], [3.05],
    [mixture_ratio], [0.1], [0.1], [0.5], [0.5], [0.1], [0.5],
  )
]

== Comparação

#align(center + horizon)[
  #set text(size: 20pt)
  #table(
    columns: (auto, auto, 1fr, auto, auto),

    table.header(strong[Algoritmo], strong[Di.], strong[Valor], strong[Iterações], strong[Tempo (s)]),

    table.cell(rowspan: 2)[Rosenbrock],
    [10],
    [value #text(fill: gray)[± std]],
    [0],
    [value #text(fill: gray)[± std]],
    [100], [value #text(fill: gray)[± std]],
    [0], [value #text(fill: gray)[± std]],

    table.cell(rowspan: 2)[Schwefel],
    [10],
    [value #text(fill: gray)[± std]],
    [0],
    [value #text(fill: gray)[± std]],
    [100], [value #text(fill: gray)[± std]],
    [0], [value #text(fill: gray)[± std]],

    table.cell(rowspan: 2)[HappyCat],
    [10],
    [value #text(fill: gray)[± std]],
    [0],
    [value #text(fill: gray)[± std]],
    [100], [value #text(fill: gray)[± std]],
    [0], [value #text(fill: gray)[± std]],
  )
]
