"""The Pass Tape.

One cell per pass that is on, in order, 281 of the 395 GCC knows about for `l1.c` at `-O2`.
Above the strip, the IR at the selected boundary. Below it, how the statement, block and SSA
name counts move across the whole pipeline.

The thing this widget is for is not any single pass. It is the shape of the pipeline: at
`-O2` almost every pass leaves the function exactly as it found it, and seeing hundreds of
cells with a handful marked is a better argument than a paragraph saying so. A reader who
has scrubbed the tape once stops thinking of optimization as a list of transformations and
starts thinking of it as a long conversation that is mostly analysis.

A pass is marked as having changed the IR only when there is a dump on both sides of it to
compare. GCC writes a dump for a pass only when the pass has one and it ran for this
function, so most cells have no evidence either way and say so rather than guessing. That is
a third state, not a missing feature, and the legend names it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from gxray.gimple import Function
from gxray.passes import Pipeline
from gxwidgets.base import Widget
from gxwidgets.html import el, esc, join, role_legend, void

CHANGED = {True: "1", False: "0", None: "?"}


@dataclass
class Cell:
    """One pass, as the tape sees it."""

    index: int
    name: str
    short: str
    phase: str | None
    depth: int
    dump_key: str | None
    changed: bool | None = None
    stats: dict[str, int] | None = None

    @property
    def label(self) -> str:
        counts = ""
        if self.stats:
            counts = ", {statements} statements, {blocks} blocks".format(**self.stats)
        state = {
            True: "changed the IR",
            False: "left the IR alone",
            None: "nothing recorded to compare",
        }
        phase = f"{self.phase} pass" if self.phase else "pass"
        return f"{self.index + 1}. {self.name}, {phase}, {state[self.changed]}{counts}"


def fingerprint(f: Function) -> tuple[str, ...]:
    """What counts as the IR being the same, for the purpose of marking a cell.

    Statement text in block order. Not the dump text, which carries the pass name and a
    header full of things that differ between two dumps of an identical function.
    """
    return tuple(
        line
        for b in f.ordered_blocks
        for line in [f"<bb {b.index}>", *[str(p) for p in b.phis], *[s.text for s in b.stmts]]
    )


def measure(f: Function) -> dict[str, int]:
    names = {str(n) for b in f.ordered_blocks for s in b.stmts for n in s.operands}
    names |= {str(s.lhs) for b in f.ordered_blocks for s in b.stmts if s.lhs is not None}
    names |= {str(p.lhs) for b in f.ordered_blocks for p in b.phis}
    return {
        "statements": len(f.stmts),
        "blocks": len(f.blocks),
        "names": len([n for n in names if "_" in n]),
    }


class PassTape(Widget):
    kind = "passtape"
    title = "The pass pipeline"
    defaults = {"at": "", "only": "all", "phase": "all"}

    def __init__(
        self,
        pipeline: Pipeline,
        dumps: dict[str, Function] | None = None,
        function: str = "",
        options: str = "-O2",
        **kw: str,
    ) -> None:
        self.pipeline = pipeline
        self.dumps = dumps or {}
        self.function = function
        self.options = options
        self.cells = self._cells()
        super().__init__(**kw)
        if not self.view["at"] and self.cells:
            self.view["at"] = (self.marked or self.cells)[0].name

    def _cells(self) -> list[Cell]:
        cells: list[Cell] = []
        previous: tuple[str, ...] | None = None
        for i, p in enumerate(self.pipeline.enabled):
            cell = Cell(
                index=i,
                name=p.name,
                short=p.short_name,
                phase=p.phase,
                depth=p.depth,
                dump_key=p.dump_key,
            )
            f = self.dumps.get(p.dump_key or "")
            if f is not None:
                current = fingerprint(f)
                cell.changed = None if previous is None else current != previous
                cell.stats = measure(f)
                previous = current
            cells.append(cell)
        return cells

    # What the reader is looking at

    @property
    def marked(self) -> list[Cell]:
        """The cells with a dump, which are the only ones that can say anything."""
        return [c for c in self.cells if c.stats is not None]

    @property
    def shown(self) -> list[Cell]:
        cells = self.cells
        if self.view["phase"] != "all":
            cells = [c for c in cells if c.phase == self.view["phase"]]
        if self.view["only"] == "changed":
            cells = [c for c in cells if c.changed]
        return cells

    @property
    def selected(self) -> Cell | None:
        for c in self.cells:
            if c.name == self.view["at"]:
                return c
        return self.shown[0] if self.shown else None

    def data(self) -> dict:
        return {
            "cells": [
                {"name": c.name, "phase": c.phase or "", "changed": CHANGED[c.changed]}
                for c in self.cells
            ],
            "panels": sorted({c.dump_key for c in self.marked if c.dump_key}),
        }

    # Rendering

    def body(self) -> str:
        return join(
            [
                self._summary(),
                self._controls(),
                self._strip(),
                self._sparkline(),
                self._panels(),
                self._legend(),
                self._noscript(),
            ]
        )

    def _legend(self) -> str:
        """What a cell means, and the honest note about the one thing colour is doing here.

        The stripe along the top of a cell says which phase the pass belongs to, and that is
        the one place in this widget where colour is the only channel. It is also the one
        thing a reader never has to see, because the phase buttons above the tape do the
        same job, so the note points at them.
        """
        return join(
            [
                role_legend(
                    [
                        ("changed", "this pass changed the IR"),
                        ("unknown", "no dump on both sides, so the tape claims nothing"),
                    ]
                ),
                el(
                    "p",
                    "The stripe along the top of a cell is its phase, tree, RTL or IPA. "
                    "The buttons above the tape select a phase without needing the colour.",
                    class_="gx-note",
                ),
            ]
        )

    def _summary(self) -> str:
        total = self.pipeline.counts()["total"]
        phases = Counter(c.phase or "other" for c in self.cells)
        known = len(self.marked)
        moved = len([c for c in self.cells if c.changed])
        parts = [
            f"{len(self.cells)} of {total} passes on at {self.options}",
            f"{phases['tree']} tree, {phases['rtl']} RTL, {phases['ipa']} IPA",
            f"{known} with a dump recorded, {moved} of those changed something",
        ]
        if self.function:
            parts.insert(0, f"function {self.function}")
        return el("p", join([el("span", esc(p)) for p in parts]), class_="gx-stat")

    def _controls(self) -> str:
        buttons = []
        for key, options in (
            ("only", ("all", "changed")),
            ("phase", ("all", "tree", "rtl", "ipa")),
        ):
            for value in options:
                buttons.append(
                    el(
                        "button",
                        esc(value),
                        type="button",
                        class_="gx-filter",
                        data_filter=key,
                        data_value=value,
                        aria_pressed="true" if self.view[key] == value else "false",
                    )
                )
        return el(
            "div",
            join(buttons, " "),
            class_="gx-controls",
            role="group",
            aria_label="Which passes to show",
        )

    def _strip(self) -> str:
        at = self.selected
        cells = [
            el(
                "button",
                "",
                type="button",
                class_="gx-cell",
                role="tab",
                id=f"{self.id}-cell-{c.index}",
                data_cell=c.name,
                data_phase=c.phase or "none",
                data_changed=CHANGED[c.changed],
                data_panel=c.dump_key or "nodump",
                aria_current="true" if at is not None and c.name == at.name else None,
                aria_label=c.label,
                tabindex=0 if at is not None and c.name == at.name else -1,
            )
            for c in self.shown
        ]
        if not cells:
            return el("p", "No pass matches this filter.", class_="gx-note")
        return el(
            "div",
            join(cells),
            class_="gx-tape",
            role="tablist",
            data_select="at",
            aria_label="Passes in pipeline order",
        )

    def _sparkline(self) -> str:
        """Statement count across the pipeline, as a line and also as numbers."""
        points = [(c.index, c.stats["statements"]) for c in self.marked if c.stats]
        if len(points) < 2:
            return el(
                "p",
                "Two recorded dumps are needed before a trend line means anything.",
                class_="gx-note",
            )
        width, height, top = 600, 40, max(v for _, v in points)
        span = max(self.cells[-1].index, 1)
        coords = " ".join(
            f"{x / span * width:.1f},{height - (v / top * (height - 4)):.1f}" for x, v in points
        )
        line = void(
            "polyline",
            points=coords,
            class_="thread",
            fill="none",
            stroke="currentColor",
            stroke_width="1.5",
        )
        dots = join(
            [
                void(
                    "circle",
                    cx=f"{x / span * width:.1f}",
                    cy=f"{height - (v / top * (height - 4)):.1f}",
                    r="2.5",
                    fill="currentColor",
                )
                for x, v in points
            ]
        )
        chart = el(
            "svg",
            join([line, dots]),
            viewBox=f"0 0 {width} {height}",
            width="100%",
            height=height,
            role="img",
            aria_label=self._trend_text(),
            class_="gx-spark",
        )
        return join([chart, el("p", esc(self._trend_text()), class_="gx-note")])

    def _trend_text(self) -> str:
        parts = [f"{c.short} {c.stats['statements']} statements" for c in self.marked if c.stats]
        return "Statement count across the recorded boundaries: " + ", ".join(parts) + "."

    def _panels(self) -> str:
        at = self.selected
        panels = []
        for key in sorted({c.dump_key for c in self.marked if c.dump_key}):
            f = self.dumps[key]
            panels.append(
                el(
                    "div",
                    join(
                        [
                            el("p", esc(f"{key}: {f}"), class_="gx-note"),
                            el("pre", esc(self._listing(f)), class_="gx-mono"),
                        ]
                    ),
                    class_="gx-panel",
                    role="tabpanel",
                    data_panel=key,
                    hidden=not (at is not None and at.dump_key == key),
                )
            )
        panels.append(
            el(
                "div",
                el(
                    "p",
                    "This pass has no dump recorded, so there is nothing to compare and the "
                    "tape does not claim it changed anything.",
                    class_="gx-note",
                ),
                class_="gx-panel",
                role="tabpanel",
                data_panel="nodump",
                hidden=not (at is not None and at.dump_key not in self.dumps),
            )
        )
        return join(panels)

    def _listing(self, f: Function) -> str:
        lines = []
        for b in f.ordered_blocks:
            lines.append(f"<bb {b.index}>" + (f"  [count {b.count}]" if b.count else ""))
            lines += [f"  {p}" for p in b.phis]
            lines += [f"  {s.text}" for s in b.stmts]
        return "\n".join(lines)

    def _noscript(self) -> str:
        at = self.selected
        listing = "\n".join(c.label for c in self.cells)
        return el(
            "noscript",
            join(
                [
                    el(
                        "p",
                        esc(
                            f"Scrubbing needs JavaScript. Showing {at.name if at else 'nothing'}. "
                            f"Every pass in pipeline order is below."
                        ),
                        class_="gx-note",
                    ),
                    el(
                        "details",
                        join(
                            [
                                el("summary", "The whole pipeline"),
                                el("pre", esc(listing), class_="gx-mono"),
                            ]
                        ),
                    ),
                ]
            ),
        )
