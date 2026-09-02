"""The Flag Diff.

A grid. One row per optimization level, one column per optimizer switch that is not the
same at every level, filled where that level has that switch on. Click any cell and the
panel underneath gives the whole column, which is what that one switch is at all of them.

The thing this widget is for is the shape of the levels rather than any one flag. `-O0`
through `-O3` are a staircase: each row is the row above it plus more, and the filled part
grows left to right without ever losing a column. `-Os`, `-Og` and `-Ofast` are not on that
staircase, and their rows say so on sight, because each of them has holes in a stretch that
`-O2` filled solid. The moment a reader sees `-Og` missing thirteen switches `-O1` has, the
idea that the levels are one slider from slow to fast stops being available to them.

The columns are ordered by the first row that fills them, which is what makes the staircase
a staircase instead of an alphabet. Filtering to `-O2` leaves exactly the columns `-O2` is
the first to fill, which is the answer to the question in the lesson title.

Only switches are drawn. Some of the difference between two levels is options that took a
new value rather than switches that flipped, and a cell that is on or off cannot say `went
from simple to stc`. The summary counts those out loud, because a reader who counts the
columns and quotes the number should get a number GCC would agree with.
"""

from __future__ import annotations

from dataclasses import dataclass

from gxray.options import Table
from gxwidgets.base import Widget
from gxwidgets.html import el, esc, join, legend


@dataclass(frozen=True)
class Switch:
    """One switch, and whether it is on at each level, in the order the levels were given."""

    name: str
    states: dict[str, bool]

    @property
    def first(self) -> str:
        """The first level that turns it on.

        There is always one. A switch only gets here if two levels disagree about it, and
        two booleans that disagree means at least one of them is on.
        """
        return next(level for level, on in self.states.items() if on)

    @property
    def holes(self) -> list[str]:
        """Levels after the first one that have it off again.

        The whole argument that the levels are not a ladder lives in this list being non
        empty for `-Os` and `-Og`.
        """
        seen = False
        out = []
        for level, on in self.states.items():
            if on:
                seen = True
            elif seen:
                out.append(level)
        return out

    @property
    def label(self) -> str:
        on = [level for level, state in self.states.items() if state]
        return f"{self.name}, on at {', '.join(on)}"


