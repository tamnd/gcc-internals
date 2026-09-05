"""Section 2 of `BP-BUILD`, generated from GCC's own makefile and language declarations.

Building GCC is not compiling a directory of C++. Before the first real source file is
compiled, twenty nine small programs are built and run, and they write the files that most
of the compiler then includes. `insn-recog.cc` does not exist in the tree. It is written
during your build, out of your target's machine description, by a program that was itself
compiled during your build. A reader who does not know this looks for `gen_movsi` in the
source, does not find it, and concludes the tree is incomplete.

So two tables, read out of the pinned tree every time the blueprint is built:

    gcc/Makefile.in         every generator program, what it links, what it writes
    gcc/*/config-lang.in    every front end, and whether it is on by default

Neither is in the manual. `gccint` documents some generators in prose and omits others,
and the list of languages `--enable-languages` accepts is spread across fourteen shell
fragments that the top level configure sources.

Reading a makefile means expanding variables, because the interesting lists are written as
substitution references over other lists. `$(simple_generated_h:insn-%.h=s-%)` is seven
rules written once. The expander here does `$(NAME)` and `$(NAME:from=to)` and nothing
else, which is enough for this file and says so when it meets something it cannot do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tools.bpc import generator
from tools.bpc.gccsrc import SourceError, read

MAKEFILE = "gcc/Makefile.in"

# The four lists in Makefile.in that say which generator programs exist. Each is the one
# before it plus more, so a program's library needs are the first list it appears in.
READERS = [
    ("genprogrtl", "the RTL reader"),
    ("genprogmd", "the MD reader"),
    ("genprogerr", "error reporting"),
    ("genprog", "nothing extra"),
]

REF = re.compile(r"\$\((?P<body>[^()]*)\)")
STEM = re.compile(r"\$\*")
MOVE = re.compile(r"move-if-change\s+\S+\s+(?P<out>\S+)")
# Every generator is run through `$(RUN_GEN)`, which is empty unless the build was
# configured to run them under valgrind. Anchoring on it is what tells the program being
# run apart from a program's name appearing as an output, which `genconditions` does: it
# writes `build/gencondmd.cc`, the source of another generator.
USES = re.compile(r"\$\(RUN_GEN\)\s+build/gen(?P<name>[a-z0-9-]+|\$\*)")


def logical_lines(text: str) -> list[str]:
    """The makefile with backslash continuations joined, so a rule is one line.

    Line numbers are lost on purpose. Nothing generated from this cites a line, because a
    citation into a makefile that a reader will see with different line breaks is worse
    than no citation.
    """
    out: list[str] = []
    held = ""
    for line in text.split("\n"):
        if line.endswith("\\"):
            held += line[:-1]
            continue
        out.append(held + line)
        held = ""
    if held:
        out.append(held)
    return out


ASSIGN = re.compile(r"^(?P<name>[A-Za-z_][\w.-]*)\s*(?P<op>:?=)\s*(?P<value>.*)$")


def variables(lines: list[str]) -> dict[str, str]:
    """Every simple variable assignment, last one wins, as make itself would read it."""
    found: dict[str, str] = {}
    for line in lines:
        if line.startswith(("\t", "#")) or ":" in line.split("=")[0].replace(":=", ""):
            continue
        if (m := ASSIGN.match(line)) is not None:
            found[m.group("name")] = m.group("value").strip()
    return found


def substitute(word: str, frm: str, to: str) -> str:
    """One word of a `$(VAR:from=to)` reference, in both of make's two forms."""
    if "%" in frm:
        head, _, tail = frm.partition("%")
        if not (word.startswith(head) and word.endswith(tail) and len(word) >= len(frm) - 1):
            return word
        return to.replace("%", stem_of(word, frm))
    return word[: -len(frm)] + to if frm and word.endswith(frm) else word


