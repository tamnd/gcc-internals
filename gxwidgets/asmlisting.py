"""The assembly file, every line of it, and what put each one there.

An assembly listing is mostly not instructions. The one this widget was built for is forty
six lines long and twelve of them are instructions, and a reader who has only ever seen the
filtered view on a compiler explorer page has never been shown the other thirty four. So the
default here is the whole file, and instructions only is a button, which is the opposite way
round from the tools people arrive with.

Every line is selectable and every line has a panel. A directive gets a sentence about what
the assembler does with it. An instruction gets the `-dp` annotation taken apart: the uid of
the RTL insn it came from, the cost and length the compiler put on it, the pattern in the
machine description that emitted it, and the row of that pattern's alternative table that the
operands actually fit. That last one is the point of the widget. The text on the left of the
screen is the output template on the right with the operands substituted in, and once a
reader has seen that happen three times the back end stops being a black box.

The machine description extract is committed rather than read from a GCC checkout, because a
reader in a browser does not have 1.3 GB of GCC. Every pattern in it carries the file, the
line and the tag it was taken from.
"""

from __future__ import annotations

from gxray.asm import Line, Listing, explain
from gxwidgets.base import Widget
from gxwidgets.html import el, esc, join, legend

#: The chip each kind of line gets: the glyph, the palette role, and what the legend says it
#: means. Seven roles exist and this widget uses five of them, one per kind.
MARKS = {
    "instruction": ("+", "gx-added", "an instruction, the only kind of line that runs"),
    "directive": ("=", "gx-constant", "a directive, which tells the assembler something"),
    "label": (">", "gx-focus", "a label, which is a name for the address it sits at"),
    "comment": ("?", "gx-unknown", "a comment, which the assembler reads past"),
    "blank": (".", "gx-neutral", "a blank line"),
}

#: An instruction with no annotation of its own. One RTL insn can emit several lines and only
#: the first is annotated, so this is a continuation rather than an insn in its own right.
CONTINUED = ("~", "gx-changed", "an instruction that continues the insn above it")

#: What the reader can filter down to. Every line first, because that is the argument.
FILTERS = [
    ("all", "every line"),
    ("instruction", "instructions"),
    ("directive", "directives"),
]


def shown(line: Line) -> str:
    """The line as the assembler sees it, without the annotation the widget shows separately.

    Repeating `// 12 [c=4 l=4] *addsi3_aarch64/1` in the listing when the same four facts are
    already in a column of their own would make the listing wider and say nothing new.
    """
    if line.kind == "blank":
        return ""
    if line.kind == "comment":
        return line.text.strip()
    if line.kind == "label":
        return f"{line.name}:"
    return f"{line.name} {line.args}".rstrip()


def chosen(pattern: dict, line: Line) -> dict | None:
    """The alternative the annotation pointed at, or None if the pattern has no table.

    A pattern with one alternative prints no slash, because `final` only prints one when
    there is a choice to record. So a missing slash and a one row table mean the same thing
    and both land on row zero.
    """
    rows = pattern.get("alternatives") or []
    if line.alternative is not None:
        return rows[line.alternative] if line.alternative < len(rows) else None
    return rows[0] if len(rows) == 1 else None


def reading(line: Line, pattern: dict | None, row: dict | None) -> str:
    """A sentence or two about where this line came from, in the reader's own words."""
    if line.kind != "instruction":
        return explain(line)
    if not line.annotated:
        return (
            "No annotation of its own. One insn can emit more than one instruction and only "
            "the first line gets the comment, so this line belongs to the insn above it."
        )
    if pattern is None:
        return (
            f"Emitted by {line.pattern}, which is not in the committed extract. "
            "The extract holds the patterns this lesson's recordings named and nothing else."
        )
    where = f"{pattern['file']}:{pattern['line']}"
    written = pattern["written"]
    total = len(pattern.get("alternatives") or [])
    if row is None:
        return (
            f"Emitted by {written} at {where}. This pattern picks its text in C rather than "
            "from a table, so there is no alternative to number and the annotation has no "
            "slash after the name."
        )
    if total == 1:
        return (
            f"Emitted by {written} at {where}. The pattern has one alternative, so there is "
            "nothing to choose between and the annotation prints no slash."
        )
    return (
        f"Emitted by {written} at {where}. The operands this insn ended up with fit row "
        f"{row['index']} of {total}, and the text on the left is that row's output template "
        "with the operands filled in."
    )