class FlagDiff(Widget):
    kind = "flagdiff"
    title = "What each level turns on"
    defaults = {"at": "", "first": "all"}

    def __init__(self, tables: dict[str, Table], **kw: str) -> None:
        self.tables = tables
        self.levels = list(tables)
        self.switches = self._switches()
        super().__init__(**kw)
        if not self.view["at"] and self.switches:
            first = self.switches[0]
            self.view["at"] = f"{first.first} {first.name}"

    def _switches(self) -> list[Switch]:
        """Every switch the levels do not agree about, ordered by the row that fills it.

        Ordered by arrival and then by name, so that two runs of this over the same tables
        produce the same grid and a screenshot of it stays true.
        """
        names = sorted({o.name for t in self.tables.values() for o in t.booleans})
        found = []
        for name in names:
            states = {
                level: bool(t[name].on)
                for level, t in self.tables.items()
                if name in t and t[name].boolean
            }
            if len(set(states.values())) > 1:
                found.append(Switch(name=name, states=states))
        arrival = {level: i for i, level in enumerate(self.levels)}
        return sorted(found, key=lambda s: (arrival[s.first], s.name))

    # What the reader is looking at

    @property
    def shown(self) -> list[Switch]:
        if self.view["first"] == "all":
            return self.switches
        return [s for s in self.switches if s.first == self.view["first"]]

    @property
    def selected(self) -> Switch | None:
        """The switch whose column is picked out.

        The view holds a cell rather than a column, `-O2 -ftree-pre`, because the same
        column has a cell in every row and the browser side needs to know which one is lit.
        Neither a level nor a switch name has a space in it, so one split is enough.

        Only a column that is on screen can be selected. A filter that hides the column the
        URL asked for has to land somewhere, and landing on a hidden one shows a panel with
        nothing on the grid pointing at it.
        """
        wanted = self.view["at"].split(" ", 1)[-1]
        for s in self.shown:
            if s.name == wanted:
                return s
        return self.shown[0] if self.shown else None

    @property
    def current(self) -> str:
        """The one cell that is lit, as `level switch`.

        The reader may have clicked any row, so the level in the view is kept when it is a
        real one. When it is not, the cell in the row that first turns the switch on is the
        one to light, because that is the row the column is filed under.
        """
        at = self.selected
        if at is None:
            return ""
        level, _, name = self.view["at"].partition(" ")
        keep = name == at.name and level in at.states
        return f"{level if keep else at.first} {at.name}"

    @property
    def arrivals(self) -> list[str]:
        """The levels that are the first to turn something on, so no button does nothing."""
        seen = {s.first for s in self.switches}
        return [level for level in self.levels if level in seen]

    def on_at(self, level: str) -> list[Switch]:
        return [s for s in self.switches if s.states.get(level)]

    def data(self) -> dict:
        return {
            "levels": self.levels,
            "switches": [
                {
                    "name": s.name,
                    "first": s.first,
                    "on": [level for level, on in s.states.items() if on],
                }
                for s in self.switches
            ],
        }

    # Rendering

    def body(self) -> str:
        return join(
            [
                self._summary(),
                self._controls(),
                self._grid(),
                self._panels(),
                self._legend(),
                self._noscript(),
            ]
        )

    def _summary(self) -> str:
        every = {o.name for t in self.tables.values() for o in t.booleans}
        valued = {o.name for t in self.tables.values() for o in t.valued}
        parts = [
            f"{len(self.levels)} levels, {len(every)} switches between them",
            f"{len(self.switches)} of those switches differ, and only those are drawn",
            f"{len(valued)} more options take a value instead of flipping, and are not here",
        ]
        return el("p", join([el("span", esc(p)) for p in parts]), class_="gx-stat")

    def _controls(self) -> str:
        buttons = []
        for value in ["all", *self.arrivals]:
            count = len([s for s in self.switches if value in ("all", s.first)])
            buttons.append(
                el(
                    "button",
                    esc(f"{value} ({count})"),
                    type="button",
                    class_="gx-filter",
                    data_filter="first",
                    data_value=value,
                    aria_pressed="true" if self.view["first"] == value else "false",
                )
            )
        return el(
            "div",
            join(buttons, " "),
            class_="gx-controls",
            role="group",
            aria_label="Show only the switches this level is the first to turn on",
        )

    def _grid(self) -> str:
        if not self.shown:
            return el("p", "No switch arrives at that level.", class_="gx-note")
        current = self.current
        rows = []
        for level in self.levels:
            cells = [
                el(
                    "button",
                    "",
                    type="button",
                    class_="gx-cell",
                    id=f"{self.id}-{level}-{i}",
                    data_cell=f"{level} {s.name}",
                    data_level=level,
                    data_first=s.first,
                    data_on="1" if s.states.get(level) else "0",
                    data_panel=s.name,
                    aria_current="true" if f"{level} {s.name}" == current else None,
                    aria_label=f"{level}, {s.name}, {'on' if s.states.get(level) else 'off'}",
                    tabindex=0 if f"{level} {s.name}" == current else -1,
                )
                for i, s in enumerate(self.shown)
            ]
            on = len([s for s in self.shown if s.states.get(level)])
            rows.append(
                el(
                    "div",
                    join(
                        [
                            el("span", esc(level), class_="gx-ladder-name"),
                            el("span", join(cells), class_="gx-ladder-cells"),
                            el("span", esc(f"{on}"), class_="gx-ladder-n"),
                        ]
                    ),
                    class_="gx-ladder-row",
                    role="group",
                    aria_label=f"{level}, {on} of these {len(self.shown)} switches on",
                )
            )
        return el(
            "div",
            join(rows),
            class_="gx-ladder",
            role="group",
            data_select="at",
            aria_label="Optimization levels down the side, switches across the top",
        )

    def _panels(self) -> str:
        at = self.selected
        panels = []
        for s in self.switches:
            rows = "\n".join(
                f"{level:>7}  {'on' if on else 'off'}" for level, on in s.states.items()
            )
            note = f"{s.name}, first on at {s.first}"
            if s.holes:
                note += f", and off again at {', '.join(s.holes)}"
            panels.append(
                el(
                    "div",
                    join(
                        [
                            el("p", esc(note), class_="gx-note"),
                            el("pre", esc(rows), class_="gx-mono"),
                        ]
                    ),
                    class_="gx-panel",
                    role="tabpanel",
                    data_panel=s.name,
                    hidden=not (at is not None and at.name == s.name),
                )
            )
        return join(panels)

    def _legend(self) -> str:
        """What a filled cell means, and the honest note about how thin a cell is.

        A column is a few pixels wide and there is no room in it for a glyph, so the second
        channel is the bar under the cell: a solid one where the switch is on, a faint one
        where it is off. The number at the end of each row is the third channel, and it is
        the one a screen reader gets first.
        """
        return join(
            [
                legend(
                    [
                        ("+", "gx-added", "the switch is on at this level"),
                        (".", "gx-neutral", "the switch is off at this level"),
                    ]
                ),
                el(
                    "p",
                    "A filled cell also has a solid bar under it, so the grid still reads "
                    "in greyscale. The number at the end of a row is how many of the shown "
                    "switches that level has on.",
                    class_="gx-note",
                ),
            ]
        )

    def _noscript(self) -> str:
        lines = [f"{level:>7}  {len(self.on_at(level))} on" for level in self.levels]
        listing = "\n".join([*lines, "", *(s.label for s in self.switches)])
        return el(
            "noscript",
            join(
                [
                    el(
                        "p",
                        "Filtering and the panels need JavaScript. The grid above is already "
                        "drawn, and every switch is written out below.",
                        class_="gx-note",
                    ),
                    el(
                        "details",
                        join(
                            [
                                el("summary", "Every switch the levels disagree about"),
                                el("pre", esc(listing), class_="gx-mono"),
                            ]
                        ),
                    ),
                ]
            ),
        )
