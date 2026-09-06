"""The little language the driver is written in.

`gcc` decides which programs to run, and the decision is not written in C. It is written in
a string substitution language, and the C in `gcc/gcc.cc` is an interpreter for it. `gcc
-dumpspecs` prints the program:

    from gxray import specs
    table = specs.load().table("local")

    len(table)                        # 56 blocks on this build
    table["invoke_as"].value          # the string that appends the assembler
    specs.explain(table["invoke_as"].value)   # the same string, one token per line

This module is a reader for that language, not a second implementation of it. It says what
each `%` form is and what it is for; it never substitutes anything, because substituting
would need the command line, the target, the filesystem and a temporary directory, and a
lesson that faked those would be teaching a fiction.

The two things it does that a reader cannot easily do by eye:

`tokenize` splits a spec into its forms, which matters because the language has no
whitespace rules and a 700 character spec is one line. Every form GCC's `do_spec_1`
handles is in `FORMS`, and a form that is not gets the kind `unknown`, so a spec that grew
a construct this module has not heard of says so instead of quietly showing it as text.
That is the same bargain `gimple.parse` makes with `unparsed`.

`Table.reach` follows `%(name)` and the ten letters that run a named spec, which turns 56
unrelated strings into the call graph they actually are. The roots of that graph are not in
the table: they are the compiler table in `gcc/gcc.cc` and `*link_command`, which
`-dumpspecs` prints from a variable of its own at `gcc/gcc.cc:4242@releases/gcc-16.2.0`
rather than from the spec list.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

#: Where a recording of one compiler's specs lives.
CORPUS = Path(__file__).resolve().parent.parent / "corpora" / "specs"


class SpecError(Exception):
    """Something asked of a spec table that it cannot answer."""


@dataclass(frozen=True)
class Form:
    """One `%` form of the spec language.

    `family` is the grouping BP-DRIVER uses, because five families is a thing a person can
    hold and forty five letters is not. `operand` is how many characters after the letter
    belong to the form, which is the part a tokenizer has to get right and a reader usually
    gets wrong.
    """

    family: str
    operand: str
    about: str


#: How far past the letter the form reaches.
#:
#: `none` is the letter alone. `suffix` swallows `[.0-9A-Za-z]*`, optionally followed by a
#: literal `%O`, which is why `%|.s` is one form and not a form plus the text `.s`. `switch`
#: runs to the next space or tab, `line` to the next newline, and `brace` means a balanced
#: `{...}` follows. GCC's own reading of each of these is in `do_spec_1` at
#: `gcc/gcc.cc:6163@releases/gcc-16.2.0`, and the cases there are what this table copies.
OPERANDS = ("none", "suffix", "switch", "line", "brace")

#: Every form `do_spec_1` handles, minus whitespace, which ends an argument rather than
#: substituting anything, and minus the three compound forms: `%{`, which is
#: `handle_braces`, `%:`, which is `handle_spec_function`, and `%(name)`, which runs a named
#: spec. The tokenizer reads those three itself, and a test compares this table against the
#: case labels of `do_spec_1` so a GCC that grows a form fails the build.
#:
#: The `about` strings are one line each because they are printed next to the form in a
#: notebook, under a spec the reader is looking at. Anything longer would push the spec off
#: the screen, which defeats the purpose.
FORMS: dict[str, Form] = {
    "%": Form("text", "none", "a literal percent sign"),
    '"': Form("text", "none", "an empty argument, and the end of the one before it"),
    "i": Form("text", "none", "the input file"),
    "b": Form("text", "none", "the input file's base name, without the suffix"),
    "B": Form("text", "none", "the input file's base name, suffix included"),
    "o": Form("text", "none", "every output file so far, which is what the linker is given"),
    "O": Form("text", "none", "the object file suffix for this target"),
    "I": Form("text", "none", "the include options the driver worked out for itself"),
    "s": Form("text", "none", "search for the argument as a library or startup file"),
    "T": Form("text", "none", "search for the argument as a linker script"),
    "D": Form("text", "none", "a -L for every directory in startfile_prefixes"),
    "P": Form("text", "none", "a runpath option for every directory in startfile_prefixes"),
    "M": Form("text", "none", "the multilib os directory"),
    "R": Form("text", "none", "the sysroot, with its suffix"),
    "X": Form("text", "none", "the linker options that %x collected"),
    "Y": Form("text", "none", "the assembler options from the command line"),
    "Z": Form("text", "none", "the preprocessor options from the command line"),
    "*": Form("text", "none", "the variable part of the switch this brace matched"),
    "g": Form("text", "suffix", "a temporary file, one per compilation"),
    "u": Form("text", "suffix", "a temporary file, a new one every time"),
    "U": Form("text", "suffix", "the file the last %u made, or a new one"),
    "j": Form("text", "suffix", "the bit bucket, or a temporary if there is not one"),
    "|": Form("text", "suffix", "a temporary file, or a bare - when -pipe is in effect"),
    "m": Form("text", "suffix", "a temporary file, or nothing at all when -pipe is in effect"),
    ".": Form("text", "suffix", "the suffix the next %* should use instead of its own"),
    "a": Form("spec", "none", "run the asm spec"),
    "A": Form("spec", "none", "run the asm_final spec"),
    "C": Form("spec", "none", "run the cpp spec"),
    "E": Form("spec", "none", "run the endfile spec"),
    "G": Form("spec", "none", "run the libgcc spec"),
    "l": Form("spec", "none", "run the link spec"),
    "L": Form("spec", "none", "run the lib spec"),
    "S": Form("spec", "none", "run the startfile spec"),
    "1": Form("spec", "none", "run the cc1 spec"),
    "2": Form("spec", "none", "run the cc1plus spec"),
    "d": Form("mark", "none", "delete the file this argument names, if the compilation works"),
    "w": Form("mark", "none", "this argument is the output file, and is what %o will find"),
    "V": Form("mark", "none", "this compilation produces no output file"),
    "W": Form("mark", "brace", "like %{...}, but delete the file it names if the run fails"),
    "@": Form("mark", "brace", "like %{...}, but put the result in a file and pass @that"),
    "x": Form("mark", "brace", "collect a linker option for %X to substitute later"),
    "<": Form("switch", "switch", "drop this switch from here on, and from what is passed on"),
    ">": Form("switch", "switch", "drop this switch from what is passed on, but keep it here"),
    "e": Form("message", "line", "print the rest of the line as an error and abandon this file"),
    "n": Form("message", "line", "print the rest of the line as a notice"),
}

#: The ten letters that are a call to a named spec, and the name each one calls. Without
#: this the call graph has holes in it: `%(lib)` and `%L` are the same edge written two ways
#: and only one of them looks like a call.
LETTER_SPECS = {
    "a": "asm",
    "A": "asm_final",
    "C": "cpp",
    "E": "endfile",
    "G": "libgcc",
    "l": "link",
    "L": "lib",
    "S": "startfile",
    "1": "cc1",
    "2": "cc1plus",
}

#: What each family is, in the words BP-DRIVER section 3.3 uses.
FAMILIES = {
    "literal": "text, passed through as it stands",
    "text": "substitutes text",
    "spec": "runs another spec",
    "mark": "changes how an argument is treated",
    "brace": "a conditional",
    "call": "calls a C function",
    "switch": "removes a switch from the command line",
    "message": "says something and stops",
    "unknown": "not a form this reader knows",
}

_SUFFIX_CHARS = ".0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class Token:
    """One piece of a spec: either a run of plain text or a single `%` form."""

    kind: str
    text: str

    #: The character after the `%`, for a form that has one. `{` for a brace and `:` for a
    #: function call. Empty for plain text and for `%(name)`.
    letter: str = ""

    #: The spec a `spec` token runs, or the function a `call` token calls. `%a` and
    #: `%(asm)` both come back with the name `asm`, because they are the same edge in the
    #: call graph and only one of them looks like one.
    name: str = ""

    #: For a brace, the part before the colon, which is the predicate, and the part after
    #: it, which is what gets substituted. `%{S}` has a head and no body, and that is the
    #: difference between passing the switch on and substituting something else.
    head: str = ""
    body: str = ""

    #: Every clause of an n-way brace, as predicate and text. `%{S:X;T:Y;:D}` has three,
    #: and the last one has an empty predicate, which is the default. One clause for an
    #: ordinary brace, and `head` and `body` are that clause.
    clauses: tuple[tuple[str, str], ...] = ()

    @property
    def about(self) -> str:
        """One line saying what this token does, for printing beside it."""
        if self.kind == "literal":
            return "text" if self.text.strip() else "whitespace, which ends an argument"
        if self.kind == "call":
            return f"call the spec function {self.name}"
        if self.kind == "brace":
            if self.body or len(self.clauses) > 1:
                return f"{predicate(self.head)}, substitute"
            return passed_on(self.head)
        form = FORMS.get(self.letter)
        if form is not None:
            return form.about
        if self.kind == "spec":
            return f"run the {self.name} spec"
        return FAMILIES.get(self.kind, "")

    def __str__(self) -> str:
        return self.text


def predicate(head: str) -> str:
    """A brace's condition in words.

    The forms are in the language reference at `gcc/gcc.cc:473@releases/gcc-16.2.0` and
    there are not many of them: a switch name, the same negated, several alternatives
    separated by bars, a leading dot for the input file's suffix, a leading comma for the
    spec in use, and a function call that counts as true when it returns anything.
    """
    asked = " ".join(head.split())
    if not asked:
        return "otherwise"
    if asked.startswith("%:"):
        return f"if {asked} returns anything"
    negated = asked.startswith("!")
    body = asked[1:] if negated else asked
    lead = "unless" if negated else "if"
    if body.startswith("."):
        return f"{lead} the input file's suffix is {body}"
    if body.startswith(","):
        return f"{lead} the spec being used is {body[1:]}"
    if "|" in body:
        names = ", ".join("-" + part.strip().lstrip("!") for part in body.split("|"))
        return f"{lead} any of {names} was given"
    return f"{lead} -{body} was given"


def passed_on(head: str) -> str:
    """What a brace with no body does, which is hand the switch straight through."""
    asked = " ".join(head.split())
    if asked.endswith("*") or "&" in asked:
        return f"pass on every switch matching {asked}"
    return f"pass -{asked} on, if it was given"


def _balanced(text: str, start: int, opener: str, closer: str) -> int:
    """Index just past the `closer` that matches the `opener` at `start`.

    Backslash escapes one character, because the language uses that to match a switch whose
    name contains a colon, and a spec that says `%{std=iso9899\\:1999:X}` would otherwise be
    split in the wrong place. Returns the length of the string if nothing closes it.
    """
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _split_brace(inner: str) -> tuple[str, str]:
    """A brace's predicate and its body, split at the colon that separates them.

    Not the first colon. `%{%:debug-level-gt(0):-dD}` has a colon in the predicate, because
    the predicate is a function call, and a naive split reads that spec backwards. Nested
    braces are skipped for the same reason.
    """
    i = 0
    while i < len(inner):
        c = inner[i]
        if c == "\\":
            i += 2
            continue
        if c == "%" and i + 1 < len(inner) and inner[i + 1] == ":":
            i += 2
            while i < len(inner) and inner[i] != "(":
                i += 1
            i = _balanced(inner, i, "(", ")") if i < len(inner) else i
            continue
        if c == "%" and i + 1 < len(inner) and inner[i + 1] == "{":
            i = _balanced(inner, i + 1, "{", "}")
            continue
        if c == ":":
            return inner[:i], inner[i + 1 :]
        i += 1
    return inner, ""


def _clauses(inner: str) -> tuple[tuple[str, str], ...]:
    """A brace's clauses, split at the semicolons that separate them.

    `%{S:X;T:Y;:D}` is an n-way choice and reading it as one condition with a body full of
    semicolons gets it backwards. Only semicolons outside a nested brace or a function
    call's parentheses count.
    """
    pieces: list[str] = []
    start = 0
    i = 0
    while i < len(inner):
        c = inner[i]
        if c == "\\":
            i += 2
            continue
        if c == "%" and inner[i + 1 : i + 2] == "{":
            i = _balanced(inner, i + 1, "{", "}")
            continue
        if c == "(":
            i = _balanced(inner, i, "(", ")")
            continue
        if c == ";":
            pieces.append(inner[start:i])
            start = i + 1
        i += 1
    pieces.append(inner[start:])
    return tuple(_split_brace(piece) for piece in pieces)


def _suffix_end(text: str, start: int) -> int:
    """Where the suffix after `%g` and its four relatives stops.

    `[.0-9A-Za-z]*`, then an optional literal `%O`, which is exactly the loop in the
    `create_temp_file` case of `do_spec_1`. This is why `%|.s` is one token: the `.s` is
    part of the form and naming the temporary file, not text going on the command line.
    """
    i = start
    while i < len(text) and text[i] in _SUFFIX_CHARS:
        i += 1
    if text[i : i + 2] == "%O":
        i += 2
    return i


def tokenize(value: str) -> list[Token]:
    """Split a spec string into plain text and `%` forms.

    Reading only. Nothing is substituted, no switch is consulted, and a brace's body comes
    back as a string rather than as tokens, because a body is a spec and the caller can
    tokenize it again if it wants to go down a level.
    """
    out: list[Token] = []
    plain: list[str] = []
    i, n = 0, len(value)

    def flush() -> None:
        if plain:
            out.append(Token("literal", "".join(plain)))
            plain.clear()

    while i < n:
        if value[i] == "\\" and i + 1 < n:
            # A backslash makes the next character ordinary, which is how a spec puts a
            # literal percent sign or brace on a command line. `do_spec_1` falls straight
            # through from `case '\\'` into `default`, and so does this.
            plain.append(value[i + 1])
            i += 2
            continue
        if value[i] != "%":
            plain.append(value[i])
            i += 1
            continue
        flush()
        if i + 1 >= n:
            out.append(Token("unknown", "%"))
            break
        c = value[i + 1]

        if c == "(":
            end = value.find(")", i + 2)
            if end < 0:
                out.append(Token("unknown", value[i:]))
                break
            out.append(Token("spec", value[i : end + 1], name=value[i + 2 : end]))
            i = end + 1
            continue

        if c == ":":
            open_paren = value.find("(", i + 2)
            if open_paren < 0:
                out.append(Token("unknown", value[i:]))
                break
            end = _balanced(value, open_paren, "(", ")")
            out.append(
                Token(
                    "call",
                    value[i:end],
                    letter=":",
                    name=value[i + 2 : open_paren],
                    body=value[open_paren + 1 : end - 1],
                )
            )
            i = end
            continue

        if c == "{":
            end = _balanced(value, i + 1, "{", "}")
            clauses = _clauses(value[i + 2 : end - 1])
            out.append(
                Token(
                    "brace",
                    value[i:end],
                    letter="{",
                    head=clauses[0][0],
                    body=clauses[0][1],
                    clauses=clauses,
                )
            )
            i = end
            continue

        form = FORMS.get(c)
        if form is None:
            out.append(Token("unknown", value[i : i + 2], letter=c))
            i += 2
            continue

        if form.operand == "brace":
            if value[i + 2 : i + 3] != "{":
                out.append(Token("unknown", value[i : i + 2], letter=c))
                i += 2
                continue
            end = _balanced(value, i + 2, "{", "}")
            clauses = _clauses(value[i + 3 : end - 1])
            out.append(
                Token(
                    form.family,
                    value[i:end],
                    letter=c,
                    head=clauses[0][0],
                    body=clauses[0][1],
                    clauses=clauses,
                )
            )
            i = end
            continue

        if form.operand == "suffix":
            end = _suffix_end(value, i + 2)
        elif form.operand == "switch":
            end = i + 2
            while end < len(value) and value[end] not in " \t":
                end += 1
        elif form.operand == "line":
            end = value.find("\n", i + 2)
            end = len(value) if end < 0 else end
        else:
            end = i + 2
        out.append(Token(form.family, value[i:end], letter=c, name=LETTER_SPECS.get(c, "")))
        i = end

    flush()
    return out


def walk(value: str):
    """Every token in a spec, nested ones included, in the order they are written.

    A brace's predicate and its body are both specs, and most of what a spec does is
    inside one, so a walk that stopped at the top level would report `*cc1_options` as
    thirty braces and nothing else.
    """
    for token in tokenize(value):
        yield token
        for head, body in token.clauses or ((token.head, token.body),):
            if head:
                yield from walk(head)
            if body:
                yield from walk(body)


def _walk(value: str, kind: str) -> list[str]:
    """The names of every nested token of one kind, in order, without repeats."""
    found: list[str] = []
    for token in walk(value):
        if token.kind == kind and token.name and token.name not in found:
            found.append(token.name)
    return found


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "0": "\0"}


def from_c_literal(text: str) -> str:
    """The spec that a C string literal in the driver's source spells out.

    The specs that matter most are not in `-dumpspecs` at all. The one that runs a C file
    is a field of the compiler table, written across sixteen lines of `gcc/gcc.cc` as a
    string literal with a backslash at the end of every line, and reading it as it is
    printed there means reading around the C.

    So: comments out, line continuations joined the way translation phase 2 joins them,
    adjacent literals concatenated, and the ordinary escapes turned back into characters.
    The `\\n` in the middle of that entry survives as a real newline, which matters, because
    a newline is what ends one command and starts the next.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = text.replace("\\\n", "")
    out: list[str] = []
    for match in re.finditer(r'"((?:[^"\\]|\\.)*)"', text, flags=re.S):
        chunk = match.group(1)
        i = 0
        while i < len(chunk):
            if chunk[i] == "\\" and i + 1 < len(chunk):
                out.append(_ESCAPES.get(chunk[i + 1], chunk[i + 1]))
                i += 2
                continue
            out.append(chunk[i])
            i += 1
    return "".join(out)


