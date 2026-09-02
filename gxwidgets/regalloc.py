"""Where every value in a function ended up, on two machines at once.

The same five functions, the same flags, the same version of GCC, and one back end runs out
of registers three functions before the other one does. That is the whole widget. The left
column is a target with fifteen registers to give away and the right column is a target with
thirty, and the reader watches the point where the left column starts putting values in
memory and the right column does not.

Each row is one pseudo register. The bar in the middle is the live range: the program points
where that value has to exist, after IRA has compressed the numbering. Two rows whose bars
overlap cannot share a register, and the number of bars crossing the busiest column is the
register pressure, which is the number in the header. The rest of the lesson is arithmetic
between that number and the number of registers the target has.

Nothing here names a hard register. IRA prints `assign reg 2`, and the 2 is an index into a
table only the target has, so this widget shows the number and the lesson gets the names off
the assembly instead.
"""

from __future__ import annotations

from gxray.regalloc import GENERAL, Allocation
from gxwidgets.base import Widget
from gxwidgets.html import el, esc, join, legend

#: The rows of the header table, in the order that makes the argument. Supply, then demand,
#: then the gap, then what the gap cost.
ROWS = [
    ("available", "registers the target can hand out"),
    ("peak", "values alive at the busiest point"),
    ("over", "how many more than there are"),
    ("spilled", "pseudos that ended up in memory"),
    ("mem", "what IRA charged for the memory traffic"),
]

#: Every filter the reader gets, as the value and the button.
HOMES = [("all", "every pseudo"), ("register", "kept in registers"), ("memory", "in memory")]

#: How wide one program point is drawn, in pixels. A whole function has to fit on a phone,
#: and the widest one here is sixty five points across.
POINT = 4


def summary(alloc: Allocation, klass: str = GENERAL) -> dict[str, str]:
    """One column of the header table for one function on one target."""
    over = alloc.over(klass)
    return {
        "available": str(alloc.available(klass)),
        "peak": str(alloc.peak(klass)),
        "over": str(over) if over > 0 else "none, it fits",
        "spilled": str(len(alloc.spilled)),
        "mem": str(alloc.totals.mem),
    }


def lifetime(alloc: Allocation, pseudo: int) -> set[int]:
    """Every program point this pseudo is alive at, across all the regions it appears in."""
    points: set[int] = set()
    for a in alloc.pseudos.get(pseudo, []):
        for start, stop in a.ranges:
            points.update(range(start, stop + 1))
    return points


def width(alloc: Allocation) -> int:
    """How many program points the compressed numbering has.

    Taken from the ranges rather than from the compression line, because a function that IRA
    did not bother compressing has no compression line and still has ranges.
    """
    ends = [stop for a in alloc for _, stop in a.ranges]
    return max(ends) + 1 if ends else 0


def runs(alive: set[int], span: int) -> list[tuple[bool, int]]:
    """A live range as alternating stretches of alive and not, so the bar is a few elements.

    One element per program point would be honest and would also put twenty five thousand
    spans on the page for five functions, which a notebook feels. A stretch carries exactly
    the same information because every point in it has the same answer.
    """
    out: list[tuple[bool, int]] = []
    for n in range(span):
        on = n in alive
        if out and out[-1][0] == on:
            out[-1] = (on, out[-1][1] + 1)
        else:
            out.append((on, 1))
    return out


def home(alloc: Allocation, pseudo: int) -> str:
    """Where a pseudo lives, in one word, folding its regions together.

    A pseudo with an allocno in memory anywhere counts as in memory. That is the honest
    reading: the value gets stored and reloaded somewhere, and the loop is where it hurts.
    """
    group = alloc.pseudos.get(pseudo, [])
    if any(a.spilled for a in group):
        return "memory"
    return "register" if any(a.placed for a in group) else "nowhere"


