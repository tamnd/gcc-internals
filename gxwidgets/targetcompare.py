"""The same four lines of C, on four machines, at the same moment.

Up to expand, this book has been able to say "the compiler" and mean one thing. RTL is where
that stops. The front end and the middle end are shared, the expander is where the target
gets a say, and the cheapest way to show what that means is to run the same source through
four back ends and put the four answers next to each other.

What comes out is not a difference in quality. It is a difference in vocabulary. x86-64 has
to write down that adding two numbers destroys the flags register, so its add is a `parallel`
with a `clobber` in it. RISC-V has no flags register at all, so its compare and its branch
are one insn instead of two. PowerPC's condition code lives in a pseudo, because the machine
has eight of them and the allocator picks. None of that is visible one pass earlier.

The comparison table is the widget. The per target listings are there so a reader who does
not believe a row can go and look, which is the only way a table like this earns anything.
"""

from __future__ import annotations

from gxray.rtl import Listing
from gxwidgets.base import Widget
from gxwidgets.html import el, esc, join, legend

#: The rows of the table, in the order that tells the story. Counts first, because they are
#: the rows a reader can check by eye, then the registers, then the modes, which is where the
#: real difference is and which needs the first two rows to land.
ROWS = [
    ("entries", "entries in the chain"),
    ("code", "of those, real instructions"),
    ("pseudos", "pseudo registers used"),
    ("first", "lowest pseudo number"),
    ("hard", "hard registers named"),
    ("codes", "different RTX codes"),
    ("modes", "machine modes"),
    ("cc", "where the condition code lives"),
    ("branch", "compare and branch"),
    ("clobber", "does adding destroy anything"),
]


def hard_names(listing: Listing) -> list[str]:
    """The hard registers by the name the target prints, which is the name in its manual.

    PowerPC prints its general registers as bare numbers, so a name here can be a digit.
    That is the target's own spelling and it is left alone.
    """
    seen: list[str] = []
    for insn in listing:
        for node in insn.registers:
            if node.pseudo or node.register is None:
                continue
            named = [x for x in node.leaves[1:] if not x.startswith("[")]
            label = named[0] if named else str(node.register)
            if label not in seen:
                seen.append(label)
    return seen


def condition_code(listing: Listing) -> str:
    """Which condition code modes the target uses, and whether they sit in a fixed register.

    Three different answers turn up in four targets, which is the whole reason this row is
    here. x86 and aarch64 have one flags register and name it. PowerPC has eight condition
    fields, so the compare writes a pseudo and the allocator decides later. RISC-V has none.
    """
    modes: list[str] = []
    hard = pseudo = False
    for insn in listing:
        for node in insn.registers:
            if not node.mode.startswith("CC"):
                continue
            if node.mode not in modes:
                modes.append(node.mode)
            if node.pseudo:
                pseudo = True
            else:
                hard = True
    if not modes:
        return "nowhere, this machine has no flags register"
    where = "a pseudo, the allocator picks which" if pseudo and not hard else "a fixed register"
    return f"{', '.join(modes)} in {where}"


def branching(listing: Listing) -> str:
    """Whether a conditional branch needs a compare in front of it."""
    for insn in listing:
        if insn.pattern is None:
            continue
        for node in insn.pattern.walk():
            if node.code != "if_then_else" or not node.children:
                continue
            test = node.children[0]
            cc = any(k.code == "reg" and k.mode.startswith("CC") for k in test.children)
            return "two insns, compare then branch" if cc else "one insn, the compare is in it"
    return "no branch in this function"


def clobbering(listing: Listing) -> str:
    """Whether the target's add has to say out loud that it wrecks something."""
    for insn in listing:
        p = insn.pattern
        if p is None or p.code != "parallel":
            continue
        nodes = list(p.walk())
        if any(n.code == "clobber" for n in nodes) and any(n.code == "plus" for n in nodes):
            return "yes, the add is a parallel with a clobber in it"
    return "no, the add is a plain set"


def facts(listing: Listing) -> dict[str, str]:
    """One column of the table."""
    pseudo, _ = listing.registers()
    return {
        "entries": str(len(listing)),
        "code": str(len(listing.code)),
        "pseudos": str(len(pseudo)),
        "first": str(pseudo[0]) if pseudo else "none",
        "hard": ", ".join(hard_names(listing)) or "none",
        "codes": str(len(listing.codes())),
        "modes": ", ".join(listing.modes()),
        "cc": condition_code(listing),
        "branch": branching(listing),
        "clobber": clobbering(listing),
    }