@dataclass(frozen=True)
class Spec:
    """One named string out of `-dumpspecs`."""

    name: str
    value: str

    def __len__(self) -> int:
        return len(self.value)

    def __str__(self) -> str:
        return f"*{self.name}"

    @property
    def empty(self) -> bool:
        """Is this spec blank?

        Worth asking. A third of the table is empty on any given build, because a spec that
        a target does not need is defined as `""` rather than left out, so that `%(name)`
        always resolves.
        """
        return not self.value.strip()

    @property
    def tokens(self) -> list[Token]:
        return tokenize(self.value)

    @property
    def calls(self) -> list[str]:
        """Every spec this one runs, in the order it runs them, without duplicates.

        Both spellings count: `%(lib)` and `%L` are the same edge.
        """
        return _walk(self.value, "spec")

    @property
    def functions(self) -> list[str]:
        """Every spec function this one calls, in the order it calls them."""
        return _walk(self.value, "call")

    def counts(self) -> dict[str, int]:
        """How many tokens of each family, nested bodies included.

        The shape of a spec in six numbers, which is the only way to compare two 700
        character strings without reading both of them.
        """
        totals: dict[str, int] = {}
        for token in walk(self.value):
            if token.kind == "literal" and not token.text.strip():
                continue
            totals[token.kind] = totals.get(token.kind, 0) + 1
        return totals


