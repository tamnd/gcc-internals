"""The SSA web: where a name comes from, and everywhere it goes.

One definition, some number of uses, and a thread from the first to each of the rest. That
is the whole of SSA's usefulness in one picture, and the reason it is worth drawing is that
in the dump the definition and its uses are twenty lines apart and look like every other
line on the page.

The layout is computed here in Python rather than in the browser, and the output is an SVG.
That means the picture in a printed page, in a terminal screenshot and in a live notebook is
the same picture, and it means the static fallback is a real drawing rather than a
placeholder. Monospace metrics are close enough to exact at a fixed font size that the
threads land on the right rows.

Every name gets its own drawing, all of them rendered up front and all but one hidden, so
switching names works on a page with nothing running. A function with more names than
`INLINE_LIMIT` only draws the selected one, because a lesson that ships four hundred SVGs to
show one has lost the plot; past that limit the picker needs a live runtime and says so.

The data comes from `Function.ssa_web`, which does the work of finding the definition and
the uses. This file draws what it is handed and knows nothing about GIMPLE.
"""

from __future__ import annotations

from dataclasses import dataclass

from gxray.gimple import Function
from gxwidgets.base import Widget
from gxwidgets.html import el, esc, join, legend

ROW = 18
GUTTER = 56
CHAR = 7.3
PAD = 10
INLINE_LIMIT = 12


@dataclass
class Row:
    """One line of the listing, and what the name being followed does on it."""

    text: str
    kind: str  # header, def, use, plain
    y: int

    @property
    def anchor(self) -> float:
        return self.y + ROW / 2


