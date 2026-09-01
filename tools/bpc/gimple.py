"""Section 2 of `BP-GIMPLE`, generated from GCC's own description of GIMPLE.

Nothing in this file knows how many statement codes GIMPLE has, what any of them mean, or
which C structure holds which one. All of that is read out of three files in the pinned
tree every time the blueprint is built:

    gcc/gimple.def      every statement code, its printable name and its layout
    gcc/gsstruct.def    every layout structure and whether it carries tree operands
    gcc/gimple.h        the structures themselves, the C++ classes, the code ranges

The point is not to save typing. It is that a hand written inventory is wrong the day a
statement code is added and stays wrong until somebody notices, and nobody notices, because
the person who would notice is the person who already knows. A generated inventory is wrong
for exactly as long as it takes to run `bpc build`.

Two things here are worth reading even if you never touch the generator. The first is that
`gimple.def` is ordered and the order is load bearing: two of GIMPLE's most used predicates
are range checks over the enum, so the file carries warnings telling you not to rearrange
it, and section 2.2 pulls those warnings out and pairs them with the code that relies on
them. The second is that the map from a statement code to the C++ class you may cast it to
lives in template specialisations rather than in any table, and section 2.5 is that map,
which as far as I can tell is not written down anywhere else.
"""

from __future__ import annotations

from pathlib import Path

from tools.bpc import generator
from tools.bpc.gccsrc import (
    Entry,
    Field,
    Struct,
    parse_code_ranges,
    parse_is_a_helpers,
    parse_structs,
    read,
)
from tools.bpc.gccsrc import parse_def as parse_def_file

GIMPLE_DEF = "gcc/gimple.def"
GSSTRUCT_DEF = "gcc/gsstruct.def"
GIMPLE_H = "gcc/gimple.h"


def codes(root: Path) -> list[Entry]:
    return parse_def_file(read(root / "gimple.def"), "DEFGSCODE")


def layouts(root: Path) -> list[Entry]:
    return parse_def_file(read(root / "gsstruct.def"), "DEFGSSTRUCT")


def header(root: Path) -> str:
    return read(root / "gimple.h")


def cell(text: str) -> str:
    """One line of a markdown table cell. A pipe would end the cell, so it goes."""
    return " ".join(text.split()).replace("|", "/")


def prose_cell(text: str) -> str:
    """A cell that is not inside backticks, so angle brackets have to be escaped."""
    return cell(text).replace("<", "&lt;").replace(">", "&gt;")


def sentence(facts: list[str]) -> str:
    """A list of facts as one sentence, without lowercasing the identifiers in it."""
    joined = ", ".join(facts)
    return joined[0].upper() + joined[1:] + "."


def quote(text: str) -> str:
    """GCC's own words, in a fenced block so the house prose rules leave them alone."""
    return "```text\n" + (text.rstrip() or "(no comment in the file)") + "\n```"