@dataclass(frozen=True)
class Table:
    """Everything `-dumpspecs` printed, and where it came from."""

    specs: tuple[Spec, ...]
    text: str
    compiler: str = ""
    target: str = ""
    about: str = ""

    def __len__(self) -> int:
        return len(self.specs)

    def __iter__(self):
        return iter(self.specs)

    def __contains__(self, name: str) -> bool:
        return any(spec.name == name for spec in self.specs)

    def __getitem__(self, name: str) -> Spec:
        """The spec with this name, the last one if it is defined twice.

        Last, because that is what the driver does: `set_spec` overwrites, so a later
        definition of a name wins, and a specs file works by being read after the built in
        table. A build that defines a name twice is not a bug and `duplicates` names them.
        """
        for spec in reversed(self.specs):
            if spec.name == name:
                return spec
        raise SpecError(f"no spec called {name!r} in this table. It has {len(self)} of them.")

    def __str__(self) -> str:
        where = self.target or "an unknown target"
        return f"{len(self)} specs for {where}"

    @property
    def names(self) -> list[str]:
        return [spec.name for spec in self.specs]

    @property
    def duplicates(self) -> list[str]:
        seen: set[str] = set()
        twice: list[str] = []
        for name in self.names:
            if name in seen and name not in twice:
                twice.append(name)
            seen.add(name)
        return twice

    @property
    def empties(self) -> list[str]:
        return [spec.name for spec in self.specs if spec.empty]

    def unknown(self) -> list[tuple[str, str]]:
        """Every `%` form in this table that this module does not recognise.

        Empty, and a test keeps it that way. A GCC that grows a new spec form should fail
        the build here rather than have a lesson print the new form as though it were text.
        """
        return [
            (spec.name, token.text)
            for spec in self.specs
            for token in walk(spec.value)
            if token.kind == "unknown"
        ]

    def reach(self, *roots: str) -> list[str]:
        """Every spec reachable from these, breadth first, roots included.

        Breadth first because the order is shown to a reader and depth first would put
        `asm_debug_option` between `cpp` and `cc1`, which says something untrue about how
        close together they are.
        """
        order: list[str] = []
        queue = [name for name in roots]
        while queue:
            name = queue.pop(0)
            if name in order:
                continue
            order.append(name)
            if name in self:
                queue.extend(self[name].calls)
        return order

    def dangling(self, *roots: str) -> list[str]:
        """Names that are called from these roots and are not in the table.

        Not an error. `%(link_command)` is the obvious one: the driver keeps it in a
        variable of its own rather than in the spec list, so nothing can call it and
        `-dumpspecs` prints it separately at the end.
        """
        return [name for name in self.reach(*roots) if name not in self]

    def callers(self, name: str) -> list[str]:
        """Every spec in the table that runs this one directly."""
        return [spec.name for spec in self.specs if name in spec.calls]