class AsmListing(Widget):
    kind = "asmlisting"
    title = "Every line, and what put it there"
    defaults = {"at": "", "kind": "all"}

    def __init__(self, listing: Listing, machine: dict | None = None, **kw: str) -> None:
        """`machine` is a committed machine description extract, from `gxray.mdesc`."""
        self.listing = listing
        self.machine = dict(machine or {})
        self.patterns: dict[str, dict] = self.machine.get("patterns", {})
        super().__init__(**kw)
        if not self.view["at"] and self.lines:
            first = self.listing.insns or list(self.lines)
            self.view["at"] = str(first[0].number)

    @property
    def lines(self) -> tuple[Line, ...]:
        return self.listing.lines

    @property
    def selected(self) -> str:
        known = {str(x.number) for x in self.lines}
        return self.view["at"] if self.view["at"] in known else next(iter(sorted(known)), "")

    def pattern(self, line: Line) -> dict | None:
        return self.patterns.get(line.pattern) if line.pattern else None

    def data(self) -> dict:
        counts = self.listing.counts()
        return {
            "counts": counts,
            "patterns": {name: len(uses) for name, uses in self.listing.patterns().items()},
            "sections": list(self.listing.sections),
            "tag": self.machine.get("tag", ""),
        }

    # Rendering

    def body(self) -> str:
        if not self.lines:
            return el("p", "Nothing to show. The recording has no assembly in it.")
        return join(
            [
                self._summary(),
                self._filters(),
                self._listing(),
                join([self._panel(line) for line in self.lines]),
                self._legend(),
                self._noscript(),
            ]
        )

    def _summary(self) -> str:
        c = self.listing.counts()
        parts = [
            f"{c['total']} lines",
            f"{c['instruction']} instructions",
            f"{c['annotated']} insns",
            f"{c['sections']} sections",
            f"{len(self.listing.patterns())} patterns",
        ]
        return el("p", join([el("span", esc(p)) for p in parts]), class_="gx-stat")

    def _filters(self) -> str:
        buttons = [
            el(
                "button",
                esc(title),
                type="button",
                data_filter="kind",
                data_value=value,
                aria_pressed="true" if self.view["kind"] == value else "false",
            )
            for value, title in FILTERS
        ]
        return el("div", join(buttons), class_="gx-controls", aria_label="Which lines to show")

    def _listing(self) -> str:
        return el(
            "div",
            join([self._line(line) for line in self.lines]),
            class_="gx-listing",
            role="tablist",
            aria_orientation="vertical",
            data_select="at",
            aria_label="The assembly, one line at a time",
        )

    def _line(self, line: Line) -> str:
        at = str(line.number)
        glyph, role, _ = CONTINUED if self._continues(line) else MARKS[line.kind]
        text = shown(line)
        body = join(
            [
                el("span", esc(at), class_="gx-asmline-no"),
                el("span", glyph, class_=f"gx-chip {role}", aria_hidden="true"),
                el("code", esc(text), class_="gx-asmline-text"),
                el("span", esc(line.slot), class_="gx-asmline-slot"),
            ]
        )
        return el(
            "button",
            body,
            type="button",
            class_="gx-asmline",
            role="tab",
            data_cell=at,
            data_panel=at,
            data_kind=line.kind,
            aria_current="true" if at == self.selected else "false",
            tabindex=0 if at == self.selected else -1,
            aria_label=self._label(line),
        )

    def _continues(self, line: Line) -> bool:
        return line.kind == "instruction" and not line.annotated

    def _label(self, line: Line) -> str:
        text = shown(line) or "blank line"
        if line.slot:
            return f"line {line.number}, {text}, from {line.slot}"
        return f"line {line.number}, {line.kind}, {text}"

    def _panel(self, line: Line) -> str:
        at = str(line.number)
        pattern = self.pattern(line)
        row = chosen(pattern, line) if pattern else None
        parts = [
            el("p", esc(reading(line, pattern, row)), class_="gx-reading"),
            self._facts(line, pattern, row),
        ]
        if row is not None:
            parts.append(self._substitution(line, row))
        if pattern is not None:
            parts.append(self._alternatives(pattern, row))
            parts.append(self._source(pattern))
        return el(
            "div",
            join(parts),
            class_="gx-panel",
            role="tabpanel",
            data_panel=at,
            hidden=at != self.selected,
        )

    def _facts(self, line: Line, pattern: dict | None, row: dict | None) -> str:
        facts: list[tuple[str, str]] = [("line", str(line.number)), ("section", line.section)]
        if line.annotated:
            facts += [("insn", f"uid {line.uid}"), ("cost", str(line.cost))]
            if line.length is not None:
                facts.append(("length", f"{line.length} bytes"))
            facts.append(("pattern", line.pattern))
        if line.note:
            facts.append(("operands", line.note))
        if pattern is not None:
            facts.append(("from", pattern["citation"]))
            for iterator, mode in pattern.get("modes") or []:
                facts.append((f"{iterator} is", mode))
            if pattern.get("condition"):
                facts.append(("only when", pattern["condition"]))
        if row is not None and row.get("attrs"):
            heads = pattern["attr_heads"] if pattern else []
            for head, value in zip(heads, row["attrs"], strict=False):
                facts.append((head, value))
        items = [
            el("li", join([esc(f"{key} "), el("code", esc(value))]))
            for key, value in facts
            if value
        ]
        return el("ul", join(items), class_="gx-facts")

    def _substitution(self, line: Line, row: dict) -> str:
        """The template and what came out of it, one above the other, so it can be compared."""
        text = f"template  {row['template']}\nemitted   {shown(line)}"
        return el("pre", esc(text), class_="gx-mono")

    def _alternatives(self, pattern: dict, row: dict | None) -> str:
        """The whole alternative table, with the row that was used marked.

        All of it, not just the row that won. Twenty three rows is a lot of screen for one
        `mov`, and it is also the honest answer to why that `mov` came out the way it did.
        """
        rows = pattern.get("alternatives") or []
        if not rows:
            block = (pattern.get("template") or "").strip()
            if not block:
                return ""
            said = "The C this pattern runs instead of a template. What it returns is printed."
            return join(
                [el("p", esc(said), class_="gx-note"), el("pre", esc(block), class_="gx-mono")]
            )
        heads = ["row", *pattern.get("cons_heads", []), "template"]
        head = el("tr", join([el("th", esc(h), scope="col") for h in heads]))
        body = [self._alternative(pattern, one, one is row) for one in rows]
        return el(
            "table",
            join([el("thead", head), el("tbody", join(body))]),
            class_="gx-alts",
            aria_label="Every alternative in this pattern, and which one was used",
        )

    def _alternative(self, pattern: dict, row: dict, current: bool) -> str:
        wide = len(pattern.get("cons_heads") or [])
        cons = list(row["cons"]) + [""] * (wide - len(row["cons"]))
        mark = el("span", ">", class_="gx-chip gx-focus") if current else ""
        cells = [
            el("th", join([mark, esc(str(row["index"]))], " "), scope="row"),
            *[el("td", esc(c)) for c in cons[:wide]],
            el("td", esc(row["template"]), title="written as ^" if row["inherited"] else None),
        ]
        return el("tr", join(cells), aria_current="true" if current else None)

    def _source(self, pattern: dict) -> str:
        summary = f"{pattern['written']} as written, {pattern['span']} lines"
        return el(
            "details",
            join([el("summary", esc(summary)), el("pre", esc(pattern["text"]), class_="gx-mono")]),
            class_="gx-source",
        )

    def _legend(self) -> str:
        used = {line.kind for line in self.lines}
        items = [(g, r, m) for kind, (g, r, m) in MARKS.items() if kind in used]
        if any(self._continues(line) for line in self.lines):
            items.append(CONTINUED)
        return join(
            [
                legend(items),
                el(
                    "p",
                    esc(
                        "The pattern name and the row number come from `-dp`, which writes "
                        "them as a comment on the first line of each insn. The row number is "
                        "only printed when the pattern has more than one row to choose from."
                    ),
                    class_="gx-note",
                ),
            ]
        )

    def _noscript(self) -> str:
        lines = [f"{x.number:>4}  {shown(x):<34}{x.slot}".rstrip() for x in self.lines]
        return el(
            "noscript",
            el(
                "details",
                join(
                    [
                        el("summary", "The whole listing at once"),
                        el("pre", esc("\n".join(lines)), class_="gx-mono"),
                    ]
                ),
            ),
        )
