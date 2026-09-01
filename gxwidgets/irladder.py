"""One line of C, at every level GCC turns it into.

The ladder is the widget this project was worth building for. Everything else shows one
representation clearly. This one shows that GENERIC, GIMPLE, RTL and the assembly are the
same program, by putting a source line on the left and everything the compiler made of it
on the right.

A reader picks a line and sees four answers to the same question. Some of them are
surprising in a way no amount of prose achieves, because the numbers are right there:

    line 5   int s = 0;                   1 GENERIC, 2 GIMPLE, 2 RTL, 2 instructions
    line 6   for (int i = 0; i < n; i++)  5 GENERIC, 4 GIMPLE, 6 RTL, 6 instructions
    line 7   s += i;                      1 GENERIC, 1 GIMPLE, 1 RTL, 1 instruction
    line 8   return s;                    1 GENERIC, 1 GIMPLE, 0 RTL, 0 instructions

The initialisation on line 5 became two instructions because there are two paths into the
loop. The `return` on line 8 has nothing at the bottom two levels at all, because the value
was already in the return register and the epilogue is filed under the closing brace. That
last one takes a paragraph to explain and one glance to notice.

The join between the levels is the source location, and only the source location. Nothing
else survives the trip. `gxray.locs` does the reading, this file draws what it is handed.
"""

from __future__ import annotations

from gxray.locs import LEVEL_NAMES, LEVELS, Ladder
from gxwidgets.base import Widget
from gxwidgets.html import el, esc, join, legend

# How wide one item is worth in the little bar on a rung. Small, because six instructions
# on one line is common and the bar has to stay inside a button.
BAR = 7
BAR_MAX = 84


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


class IRLadder(Widget):
    kind = "irladder"
    title = "One line of C, at four levels"
    defaults = {"line": ""}

    def __init__(self, ladder: Ladder, line: int | str = "", **kw: str) -> None:
        self.ladder = ladder
        super().__init__(**kw)
        if line:
            self.view["line"] = str(line)
        if self.view["line"] not in [str(r.line) for r in ladder.rungs]:
            self.view["line"] = str(ladder.rungs[0].line) if ladder.rungs else ""

    @property
    def selected(self):
        wanted = self.view["line"]
        return next((r for r in self.ladder.rungs if str(r.line) == wanted), None)

    def totals(self) -> dict[str, int]:
        return {lv: sum(len(r.at(lv)) for r in self.ladder.rungs) for lv in LEVELS}

    def data(self) -> dict:
        return {"lines": self.ladder.lines, "totals": self.totals()}

    # Rendering

    def body(self) -> str:
        if not self.ladder.rungs:
            return el("p", "Nothing to draw. No level in this build carried a location.")
        return join(
            [
                self._summary(),
                self._chain(),
                self._rungs(),
                join([self._panel(r) for r in self.ladder.rungs]),
                self._legend(),
                self._noscript(),
            ]
        )

    def _summary(self) -> str:
        totals = self.totals()
        rungs = plural(len(self.ladder.rungs), "source line")
        parts = [
            f"{self.ladder.file}, {rungs} with anything on them",
            ", ".join(f"{totals[lv]} {LEVEL_NAMES[lv]}" for lv in LEVELS),
        ]
        return el("p", join([el("span", esc(p)) for p in parts]), class_="gx-stat")

    def _chain(self) -> str:
        """The order of the levels, written out, because the widget assumes you know it."""
        steps = ["C source", *[LEVEL_NAMES[lv] for lv in LEVELS]]
        return el(
            "p",
            join([el("span", esc(s), class_="gx-step") for s in steps]),
            class_="gx-chain",
            aria_label="The order the compiler goes through these",
        )

    def _rungs(self) -> str:
        rows = []
        for r in self.ladder.rungs:
            counts = r.counts()
            bars = join(
                [
                    el(
                        "span",
                        el("span", "", class_="gx-bar-fill", style=f"width:{self._width(n)}px")
                        + el("span", str(n), class_="gx-bar-n"),
                        class_="gx-bar",
                        title=f"{n} {LEVEL_NAMES[lv]}",
                    )
                    for lv, n in counts.items()
                ]
            )
            rows.append(
                el(
                    "button",
                    join(
                        [
                            el("span", str(r.line), class_="gx-rung-no"),
                            el("code", esc(r.source.strip() or "(blank)"), class_="gx-rung-src"),
                            el("span", bars, class_="gx-bars"),
                        ]
                    ),
                    type="button",
                    class_="gx-rung",
                    role="tab",
                    data_cell=str(r.line),
                    data_panel=str(r.line),
                    aria_current="true" if str(r.line) == self.view["line"] else None,
                    tabindex=0 if str(r.line) == self.view["line"] else -1,
                    aria_label=self._rung_label(r),
                )
            )
        return el(
            "div",
            join(rows),
            class_="gx-rungs",
            role="tablist",
            data_select="line",
            aria_label="Which source line to follow down",
        )

    @staticmethod
    def _width(n: int) -> int:
        return min(BAR_MAX, n * BAR)

    def _rung_label(self, rung) -> str:
        """What a screen reader hears. The bars are a picture of exactly this sentence."""
        counts = rung.counts()
        made = ", ".join(f"{counts[lv]} {LEVEL_NAMES[lv]}" for lv in LEVELS)
        return f"Line {rung.line}, {rung.source.strip()}, became {made}"

    def _panel(self, rung) -> str:
        blocks = [
            el(
                "p",
                join(
                    [
                        el("span", f"line {rung.line}", class_="gx-rung-no"),
                        el("code", esc(rung.source.strip() or "(blank)")),
                    ],
                    " ",
                ),
                class_="gx-rung-head",
            )
        ]
        for lv in LEVELS:
            items = rung.at(lv)
            head = el(
                "h5",
                esc(f"{LEVEL_NAMES[lv]}, {plural(len(items), 'item')}"),
                class_="gx-level-name",
            )
            if items:
                shown = el("pre", esc("\n".join(i.text for i in items)), class_="gx-mono")
            else:
                shown = el("p", "Nothing here.", class_="gx-note")
            blocks.append(el("li", join([head, shown]), class_="gx-level"))

        return el(
            "div",
            join([blocks[0], el("ol", join(blocks[1:]), class_="gx-levels")]),
            class_="gx-panel",
            role="tabpanel",
            data_panel=str(rung.line),
            hidden=str(rung.line) != self.view["line"],
        )

    def _legend(self) -> str:
        return legend(
            [
                ("1", "gx-neutral", "how many items that level has for this line"),
                (".", "gx-unknown", "nothing at that level, which is worth asking about"),
            ]
        )

    def _noscript(self) -> str:
        """Every rung as one sentence, for a page with no script and for a screen reader."""
        lines = [self._rung_label(r) for r in self.ladder.rungs]
        return el(
            "noscript",
            el(
                "details",
                join(
                    [
                        el("summary", "Every line at once"),
                        el("pre", esc("\n".join(lines)), class_="gx-mono"),
                    ]
                ),
            ),
        )