def parse(text: str, *, compiler: str = "", target: str = "", about: str = "") -> Table:
    """Read `gcc -dumpspecs`.

    The format is one `printf` in the driver, `"*%s:\\n%s\\n\\n"`, so a block starts at a
    line that is a name between a star and a colon and runs to the next one. The value keeps
    its newlines, because `invoke_as` has one in it and that newline is what separates the
    compiler from the assembler in the command list.
    """
    specs: list[Spec] = []
    name = ""
    body: list[str] = []

    def close() -> None:
        if name:
            specs.append(Spec(name, "\n".join(body).strip("\n")))

    for line in text.splitlines():
        if line.startswith("*") and line.endswith(":") and " " not in line:
            close()
            name, body = line[1:-1], []
            continue
        if name:
            body.append(line)
    close()
    return Table(tuple(specs), text=text, compiler=compiler, target=target, about=about)


def explain(value: str, *, width: int = 34, depth: int = 3) -> str:
    """A spec with one token per line and what each token does beside it.

    This is the whole reason the module exists. A spec is one line of up to a thousand
    characters with no spaces where you want them, and nobody reads one by looking at it.

    A brace is printed as its predicate and then, indented under it, whatever it would
    substitute. `depth` is how far in to go; the default of three is enough for every spec
    in a C compilation and short of the eight levels the sanitizer specs reach.
    """
    rows: list[str] = []
    _explain(value, 0, depth, width, rows)
    return "\n".join(rows)


