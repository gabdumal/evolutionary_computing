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
      [smp], [2], [3], [4],
      [srd], [0.1], [0.2], [0.4],
      [cdc], [0.65], [0.85], [1.0],
      [spc], [], [True], [False],
      [max_velocity], [0.9], [1.9], [2.9],
      [c1], [1.05], [2.05], [3.05],
      [mixture_ratio], [0.05], [0.10], [0.20],
    )
  ],
)

#pagebreak()

== Rosenbrock

#{
  set text(size: 21pt)
  table(
    columns: (auto, auto, auto, auto, auto),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Intervalo de efeito]],
      table.cell(colspan: 2)[#strong[Melhor param.]],
      strong[D=10], strong[D=100],
      strong[D=10], strong[D=100],
    ),

    [population_size], [0.023453 #text(fill: gray)[± 0.011779]], [0.001885 #text(fill: gray)[± 0.001084]], [15], [30],
    [srd], [0.019357 #text(fill: gray)[± 0.010052]], [0.003299 #text(fill: gray)[± 0.001901]], [0.4], [0.4],
    [cdc], [0.014374 #text(fill: gray)[± 0.007540]], [0.002229 #text(fill: gray)[± 0.001272]], [0.85], [1.00],
    [smp], [0.008137 #text(fill: gray)[± 0.004138]], [0.001332 #text(fill: gray)[± 0.000667]], [2], [4],
    [c1], [0.005687 #text(fill: gray)[± 0.002844]], [0.000992 #text(fill: gray)[± 0.000502]], [1.05], [2.05],
    [max_velocity], [0.005600 #text(fill: gray)[± 0.002887]], [0.002524 #text(fill: gray)[± 0.001365]], [0.9], [0.9],
    [mixture_ratio], [0.004645 #text(fill: gray)[± 0.002352]], [0.003222 #text(fill: gray)[± 0.001856]], [0.10], [0.05],
    [spc], [0.002451 #text(fill: gray)[± 0.001733]], [0.001626 #text(fill: gray)[± 0.001150]], [True], [False],
  )
}

#pagebreak()

== Schwefel

#{
  set text(size: 21pt)
  table(
    columns: (auto, auto, auto, auto, auto),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Intervalo de efeito]],
      table.cell(colspan: 2)[#strong[Melhor param.]],
      strong[D=10], strong[D=100],
      strong[D=10], strong[D=100],
    ),

    [srd], [0.275115 #text(fill: gray)[± 0.138753]], [0.177855 #text(fill: gray)[± 0.088961]], [0.1], [0.1],
    [cdc], [0.159198 #text(fill: gray)[± 0.085463]], [0.095859 #text(fill: gray)[± 0.053787]], [0.65], [0.65],
    [population_size], [0.067603 #text(fill: gray)[± 0.037044]], [0.015721 #text(fill: gray)[± 0.008811]], [60], [15],
    [mixture_ratio], [0.059129 #text(fill: gray)[± 0.030868]], [0.037986 #text(fill: gray)[± 0.019542]], [0.2], [0.2],
    [max_velocity], [0.028295 #text(fill: gray)[± 0.014332]], [0.021151 #text(fill: gray)[± 0.010633]], [2.9], [2.9],
    [spc], [0.023536 #text(fill: gray)[± 0.016642]], [0.008293 #text(fill: gray)[± 0.005864]], [False], [True],
    [smp], [0.022237 #text(fill: gray)[± 0.012558]], [0.032020 #text(fill: gray)[± 0.016720]], [2], [2],
    [c1], [0.003584 #text(fill: gray)[± 0.001863]], [0.004207 #text(fill: gray)[± 0.002198]], [3.05], [3.05],
  )
}

#pagebreak()

== HappyCat

#{
  set text(size: 21pt)
  table(
    columns: (auto, auto, auto, auto, auto),

    table.header(
      table.cell(rowspan: 2)[#strong[Parâmetro]],
      table.cell(colspan: 2)[#strong[Intervalo de efeito]],
      table.cell(colspan: 2)[#strong[Melhor param.]],
      strong[D=10], strong[D=100],
      strong[D=10], strong[D=100],
    ),

    [cdc], [0.118847 #text(fill: gray)[± 0.066744]], [0.141658 #text(fill: gray)[± 0.075992]], [1.00], [1.00],
    [mixture_ratio], [0.098336 #text(fill: gray)[± 0.056664]], [0.112093 #text(fill: gray)[± 0.056854]], [0.2], [0.2],
    [srd], [0.078466 #text(fill: gray)[± 0.039398]], [0.085304 #text(fill: gray)[± 0.044882]], [0.4], [0.4],
    [population_size], [0.062613 #text(fill: gray)[± 0.031438]], [0.029104 #text(fill: gray)[± 0.016574]], [30], [30],
    [smp], [0.030782 #text(fill: gray)[± 0.015727]], [0.027571 #text(fill: gray)[± 0.013882]], [2], [2],
    [max_velocity], [0.022715 #text(fill: gray)[± 0.012213]], [0.045666 #text(fill: gray)[± 0.023339]], [1.9], [2.9],
    [spc], [0.018161 #text(fill: gray)[± 0.012842]], [0.048824 #text(fill: gray)[± 0.034524]], [False], [False],
    [c1], [0.008490 #text(fill: gray)[± 0.004345]], [0.001090 #text(fill: gray)[± 0.000590]], [3.05], [3.05],
  )
}

#pagebreak()

== Parâmetros selecionados

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
  [smp], [2], [2], [2], [2], [2], [3],
  [srd], [0.1], [0.4], [0.4], [0.1], [0.4], [0.4],
  [cdc], [0.65], [0.85], [1.0], [0.65], [1.0], [1.0],
  [spc], [True], [True], [False], [True], [False], [False],
  [max_velocity], [1.9], [0.9], [1.9], [2.9], [0.9], [2.9],
  [c1], [1.05], [1.05], [1.05], [3.05], [1.05], [1.05],
  [mixture_ratio], [0.1], [0.2], [0.05], [0.2], [0.2], [0.2],
)

== Comparação

#table(
  columns: (auto, 1fr, 1fr, 1fr, 1fr),

  table.header(strong[Algoritmo], strong[Dimensão], strong[Valor], strong[Iterações], strong[Tempo]),

  table.cell(rowspan: 2)[Rosenbrock], [10], [value ± std], [value ± std], [value ± std],
  [100], [value ± std], [value ± std], [value ± std],

  table.cell(rowspan: 2)[Schwefel], [10], [value ± std], [value ± std], [value ± std],
  [100], [value ± std], [value ± std], [value ± std],

  table.cell(rowspan: 2)[HappyCat], [10], [value ± std], [value ± std], [value ± std],
  [100], [value ± std], [value ± std], [value ± std],
)
