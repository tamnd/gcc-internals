"""Two dumps of one function, side by side, with the noise taken out of the comparison.

The rule the authoring guide states is that a single dump is data and two dumps side by side
are a transformation, so this is the widget for every claim of the form "this pass did that".
It is deliberately plain: two columns of monospace text, a marker down the middle, and a
count at the top. Nothing here moves.

What earns it its place is the normalizing in `gxray.diff`. Diff two GIMPLE dumps as text and
almost every line comes out red and green, because the SSA names are renumbered whenever
anything is created or deleted and the branch probabilities are reprinted in a different form
once the profile is guessed. Neither of those is the pass. The comparison is done on the
normalized text and the real text is what gets drawn, so the reader sees the actual lines with
only the rows that moved marked, and a row where nothing but the numbers moved says so.

The filter is the one the Pass Tape uses, `only`, with the same two values and the same
meaning, so a reader who has driven one has driven this.
"""

from __future__ import annotations

from gxmanim.palette import ROLES
from gxray.diff import Diff, Row
from gxwidgets.base import Widget
from gxwidgets.html import count_of, el, esc, join, legend

#: Past this many rows the table is cut and the reader is told. A dump pair with four hundred
#: rows in it is a lesson that should have picked one pass rather than the whole pipeline, and
#: rendering all of it into a notebook cell helps nobody.
LIMIT = 200


class DumpDiff(Widget):
    kind = "dumpdiff"
    title = "Two dumps, side by side"
    defaults = {"only": "all"}

    def __init__(self, diff: Diff, **kw: str) -> None:
        self.diff = diff
        super().__init__(**kw)
        self.title = f"{diff.before_name} to {diff.after_name}"

    # What the reader is looking at

    @property
    def rows(self) -> list[Row]:
        """Every row, or the cut of it, in dump order.

        Filtering happens in the browser rather than here, so that the static page holds
        every row and turning the runtime on does not change what is in the document. The
        cut is different: those rows are not rendered at all, and the widget says so.
        """
        return list(self.diff.rows[:LIMIT])

    @property
    def cut(self) -> int:
        return max(0, len(self.diff.rows) - LIMIT)

    def data(self) -> dict:
        return {
            "before": self.diff.before_name,
            "after": self.diff.after_name,
            "counts": self.diff.counts,
            "renumbered": len(self.diff.renumbered),
            "rows": len(self.diff.rows),
        }

    # Rendering

    def body(self) -> str:
        return join(
            [
                self._summary(),
                self._controls(),
                self._table(),
                self._cut_note(),
                legend(
                    [
                        ("+", "gx-added", "a line the later dump has and the earlier one does not"),
                        (
                            "-",
                            "gx-removed",
                            "a line the earlier dump has and the later one does not",
                        ),
                        ("~", "gx-changed", "a line on both sides that says something different"),
                        ("~", "gx-neutral", "the same marker, line left plain: only numbers moved"),
                    ]
                ),
                self._text(),
            ]
        )

    def _summary(self) -> str:
        c = self.diff.counts
        parts = [
            f"{count_of(len(self.diff.rows), 'line')} in all",
            f"{c['added']} added",
            f"{c['removed']} removed",
            f"{c['changed']} changed",
        ]
        renumbered = len(self.diff.renumbered)
        if renumbered:
            # The number worth printing. A reader who sees that most of the change is
            # renumbering stops treating a wall of marked lines as a wall of work.
            parts.append(f"{renumbered} of those only moved their numbers")
        if not self.diff:
            parts = ["Nothing moved. The two dumps are the same function, line for line."]
        return el("p", join([el("span", esc(p)) for p in parts]), class_="gx-stat")

    def _controls(self) -> str:
        counts = {
            "all": len(self.rows),
            "changed": len([r for r in self.rows if r.role != "neutral"]),
        }
        buttons = [
            el(
                "button",
                esc(f"{label} ({counts[value]})"),
                type="button",
                class_="gx-filter",
                data_filter="only",
                data_value=value,
                aria_pressed="true" if self.view["only"] == value else "false",
            )
            for value, label in [("all", "every line"), ("changed", "only what moved")]
        ]
        return el(
            "div",
            join(buttons, " "),
            class_="gx-controls",
            role="group",
            aria_label="Which lines to show",
        )

    def _table(self) -> str:
        if not self.rows:
            return el("p", "Neither dump has a line in it.", class_="gx-note")
        head = el(
            "tr",
            join(
                [
                    el("th", esc(self.diff.before_name), colspan="2", scope="col"),
                    el("th", "", class_="gx-diff-gutter"),
                    el("th", esc(self.diff.after_name), colspan="2", scope="col"),
                ]
            ),
        )
        return el(
            "table",
            join([el("thead", head), el("tbody", join([self._row(r) for r in self.rows]))]),
            class_="gx-diff",
        )

    def _row(self, row: Row) -> str:
        glyph = ROLES[row.role].glyph
        cells = [
            el("td", self._number(row.before_line), class_="gx-diff-no"),
            el("td", esc(row.before), class_="gx-diff-old"),
            el("td", esc(glyph), class_="gx-diff-gutter", aria_hidden="true"),
            el("td", self._number(row.after_line), class_="gx-diff-no"),
            el("td", esc(row.after), class_="gx-diff-new"),
        ]
        return el(
            "tr",
            join(cells),
            # `data-changed` is what the shared filter reads, and here it means the row moved
            # rather than that a pass ran, which is the same question one level down.
            class_="gx-diffrow",
            data_changed="1" if row.role != "neutral" else "0",
            data_role=row.role,
            data_renumbered="1" if row.renumbered else "0",
            aria_label=row.label,
        )

    def _number(self, line: int | None) -> str:
        return "" if line is None else str(line + 1)

    def _cut_note(self) -> str:
        if not self.cut:
            return ""
        return el(
            "p",
            esc(
                f"{count_of(self.cut, 'more line')} are not drawn. A pair of dumps this far "
                f"apart is two lessons, and the one worth writing picks a single pass."
            ),
            class_="gx-note",
        )

    def _text(self) -> str:
        """The same comparison in the form a reader can paste into a bug report."""
        marks = {r: ROLES[r].glyph or " " for r in ("neutral", "added", "removed", "changed")}
        lines = [f"--- {self.diff.before_name}", f"+++ {self.diff.after_name}"]
        for row in self.diff.rows:
            if row.role == "changed":
                lines.append(f"- {row.before}")
                lines.append(f"+ {row.after}")
            else:
                lines.append(f"{marks[row.role]} {row.text}")
        return el(
            "details",
            join(
                [
                    el("summary", "The same comparison as a patch"),
                    el("pre", esc("\n".join(lines)), class_="gx-mono"),
                ]
            ),
        )