class TargetCompare(Widget):
    kind = "targetcompare"
    title = "One program, four back ends"
    defaults = {"at": ""}

    def __init__(
        self,
        listings: dict[str, Listing],
        compilers: dict[str, str] | None = None,
        source: str = "",
        **kw: str,
    ) -> None:
        self.listings = dict(listings)
        self.compilers = dict(compilers or {})
        self.source = source
        self.facts = {name: facts(fn) for name, fn in self.listings.items()}
        super().__init__(**kw)
        if not self.view["at"] and self.listings:
            self.view["at"] = next(iter(self.listings))

    @property
    def targets(self) -> list[str]:
        return list(self.listings)

    @property
    def selected(self) -> str:
        return self.view["at"] if self.view["at"] in self.listings else (self.targets or [""])[0]

    def agrees(self, key: str) -> bool:
        """Whether every target gave the same answer for one row."""
        return len({f[key] for f in self.facts.values()}) == 1

    def data(self) -> dict:
        return {"targets": self.targets, "rows": {k: self.agrees(k) for k, _ in ROWS}}

    # Rendering

    def body(self) -> str:
        if not self.listings:
            return el("p", "Nothing to compare. No target was recorded.")
        return join(
            [
                self._summary(),
                self._picker(),
                self._table(),
                join([self._panel(name) for name in self.targets]),
                self._legend(),
                self._noscript(),
            ]
        )

    def _summary(self) -> str:
        agree = len([k for k, _ in ROWS if self.agrees(k)])
        parts = [
            f"{len(self.listings)} targets",
            f"{agree} of {len(ROWS)} rows the same everywhere",
            "same source, same flags, same version",
        ]
        return el("p", join([el("span", esc(p)) for p in parts]), class_="gx-stat")

    def _picker(self) -> str:
        buttons = [
            el(
                "button",
                join(
                    [
                        el("span", esc(name), class_="gx-target-name"),
                        el("span", esc(self.compilers.get(name, "")), class_="gx-target-sub"),
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
            for name in self.targets
        ]
        return el(
            "div",
            join(buttons),
            class_="gx-targets",
            role="tablist",
            data_select="at",
            aria_label="Which target to look at",
        )

    def _label(self, name: str) -> str:
        f = self.facts[name]
        return (
            f"{name}, {f['code']} instructions, {f['pseudos']} pseudo registers, "
            f"condition code {f['cc']}, {f['branch']}"
        )

    def _table(self) -> str:
        head = el(
            "tr",
            join(
                [el("th", "", scope="col")]
                + [el("th", esc(name), scope="col") for name in self.targets]
            ),
        )
        rows = []
        for key, title in ROWS:
            same = self.agrees(key)
            cells = [
                el(
                    "td",
                    esc(self.facts[name][key]),
                    class_="gx-same" if same else "gx-differs",
                )
                for name in self.targets
            ]
            # The glyph in the row header, not colour in the cells, is what says whether the
            # targets agreed. A table that only said it in colour would be saying nothing to
            # a reader printing this out.
            mark = el(
                "span",
                "=" if same else "!",
                class_=f"gx-chip {'gx-unknown' if same else 'gx-changed'}",
            )
            header = el("th", join([mark, el("span", esc(title))], " "), scope="row")
            rows.append(el("tr", join([header, *cells])))
        return el(
            "table",
            join([el("thead", head), el("tbody", join(rows))]),
            class_="gx-facts-table",
        )

    def _panel(self, name: str) -> str:
        listing = self.listings[name]
        lines = [f"{i.uid:>4}  {i.pattern}" for i in listing.code]
        return el(
            "div",
            join(
                [
                    el("p", esc(self._label(name)), class_="gx-note"),
                    el("pre", esc("\n".join(lines)), class_="gx-mono"),
                ]
            ),
            class_="gx-panel",
            role="tabpanel",
            data_panel=name,
            hidden=name != self.selected,
        )

    def _legend(self) -> str:
        return join(
            [
                legend(
                    [
                        ("=", "gx-unknown", "every target gave the same answer"),
                        ("!", "gx-changed", "the targets disagree, which is the point"),
                    ]
                ),
                el(
                    "p",
                    esc(
                        "Only the instructions are listed under each target. The notes, the "
                        "labels and the debug entries are left out, because they are the same "
                        "everywhere and they are two thirds of the chain."
                    ),
                    class_="gx-note",
                ),
            ]
        )

    def _noscript(self) -> str:
        lines = [self._label(name) for name in self.targets]
        return el(
            "noscript",
            el(
                "details",
                join(
                    [
                        el("summary", "Every target at once"),
                        el("pre", esc("\n".join(lines)), class_="gx-mono"),
                    ]
                ),
            ),
        )
