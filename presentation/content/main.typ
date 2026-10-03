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
