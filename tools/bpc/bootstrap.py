"""Section 2 of `BP-BOOTSTRAP`, generated from the top level of the pinned tree.

The bootstrap is the only part of GCC that checks GCC. Everything else in the project
tests what the compiler does to a program somebody wrote. The bootstrap tests whether the
compiler, compiled by itself, is the same compiler, and it does that by building the whole
thing three times and requiring the last two to be identical object file for object file.

Nothing about it lives in `gcc/`. The stages, the rules that run them, and the comparison
are all at the top level of the tree, in three files that are not makefiles:

    Makefile.def            nine stage declarations, and which modules are rebuilt in each
    Makefile.tpl            the rules, as an autogen template with `[+ FOR +]` in it
    configure.ac            what the comparison is allowed to forgive
    config/bootstrap-*.mk   the build configurations `--with-build-config` selects

`Makefile.in` at the top level is generated from the first two by autogen and is about
sixty thousand lines, so reading the generated file to find out what the bootstrap does is
reading nine copies of the same thing with the stage substituted in. The declarations are
what this reads.

The stage names are not 1, 2, 3. There are nine, four of them numbered and five named,
because the profiled bootstrap builds a compiler to collect profiles with, and the auto
profiled bootstrap builds one to run `perf` against. A reader who thinks a bootstrap is
three stages is right about the default and wrong about the mechanism.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from tools.bpc import generator
from tools.bpc.gccsrc import SourceError, read

DEFINITIONS = "Makefile.def"
TEMPLATE = "Makefile.tpl"
CONFIGURE = "configure.ac"
CONFIGS = "config"

# A stage assignment in the template. `STAGE2_CFLAGS += -fno-checking` and its friends are
# what actually differ between one stage and the next, and they are written flat rather
# than inside the `[+ FOR +]`, because each one is about one stage.
FLAG = re.compile(
    r"^STAGE(?P<stage>[A-Za-z0-9]+)_"
    r"(?P<what>GENERATOR_CFLAGS|CFLAGS|CXXFLAGS|GDCFLAGS|TFLAGS|CONFIGURE_FLAGS)\s*"
    r"(?P<op>\+?=)\s*(?P<value>.*)$",
    re.MULTILINE,
)
# Any assignment at column zero in a build configuration fragment. Anchored, so the two
# lines `bootstrap-debug-ckovw.mk` comments out are not counted as things it does.
ASSIGNS = re.compile(r"^(?:override\s+)?(?P<name>[\w-]+)\s*[:+]?=", re.MULTILINE)
# `compare_exclusions="..."` in the top level configure.ac, including the lines that append
# to it. The value is a shell case pattern with `|` between the alternatives.
EXCLUSION = re.compile(r'^compare_exclusions="(?:\$compare_exclusions \| )?(?P<pattern>[^"]*)"')


def top(root: Path) -> Path:
    """The top of the tree. Everything else in `bpc` reads `gcc/`, and none of this is
    there: a bootstrap is the top level driving `gcc/` three times."""
    return root.parent


@dataclass
class Definition:
    """One `name = { ... };` block of an autogen definitions file.

    A field can be given more than once, which is how `missing=` lists several targets, so
    every value is a list and `one` is for the fields that are not lists.
    """

    name: str
    fields: dict[str, list[str]] = field(default_factory=dict)

    def one(self, key: str, default: str = "") -> str:
        values = self.fields.get(key)
        return values[0] if values else default

    def has(self, key: str) -> bool:
        return key in self.fields


def _strip_comments(text: str) -> str:
    """`//` to end of line, unless it is inside a quoted value.

    `Makefile.def` has comments inside blocks, between fields, and a value in it contains
    `http://` in a URL, so a plain split on `//` loses part of a configure flag.
    """
    out: list[str] = []
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
            out.append(ch)
        elif ch in "'\"":
            quote = ch
            out.append(ch)
        elif ch == "/" and text[i + 1 : i + 2] == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _split_fields(body: str) -> list[str]:
    """A block body split at the semicolons that are not inside quotes."""
    out: list[str] = []
    held: list[str] = []
    quote = ""
    for ch in body:
        if quote:
            held.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
            held.append(ch)
        elif ch == ";":
            out.append("".join(held))
            held = []
        else:
            held.append(ch)
    if "".join(held).strip():
        out.append("".join(held))
    return out


def definitions(text: str) -> list[Definition]:
    """Every `name = { ... };` block of an autogen definitions file, in file order."""
    clean = _strip_comments(text)
    found: list[Definition] = []
    at = 0
    # `finditer` would also find any block nested inside one already taken, and report it as
    # a declaration of its own. `Makefile.def` nests nothing today, so the difference is
    # invisible until somebody nests something and every later block goes missing.
    while (m := re.compile(r"(?P<name>[\w-]+)\s*=\s*\{").search(clean, at)) is not None:
        depth, i = 1, m.end()
        while i < len(clean) and depth:
            depth += {"{": 1, "}": -1}.get(clean[i], 0)
            i += 1
        if depth:
            raise SourceError(f"an autogen block opened by {m.group('name')} is never closed")
        entry = Definition(name=m.group("name"))
        for part in _split_fields(clean[m.end() : i - 1]):
            key, sep, value = part.partition("=")
            if not sep or not key.strip():
                continue
            entry.fields.setdefault(key.strip(), []).append(value.strip().strip("'\""))
        found.append(entry)
        at = i
    if not found:
        raise SourceError("no autogen definitions found, so this is not Makefile.def")
    return found


def stages(root: Path) -> list[Definition]:
    """The bootstrap stages, in declaration order, which is also dependency order."""
    found = [d for d in definitions(read(top(root) / DEFINITIONS)) if d.name == "bootstrap_stage"]
    if not found:
        raise SourceError(f"{DEFINITIONS} declares no bootstrap_stage")
    return found


def modules(root: Path) -> tuple[list[str], list[str]]:
    """The host modules rebuilt in every stage, and the ones built once.

    `bootstrap=true` is what puts a module inside the stage loop. Everything without it is
    built once against the final compiler, which is why a bug in `gdb` cannot make a
    bootstrap comparison fail and a bug in `libiberty` can.
    """
    every = [d for d in definitions(read(top(root) / DEFINITIONS)) if d.name == "host_modules"]
    inside = [d.one("module") for d in every if d.one("bootstrap") == "true"]
    outside = [d.one("module") for d in every if d.one("bootstrap") != "true"]
    return inside, outside


def target_modules(root: Path) -> tuple[list[str], list[str]]:
    """The target libraries rebuilt in every stage, and the ones built once.

    Separate from `modules` because a target library is a different animal: it is compiled by
    the stage's own compiler, for the target machine, rather than by the compiler doing the
    building. The ones marked `bootstrap=true` are staged and therefore compared, which is
    the only reason the comparison has anything to say about generated target code at all.
    """
    every = [d for d in definitions(read(top(root) / DEFINITIONS)) if d.name == "target_modules"]
    inside = [d.one("module") for d in every if d.one("bootstrap") == "true"]
    outside = [d.one("module") for d in every if d.one("bootstrap") != "true"]
    return inside, outside


def flags(root: Path) -> dict[str, list[tuple[str, str, str]]]:
    """Every per stage flag assignment in the template, keyed by stage.

    Read from `Makefile.tpl` and not from the generated `Makefile.in`, because the
    generated file has these lines nine times with the stage substituted and no way to tell
    the default apart from the override.
    """
    found: dict[str, list[tuple[str, str, str]]] = {}
    for m in FLAG.finditer(read(top(root) / TEMPLATE)):
        # The `[+ FOR +]` block writes `STAGE[+id+]_CFLAGS`, which is the default and not an
        # override. It does not match, because a stage name here is letters and digits.
        found.setdefault(m.group("stage"), []).append(
            (m.group("what"), m.group("op"), m.group("value").strip())
        )
    if not found:
        raise SourceError(f"{TEMPLATE} no longer assigns any STAGE<n>_CFLAGS")
    return found


def exclusions(root: Path) -> list[str]:
    """The object files a stage comparison is allowed to find different.

    Every one of these is a file that legitimately differs between two identical compilers,
    and the list is short on purpose: an entry here is a hole in the only end to end check
    GCC has on itself.
    """
    found: list[str] = []
    for line in read(top(root) / CONFIGURE).split("\n"):
        if (m := EXCLUSION.match(line)) is not None:
            found += [p.strip().replace("\\$", "$") for p in m.group("pattern").split("|")]
    if not found:
        raise SourceError(f"{CONFIGURE} no longer sets compare_exclusions")
    return found


@dataclass
class BuildConfig:
    """One `config/bootstrap-*.mk`, as its name, its own comment, and what it assigns."""

    name: str
    doc: str
    sets: list[str]
    stages: list[str]

    def changes(self) -> str:
        """What this fragment does, in the terms the rest of the blueprint uses."""
        parts = [f"`stage{s}`" for s in self.stages]
        if "do-compare" in self.sets:
            parts.append("the comparison itself")
        if "BOOT_CFLAGS" in self.sets:
            parts.append("`BOOT_CFLAGS`, so every stage")
        return ", ".join(parts) or ", ".join(f"`{s}`" for s in self.sets)


def _lead_comment(text: str) -> str:
    """The first comment paragraph of a makefile fragment, as one line.

    Every one of these files opens by saying what it is for, in GCC's own words, which is
    better than anything a table could say about it and is the only documentation some of
    them have.
    """
    words: list[str] = []
    for line in text.split("\n"):
        if line.startswith("#"):
            words += line.lstrip("#").split()
        elif words:
            break
    return " ".join(words)


def build_configs(root: Path) -> list[BuildConfig]:
    """Every value `--with-build-config` accepts, read from the files that implement it."""
    found = []
    for path in sorted((top(root) / CONFIGS).glob("bootstrap-*.mk")):
        text = read(path)
        names = list(dict.fromkeys(m.group("name") for m in ASSIGNS.finditer(text)))
        touches = sorted({m.group("stage") for m in FLAG.finditer(text)})
        found.append(
            BuildConfig(name=path.stem, doc=_lead_comment(text), sets=names, stages=touches)
        )
    if not found:
        raise SourceError(f"no {CONFIGS}/bootstrap-*.mk files, so the tree is not a GCC tree")
    return found


def config_names(root: Path) -> list[str]:
    """The inventory `bpc coverage` classifies, spelled the way `--with-build-config` takes
    it, so that a reader who found a name in the ledger can paste it into a configure line."""
    return [c.name for c in build_configs(root)]


def sentence(doc: str) -> str:
    """GCC's own description, cut to its first sentence, which is where it says what it is
    for. Five of the fragments are one line of makefile with no comment at all."""
    return doc.split(". ")[0].rstrip(".") if doc else "the fragment carries no comment"


@generator("bootstrap-stages")
def bootstrap_stages(root: Path) -> str:
    every = stages(root)
    changes = flags(root)
    numbered = [d for d in every if d.one("id").isdigit()]

    rows = ["| Stage | Built by | Compared against | `make` target | Flags, against the default |"]
    rows.append("|---|---|---|---|---|")
    for d in every:
        sid = d.one("id")
        prev = d.one("prev")
        # `+=` adds to what the stage would have had and `=` replaces it, and the
        # difference matters: `STAGEprofile_CFLAGS = $(STAGE2_CFLAGS) -fprofile-generate`
        # is a stage that took stage two's flags rather than the default's.
        added = [
            f"`{what} {op} {value}`"
            for what, op, value in changes.get(sid, [])
            if what in ("CFLAGS", "TFLAGS")
        ]
        built_by = f"`stage{prev}`" if prev else "the compiler already on the machine"
        against = f"`stage{prev}`" if d.has("compare_target") else "nothing"
        target = f"`make {d.one('bootstrap_target')}`" if d.has("bootstrap_target") else "none"
        adds = ", ".join(dict.fromkeys(added)) if added else "the default"
        rows.append(f"| `stage{sid}` | {built_by} | {against} | {target} | {adds} |")

    summary = (
        f"There are **{len(every)} bootstrap stages** declared, {len(numbered)} of them "
        f"numbered and {len(every) - len(numbered)} named. A default `make bootstrap` runs "
        f"three of them and compares the last two. The rest exist for the profiled and the "
        f"auto profiled bootstraps, which build extra compilers whose only job is to "
        f"produce the profile the final one is optimised with."
    )
    compared = [d.one("id") for d in every if d.has("compare_target")]
    tail = (
        f"Only {len(compared)} of the {len(every)} stages compare anything: "
        f"{', '.join(f'`stage{s}`' for s in compared)}. A stage with no comparison is a "
        f"compiler that got built and believed. The `Built by` column is the whole "
        f"argument: every stage after the first is compiled by the stage above it, so "
        f"`stage3` and `stage2` are the same source built by two different compilers, and "
        f"the compiler that built `stage2` is the one being tested."
    )
    return "\n".join(["", summary, "", *rows, "", tail])


@generator("bootstrap-modules")
def bootstrap_modules(root: Path) -> str:
    inside, outside = modules(root)
    named = ", ".join(f"`{m}`" for m in inside)
    return "\n".join(
        [
            "",
            f"**{len(inside)} of the {len(inside) + len(outside)} host modules** are built "
            f"again in every stage. `bootstrap=true` in `Makefile.def` is what puts one "
            f"inside the loop, and it is the whole of the difference:",
            "",
            named + ".",
            "",
            f"The other {len(outside)} are built once, against the compiler the bootstrap "
            f"finished with. That is the line between a bug that a stage comparison can "
            f"catch and a bug it cannot. `libiberty` is linked into the compiler and is in "
            f"the list, so a miscompilation of it shows up as a differing object file. "
            f"`gdb` is not, so it could be miscompiled by every stage and the bootstrap "
            f"would still say it succeeded.",
        ]
    )


@generator("bootstrap-compare")
def bootstrap_compare(root: Path) -> str:
    every = exclusions(root)
    rows = ["| Pattern | Why it is allowed to differ |"]
    rows.append("|---|---|")
    why = {
        "gcc/cc*-checksum$(objext)": (
            "The checksum of the compiler's own object files, which is a hash of stage "
            "two's binaries in stage two and of stage three's in stage three. It is "
            "supposed to differ, and it is what makes every other object file's PCH "
            "validation work."
        ),
        "gcc/ada/*tools/*": (
            "Ada's tools are built by the Ada compiler of the stage that is building, "
            "and stage two's gnat1 is not stage three's."
        ),
        "gcc/m2/gm2-compiler-boot/M2Version*": (
            "`M2Version.def` says its implementation module is generated, and one of the "
            "four things it returns is `GetGM2Date`, documented there as the date of the "
            "build. A date in an object file cannot survive being built twice."
        ),
        "gcc/m2/gm2-compiler-boot/SYSTEM*": (
            "`SYSTEM.def` is generated by `m2/tools-src/makeSystem`, which runs the "
            "current stage's own `gm2` to find out what the target's types are. What it "
            "writes is therefore a product of the compiler doing the building."
        ),
        "gcc/m2/gm2version*": (
            "The version number again, from the front end side. There is a "
            "`gcc/m2/gm2version.h` in the tree and no matching source file, so the "
            "implementation is another thing generated during the build."
        ),
        "gcc/cobol/parse$(objext)": (
            "GCC's sources do not say, and this table will not guess. `parse.cc` is "
            "generated from `parse.y` by bison, and something in it differs between two "
            "stages of an otherwise identical build."
        ),
    }
    unexplained = [p for p in every if p not in why]
    for pattern in every:
        said = why.get(pattern, "GCC's own sources do not say, and neither does this table.")
        rows.append(f"| `{pattern}` | {said} |")
    return "\n".join(
        [
            "",
            f"A stage comparison walks every `*.o` under `stage3-*`, finds the matching file "
            f"under `stage2-*`, and requires them to be equal after the first 16 bytes. "
            f"**{len(every)} patterns** are forgiven on every target"
            + (f", and {len(unexplained)} of them are not explained here" if unexplained else "")
            + ":",
            "",
            *rows,
            "",
            "One more, `*libgomp*$(objext)`, is added by the `powerpc*-ibm-aix*` arm of a "
            "case on the target, so on every other target it is not in the list at all.",
            "",
            "Anything else that differs goes into `.bad_compare`, and the build stops with "
            "`Bootstrap comparison failure!` and the list. The 16 bytes are skipped because "
            "some object formats put a timestamp there. `configure` works out at build time "
            "whether the local `cmp` can skip bytes itself, and falls back to a pair of "
            "`tail -c +17` calls into temporary files when it cannot.",
        ]
    )


@generator("bootstrap-configs")
def bootstrap_configs(root: Path) -> str:
    every = build_configs(root)
    rows = ["| `--with-build-config=` | What it changes | What GCC says it is for |"]
    rows.append("|---|---|---|")
    for c in every:
        rows.append(f"| `{c.name}` | {c.changes()} | {sentence(c.doc)} |")
    return "\n".join(
        [
            "",
            f"**{len(every)} build configurations** ship in `config/`, and "
            f"`--with-build-config` takes a space separated list of them. A configuration "
            f"is a makefile fragment included after the defaults, so it can add to a "
            f"stage's flags, replace them, or replace the comparison itself:",
            "",
            *rows,
            "",
            "`bootstrap-debug` is the one to know. It is on by default on any target where "
            "it works, and it turns the stage comparison into a check that generating debug "
            "information does not change the code generated, which is a class of bug that "
            "nothing else in GCC looks for.",
        ]
    )