def expand(value: str, names: dict[str, str], depth: int = 0) -> str:
    """A makefile value with `$(NAME)` and `$(NAME:from=to)` resolved.

    An unknown name expands to nothing, which is what make does. The depth limit is for a
    variable defined in terms of itself, which make catches and this would not.
    """
    if depth > 20:
        raise SourceError(f"{value!r} still has variable references after 20 rounds")

    def one(m: re.Match[str]) -> str:
        body = m.group("body")
        if ":" in body:
            name, _, subst = body.partition(":")
            frm, _, to = subst.partition("=")
            words = expand(names.get(name.strip(), ""), names, depth + 1).split()
            return " ".join(substitute(w, frm, to) for w in words)
        return expand(names.get(body.strip(), ""), names, depth + 1)

    new = REF.sub(one, value)
    return new if new == value else expand(new, names, depth + 1)


def split_head(line: str) -> list[str] | None:
    """A rule head split at its top level colons, or nothing if this is not a rule head.

    An ordinary rule is `targets: prerequisites`. A static pattern rule is `targets:
    pattern: prerequisites`, and GCC uses one of those to write seven generator rules at
    once, so both shapes have to come back. Colons inside `$(...)` are substitution
    references and are not separators.
    """
    if not line or line.startswith(("\t", "#", " ")):
        return None
    fields: list[str] = []
    depth = current = 0
    for i, ch in enumerate(line):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ":" and depth == 0:
            if line[i + 1 : i + 2] in ("=", ":"):
                return None
            fields.append(line[current:i])
            current = i + 1
    if not fields:
        return None
    fields.append(line[current:])
    # A target list can hold an `=` inside a substitution reference, so the test for an
    # assignment has to ignore what is inside the parentheses.
    if "=" in REF.sub("", fields[0]):
        return None
    return fields


@dataclass
class Rule:
    """One makefile rule, with its recipe and the stems its targets expand to."""

    targets: list[str]
    pattern: str
    prerequisites: str
    recipe: list[str]


def rules(lines: list[str], names: dict[str, str]) -> list[Rule]:
    """Every rule with a recipe, with its target list expanded.

    A comment at column zero inside a recipe is still part of the recipe as far as make is
    concerned, and `s-gtype` has two of them between its commands, so they do not end it.
    """
    found: list[Rule] = []
    i = 0
    while i < len(lines):
        fields = split_head(lines[i])
        if fields is None:
            i += 1
            continue
        i += 1
        recipe: list[str] = []
        while i < len(lines) and (lines[i].startswith(("\t", "#")) or not lines[i].strip()):
            if lines[i].startswith("\t"):
                recipe.append(lines[i])
            elif not lines[i].startswith("#"):
                break
            i += 1
        while recipe and not recipe[-1].strip():
            recipe.pop()
        if not recipe:
            continue
        found.append(
            Rule(
                targets=expand(fields[0], names).split(),
                pattern=fields[1].strip() if len(fields) > 2 else "",
                prerequisites=fields[-1],
                recipe=recipe,
            )
        )
    return found


def stem_of(target: str, pattern: str) -> str:
    """What `$*` stands for in a static pattern rule, for one of its targets."""
    head, _, tail = pattern.partition("%")
    if not target.startswith(head) or not target.endswith(tail):
        return ""
    return target[len(head) : len(target) - len(tail)] if tail else target[len(head) :]


def tidy(name: str) -> str:
    """An output filename as a reader would see it on disk.

    A `$(foreach)` over the split outputs leaves the loop's own punctuation on the last
    word, and the split count is an autoconf substitution, so the number is not in the file
    and `N` is the honest thing to print.
    """
    name = name.rstrip(";)").strip()
    return re.sub(r"\$\(\w+\)", "N", name)