def _row(pad: str, shown: str, note: str, width: int) -> str:
    shown = pad + " ".join(shown.split())
    if len(shown) > width:
        shown = shown[: width - 1] + "…"
    return f"{shown:<{width}}  {note}"


def _explain(value: str, level: int, depth: int, width: int, rows: list[str]) -> None:
    pad = "  " * level
    for token in tokenize(value):
        if token.kind == "literal" and not token.text.strip():
            continue
        if token.kind != "brace" or not (token.body or len(token.clauses) > 1):
            rows.append(_row(pad, token.text, token.about, width))
            continue
        # A brace with something to substitute is printed as one row per clause, with what
        # each clause substitutes indented under it. The head keeps its punctuation,
        # because `%{!S:` is the string a reader will go and search the spec for.
        for n, (head, body) in enumerate(token.clauses):
            # The first clause opens the brace and the rest follow a semicolon, which is
            # how they are written, so a reader searching the spec for what they see finds
            # it. `;:` at the end is the default clause and has no predicate at all.
            opener = "%{" if n == 0 else ";"
            rows.append(_row(pad, f"{opener}{head}:", predicate(head) + ", substitute", width))
            if not body.strip():
                rows.append(_row(pad + "  ", "", "nothing", width))
            elif level + 1 < depth:
                _explain(body, level + 1, depth, width, rows)
            else:
                rows.append(_row(pad + "  ", "…", f"{len(body)} more characters", width))


