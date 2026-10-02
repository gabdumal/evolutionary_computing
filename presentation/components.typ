// # Components. Componentes.

#import "data/data.typ": authors, date, subtitle, title
#import "data/terms.typ": get_term
#import "packages.typ": (
  hydra, quati-abnt.article, quati-abnt.bibliography.cite_prose, quati-abnt.common.components,
  quati-abnt.common.components.describe_figure, quati-abnt.common.components.equation,
  quati-abnt.common.components.foreign_text, quati-abnt.common.components.format_table,
  quati-abnt.note.closed_discussion_note, quati-abnt.note.create_status_note, quati-abnt.note.done_note,
  quati-abnt.note.editor_note, quati-abnt.note.open_discussion_note, quati-abnt.note.progress_note,
  quati-abnt.note.todo_note,
)
#import "style/style.typ": large_leading, larger_leading, leading, small_leading, theme_color


// ## Page. Página.

#let cover_slide = [
  #counter(footnote).update(0)

  #set page(
    header: none,
    footer: none,
    foreground: none,
    margin: leading,
  )

  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [
      #grid(
        columns: 1,
        rows: 2,
        row-gutter: leading,
        [
          #text(
            fill: theme_color,
            weight: "bold",
            heading(
              text(
                size: larger_leading,
                title,
              ),
            ),
          )],
        [
          #text(
            size: large_leading,
            subtitle,
          )
        ],
      )

      #date.display("[day]/[month]/[year]")

      #(
        authors
          .map(author => [#(
              (
                author.first_name,
                author.middle_name,
                author.last_name,
              )
                .filter(name => name != none)
                .join(" ")
            )#footnote(text(small_leading, author.curriculum))])
          .join(", ")
      )
    ],
    [
      #image(
        "assets/images/brasao_ufjf.png",
        width: 5cm,
      )
    ],
  )

  #counter(footnote).update(0)
  #pagebreak(weak: true)
]


#let focus_slide = (
  color: theme_color,
  it,
) => [
  #set page(
    header: none,
    footer: none,
    foreground: none,
    margin: leading,
    fill: color,
  )
  #set align(center + horizon)
  #set text(
    fill: white,
    weight: "black",
    size: larger_leading,
  )
  #it
  #pagebreak(weak: true)
]


#let title_slide = title => focus_slide[
  #show heading.where(level: 1): set text(
    weight: "black",
    size: larger_leading,
  )
  #heading(
    level: 1,
    title,
  )
]


// ## Note. Nota.

#let review_note = (
  prefixes: none,
  it,
) => {
  let color = oklch(82.01%, 0.159, 323.15deg)
  create_status_note(
    fill: color,
    prefixes: prefixes,
    status: "REVISAR",
    stroke: color.saturate(50%),
    it,
  )
}

#let note_from_gabriel = (
  note: editor_note,
  it,
) => {
  let color = oklch(80.43%, 0.1, 278.25deg)
  note(
    prefixes: (
      (
        body: "Gabriel",
        fill: color,
        stroke: color.saturate(25%),
      ),
    ),
    it,
  )
}


// ## Highlight. Destaque.

#let stress = it => {
  text(fill: theme_color, strong(it))
}

#let copy_last_heading(level: 2) = context { hydra(level, display: (ctx, it) => it) }
