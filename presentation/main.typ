#import "packages.typ": *
#import "components.typ": *
#import "data/glossary.typ": glossaries_entries
#import "template.typ": *


// ## Layout. Leiaute.
#show: it => template(it)
#show: it => quati-abnt.link.template(
  it,
  // Define the color of links and cross-references.
  // Defina a cor dos links e das referências cruzadas.
  color_of_links: theme_color.darken(30%),
)
#show: it => quati-abnt.bibliography.template(it)
#show: it => quati-abnt.footnote.template(it)


#show: glossarium.make-glossary
#glossarium.register-glossary(glossaries_entries)


// ## Content. Conteúdo.

#cover_slide

#include "content/main.typ"

#title_slide("Referências")
#bibliography(
  title: none,
  "data/bibliography.bib",
)

#focus_slide[
  #set text(
    size: larger_leading,
  )

  Agradecemos pela atenção!

  #text(leading)[
    Este trabalho recebeu apoio da Fundação de Amparo à Pesquisa do Estado de Minas Gerais (FAPEMIG).
  ]
]


#glossarium.print-glossary(
  disable-back-references: true,
  invisible: true,
  glossaries_entries,
)