def count_of(n: int, word: str) -> str:
    """`1 use`, `2 uses`. Small, and the alternative is prose that reads like a machine."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


class SSAWeb(Widget):
    kind = "ssaweb"
    title = "One SSA name, defined once and used everywhere"
    defaults = {"name": ""}

    def __init__(self, function: Function, name: str = "", **kw: str) -> None:
        self.function = function
        self.names = self._names()
        super().__init__(**kw)
        if name:
            self.view["name"] = name
        wanted = self.view["name"]
        if wanted and wanted not in self.names:
            # A parameter has no definition in the function, and following one is a fair
            # thing to want, so it joins the list rather than rendering an empty panel.
            self.names.append(wanted)
        if not wanted and self.names:
            self.view["name"] = self.names[0]

    def _names(self) -> list[str]:
        """Every name with a definition in this function, in the order they are defined."""
        out: list[str] = []
        for b in self.function.ordered_blocks:
            for p in b.phis:
                out.append(str(p.lhs))
            for s in b.stmts:
                if s.lhs is not None and "_" in str(s.lhs):
                    out.append(str(s.lhs))
        return list(dict.fromkeys(out))

    @property
    def drawn(self) -> list[str]:
        """The names that get a drawing in this render."""
        if len(self.names) <= INLINE_LIMIT:
            return self.names
        return [self.view["name"]] if self.view["name"] else []

    def rows(self, name: str) -> list[Row]:
        web = self.function.ssa_web(name)
        definition, uses = web["def"], list(web["uses"])
        rows: list[Row] = []
        y = 0
        for b in self.function.ordered_blocks:
            rows.append(Row(f"<bb {b.index}>", "header", y))
            y += ROW
            for item in [*b.phis, *b.stmts]:
                kind = "plain"
                if item is definition:
                    kind = "def"
                elif item in uses:
                    kind = "use"
                rows.append(Row(f"  {item}", kind, y))
                y += ROW
        return rows

    def data(self) -> dict:
        return {"names": self.names, "drawn": self.drawn}

    # Rendering

    def body(self) -> str:
        return join(
            [
                self._picker(),
                join([self._panel(n) for n in self.drawn]),
                self._overflow_note(),
                legend(
                    [
                        ("D", "gx-focus", "the one definition, a filled square in the gutter"),
                        ("u", "gx-neutral", "a use, an open circle, joined to the definition"),
                    ]
                ),
            ]
        )

    def _picker(self) -> str:
        if len(self.names) < 2:
            return ""
        buttons = [
            el(
                "button",
                esc(n),
                type="button",
                class_="gx-name",
                role="tab",
                data_cell=n,
                data_panel=n,
                aria_current="true" if n == self.view["name"] else None,
                tabindex=0 if n == self.view["name"] else -1,
                disabled=n not in self.drawn,
            )
            for n in self.names
        ]
        return el(
            "div",
            join(buttons, " "),
            class_="gx-controls",
            role="tablist",
            data_select="name",
            aria_label="Which SSA name to follow",
        )

    def _overflow_note(self) -> str:
        if len(self.names) <= INLINE_LIMIT:
            return ""
        return el(
            "p",
            esc(
                f"This function has {len(self.names)} SSA names, more than the {INLINE_LIMIT} "
                f"this widget draws up front, so only the selected one is here. In a notebook "
                f"the rest are one click away."
            ),
            class_="gx-note",
        )

    def _panel(self, name: str) -> str:
        return el(
            "div",
            join([self._summary(name), self._svg(name), self._listing(name)]),
            class_="gx-panel",
            role="tabpanel",
            data_panel=name,
            hidden=name != self.view["name"],
        )

    def _summary(self, name: str) -> str:
        web = self.function.ssa_web(name)
        where = "has no definition here, so it arrived as a parameter"
        if web["def"] is not None:
            where = f"is defined by {str(web['def']).strip().rstrip(';')}"
        used = count_of(len(web["uses"]), "use")
        return el(
            "p",
            esc(f"{web['name']} {where}, and has {used}."),
            class_="gx-stat",
        )

    def _svg(self, name: str) -> str:
        rows = self.rows(name)
        if not rows:
            return el("p", "This function has no statements to draw.", class_="gx-note")

        width = GUTTER + PAD + int(max(len(r.text) for r in rows) * CHAR) + PAD
        height = rows[-1].y + ROW + PAD
        definition = next((r for r in rows if r.kind == "def"), None)

        threads = []
        if definition is not None:
            for u in [r for r in rows if r.kind == "use"]:
                bulge = min(GUTTER - 16, 12 + abs(u.anchor - definition.anchor) / 4)
                threads.append(
                    f'<path class="thread" d="M {GUTTER - 8} {definition.anchor:.1f} '
                    f"C {GUTTER - 8 - bulge:.1f} {definition.anchor:.1f} "
                    f"{GUTTER - 8 - bulge:.1f} {u.anchor:.1f} "
                    f'{GUTTER - 8} {u.anchor:.1f}" />'
                )

        marks = []
        for r in rows:
            if r.kind == "def":
                marks.append(
                    f'<rect class="def" x="{GUTTER - 13}" y="{r.anchor - 5:.1f}" '
                    f'width="10" height="10" rx="2" />'
                )
            elif r.kind == "use":
                marks.append(
                    f'<circle class="use" cx="{GUTTER - 8}" cy="{r.anchor:.1f}" r="4.5" />'
                )
            glyph = {"def": "D", "use": "u"}.get(r.kind, "")
            if glyph:
                marks.append(
                    f'<text class="tick" x="{GUTTER - 32}" y="{r.anchor + 4:.1f}" '
                    f'aria-hidden="true">{glyph}</text>'
                )
            marks.append(
                f'<text class="row row-{r.kind}" x="{GUTTER + PAD}" '
                f'y="{r.anchor + 4:.1f}">{self._spans(r.text, name)}</text>'
            )

        described = self._description(name)
        return el(
            "svg",
            join([*threads, *marks]),
            class_="gx-web",
            viewBox=f"0 0 {width} {height}",
            width=width,
            height=height,
            role="img",
            aria_label=described,
        )

    def _spans(self, text: str, name: str) -> str:
        """The row's text, with every mention of the name being followed marked."""
        if not name or name not in text:
            return esc(text)
        out = []
        for n, piece in enumerate(text.split(name)):
            if n:
                out.append(f'<tspan class="hit">{esc(name)}</tspan>')
            out.append(esc(piece))
        return "".join(out)

    def _description(self, name: str) -> str:
        """What the drawing says, in words, for a reader who is not looking at it."""
        web = self.function.ssa_web(name)
        parts = [f"The SSA web of {web['name']}."]
        if web["def"] is None:
            parts.append("It has no definition here, so it arrived as a parameter.")
        else:
            parts.append(f"It is defined by {str(web['def']).strip().rstrip(';')}.")
        if not web["uses"]:
            parts.append("Nothing uses it.")
        else:
            listed = "; ".join(str(u).strip().rstrip(";") for u in web["uses"])
            parts.append(f"It has {count_of(len(web['uses']), 'use')}: {listed}.")
        return " ".join(parts)

    def _listing(self, name: str) -> str:
        web = self.function.ssa_web(name)
        lines = [f"def: {str(web['def']).strip() if web['def'] is not None else '(a parameter)'}"]
        lines += [f"use: {str(u).strip()}" for u in web["uses"]]
        return el(
            "details",
            join(
                [
                    el("summary", "The same thing as text"),
                    el("pre", esc("\n".join(lines)), class_="gx-mono"),
                ]
            ),
        )