@dataclass(frozen=True)
class Override:
    """One recorded pair of `-###` runs, with and without a specs file.

    The point of the pair is that nothing else differs. Same compiler, same source, same
    flags, one text file. Whatever moved between `before` and `after` moved because of the
    strings in that file.
    """

    name: str
    about: str
    file_text: str
    argv: tuple[str, ...]
    before: str
    after: str

    @property
    def command(self) -> str:
        return " ".join(self.argv)

    @property
    def chain_before(self):
        from gxray import chain as chain_mod

        return chain_mod.parse(self.before)

    @property
    def chain_after(self):
        from gxray import chain as chain_mod

        return chain_mod.parse(self.after)

    @property
    def moved(self) -> bool:
        return self.before != self.after

    def programs(self) -> tuple[list[str], list[str]]:
        return self.chain_before.names, self.chain_after.names


@dataclass(frozen=True)
class Builtin:
    """What the driver has compiled into it, read out of the pinned tree when recording.

    A spec table is two things mixed together. Forty-five of the names come from
    `static_specs` in `gcc/gcc.cc` and are the same on every target. The rest were added by
    the target's own configuration, and telling the two apart is most of understanding why
    one machine's `-dumpspecs` is nine blocks longer than another's.

    The suffixes and the languages are the compiler table, which is the other half of the
    driver's data and the half that is not in `-dumpspecs` at all.
    """

    static_specs: tuple[str, ...]
    functions: tuple[str, ...]
    suffixes: tuple[str, ...]
    languages: tuple[str, ...]

    def added_by(self, table: Table) -> list[str]:
        """The names in `table` that are not built in, which is what the target added."""
        known = set(self.static_specs)
        return [name for name in table.names if name not in known]

    def missing_from(self, table: Table) -> list[str]:
        """Built-in names that this target's table does not have. Normally none."""
        return [name for name in self.static_specs if name not in table]


