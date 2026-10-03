#import "packages.typ": anchor, hydra
#import "style/style.typ": larger_leading, leading, small_leading, theme_color

#let page_footer = context {
  set text(
    size: small_leading,
  )
  counter(page).display(
    "1 / 1",
    both: true,
  )
}

#let page_progress_bar = context {
  let height = 4pt
  let ratio = counter(page).get().first() / counter(page).final().first()
  {
    stack(
      dir: ltr,
      rect(stroke: none, fill: theme_color, height: height, width: ratio * 100%),
      rect(stroke: none, fill: none, height: height, width: (1 - ratio) * 100%),
    )
  }
}

#let template = it => {
  set text(
    lang: "pt",
    region: "br",
    font: "Atkinson Hyperlegible Next",
    size: leading,
  )

  show heading: set block(above: larger_leading, below: leading)

  set table(inset: 6pt)

  set page(
    paper: "presentation-16-9",
    margin: (y: larger_leading, x: leading),
    footer: [
      #align(right, page_footer)
      #anchor()
    ],
    foreground: align(bottom, page_progress_bar),
    header: context align(
      right,
      [
        #anchor()
        #text(
          weight: "semibold",
          fill: theme_color,
          hydra(1),
        )
      ],
    ),
  )

  set table(
    inset: leading / 3,
    align: (x, _) => if x == 0 { left } else { right },
  )

  set grid(gutter: small_leading)

  it
}
