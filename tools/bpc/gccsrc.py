"""Reading GCC's own machine readable descriptions of itself.

GCC keeps the parts that have to stay consistent across fifty one targets and twelve front
ends in X macro files. `gimple.def` lists every GIMPLE statement code, `gsstruct.def` lists
every layout structure, `tree.def` lists every GENERIC node, `rtl.def` lists every RTX and
the format string that says how to walk it. They are the closest thing GCC has to a formal
specification of its own data, and they are all the same shape:

    /* A block comment explaining the entry.  */
    DEFGSCODE(GIMPLE_COND, "gimple_cond", GSS_WITH_OPS)

So one parser reads all of them. That is what makes generating a blueprint section
affordable, and it is why the blueprints can be regenerated for a new GCC release rather
than reread by hand.

There is also a header reader here, because a `.def` file gives the inventory and the
header gives the layout. `gimple.def` says `GIMPLE_COND` uses `GSS_WITH_OPS`, and only
`gimple.h` says what is in a `GSS_WITH_OPS`.

Nothing here is a C parser. It is a reader for a small set of files written in a house
style that has not changed in fifteen years, and it says so loudly when a file stops
matching that style rather than quietly returning less. Every function that finds nothing
where something was expected raises, because a blueprint section that silently loses half
its rows is worse than a build failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

COMMENT_OPEN = re.compile(r"/\*")
COMMENT_CLOSE = re.compile(r"\*/")
MACRO_START = re.compile(r"^(?P<macro>[A-Z][A-Z0-9_]*)\s*\(")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class SourceError(RuntimeError):
    """A GCC file did not look the way the reader expects."""


def read(path: Path) -> str:
    if not path.is_file():
        raise SourceError(
            f"{path} is not there. If the pinned tree is not checked out, run "
            f"`git submodule update --init --depth 1`."
        )
    return path.read_text(encoding="utf-8", errors="replace")


def clean_comment(raw: list[str]) -> str:
    """A block comment as plain text, with the comment furniture taken off.

    GCC indents continuation lines under the `/*`, so the second line of a comment starts
    three spaces in and the rest of the paragraph lines up with it. Taking off a fixed
    three spaces keeps the internal indentation of the pseudo syntax in these comments,
    which is most of what makes them readable.
    """
    body = "\n".join(raw)
    body = body.strip()
    if body.startswith("/*"):
        body = body[2:]
    if body.endswith("*/"):
        body = body[:-2]

    out = []
    for n, line in enumerate(body.split("\n")):
        line = line.expandtabs(8)
        out.append(line.lstrip() if n == 0 else line[3:] if line[:3] == "   " else line.lstrip())
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(line.rstrip() for line in out)


@dataclass
class Entry:
    """One X macro invocation, with whatever was written above it."""

    macro: str
    args: list[str]
    line: int
    doc: str = ""
    notes: list[str] = field(default_factory=list)
    index: int = 0

    @property
    def name(self) -> str:
        return self.args[0]

    def arg(self, n: int) -> str:
        """Argument n with any surrounding quotes taken off."""
        return self.args[n].strip().strip('"')


def split_args(text: str) -> list[str]:
    """Split a macro argument list on top level commas.

    Commas inside nested parentheses and inside string literals are not separators.
    `target.def` needs the second of those, because a hook's documentation is a string
    argument with ordinary English punctuation in it.
    """
    args, depth, current, quoted = [], 0, "", False
    for ch in text:
        if quoted:
            current += ch
            if ch == '"' and not current.endswith('\\"'):
                quoted = False
            continue
        if ch == '"':
            quoted = True
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        args.append(current.strip())
    return args


def parse_def(text: str, macro: str) -> list[Entry]:
    """Every invocation of one X macro in a `.def` file, in file order.

    Comments directly above an invocation become its documentation. Where several comments
    stack up, the last one is the documentation and the earlier ones are notes, which is
    how `gimple.def` writes the "do not rearrange these codes" warnings: as a separate
    comment above the comment for the next code.
    """
    lines = text.splitlines()
    entries: list[Entry] = []
    pending: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("/*"):
            block = [line]
            while "*/" not in block[-1]:
                i += 1
                if i >= len(lines):
                    raise SourceError("a block comment runs off the end of the file")
                block.append(lines[i])
            pending.append(clean_comment(block))
            i += 1
            continue

        m = MACRO_START.match(stripped)
        if m:
            start, invocation = i, stripped
            while _balance(invocation) > 0:
                i += 1
                if i >= len(lines):
                    raise SourceError(f"unclosed macro call at line {start + 1}")
                invocation += " " + lines[i].strip()
            if m.group("macro") == macro:
                inside = invocation[invocation.index("(") + 1 : invocation.rindex(")")]
                entries.append(
                    Entry(
                        macro=macro,
                        args=split_args(inside),
                        line=start + 1,
                        doc=pending[-1] if pending else "",
                        notes=pending[:-1],
                        index=len(entries),
                    )
                )
            pending = []
            i += 1
            continue

        if stripped:
            pending = []
        i += 1

    if not entries:
        raise SourceError(f"no {macro} entries found, which means the file changed shape")
    return entries


@dataclass
class Field:
    """One member of a C struct, with what the comment above it said."""

    name: str
    type: str
    gty: str
    doc: str
    word: str
    notes: list[str] = field(default_factory=list)
    members: list[Field] = field(default_factory=list)


@dataclass
class Struct:
    """One C struct declaration from a GCC header."""

    name: str
    base: str
    tag: str
    gty: str
    line: int
    doc: str
    fields: list[Field] = field(default_factory=list)
    code: str = ""
    inherited_words: str = ""


STRUCT_START = re.compile(r"^struct\s+GTY\s*\(\(")
STRUCT_NAME = re.compile(r"^\s*(?P<name>[a-z_][a-z0-9_]*)\s*(?::\s*public\s+(?P<base>[\w:]+))?\s*$")
TAG = re.compile(r'tag\s*\(\s*"(?P<tag>\w+)"\s*\)')
WORD = re.compile(r"^\[\s*(?P<word>WORD[^\]]*)\]\s*", re.IGNORECASE)
GTY_MARKER = re.compile(r"GTY\s*\(\((?P<body>.*?)\)\)\s*")
CODE_MEMBER = re.compile(r"static\s+const\s+enum\s+gimple_code\s+code_\s*=\s*(?P<code>\w+)")


def _balance(text: str) -> int:
    return text.count("(") - text.count(")")


def parse_structs(text: str) -> list[Struct]:
    """Every `struct GTY((...)) name : public base { ... }` in a header, in file order.

    This handles the shape GCC writes in `gimple.h` and `tree-core.h`: the GTY marker on
    one line, the struct name and base on the next, then fields with a block comment above
    each one. Anything else is skipped rather than guessed at.
    """
    lines = text.splitlines()
    structs: list[Struct] = []
    pending: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("/*"):
            block = [line]
            while "*/" not in block[-1]:
                i += 1
                block.append(lines[i])
            pending.append(clean_comment(block))
            i += 1
            continue

        if not STRUCT_START.match(stripped):
            if stripped and not stripped.startswith("//"):
                pending = []
            i += 1
            continue

        start = i
        header = stripped
        while _balance(header) > 0:
            i += 1
            header += " " + lines[i].strip()

        gty = header[header.index("((") + 2 : header.rindex("))")]
        rest = header[header.rindex("))") + 2 :].strip()
        while not rest.endswith("{") and "{" not in rest:
            i += 1
            if i >= len(lines):
                raise SourceError(f"struct at line {start + 1} has no body")
            rest = (rest + " " + lines[i].strip()).strip()
            if ";" in rest:  # a forward declaration, not a definition
                break
        if "{" not in rest:
            pending = []
            i += 1
            continue

        head = rest[: rest.index("{")].strip()
        m = STRUCT_NAME.match(head)
        if not m:
            pending = []
            i += 1
            continue

        tag = TAG.search(gty)
        struct = Struct(
            name=m.group("name"),
            base=m.group("base") or "",
            tag=tag.group("tag") if tag else "",
            gty=" ".join(gty.split()),
            line=start + 1,
            doc=pending[-1] if pending else "",
        )
        i = _parse_body(lines, i, struct)
        structs.append(struct)
        pending = []

    return structs


# GCC marks the words a struct gets from its base with a comment of its own, so that the
# word numbering on the fields below it starts where the base left off.
BASE_NOTE = re.compile(r"^\[\s*(?P<word>WORD[^\]]*)\]\s*:?\s*base class\.?\s*$", re.IGNORECASE)
UNION_START = re.compile(r"^(union|struct)\b.*\{\s*$")


def _parse_body(lines: list[str], i: int, struct: Struct) -> int:
    """Read a struct body into `struct`, and return the line after it."""
    pending: list[str] = []
    held: list[str] = []
    nested: list[Field] | None = None
    depth = lines[i].count("{") - lines[i].count("}")
    i += 1

    while depth > 0:
        if i >= len(lines):
            raise SourceError(f"the body of {struct.name} runs off the end of the file")
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("/*"):
            block = [line]
            while "*/" not in block[-1]:
                i += 1
                block.append(lines[i])
            comment = clean_comment(block)
            if (m := BASE_NOTE.match(comment)) is not None:
                struct.inherited_words = " ".join(m.group("word").split())
            else:
                pending.append(comment)
            i += 1
            continue

        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break

        # An anonymous union is one field of the struct that happens to hold alternatives,
        # so its members are collected under it rather than alongside the real fields.
        if nested is None and UNION_START.match(stripped):
            nested, held, pending = [], pending, []
            union_gty = _take_gty(stripped)[1]
        elif stripped.startswith("}") and stripped.endswith(";") and nested is not None:
            name = stripped.lstrip("}").rstrip(";").strip()
            struct.fields.append(_union_field(name, union_gty, nested, held))
            nested, held, pending = None, [], []
        elif (m := CODE_MEMBER.search(stripped)) is not None:
            struct.code = m.group("code")
            pending = []
        elif stripped.endswith(";") and not stripped.startswith(("static", "#", "typedef", "}")):
            if (f := _parse_field(stripped, pending)) is not None:
                (struct.fields if nested is None else nested).append(f)
            pending = []
        elif stripped:
            pending = []
        i += 1

    return i + 1


def _union_field(name: str, gty: str, members: list[Field], comments: list[str]) -> Field:
    """An anonymous union member, kept as one field with its alternatives underneath."""
    doc = comments[-1].strip() if comments else ""
    word = ""
    if (m := WORD.match(doc)) is not None:
        word = " ".join(m.group("word").split())
        doc = doc[m.end() :].strip()
    return Field(
        name=name,
        type="union",
        gty=gty,
        doc=doc,
        word=word,
        notes=[c.strip() for c in comments[:-1]],
        members=members,
    )


def _take_gty(text: str) -> tuple[str, str]:
    """Pull a `GTY((...))` marker out of a declaration, matching its parentheses properly."""
    at = text.find("GTY")
    if at < 0:
        return text, ""
    open_at = text.find("(", at)
    if open_at < 0:
        return text, ""
    depth, i = 0, open_at
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    if depth != 0:
        raise SourceError(f"unbalanced GTY marker in {text!r}")
    inner = text[open_at + 1 : i].strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    return (text[:at] + " " + text[i + 1 :]).strip(), " ".join(inner.split())


def _parse_field(decl: str, comments: list[str]) -> Field | None:
    """One field declaration, split into a type, a name, a GTY marker and a meaning."""
    body, gty = _take_gty(decl.rstrip(";").strip())

    # A bitfield is `unsigned int subcode : 16`, and the width belongs with the type.
    width = ""
    if ":" in body:
        body, width = body.rsplit(":", 1)
        body, width = body.strip(), width.strip()

    tokens = body.replace("*", " * ").split()
    if len(tokens) < 2:
        return None

    name = tokens[-1]
    array = ""
    if "[" in name:
        name, array = name[: name.index("[")], name[name.index("[") :]
    if not IDENT.fullmatch(name):
        return None

    type_ = " ".join(tokens[:-1]).replace(" * ", " *").strip()
    if array:
        type_ += array
    if width:
        type_ += f" : {width}"

    # The comment directly above a field is its meaning. Anything above that belongs to the
    # layout rather than to the field, and is kept as a note so nothing is thrown away.
    doc = comments[-1].strip() if comments else ""
    word = ""
    if (m := WORD.match(doc)) is not None:
        word = " ".join(m.group("word").split())
        doc = doc[m.end() :].strip()

    return Field(
        name=name,
        type=type_,
        gty=gty,
        doc=doc,
        word=word,
        notes=[c.strip() for c in comments[:-1]],
    )


IS_A_HELPER = re.compile(
    r"is_a_helper\s*<\s*(?P<const>const\s+)?(?P<cls>[\w:]+)\s*\*\s*>::test\s*\([^)]*\)\s*\{"
    r"(?P<body>[^}]*)\}",
    re.DOTALL,
)


def parse_is_a_helpers(text: str) -> dict[str, list[str]]:
    """Which statement codes each C++ statement class accepts.

    GCC's `is_a <gassign *> (stmt)` is spelled as a specialisation of `is_a_helper::test`
    whose body compares `gs->code` against one or more codes. Reading them gives the map
    from a code to the class you are allowed to cast it to, which is the single fact a
    reader most often wants and which is written down nowhere else.
    """
    out: dict[str, list[str]] = {}
    for m in IS_A_HELPER.finditer(text):
        known = out.setdefault(m.group("cls"), [])
        for c in re.findall(r"\bGIMPLE_[A-Z0-9_]+\b", m.group("body")):
            if c not in known:
                known.append(c)
    return out


RANGE_FN = re.compile(
    r"^\w[\w\s*]*\n(?P<name>\w+)\s*\(const gimple \*g\)\s*\n\{\s*\n\s*return (?P<body>[^;]*);",
    re.MULTILINE,
)


def parse_code_ranges(text: str) -> dict[str, tuple[str, str]]:
    """The `code >= X && code <= Y` predicates, as the pair of codes that bound them.

    Two of GIMPLE's most load bearing facts are ranges over the code enum rather than
    fields on a statement: whether a statement has operands at all, and whether it has
    memory operands. That is why `gimple.def` tells you not to rearrange the codes.
    """
    out: dict[str, tuple[str, str]] = {}
    for m in RANGE_FN.finditer(text):
        body = " ".join(m.group("body").split())
        lo = re.search(r">=\s*(GIMPLE_[A-Z0-9_]+)", body)
        hi = re.search(r"<=\s*(GIMPLE_[A-Z0-9_]+)", body)
        if lo and hi:
            out[m.group("name")] = (lo.group(1), hi.group(1))
    return out