def outputs(root: Path) -> dict[str, list[str]]:
    """What each generator program writes, keyed by the program's name without `gen`.

    Read from the `move-if-change` calls in the recipes rather than from a list, because
    there is no list. GCC writes to a temporary and moves it into place only when the
    contents changed, which is what keeps a rebuild from recompiling the world, and it
    means the second argument of every one of those calls is a generated file.
    """
    lines = logical_lines(read(root / "Makefile.in"))
    names = variables(lines)
    found: dict[str, list[str]] = {}
    for rule in rules(lines, names):
        text = " ".join(rule.recipe)
        moved = MOVE.findall(text)
        if not moved:
            continue
        used = USES.findall(text + " " + rule.prerequisites)
        if not used:
            continue
        for target in rule.targets:
            stem = stem_of(target, rule.pattern) if rule.pattern else ""
            for who in dict.fromkeys(used):
                program = stem if who == "$*" else who
                if not program:
                    continue
                have = found.setdefault(program, [])
                for out in moved:
                    written = tidy(STEM.sub(stem, out))
                    if written not in have:
                        have.append(written)
    return found


def programs(root: Path) -> list[tuple[str, str]]:
    """Every generator program the build compiles, with what it has to link against."""
    lines = logical_lines(read(root / "Makefile.in"))
    names = variables(lines)
    seen: dict[str, str] = {}
    for variable, what in READERS:
        if variable not in names:
            raise SourceError(f"Makefile.in no longer defines {variable}")
        for name in expand(names[variable], names).split():
            seen.setdefault(name, what)
    return sorted(seen.items())