@dataclass(frozen=True)
class Recording:
    """One run of the F01 recorder: spec tables, and the overrides that moved a chain."""

    recorded: str
    compiler: str
    target: str
    source: str
    tables: dict[str, Table]
    overrides: dict[str, Override]
    builtin: Builtin

    def table(self, label: str = "local") -> Table:
        if label not in self.tables:
            have = ", ".join(sorted(self.tables))
            raise SpecError(f"no spec table called {label!r}. There is: {have}")
        return self.tables[label]

    def override(self, name: str) -> Override:
        if name not in self.overrides:
            have = ", ".join(sorted(self.overrides))
            raise SpecError(f"no override called {name!r}. There is: {have}")
        return self.overrides[name]

    def __getitem__(self, name: str) -> Override:
        return self.override(name)


def load(name: str = "f01", root: Path | str | None = None) -> Recording:
    target = Path(root or CORPUS) / f"{name}.json"
    if not target.is_file():
        raise SpecError(f"{target} is not there. Run lessons/f01-the-spec-language/record.py.")
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Recording(
        recorded=raw["recorded"],
        compiler=raw["compiler"],
        target=raw["target"],
        source=raw["source"],
        tables={
            label: parse(
                one["text"],
                compiler=one["compiler"],
                target=one["target"],
                about=one["about"],
            )
            for label, one in raw["tables"].items()
        },
        overrides={
            key: Override(
                name=key,
                about=one["about"],
                file_text=one["file"],
                argv=tuple(one["argv"]),
                before=one["before"],
                after=one["after"],
            )
            for key, one in raw["overrides"].items()
        },
        builtin=Builtin(
            static_specs=tuple(raw["builtin"]["static_specs"]),
            functions=tuple(raw["builtin"]["functions"]),
            suffixes=tuple(raw["builtin"]["suffixes"]),
            languages=tuple(raw["builtin"]["languages"]),
        ),
    )