def table(headings: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headings) + " |", "|" + "|".join(["---"] * len(headings)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def operand_class(index: int, bounds: dict[str, tuple[int, int]]) -> str:
    if bounds["mem"][0] <= index <= bounds["mem"][1]:
        return "registers and memory"
    if bounds["ops"][0] <= index <= bounds["ops"][1]:
        return "registers"
    return "none"


def _bounds(root: Path) -> dict[str, tuple[int, int]]:
    """The two operand ranges, as index pairs into the code enum."""
    ranges = parse_code_ranges(header(root))
    order = {e.name: e.index for e in codes(root)}
    missing = {"gimple_has_ops", "gimple_has_mem_ops"} - set(ranges)
    if missing:
        raise KeyError(f"gimple.h no longer defines {sorted(missing)} as a range check")
    return {
        "ops": (order[ranges["gimple_has_ops"][0]], order[ranges["gimple_has_ops"][1]]),
        "mem": (order[ranges["gimple_has_mem_ops"][0]], order[ranges["gimple_has_mem_ops"][1]]),
    }


def _class_of(root: Path) -> dict[str, str]:
    """Code to the single C++ class that tests for exactly that code."""
    out = {}
    for cls, accepted in parse_is_a_helpers(header(root)).items():
        if len(accepted) == 1:
            out.setdefault(accepted[0], cls)
    return out


@generator("gimple-codes")
def gimple_codes(root: Path) -> str:
    entries = codes(root)
    bounds = _bounds(root)
    classes = _class_of(root)

    rows = [
        [
            str(e.index),
            f"`{e.name}`",
            f"`{e.arg(1)}`",
            f"`{e.arg(2)}`",
            f"`{classes[e.name]}`" if e.name in classes else "none",
            operand_class(e.index, bounds),
        ]
        for e in entries
    ]

    by_layout: dict[str, int] = {}
    for e in entries:
        by_layout[e.arg(2)] = by_layout.get(e.arg(2), 0) + 1

    with_ops = sum(1 for e in entries if operand_class(e.index, bounds) != "none")
    return "\n\n".join(
        [
            f"GIMPLE has **{len(entries)} statement codes** in GCC 16.2.0, laid out in "
            f"**{len(by_layout)} of the {len(layouts(root))} structures** that `gsstruct.def` "
            f"declares. {with_ops} of the codes carry operands. The rest are markers, and a "
            f"marker with no operands is still a statement that a pass has to handle.",
            "The number in the first column is the value of the enumerator, which is also its "
            "position in `gimple.def`. It is not stable across releases and no code should "
            "depend on a particular value, but the *order* is depended on heavily, which "
            "section 2.2 covers.",
            table(
                ["#", "Code", "Printable name", "Layout", "C++ class", "Operands"],
                rows,
            ),
            f"Read from `{GIMPLE_DEF}`, `{GSSTRUCT_DEF}` and `{GIMPLE_H}`.",
        ]
    )


@generator("gimple-ordering")
def gimple_ordering(root: Path) -> str:
    entries = codes(root)
    bounds = _bounds(root)
    ranges = parse_code_ranges(header(root))
    by_index = {e.index: e for e in entries}

    parts = [
        "Two predicates that every pass in the middle end calls are range checks over the "
        "code enum rather than flags on a statement. That makes the order of `gimple.def` "
        "part of the interface, and the file says so in comments that sit above the codes "
        "they protect."
    ]

    rows = []
    for key, label in [("ops", "gimple_has_ops"), ("mem", "gimple_has_mem_ops")]:
        lo, hi = bounds[key]
        members = ", ".join(f"`{by_index[i].name}`" for i in range(lo, hi + 1))
        rows.append(
            [
                f"`{label}`",
                f"`{ranges[label][0]}` to `{ranges[label][1]}`",
                f"{hi - lo + 1}",
                members,
            ]
        )
    parts.append(table(["Predicate", "Range", "Codes", "Which ones"], rows))

    warnings = [(e, n) for e in entries for n in e.notes if "rearrange" in n.lower()]
    parts.append(
        f"`gimple.def` carries {len(warnings)} warnings of its own about the ordering. "
        f"Each one sits directly above the first code it applies to."
    )
    for e, note in warnings:
        parts.append(f"Above `{e.name}`, which is defined at `{GIMPLE_DEF}:{e.line}`:")
        parts.append(quote(note))

    parts.append(
        "The consequence for anyone adding a statement code: a code with operands goes "
        "inside the existing run, a code without operands goes outside it, and putting one "
        "in the wrong place changes the meaning of every `gimple_has_ops` call in the "
        "compiler without changing a line of their source."
    )
    return "\n\n".join(parts)


def _tree(structs: list[Struct]) -> str:
    """The inheritance chain as an indented tree, so the layout hierarchy is visible."""
    children: dict[str, list[Struct]] = {}
    for s in structs:
        children.setdefault(s.base, []).append(s)

    lines: list[str] = []

    def walk(name: str, depth: int) -> None:
        for s in children.get(name, []):
            tag = f"  [{s.tag}]" if s.tag else ""
            lines.append("  " * depth + s.name + tag)
            walk(s.name, depth + 1)

    walk("", 0)
    if len(lines) != len(structs):
        missing = set(children) - {s.name for s in structs} - {""}
        raise KeyError(f"these structures extend something outside gimple.h: {sorted(missing)}")
    return "```text\n" + "\n".join(lines) + "\n```"


@generator("gimple-layouts")
def gimple_layouts(root: Path) -> str:
    structs = parse_structs(header(root))
    entries = codes(root)
    by_tag: dict[str, list[str]] = {}
    for e in entries:
        by_tag.setdefault(e.arg(2), []).append(e.name)

    rows = []
    for layout in layouts(root):
        tag, struct, has_ops = layout.arg(0), layout.arg(1), layout.arg(2)
        users = by_tag.get(tag, [])
        rows.append(
            [
                f"`{tag}`",
                f"`{struct}`",
                "yes" if has_ops == "true" else "no",
                str(len(users)),
                ", ".join(f"`{u}`" for u in users) or "none",
            ]
        )

    unused = [r[0] for r in rows if r[3] == "0"]
    parts = [
        "A statement's layout is not its code. Several codes share one structure, and the "
        "structure is what decides how much memory the statement takes and where its "
        "operands live. `gsstruct.def` is the list of layouts, and the third argument says "
        "whether the layout carries a vector of tree operands.",
        table(["Layout", "Structure", "Tree operands", "Codes", "Used by"], rows),
    ]
    if unused:
        parts.append(
            "Layouts with no code of their own: "
            + ", ".join(unused)
            + ". These are bases that other layouts extend, or layouts reached only through "
            "a subclass, and they are in the enum because the garbage collector needs a tag "
            "for every distinct shape it may walk."
        )
    parts.append(
        "The structures themselves form a single inheritance chain, and the chain is the "
        "reason a statement can be passed around as a `gimple *` and then narrowed:"
    )
    parts.append(_tree(structs))
    parts.append(
        "A name in square brackets is the GTY tag the garbage collector uses to decide "
        "which structure it is looking at, and several structures share a tag because they "
        "share a layout exactly."
    )
    return "\n\n".join(parts)


def _field_rows(fields: list[Field]) -> list[list[str]]:
    rows = []
    for f in fields:
        rows.append(
            [
                f.word or "",
                f"`{f.name}`",
                f"`{cell(f.type)}`",
                f"`{cell(f.gty)}`" if f.gty else "",
                prose_cell(f.doc) or "no comment in the header",
            ]
        )
        for m in f.members:
            rows.append(
                [
                    "",
                    f"`{f.name}.{m.name}`",
                    f"`{cell(m.type)}`",
                    f"`{cell(m.gty)}`" if m.gty else "",
                    prose_cell(m.doc) or f"one alternative of the `{f.name}` union",
                ]
            )
    return rows


@generator("gimple-fields")
def gimple_fields(root: Path) -> str:
    structs = [s for s in parse_structs(header(root)) if s.fields]
    parts = [
        f"Every structure that holds a GIMPLE statement, field by field, in declaration "
        f"order. {len(structs)} of them declare fields of their own. The word column is "
        f"GCC's own marker for which 64 bit word of the object the field lands in, which is "
        f"the only place the layout is written down, and it is a comment rather than "
        f"anything the compiler enforces.",
        "A field carrying no GTY marker is walked by the garbage collector in the ordinary "
        "way. `skip` means the collector does not follow it, which is a claim that the "
        "object is reachable by another route and a leak or a stale pointer if it is not.",
    ]
    for s in structs:
        head = f"#### `{s.name}`"
        facts = []
        if s.base:
            facts.append(f"extends `{s.base}`")
        if s.tag:
            facts.append(f"tag `{s.tag}`")
        if s.inherited_words:
            facts.append(f"inherits {s.inherited_words.lower()}")
        if s.code:
            facts.append(f"holds only `{s.code}`")
        facts.append(f"`{GIMPLE_H}:{s.line}`")
        parts.append(head)
        if s.doc:
            parts.append(quote(s.doc))
        parts.append(sentence(facts))
        parts.append(table(["Word", "Field", "Type", "GTY", "Meaning"], _field_rows(s.fields)))
        notes = [n for f in s.fields for n in f.notes]
        if notes:
            parts.append("Layout notes written in the header alongside these fields:")
            parts.append(quote("\n\n".join(notes)))
    return "\n\n".join(parts)


@generator("gimple-classes")
def gimple_classes(root: Path) -> str:
    text = header(root)
    helpers = parse_is_a_helpers(text)
    structs = {s.name: s for s in parse_structs(text)}
    entries = {e.name for e in codes(root)}

    rows = []
    for cls in sorted(helpers):
        accepted = helpers[cls]
        if not accepted:
            continue
        unknown = [c for c in accepted if c not in entries]
        if unknown:
            raise KeyError(f"is_a_helper for {cls} tests unknown codes {unknown}")
        s = structs.get(cls)
        rows.append(
            [
                f"`{cls}`",
                ", ".join(f"`{c}`" for c in accepted),
                f"`{s.base}`" if s and s.base else "",
                "yes" if s and s.code else "no",
                f"`{GIMPLE_H}:{s.line}`" if s else "",
            ]
        )

    multi = sorted(cls for cls, a in helpers.items() if len(a) > 1)
    ranged = sorted(cls for cls, a in helpers.items() if not a)
    grouping = (
        f"Only `{multi[0]}` accepts more than one code."
        if len(multi) == 1
        else f"{len(multi)} of these classes accept more than one code: "
        + ", ".join(f"`{c}`" for c in multi)
        + "."
    )
    return "\n\n".join(
        [
            f"GIMPLE statements are all `gimple *` at rest and are narrowed on use, with "
            f"`as_a` when the code is already known and `dyn_cast` when it is being tested. "
            f"Which narrowings are legal is not held in a table anywhere in GCC. It is "
            f"{len(rows)} template specialisations of `is_a_helper::test`, each of which "
            f"compares the statement's code against one or more constants. This is that map.",
            table(["Class", "Accepts", "Extends", "Declares `code_`", "Defined at"], rows),
            "The `code_` column matters more than it looks. A class that declares it can be "
            "built by the generic `gimple_build` machinery and checked at compile time. A "
            "class that does not is narrowed at run time only.",
            grouping + " That is the deliberate grouping, and a cast to it is how a pass "
            "handles a family of statements without listing its members.",
            f"{len(ranged)} more classes are narrowed by a range check over the code enum "
            f"rather than by naming codes, so they do not appear in the table: "
            + ", ".join(f"`{c}`" for c in ranged)
            + ". They are the two operand carrying layouts from section 2.3, and they are "
            "the reason section 2.2 exists.",
        ]
    )


@generator("gimple-shapes")
def gimple_shapes(root: Path) -> str:
    entries = codes(root)
    bounds = _bounds(root)
    classes = _class_of(root)

    parts = [
        f"All {len(entries)} codes, with the operand shape and the description exactly as "
        f"`gimple.def` states them. Where a code has no description of its own, the file "
        f"documents it together with the code above it and this says so rather than "
        f"inventing one.",
    ]
    for n, e in enumerate(entries):
        parts.append(f"#### `{e.name}`")
        if e.doc:
            parts.append(quote(e.doc))
        else:
            parts.append(
                f"`gimple.def` has no comment of its own for this code. It is described "
                f"together with `{entries[n - 1].name}` above it."
            )
        facts = [
            f"printable name `{e.arg(1)}`",
            f"layout `{e.arg(2)}`",
            f"operands: {operand_class(e.index, bounds)}",
        ]
        if e.name in classes:
            facts.append(f"cast to `{classes[e.name]}`")
        facts.append(f"`{GIMPLE_DEF}:{e.line}`")
        parts.append(sentence(facts))
    return "\n\n".join(parts)
