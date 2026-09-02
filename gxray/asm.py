"""Read an assembly listing back, including what `-dp` wrote in the margin.

The file GCC hands the assembler is text, and most of it is not instructions. This reader
sorts every line into one of five kinds, keeps track of which section is in force, and picks
apart the annotation `-dp` leaves on each instruction, because that annotation is the only
printed link from a line of assembly back to the pattern in the machine description that
emitted it.

What the interesting lines look like, from
`gcc-16 -O2 -dp -S corpora/programs/l1.c`:

        .text
        .globl _f
    _f:
        add	w0, w0, w1	; 12	[c=4 l=4]  *addsi3_aarch64/1

The annotation is written by `output_asm_name` at `gcc/final.cc:3219@releases/gcc-16.2.0`
and it is four things: the uid of the RTL insn, the cost the compiler put on it, the length
in bytes it expects it to assemble to, and the name of the pattern. The `/1` is the
alternative within that pattern and it is only printed when the pattern has more than one,
which is a rule worth knowing because its absence means something.

Three things this reader is careful about.

The comment character is a target decision. ELF aarch64 uses `//`, Mach-O aarch64 uses `;`,
x86 uses `#`, and the same GCC writes all three, so the reader works out which one is in
front of it from the annotations themselves rather than assuming.

`-fverbose-asm` puts its own comment on the same line, naming the operands. Compiler
Explorer turns it on and cannot be told not to, so a line can carry two comments and the
annotation is the last one.

One RTL insn can emit several lines of assembly, and only the first of them is annotated.
`output_asm_name` clears its own state to make sure of that. A reader that assumed one
annotation per line would count instructions correctly and insns wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: The four fields `-dp` prints, anchored to the end of the line so that a `-fverbose-asm`
#: comment earlier on the same line cannot be mistaken for the start of the annotation. The
#: pattern name is optional because an insn with no machine description pattern behind it,
#: such as an inline asm, is printed with a bare code number instead.
ANNOTATION = re.compile(
    r"(?P<mark>\S+)[ \t]+(?P<uid>\d+)[ \t]+"
    r"\[c=(?P<cost>-?\d+)(?: l=(?P<length>\d+))?\][ \t]*"
    r"(?P<pattern>[^\s/]+)?(?:/(?P<alternative>\d+))?[ \t]*$"
)

#: The banner `-fverbose-asm` writes, which is the other place the comment character shows
#: up in a form the reader can recognise without knowing the target.
BANNER = re.compile(r"^(?P<mark>\S+) GNU C")

#: Kinds a line can be. Everything in a listing is exactly one of these.
KINDS = ("directive", "label", "instruction", "comment", "blank")

#: Where a listing starts before any directive has said otherwise. GCC always emits a
#: section directive before the first thing it defines, so this is only ever in force for
#: the banner comments at the top of the file.
PROLOGUE = "(no section yet)"


def comment_mark(text: str) -> str:
    """Work out what this target writes a comment with.

    The annotations are the strongest evidence, because their shape is fixed by `final.cc`
    and nothing else in a listing looks like one. The `-fverbose-asm` banner is the fallback,
    and a hash is the fallback to that, because it is what most targets use.
    """
    for line in text.splitlines():
        found = ANNOTATION.search(line)
        if found:
            return found.group("mark")
    for line in text.splitlines():
        found = BANNER.match(line)
        if found:
            return found.group("mark")
    return "#"


def split_comment(line: str, mark: str) -> tuple[str, str]:
    """Cut a line into the part the assembler reads and the part it ignores.

    Quotes have to be respected. `.ascii "zR\\0"` and `.string "a;b"` both contain characters
    that would otherwise look like the start of a comment, and a reader that cut at the first
    one would lose half the string constants in the file.
    """
    quoted = False
    i = 0
    while i < len(line):
        c = line[i]
        if quoted:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                quoted = False
        elif c == '"':
            quoted = True
        elif line.startswith(mark, i):
            return line[:i], line[i + len(mark) :]
        i += 1
    return line, ""


def section_spec(args: str) -> tuple[str, str]:
    """Split the arguments of a `.section` directive into a name and everything else.

    ELF writes `.rodata.str1.8,"aMS",@progbits,1`, where the name stops at the first comma
    and the rest is flags. Mach-O writes `__TEXT,__eh_frame,coalesced,live_support`, where
    the segment and the section are two separate fields and the attributes start at the
    third. Both are `.section` and the reader has to tell them apart on sight.
    """
    fields = [f.strip() for f in args.split(",")]
    if len(fields) > 1 and fields[0].startswith("__") and fields[1].startswith("__"):
        return f"{fields[0]},{fields[1]}", ",".join(fields[2:])
    return fields[0], ",".join(fields[1:])


@dataclass(frozen=True)
class Line:
    """One line of the listing, sorted and taken apart.

    `name` is the directive name, the label name or the mnemonic depending on the kind, and
    `args` is whatever followed it. The annotation fields are only filled in on an
    instruction that `-dp` annotated, which is the first line of each RTL insn.
    """

    number: int
    kind: str
    text: str
    section: str
    name: str = ""
    args: str = ""
    note: str = ""
    uid: int | None = None
    cost: int | None = None
    length: int | None = None
    pattern: str = ""
    alternative: int | None = None

    @property
    def annotated(self) -> bool:
        """Carries a `-dp` annotation, which means it is the first line of an RTL insn."""
        return self.uid is not None

    @property
    def slot(self) -> str:
        """The pattern and the alternative the way the annotation writes them."""
        if not self.pattern:
            return ""
        if self.alternative is None:
            return self.pattern
        return f"{self.pattern}/{self.alternative}"

    def __str__(self) -> str:
        if self.kind == "instruction":
            body = f"{self.name} {self.args}".strip()
            return f"{body}  [{self.slot}]" if self.slot else body
        return self.text.strip()


@dataclass(frozen=True)
class Symbol:
    """A name the assembler is told about, and everything the listing says about it."""

    name: str
    section: str = ""
    kind: str = ""
    size: int | None = None
    exported: bool = False
    line: int = 0

    @property
    def function(self) -> bool:
        return self.kind in ("%function", "@function")

    def __str__(self) -> str:
        scope = "global" if self.exported else "local"
        what = self.kind.lstrip("%@") or "unknown"
        size = "" if self.size is None else f", {self.size} bytes"
        return f"{self.name}: {what}, {scope}, in {self.section}{size}"


@dataclass(frozen=True)
class Section:
    """One section of the object file to be, and the lines that go in it."""

    name: str
    flags: str = ""
    lines: tuple[Line, ...] = ()

    @property
    def instructions(self) -> tuple[Line, ...]:
        return tuple(x for x in self.lines if x.kind == "instruction")

    @property
    def labels(self) -> tuple[Line, ...]:
        return tuple(x for x in self.lines if x.kind == "label")

    @property
    def letters(self) -> str:
        """The ELF flag letters, out of the quoted first field of the flags.

        `"aMS"` is allocated, mergeable, strings. Mach-O writes attributes as words rather
        than letters, so this is empty there and the flags string is the thing to read.
        """
        parts = self.flags.split('"')
        return parts[1] if len(parts) > 2 else ""

    @property
    def writable(self) -> bool:
        return "w" in self.letters

    def __str__(self) -> str:
        n = len(self.instructions)
        if n:
            return f"{self.name}: {n} instruction" + ("" if n == 1 else "s")
        n = len(self.lines)
        return f"{self.name}: {n} line" + ("" if n == 1 else "s")


@dataclass
class Listing:
    """A whole assembly file, read back."""

    name: str = ""
    mark: str = "#"
    lines: tuple[Line, ...] = ()
    sections: dict[str, Section] = field(default_factory=dict)
    symbols: dict[str, Symbol] = field(default_factory=dict)

    def __iter__(self):
        return iter(self.lines)

    def __len__(self) -> int:
        return len(self.lines)

    def of(self, kind: str) -> list[Line]:
        return [x for x in self.lines if x.kind == kind]

    @property
    def instructions(self) -> list[Line]:
        return self.of("instruction")

    @property
    def insns(self) -> list[Line]:
        """The annotated lines, which is one per RTL insn rather than one per instruction."""
        return [x for x in self.lines if x.annotated]

    def by_uid(self, uid: int) -> Line | None:
        """The instruction `final` emitted for this RTL insn, or None if it emitted none."""
        for x in self.insns:
            if x.uid == uid:
                return x
        return None

    def patterns(self) -> dict[str, list[Line]]:
        """Every pattern that emitted something, and what it emitted, in first use order."""
        found: dict[str, list[Line]] = {}
        for x in self.insns:
            if x.pattern:
                found.setdefault(x.pattern, []).append(x)
        return found

    def counts(self) -> dict[str, int]:
        counts = {kind: len(self.of(kind)) for kind in KINDS}
        counts["annotated"] = len(self.insns)
        counts["sections"] = len(self.sections)
        counts["total"] = len(self.lines)
        return counts

    def __str__(self) -> str:
        c = self.counts()
        return (
            f"{self.name or 'listing'}: {c['total']} lines, {c['instruction']} instructions, "
            f"{c['directive']} directives, {c['sections']} sections"
        )


def _classify(code: str) -> tuple[str, str, str]:
    """Sort the assembler-visible part of a line into a kind, a name and the rest."""
    body = code.strip()
    if not body:
        return "blank", "", ""
    head = body.split(None, 1)
    rest = head[1].strip() if len(head) > 1 else ""
    if body.endswith(":") and len(head) == 1:
        return "label", body[:-1], ""
    if head[0].startswith("."):
        return "directive", head[0], rest
    return "instruction", head[0], rest


def parse(text: str, name: str = "") -> Listing:
    """Read a listing. Works on anything `-S` wrote, annotated or not."""
    mark = comment_mark(text)
    section = PROLOGUE
    flags = ""
    order: list[str] = []
    kept: dict[str, list[Line]] = {}
    specs: dict[str, str] = {}
    lines: list[Line] = []
    exported: set[str] = set()
    kinds: dict[str, str] = {}
    sizes: dict[str, int] = {}
    homes: dict[str, tuple[str, int]] = {}

    for number, raw in enumerate(text.splitlines(), start=1):
        code, comment = split_comment(raw, mark)
        kind, head, rest = _classify(code)
        if kind == "blank" and comment:
            kind = "comment"
        # A directive that switches section belongs to the section it switches to, because
        # that is how it reads on the page: `.bss` is the heading of the block under it.
        if kind == "directive":
            if head == ".section":
                section, flags = section_spec(rest)
            elif head in (".text", ".data", ".bss"):
                section, flags = head, ""
        found = ANNOTATION.search(raw) if kind == "instruction" else None
        note = ""
        if found:
            # Whatever `-fverbose-asm` said sits between the operands and the annotation, and
            # on a target where `-fverbose-asm` is off there is nothing between them at all.
            upto = found.start("mark") - len(code) - len(mark)
            note = comment[:upto].strip().strip(",").strip() if upto > 0 else ""
        line = Line(
            number=number,
            kind=kind,
            text=raw,
            section=section,
            name=head,
            args=rest,
            note=note,
            uid=int(found.group("uid")) if found else None,
            cost=int(found.group("cost")) if found else None,
            length=int(found.group("length")) if found and found.group("length") else None,
            pattern=found.group("pattern") or "" if found else "",
            alternative=(
                int(found.group("alternative"))
                if found and found.group("alternative") is not None
                else None
            ),
        )
        lines.append(line)
        if section not in kept:
            order.append(section)
            kept[section] = []
            specs[section] = flags
        kept[section].append(line)

        if kind == "label":
            homes.setdefault(head, (section, number))
        elif kind == "directive":
            if head in (".globl", ".global"):
                exported.update(x.strip() for x in rest.split(",") if x.strip())
            elif head == ".type":
                who, _, what = rest.partition(",")
                kinds[who.strip()] = what.strip()
            elif head == ".size":
                who, _, how = rest.partition(",")
                if how.strip().lstrip("-").isdigit():
                    sizes[who.strip()] = int(how.strip())

    named = sorted(set(kinds) | exported | (set(sizes) & set(homes)))
    symbols = {
        who: Symbol(
            name=who,
            section=homes.get(who, ("", 0))[0],
            kind=kinds.get(who, ""),
            size=sizes.get(who),
            exported=who in exported,
            line=homes.get(who, ("", 0))[1],
        )
        for who in named
    }
    sections = {s: Section(s, specs[s], tuple(kept[s])) for s in order}
    return Listing(name=name, mark=mark, lines=tuple(lines), sections=sections, symbols=symbols)


#: What each directive in a GCC listing is for, in one sentence. Every directive GCC 16 emits
#: for the programs in this book is here, and the sentence is about what the assembler does
#: with it rather than about its syntax, because the syntax is on the line already.
#:
#: This is knowledge about assembly rather than about GCC, so it does not go stale with a
#: release. Anything not in the table gets the honest answer, which is that it is a directive
#: and the assembler knows what to do with it.
DIRECTIVES = {
    ".align": "Round the location counter up, so what comes next starts on a boundary.",
    ".arch": "Which version of the instruction set the rest of the file is allowed to use.",
    ".ascii": "Put these bytes here. No terminator is added.",
    ".asciz": "Put these bytes here, followed by a zero byte.",
    ".balign": "Round the location counter up to a byte boundary, given in bytes.",
    ".bss": "Everything after this goes in the section for variables that start out zero.",
    ".build_version": "Which platform and SDK this object was built for. Mach-O only.",
    ".byte": "Put these one byte values here.",
    ".cfi_endproc": "End of the unwind description for this function.",
    ".cfi_startproc": "Start of the unwind description for this function.",
    ".comm": "Reserve this much space for a symbol, and let the linker merge duplicates.",
    ".data": "Everything after this goes in the section for writable initialised data.",
    ".file": "The name of the source file, for the debugger and for error messages.",
    ".global": "Let the linker see this name from other object files.",
    ".globl": "Let the linker see this name from other object files.",
    ".hidden": "Keep this name out of the dynamic symbol table of a shared library.",
    ".ident": "A string for the object file's comment section, saying which compiler built it.",
    ".long": "Put these four byte values here.",
    ".p2align": "Round the location counter up, with the boundary given as a power of two.",
    ".quad": "Put these eight byte values here.",
    ".section": "Everything after this goes in the named section.",
    ".set": "Define a symbol as equal to an expression, without reserving any space.",
    ".size": "How many bytes this symbol covers, for the linker and the debugger.",
    ".skip": "Leave this many bytes here, filled with zero.",
    ".sleb128": "A signed number in the variable length encoding the unwind tables use.",
    ".space": "Leave this many bytes here, filled with zero.",
    ".string": "Put these bytes here, followed by a zero byte.",
    ".subsections_via_symbols": "Tell the linker it may drop unused symbols. Mach-O only.",
    ".text": "Everything after this goes in the section for code.",
    ".type": "What kind of thing this symbol is, a function or an object.",
    ".uleb128": "An unsigned number in the variable length encoding the unwind tables use.",
    ".weak": "This name may be overridden by a strong definition elsewhere.",
    ".word": "Put these values here, four bytes each on aarch64 and two on x86.",
    ".xword": "Put these eight byte values here. The aarch64 spelling of `.quad`.",
    ".zero": "Leave this many bytes here, filled with zero.",
}


def explain(line: Line) -> str:
    """One sentence about what this line is for. Empty for an instruction.

    An instruction is left alone on purpose. What a `mov` does is a question for the
    architecture manual, and where it came from is a question the annotation answers, so
    there is nothing useful for this function to add.
    """
    if line.kind == "instruction":
        return ""
    if line.kind == "label":
        return "A name for this address. It reserves no space and assembles to nothing."
    if line.kind == "comment":
        return "A comment. The assembler reads past it and nothing reaches the object file."
    if line.kind == "blank":
        return "A blank line, put there by whichever part of GCC wrote the block above it."
    if line.name.startswith(".cfi_"):
        return DIRECTIVES.get(line.name, "Part of the unwind description for this function.")
    return DIRECTIVES.get(line.name, "A directive. It tells the assembler something.")