class RegAlloc(Widget):
    kind = "regalloc"
    title = "Who got a register"
    defaults = {"fn": "", "home": "all"}

    def __init__(
        self,
        allocations: dict[str, dict[str, Allocation]],
        compilers: dict[str, str] | None = None,
        **kw: str,
    ) -> None:
        """`allocations` is target name to function name to allocation, in display order."""
        self.allocations = {t: dict(fns) for t, fns in allocations.items()}
        self.compilers = dict(compilers or {})
        super().__init__(**kw)
        if not self.view["fn"] and self.functions:
            self.view["fn"] = self.functions[0]

    @property
    def targets(self) -> list[str]:
        return list(self.allocations)

    @property
    def functions(self) -> list[str]:
        """Every function that all the targets have, in the order the first target had them."""
        if not self.allocations:
            return []
        first, *rest = self.allocations.values()
        return [name for name in first if all(name in other for other in rest)]

    @property
    def selected(self) -> str:
        return self.view["fn"] if self.view["fn"] in self.functions else (self.functions or [""])[0]

    def at(self, target: str, function: str) -> Allocation:
        return self.allocations[target][function]

    def divergence(self) -> list[str]:
        """The functions where the targets did not agree about whether everything fits."""
        out = []
        for name in self.functions:
            verdicts = {self.at(t, name).fits for t in self.targets}
            if len(verdicts) > 1:
                out.append(name)
        return out

    def data(self) -> dict:
        return {
            "targets": self.targets,
            "functions": self.functions,
            "spilled": {
                name: {t: len(self.at(t, name).spilled) for t in self.targets}
                for name in self.functions
            },
            "diverges": self.divergence(),
        }

    # Rendering

    def body(self) -> str:
        if not self.functions:
            return el("p", "Nothing to show. No allocation was recorded.")
        return join(
            [
                self._summary(),
                self._picker(),
                self._filters(),
                join([self._panel(name) for name in self.functions]),
                self._legend(),
                self._noscript(),
            ]
        )

    def _summary(self) -> str:
        split = self.divergence()
        parts = [
            f"{len(self.functions)} functions",
            f"{len(self.targets)} targets",
            (
                f"{', '.join(split)} come out differently"
                if split
                else "every function comes out the same"
            ),
        ]
        return el("p", join([el("span", esc(p)) for p in parts]), class_="gx-stat")

    def _picker(self) -> str:
        buttons = [
            el(
                "button",
                join(
                    [
                        el("span", esc(name), class_="gx-target-name"),
                        el("span", esc(self._peaks(name)), class_="gx-target-sub"),
                    ]
                ),
                type="button",
                class_="gx-target",
                role="tab",
                data_cell=name,
                data_panel=name,
                aria_current="true" if name == self.selected else None,
                tabindex=0 if name == self.selected else -1,
                aria_label=self._label(name),
            )
            for name in self.functions
        ]
        return el(
            "div",
            join(buttons),
            class_="gx-targets",
            role="tablist",
            data_select="fn",
            aria_label="Which function to look at",
        )

    def _peaks(self, name: str) -> str:
        one = self.at(self.targets[0], name)
        return f"{one.peak()} live"

    def _label(self, name: str) -> str:
        bits = []
        for t in self.targets:
            a = self.at(t, name)
            state = "fits" if a.fits else f"{len(a.spilled)} in memory"
            bits.append(f"{t}, {a.peak()} live of {a.available()}, {state}")
        return f"{name}: " + "; ".join(bits)

    def _filters(self) -> str:
        buttons = [
            el(
                "button",
                esc(title),
                type="button",
                data_filter="home",
                data_value=value,
                aria_pressed="true" if self.view["home"] == value else "false",
            )
            for value, title in HOMES
        ]
        return el("div", join(buttons), class_="gx-controls", aria_label="Which pseudos to show")

    def _panel(self, name: str) -> str:
        columns = [self._column(t, name) for t in self.targets]
        return el(
            "div",
            join([self._table(name), el("div", join(columns), class_="gx-columns")]),
            class_="gx-panel",
            role="tabpanel",
            data_panel=name,
            hidden=name != self.selected,
        )

    def _table(self, name: str) -> str:
        facts = {t: summary(self.at(t, name)) for t in self.targets}
        head = el(
            "tr",
            join(
                [el("th", "", scope="col")] + [el("th", esc(t), scope="col") for t in self.targets]
            ),
        )
        rows = []
        for key, title in ROWS:
            same = len({facts[t][key] for t in self.targets}) == 1
            cells = [
                el("td", esc(facts[t][key]), class_="gx-same" if same else "gx-differs")
                for t in self.targets
            ]
            mark = el(
                "span",
                "=" if same else "!",
                class_=f"gx-chip {'gx-unknown' if same else 'gx-changed'}",
            )
            rows.append(
                el(
                    "tr",
                    join(
                        [el("th", join([mark, el("span", esc(title))], " "), scope="row"), *cells]
                    ),
                )
            )
        return el(
            "table", join([el("thead", head), el("tbody", join(rows))]), class_="gx-facts-table"
        )

    def _column(self, target: str, name: str) -> str:
        alloc = self.at(target, name)
        span = width(alloc)
        rows = [self._slot(alloc, pseudo, span) for pseudo in sorted(alloc.pseudos)]
        head = el(
            "p",
            esc(f"{target}, {self.compilers.get(target, '')}".rstrip(", ")),
            class_="gx-rung-head",
        )
        return el(
            "div",
            join([head, el("div", join(rows), class_="gx-slots")]),
            class_="gx-column",
        )

    def _slot(self, alloc: Allocation, pseudo: int, span: int) -> str:
        where = home(alloc, pseudo)
        alive = lifetime(alloc, pseudo)
        role = "gx-removed" if where == "memory" else "gx-constant"
        glyph = "-" if where == "memory" else "="
        bar = el(
            "span",
            join(
                [
                    el("span", "", data_on="1" if on else "0", style=f"width:{POINT * n}px")
                    for on, n in runs(alive, span)
                ]
            ),
            class_="gx-life",
            aria_hidden="true",
        )
        told = ", ".join(a.where for a in alloc.pseudos[pseudo])
        return el(
            "div",
            join(
                [
                    el(
                        "span",
                        join([el("span", glyph, class_=f"gx-chip {role}"), esc(f"r{pseudo}")], " "),
                        class_="gx-slot-name",
                    ),
                    bar,
                    el("span", esc(told), class_="gx-slot-home"),
                ]
            ),
            class_="gx-slot",
            data_home=where,
            title=f"r{pseudo} alive at {len(alive)} of {span} points, {told}",
        )

    def _legend(self) -> str:
        return join(
            [
                legend(
                    [
                        ("=", "gx-constant", "this value got a register"),
                        ("-", "gx-removed", "this value ended up in memory"),
                        ("!", "gx-changed", "the two targets gave different answers"),
                    ]
                ),
                el(
                    "p",
                    esc(
                        "The bar is the live range after IRA compressed the point numbering, "
                        "so the columns line up within a target and not across two of them. "
                        "A register number is an index into the target's own table and this "
                        "widget does not try to name it."
                    ),
                    class_="gx-note",
                ),
            ]
        )

    def _noscript(self) -> str:
        lines = [self._label(name) for name in self.functions]
        return el(
            "noscript",
            el(
                "details",
                join(
                    [
                        el("summary", "Every function at once"),
                        el("pre", esc("\n".join(lines)), class_="gx-mono"),
                    ]
                ),
            ),
        )