@generator("build-generators")
def build_generators(root: Path) -> str:
    every = programs(root)
    writes = outputs(root)
    counts: dict[str, int] = {}
    for _, what in every:
        counts[what] = counts.get(what, 0) + 1

    rows = ["| Program | Links | Writes |", "|---|---|---|"]
    for name, what in every:
        made = writes.get(name, [])
        said = ", ".join(f"`{f}`" for f in made) if made else "nothing, or nothing by that route"
        rows.append(f"| `gen{name}` | {what} | {said} |")

    tally = ", ".join(f"{n} link {k}" for k, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    summary = (
        f"The build compiles **{len(every)} generator programs** before it compiles any of "
        f"the compiler. They are built with the *build* compiler rather than the host one, "
        f"because they run on the machine doing the building even when the compiler being "
        f"built runs somewhere else. {tally}."
    )
    tail = (
        "The `Writes` column is read from the `move-if-change` call in each rule, which is "
        "also why a rebuild after an unrelated edit is fast: the generator runs every time "
        "and its output replaces the file on disk only when the contents differ. A program "
        "with nothing in that column writes through some other mechanism, `gengtype` "
        "writing one file per input and `genchecksum` writing to standard output among "
        "them."
    )
    return "\n".join(["", summary, "", *rows, "", tail])


SOURCED = re.compile(r"^\.\s+\$\{srcdir\}/(?:gcc/)?(?P<rel>[\w./-]+)")
OPENS = ("if", "case")
CLOSES = ("fi", "esac")


@dataclass
class FrontEnd:
    """One `config-lang.in`, as the shell variables it sets."""

    directory: str
    fields: dict[str, str]
    conditional: set[str]

    def get(self, name: str, default: str = "") -> str:
        return self.fields.get(name, default)


def _read_declaration(path: Path, root: Path, into: FrontEnd, depth: int = 0) -> None:
    """Read one fragment into `into`, following anything it sources.

    `ada/config-lang.in` sets a language and then sources
    `ada/gcc-interface/config-lang.in` for everything else, so a reader that stops at the
    outer file reports Ada as having no compiler and no requirements. Both are wrong.
    """
    if depth > 4:
        raise SourceError(f"{path} sources files more than four deep")
    block = 0
    for raw in logical_lines(path.read_text(encoding="utf-8", errors="replace")):
        line = raw.strip()
        head = line.split()[0] if line.split() else ""
        if head in CLOSES:
            block = max(0, block - 1)
            continue
        if (m := SOURCED.match(line)) is not None:
            nested = root / m.group("rel")
            if nested.is_file():
                _read_declaration(nested, root, into, depth + 1)
            continue
        if (m := ASSIGN.match(line)) is not None and m.group("op") == "=":
            value = " ".join(m.group("value").strip().strip('"').replace("\\$", "$").split())
            into.fields[m.group("name")] = value
            if block:
                into.conditional.add(m.group("name"))
        if head in OPENS:
            block += 1


def declarations(root: Path) -> list[FrontEnd]:
    """Every front end declaration in the tree, in directory order.

    A value assigned inside a shell `if` is recorded as conditional, because Ada requires
    C and C++ only when it is not being cross built, and a table that states that
    requirement flatly is telling a reader something untrue about half of all builds.
    """
    found: list[FrontEnd] = []
    for path in sorted(root.glob("*/config-lang.in")):
        entry = FrontEnd(directory=path.parent.name, fields={}, conditional=set())
        _read_declaration(path, root, entry)
        if "language" not in entry.fields:
            raise SourceError(f"{path} sets no language, so it is not a front end declaration")
        found.append(entry)
    if not found:
        raise SourceError("no config-lang.in files found, so the tree is not a GCC tree")
    return found


@generator("build-front-ends")
def build_front_ends(root: Path) -> str:
    every = declarations(root)
    on = [d for d in every if d.get("build_by_default", "yes") != "no"]
    boot = [d for d in every if d.get("boot_language", "no") not in ("no", "")]

    rows = ["| Directory | `--enable-languages` name | Compiler | Built by default | Also needs |"]
    rows.append("|---|---|---|---|---|")
    for d in every:
        binary = d.get("compilers").replace("$(exeext)", "")
        needs = d.get("lang_requires") or d.get("lang_requires_boot_languages")
        said = f"`{needs}`" if needs else "nothing"
        if needs and "lang_requires" in d.conditional:
            said += ", when not cross building"
        rows.append(
            f"| `gcc/{d.directory}/` | `{d.get('language')}` | "
            f"{f'`{binary}`' if binary else 'none'} | "
            f"{'no' if d.get('build_by_default') == 'no' else 'yes'} | {said} |"
        )

    summary = (
        f"There are **{len(every)} front end declarations** in the tree, and "
        f"{len(on)} of them say they should be built when `--enable-languages` is not "
        f"given. A declaration is a shell fragment the top level configure sources, not a "
        f"makefile and not a list, which is why no single file in GCC holds this table."
    )
    named = ", ".join(
        f"`{d.get('language')}`"
        + ("" if d.get("boot_language") == "yes" else f" if `{d.get('boot_language')}`")
        for d in boot
    )
    tail = (
        f"The `Built by default` column is what the fragment asks for and not what you "
        f"get. The top level decides and overrides this in both directions, `lto` being "
        f"the one that says no and is built anyway, because `--enable-lto` is on unless "
        f"you turn it off. "
        f"{f'{named} set ' if named else 'No front end sets '}"
        f"`boot_language`, which puts them in stage one and so makes them available to "
        f"build the stages above."
    )
    return "\n".join(["", summary, "", *rows, "", tail])


# The `--enable-checking` block of gcc/configure.ac: a `for` loop over comma separated
# words, a case statement that sets fourteen shell variables, and then one `AC_DEFINE` per
# variable. Every part of the answer is there and no part of it is in one place.
CHECK_LOOP = "for check in release $ac_checking_flags"
CHECK_ARM = re.compile(r"\n\t(?P<names>[\w|]+)\)(?P<body>.*?);;", re.DOTALL)
CHECK_SET = re.compile(r"ac_(?P<var>\w+)=1\b")
# The `AC_DEFINE` is not always the next line. `valgrind` looks for the binary first and
# errors out if it is missing, so the search has to reach past a few lines without
# reaching into the next variable's block.
CHECK_MACRO = re.compile(
    r"if test x\$ac_(?P<var>\w+) != x ; then"
    r"(?:(?!if test x\$ac_).)*?"
    r"AC_DEFINE\s*\(\s*(?P<macro>\w+)\s*,\s*1\s*,\s*\[(?P<doc>.*?)\]\s*\)",
    re.DOTALL,
)
LEVELS = ("no|none", "release", "yes", "all")


def label(level: str) -> str:
    """A level as a table heading. A pipe in a cell ends the cell, so the two spellings of
    off are written out rather than left as the alternation configure.ac writes."""
    return " or ".join(f"`{w}`" for w in level.split("|"))


def checking(root: Path) -> tuple[dict[str, set[str]], dict[str, str], dict[str, str]]:
    """The `--enable-checking` block, as three maps.

    Returns what each word turns on, which macro each shell variable defines, and what
    GCC's own comment on that macro says.
    """
    text = read(root / "configure.ac")
    at = text.find(CHECK_LOOP)
    if at < 0:
        raise SourceError("gcc/configure.ac no longer loops over the checking flags")
    end = text.find('IFS="$ac_save_IFS"', at)
    turns_on = {
        m.group("names"): {s.group("var") for s in CHECK_SET.finditer(m.group("body"))}
        for m in CHECK_ARM.finditer(text[at:end])
    }
    if not set(LEVELS) <= set(turns_on):
        raise SourceError(f"the checking levels changed: found {sorted(turns_on)}")
    macros, docs = {}, {}
    for m in CHECK_MACRO.finditer(text):
        macros[m.group("var")] = m.group("macro")
        docs[m.group("var")] = " ".join(m.group("doc").split())
    return turns_on, macros, docs


def cost(doc: str) -> str:
    """What GCC says a check costs, which it writes as the last sentence of the comment."""
    for word in ("extremely expensive", "quite expensive", "moderately expensive", "cheap"):
        if word in doc:
            return word
    return "not said"


@generator("build-checking")
def build_checking(root: Path) -> str:
    turns_on, macros, docs = checking(root)
    categories = sorted(k for k in turns_on if k not in LEVELS)

    head = "| Category | Sets | Defines | GCC calls it |"
    rows = [head, "|---|---|---|---|"]
    for name in categories:
        variables_set = sorted(turns_on[name])
        var = variables_set[0] if len(variables_set) == 1 else ""
        macro = macros.get(var, "")
        rows.append(
            f"| `{name}` | `ac_{var}` | {f'`{macro}`' if macro else 'nothing on its own'} | "
            f"{cost(docs.get(var, ''))} |"
        )

    matrix = ["| Category | " + " | ".join(label(n) for n in LEVELS) + " |"]
    matrix.append("|---" * (len(LEVELS) + 1) + "|")
    for name in categories:
        var = next(iter(turns_on[name]), "")
        cells = ["yes" if var in turns_on[level] else "no" for level in LEVELS]
        matrix.append(f"| `{name}` | " + " | ".join(cells) + " |")

    summary = (
        f"`--enable-checking` takes a comma separated list of **{len(categories)} "
        f"categories** and {len(LEVELS)} whole settings. The loop that reads it starts "
        f"`for check in release $ac_checking_flags`, so **`release` is applied first every "
        f"single time**, and `--enable-checking=rtl` therefore means release checking plus "
        f"RTL checking rather than RTL checking alone. Only `no`, `none`, `yes` and `all` "
        f"clear what `release` set, because they are the four words whose case arm assigns "
        f"every variable rather than one."
    )
    middle = (
        "The whole settings, and which categories each one leaves turned on. This is the "
        "table to read before choosing what to build."
    )
    tail = (
        "The default is not in this table because it is not a word. A tree whose "
        "`DEV-PHASE` file says `experimental` defaults to `yes,extra` and any other tree "
        "defaults to `release`, so the same configure line gives different checking on a "
        "release tarball and on a git checkout of the development branch."
    )
    return "\n".join(["", summary, "", *rows, "", middle, "", *matrix, "", tail])
