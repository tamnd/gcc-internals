"""Read a machine description far enough to answer "which pattern emitted that line".

A `.md` file is s-expressions with two things bolted on that a plain Lisp reader would choke
on. Output templates are written in braces and contain C, so a semicolon in there is not a
comment. And pattern names contain angle brackets, which are iterator placeholders expanded
at build time, so the name in the file is `*add<mode>3_aarch64` while the name `-dp` prints
is `*addsi3_aarch64`. Both are handled here.

What the reader picks out of `gcc/config/aarch64/aarch64.md`:

    (define_insn "*add<mode>3_aarch64"
      [(set (match_operand:GPI 0 "register_operand") ...)]
      ""
      {@ [ cons: =0 , %1 , 2   ; attrs: type , arch  ]
         [ rk       , rk , I   ; alu_imm     , *     ] add\\t%<w>0, %<w>1, %2
         [ rk       , rk , r   ; alu_sreg    , *     ] add\\t%<w>0, %<w>1, %<w>2
      }
    )

Each row inside the braces is one alternative, in the order `-dp` numbers them, and it says
what the operands have to look like for that row to be chosen and what to print when it is.
That table is why `add w1, w1, 1` and `add w0, w0, w1` come from the same pattern and get
different numbers after the slash.

Three template forms exist and the reader tells them apart, because the difference is the
whole point of the section of T09 that reads them.

A plain string, `"cmp\\t%<w>0, %<w>1"`, is printed with the operands substituted.

A brace table, the `{@ ... }` above, is a list of alternatives and one of those strings.

A brace block that does not start with `@` is C. It runs at output time and returns the
string, which is how `*do_return` decides between `ret`, `retaa` and `retab` depending on
whether pointer authentication is on.

This is not a machine description compiler. It does not check that a pattern matches an
insn, it does not evaluate conditions, and it does not know about `define_subst`. It reads
what is written, resolves the mode iterators far enough to match a name, and stops.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: The forms that carry a name a `-dp` annotation could print.
NAMED = ("define_insn", "define_insn_and_split", "define_expand", "define_peephole")

#: `<w>`, `<mode>`, `<GPI:w>`. The optional first half names the iterator explicitly, which
#: matters in a pattern that has more than one.
PLACEHOLDER = re.compile(
    r"<(?:(?P<iter>[A-Za-z_][A-Za-z_0-9]*):)?(?P<attr>[A-Za-z_][A-Za-z_0-9]*)>"
)

#: A row of a `{@ ... }` table: everything in brackets, then the template.
ROW = re.compile(r"^\s*\[(?P<cells>[^\]]*)\]\s*(?P<template>.*?)\s*$")

#: A row that says nothing but a C comment, which the reader drops.
ONLY_COMMENT = re.compile(r"^\s*/\*.*\*/\s*$")


def unescape(text: str) -> str:
    r"""Turn the source of an RTL string into the string it stands for.

    Only the two escapes that change what a template says are undone. `\t` is left alone
    because it means a tab to the assembler and printing an actual tab in a lesson would
    hide it.
    """
    return text.replace('\\"', '"').replace("\\\\", "\\")


def tokenize(text: str):
    """Walk the top level of a machine description, yielding one token at a time.

    Yields `(kind, body, start, end)` where kind is one of `open`, `close`, `bracket`,
    `string`, `block` or `atom`. Comments are dropped. Brackets and braces come back whole,
    because nothing above needs to see inside them one character at a time.
    """
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == ";":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
        elif c == "(":
            yield "open", "(", i, i + 1
            i += 1
        elif c == ")":
            yield "close", ")", i, i + 1
            i += 1
        elif c == '"':
            j = _end_of_string(text, i)
            yield "string", unescape(text[i + 1 : j - 1]), i, j
            i = j
        elif c == "[":
            j = _end_of_bracket(text, i)
            yield "bracket", text[i:j], i, j
            i = j
        elif c == "{":
            j = _end_of_block(text, i)
            yield "block", text[i:j], i, j
            i = j
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()[]{}";':
                j += 1
            yield "atom", text[i:j], i, max(j, i + 1)
            i = max(j, i + 1)


def _end_of_string(text: str, i: int) -> int:
    j = i + 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == '"':
            return j + 1
        j += 1
    return len(text)


def _end_of_bracket(text: str, i: int) -> int:
    """Past the matching `]`, skipping over strings and nested brackets and braces."""
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == '"':
            j = _end_of_string(text, j)
            continue
        if c == "{":
            j = _end_of_block(text, j)
            continue
        if c == ";":
            k = text.find("\n", j)
            j = len(text) if k < 0 else k + 1
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(text)


def _end_of_block(text: str, i: int) -> int:
    """Past the matching `}`. Inside a block the rules are C's, not the md reader's."""
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c in "\"'":
            quote, j = c, j + 1
            while j < len(text) and text[j] != quote:
                j += 2 if text[j] == "\\" else 1
            j += 1
            continue
        if text.startswith("/*", j):
            k = text.find("*/", j + 2)
            j = len(text) if k < 0 else k + 2
            continue
        if text.startswith("//", j):
            k = text.find("\n", j)
            j = len(text) if k < 0 else k + 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(text)


@dataclass(frozen=True)
class Alternative:
    """One row of a `{@ ... }` table, which is one entry in the `/N` an annotation prints."""

    index: int
    cons: tuple[str, ...] = ()
    attrs: tuple[str, ...] = ()
    template: str = ""
    inherited: bool = False

    @property
    def splits(self) -> bool:
        """`#` means this alternative does not print anything, it gets split into insns."""
        return self.template.strip() == "#"

    @property
    def computed(self) -> bool:
        """`<<` means the row hands off to C, same as a whole pattern written in braces."""
        return self.template.lstrip().startswith("<<")

    def __str__(self) -> str:
        return f"{self.index}: [{', '.join(self.cons)}] {self.template}"


@dataclass(frozen=True)
class Pattern:
    """One named form out of a machine description."""

    kind: str
    name: str
    file: str = ""
    line: int = 0
    span: int = 0
    text: str = ""
    condition: str = ""
    template: str = ""
    form: str = "none"
    cons_heads: tuple[str, ...] = ()
    attr_heads: tuple[str, ...] = ()
    alternatives: tuple[Alternative, ...] = ()
    iterators: tuple[str, ...] = ()

    @property
    def generic(self) -> bool:
        """Written with iterator placeholders, so one form defines several patterns."""
        return "<" in self.name

    @property
    def hidden(self) -> bool:
        """A leading star means no `gen_` function, so nothing can ask for it by name."""
        return self.name.startswith("*")

    @property
    def citation(self) -> str:
        return f"{self.file}:{self.line}"

    def __str__(self) -> str:
        n = len(self.alternatives)
        how = {"string": "one template", "code": "C that returns a template"}.get(
            self.form, f"{n} alternative" + ("" if n == 1 else "s")
        )
        return f"{self.name} ({self.kind}, {how}) at {self.citation}"


@dataclass(frozen=True)
class Match:
    """A pattern, and the modes the name that was asked for pins its iterators to."""

    pattern: Pattern
    name: str
    modes: tuple[tuple[str, str], ...] = ()

    @property
    def mode(self) -> str:
        """The mode, for the ordinary case of a pattern with one iterator in it."""
        return self.modes[0][1] if len(self.modes) == 1 else ""

    def resolve(self, text: str, machine: Machine | None = None) -> str:
        """Fill in the iterator placeholders for the modes this match pinned down.

        A placeholder the reader cannot resolve is left exactly as it was written. That is
        better than a guess, because the reader is showing a lesson the real source and a
        wrong substitution would be indistinguishable from the truth.
        """
        chosen = dict(self.modes)
        if not chosen:
            return text
        table = machine.attrs if machine else {}

        def one(found: re.Match) -> str:
            named = found.group("iter")
            if named:
                mode = chosen.get(named, "")
            elif len(chosen) == 1:
                mode = next(iter(chosen.values()))
            else:
                mode = ""
            if not mode:
                return found.group(0)
            attr = found.group("attr")
            if attr == "mode":
                return mode.lower()
            if attr == "MODE":
                return mode.upper()
            return table.get(attr, {}).get(mode, found.group(0))

        return PLACEHOLDER.sub(one, text)

    def alternative(self, index: int | None) -> Alternative | None:
        if index is None:
            return self.pattern.alternatives[0] if self.pattern.alternatives else None
        for a in self.pattern.alternatives:
            if a.index == index:
                return a
        return None

    def __str__(self) -> str:
        where = f" as {self.pattern.name}" if self.pattern.generic else ""
        return f"{self.name}{where} at {self.pattern.citation}"

    @property
    def modes_said(self) -> str:
        return ", ".join(f"{it} is {mode}" for it, mode in self.modes)


@dataclass
class Machine:
    """Everything one pass over a machine description found."""

    patterns: tuple[Pattern, ...] = ()
    iterators: dict[str, tuple[str, ...]] = field(default_factory=dict)
    attrs: dict[str, dict[str, str]] = field(default_factory=dict)
    files: tuple[str, ...] = ()

    def __iter__(self):
        return iter(self.patterns)

    def __len__(self) -> int:
        return len(self.patterns)

    def get(self, name: str) -> Pattern | None:
        for p in self.patterns:
            if p.name == name:
                return p
        return None

    def find(self, name: str) -> Match | None:
        """The pattern that produced this name, whether or not an iterator was involved."""
        exact = self.get(name)
        if exact is not None:
            return Match(exact, name)
        for p in self.patterns:
            if not p.generic:
                continue
            modes = self._modes_that_make(p, name)
            if modes:
                return Match(p, name, modes)
        return None

    def _modes_that_make(self, pattern: Pattern, name: str) -> tuple[tuple[str, str], ...]:
        """Which members of the pattern's iterators turn its name into this one, if any.

        Only `<mode>` holes are resolved, because that is the placeholder GCC uses in a
        pattern name and it is the one whose possible values the reader knows. A name built
        out of a code attribute, such as `<optab>si3`, needs the code iterators to be read
        as well and this returns nothing for it rather than guessing.

        The regular expression is built out of the values themselves rather than a wildcard,
        because `*zero_extend<SHORT:mode><GPI:mode>2_aarch64` has two holes with nothing
        between them and only the real mode names say where one ends and the next starts.
        """
        holes = list(PLACEHOLDER.finditer(pattern.name))
        options: list[list[tuple[str, str, str]]] = []
        for hole in holes:
            if hole.group("attr") not in ("mode", "MODE"):
                return ()
            lower = hole.group("attr") == "mode"
            named = hole.group("iter")
            here = [
                (it, mode, mode.lower() if lower else mode)
                for it in ([named] if named else list(pattern.iterators))
                for mode in self.iterators.get(it, ())
            ]
            if not here:
                return ()
            options.append(here)

        parts, last = [], 0
        for hole, here in zip(holes, options, strict=True):
            spellings = sorted({text for _, _, text in here}, key=len, reverse=True)
            parts.append(re.escape(pattern.name[last : hole.start()]))
            parts.append("(" + "|".join(re.escape(s) for s in spellings) + ")")
            last = hole.end()
        parts.append(re.escape(pattern.name[last:]))
        found = re.fullmatch("".join(parts), name)
        if found is None:
            return ()

        chosen: list[tuple[str, str]] = []
        for here, text in zip(options, found.groups(), strict=True):
            for it, mode, spelling in here:
                if spelling == text and (it, mode) not in chosen:
                    chosen.append((it, mode))
                    break
        return tuple(chosen)

    def __str__(self) -> str:
        named = len([p for p in self.patterns if p.kind.startswith("define_insn")])
        return (
            f"{len(self.files)} file(s), {len(self.patterns)} named form(s), "
            f"{named} of them insn patterns, {len(self.iterators)} mode iterator(s)"
        )


def _table(block: str) -> tuple[tuple[str, ...], tuple[str, ...], list[Alternative]]:
    """Take a `{@ ... }` block apart into a header and one row per alternative."""
    body = block.strip()
    body = body[2:] if body.startswith("{@") else body.lstrip("{")
    body = body.rstrip("}")
    cons_heads: tuple[str, ...] = ()
    attr_heads: tuple[str, ...] = ()
    rows: list[Alternative] = []
    previous = ""
    for raw in body.splitlines():
        if not raw.strip() or ONLY_COMMENT.match(raw):
            continue
        found = ROW.match(raw)
        if not found:
            continue
        # The header labels its groups, `cons: ... ; attrs: ...`, and the rows below it do
        # not, so the reader learns the shape from the header and then goes by position.
        groups = [g.strip() for g in found.group("cells").split(";")]
        labelled = [g.partition(":") for g in groups]
        cells = [x.strip() for x in (labelled[0][2] if labelled[0][1] else groups[0]).split(",")]
        attrs = [
            x.strip()
            for group, (label, sep, rest) in zip(groups[1:], labelled[1:], strict=True)
            for x in (rest if sep else group).split(",")
        ]
        if not cons_heads and not rows and "cons:" in found.group("cells"):
            cons_heads, attr_heads = tuple(cells), tuple(attrs)
            continue
        template = found.group("template")
        inherited = template.strip() == "^"
        rows.append(
            Alternative(
                index=len(rows),
                cons=tuple(cells),
                attrs=tuple(attrs),
                template=previous if inherited else template,
                inherited=inherited,
            )
        )
        if not inherited:
            previous = template
    return cons_heads, attr_heads, rows


#: An operand in the RTL half of a pattern written the older way, with its constraints on
#: it rather than in a table underneath. `(match_operand:P 0 "register_operand" "=r")`.
OPERAND = re.compile(
    r"\(match_(?P<what>operand|scratch)[^\s)]*\s+(?P<num>\d+)\s+"
    r'"(?P<first>[^"]*)"(?:\s*,?\s*"(?P<second>[^"]*)")?'
)


def _inline(rtl: str, template: str) -> tuple[tuple[str, ...], list[Alternative]]:
    """Recover the alternatives of a pattern that keeps its constraints in the operands.

    Most of a machine description is still written this way. One operand carries one comma
    separated list of constraints, one entry per alternative, and the single output template
    covers all of them. The reader turns that back into the same row per alternative shape
    the newer table syntax has, so that everything above can ask one question.
    """
    cells: dict[int, list[str]] = {}
    for found in OPERAND.finditer(rtl):
        raw = found.group("first") if found.group("what") == "scratch" else found.group("second")
        cells[int(found.group("num"))] = [x.strip() for x in (raw or "").split(",")]
    if not cells:
        return (), []
    slots = sorted(cells)
    width = max(len(cells[n]) for n in slots)
    rows = [
        Alternative(
            index=i,
            cons=tuple(cells[n][i] if i < len(cells[n]) else "" for n in slots),
            template=template,
        )
        for i in range(width)
    ]
    return tuple(str(n) for n in slots), rows


def _iterator_list(bracket: str) -> tuple[str, ...]:
    """The mode names out of `[SI DI]` or `[(SI "ptr_mode == SImode") (DI "...")]`.

    A member can carry a condition and the condition is C, which can have mode names in it.
    `P` is the one that catches a reader out: both of its members are conditional and both
    conditions mention a mode, so taking every capitalised word in the brackets gives four
    members where there are two.
    """
    inner = bracket.strip()[1:-1]
    out: list[str] = []
    i = 0
    while i < len(inner):
        c = inner[i]
        if c == "(":
            depth, j = 0, i
            while j < len(inner):
                if inner[j] == "(":
                    depth += 1
                elif inner[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            head = re.match(r"\s*([A-Za-z_][A-Za-z_0-9]*)", inner[i + 1 : j])
            if head:
                out.append(head.group(1))
            i = j + 1
            continue
        word = re.match(r"[A-Za-z_][A-Za-z_0-9]*", inner[i:])
        if word:
            out.append(word.group(0))
            i += word.end()
            continue
        i += 1
    return tuple(out)


def _attr_table(bracket: str) -> dict[str, str]:
    """The mode to value map out of `[(QI "w") (SI "w") (DI "x")]`."""
    return dict(re.findall(r'\(\s*([A-Z][A-Za-z_0-9]*)\s+"([^"]*)"\s*\)', bracket))


def parse(text: str, path: str = "") -> Machine:
    """Read one machine description file. Includes are not followed here, see `load`."""
    tokens = list(tokenize(text))
    starts = [0] + [m.start() + 1 for m in re.finditer("\n", text)]
    patterns: list[Pattern] = []
    iterators: dict[str, tuple[str, ...]] = {}
    attrs: dict[str, dict[str, str]] = {}

    def line_of(offset: int) -> int:
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    depth = 0
    head: list[tuple] = []
    start = 0
    for token in tokens:
        kind, body, at, end = token
        if kind == "open":
            if depth == 0:
                head, start = [], at
            depth += 1
            continue
        if kind == "close":
            depth -= 1
            if depth == 0 and head:
                _absorb(
                    head,
                    text[start:end],
                    path,
                    line_of(start),
                    line_of(end) - line_of(start) + 1,
                    patterns,
                    iterators,
                    attrs,
                )
            continue
        if depth == 1:
            head.append(token)

    return Machine(
        patterns=tuple(patterns),
        iterators=iterators,
        attrs=attrs,
        files=(path,) if path else (),
    )


def _absorb(head, text, path, line, span, patterns, iterators, attrs) -> None:
    """Turn one top level form into whatever the reader keeps of it."""
    if head[0][0] != "atom":
        return
    kind = head[0][1]
    if kind == "define_mode_iterator" and len(head) >= 3:
        iterators[head[1][1]] = _iterator_list(head[2][1])
        return
    if kind == "define_mode_attr" and len(head) >= 3:
        attrs[head[1][1]] = _attr_table(head[2][1])
        return
    if kind not in NAMED or len(head) < 2 or head[1][0] != "string":
        return

    name = head[1][1]
    condition = ""
    template = ""
    form = "none"
    cons_heads: tuple[str, ...] = ()
    attr_heads: tuple[str, ...] = ()
    rows: list[Alternative] = []
    rtl = ""
    told = False
    for token_kind, body, _, _ in head[2:]:
        if form != "none":
            # Past the output template, and what follows it is the attribute vector or, in a
            # define_insn_and_split, a whole second pattern. Neither is read here.
            break
        if token_kind == "bracket" and not rtl:
            rtl = body
        elif token_kind == "string" and not told:
            # The condition comes first and is very often the empty string, so the reader
            # has to count strings rather than wait for one with something in it.
            condition, told = body, True
        elif token_kind == "string":
            template, form = body, "string"
        elif token_kind == "block":
            if body.lstrip("{").lstrip().startswith("@"):
                cons_heads, attr_heads, rows = _table(body)
                form = "table"
            else:
                template, form = body, "code"
    if form == "string":
        cons_heads, rows = _inline(rtl, template)

    known = set(iterators)
    used = tuple(sorted(w for w in known if re.search(rf"\b{re.escape(w)}\b", text)))
    patterns.append(
        Pattern(
            kind=kind,
            name=name,
            file=path,
            line=line,
            span=span,
            text=text,
            condition=condition,
            template=template,
            form=form,
            cons_heads=cons_heads,
            attr_heads=attr_heads,
            alternatives=tuple(rows),
            iterators=used,
        )
    )


def load(root: Path | str, relative: str, follow: bool = True) -> Machine:
    """Read a machine description and, unless told not to, everything it includes.

    Iterators live in their own file on every target that has many of them, so a reader that
    stopped at the first file would find `*add<mode>3_aarch64` and have no idea what GPI is.
    """
    root = Path(root)
    queue = [relative]
    done: list[str] = []
    machine = Machine()
    patterns: list[Pattern] = []
    while queue:
        rel = queue.pop(0)
        if rel in done:
            continue
        path = root / rel
        if not path.exists():
            continue
        done.append(rel)
        text = path.read_text(encoding="utf-8", errors="replace")
        here = parse(text, rel)
        # Later files see the iterators the earlier ones defined, which is what the real
        # reader does too, because an include is textual.
        machine.iterators.update(here.iterators)
        machine.attrs.update(here.attrs)
        patterns.extend(here.patterns)
        if follow:
            base = Path(rel).parent
            for found in re.finditer(r'^\(include\s+"([^"]+)"\)', text, re.M):
                queue.append(str((base / found.group(1)).as_posix()))
    machine.patterns = tuple(patterns)
    machine.files = tuple(done)
    # The iterators of a pattern can only be worked out once every file has been read, and
    # the first pass over aarch64.md happens before iterators.md is open.
    machine.patterns = tuple(
        p
        if p.iterators or not p.generic
        else Pattern(
            **{
                **p.__dict__,
                "iterators": tuple(
                    sorted(
                        w for w in machine.iterators if re.search(rf"\b{re.escape(w)}\b", p.text)
                    )
                ),
            }
        )
        for p in machine.patterns
    )
    return machine


def extract(machine: Machine, names: list[str], tag: str) -> dict:
    """Everything a lesson needs about a handful of patterns, ready to be committed.

    A notebook running in Colab has no GCC tree, so it cannot read a machine description. It
    reads this instead, and the provenance travels with it so a reader can go and check.
    """
    out = {"tag": tag, "files": list(machine.files), "patterns": {}}
    for name in names:
        found = machine.find(name)
        if found is None:
            continue
        p = found.pattern
        out["patterns"][name] = {
            "kind": p.kind,
            "written": p.name,
            "file": p.file,
            "line": p.line,
            "citation": f"{p.citation}@{tag}",
            "span": p.span,
            "modes": [list(pair) for pair in found.modes],
            "condition": p.condition,
            "form": p.form,
            "template": found.resolve(p.template, machine),
            "cons_heads": list(p.cons_heads),
            "attr_heads": list(p.attr_heads),
            "iterators": list(p.iterators),
            "text": p.text,
            "alternatives": [
                {
                    "index": a.index,
                    "cons": list(a.cons),
                    "attrs": list(a.attrs),
                    "template": found.resolve(a.template, machine),
                    "written": a.template,
                    "inherited": a.inherited,
                }
                for a in p.alternatives
            ],
        }
    return out


#: Where `record.py` puts what it extracted, so that a notebook can find it.
EXTRACTS = Path(__file__).resolve().parent.parent / "corpora" / "mdesc"


def load_extract(name: str, root: Path | str | None = None) -> dict:
    """Read a committed extract. This is the call a notebook makes."""
    path = Path(root or EXTRACTS) / f"{name}.json"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in path.parent.glob("*.json"))) or "none"
        raise FileNotFoundError(f"no machine description extract {name!r}. Have: {available}")
    return json.loads(path.read_text(encoding="utf-8"))
