"""Walk the pinned GCC checkout once and write the map the lesson reads.

    just corpus-z02
    python lessons/z02-where-things-are/record.py

This needs `vendor/gcc` and nothing else. It writes `corpora/layout/gcc.json`, which is what
the notebook loads, so the notebook runs in Colab where there is no checkout at all.

Everything measured here is measured, not typed. The counts, the port list, the pass table and
the sizes all come from walking the tree. What is typed is the one sentence of what each place
is for, the meaning of each file extension, and the six scavenger hunt items, because no walk
of a directory tree can tell you that `gcc/combine.cc` is where instructions get glued together
or that a beginner should leave it alone for a while.

The `cite` key on the kinds and the hunt items looks redundant with the path and line right
next to it, and it is, on purpose. `refcheck` only reads `.md` and `.py` files, so a line
number that lives only in a JSON corpus is a line number nothing pins. Writing the citation
out as a literal string here puts it in refcheck's lockfile, and `main` refuses to run if the
two ever disagree.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import layout, source  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "layout" / "gcc.json"
CUTS = ROOT / "corpora" / "source" / "z02.json"

#: What counts as source. GCC also ships an Ada front end written in Ada and a Modula-2 front
#: end written in Modula-2, and counting those would double the total and tell a reader
#: nothing, because they are separate compilers that happen to live in the same tree. This is
#: the part written in C, in C++, and in GCC's own little languages.
SRC = {".c", ".cc", ".cpp", ".h", ".hh", ".def", ".md", ".opt", ".pd", ".y", ".l"}

#: The top level of the tree, and then the inside of `gcc/`, with one sentence each. The order
#: is the order the lesson walks them in, which is roughly most useful first.
PLACES: tuple[tuple[str, str], ...] = (
    ("gcc", "The compiler. Every other directory here exists to support this one."),
    ("libgcc", "The runtime the compiler emits calls to, for division, unwinding and more."),
    ("libstdc++-v3", "The C++ standard library. A separate project that ships in the tree."),
    ("libgomp", "The OpenMP and OpenACC runtime."),
    ("libsanitizer", "The address and undefined behaviour sanitizer runtimes, from LLVM."),
    ("libcpp", "The preprocessor. Shared by the C, C++, Objective C and Fortran front ends."),
    ("libiberty", "Portability shims and the C++ symbol demangler."),
    ("include", "Headers shared between the compiler and the libraries."),
    ("fixincludes", "Patches for broken system headers. Older than most of you."),
    ("lto-plugin", "The plugin the linker loads so link time optimization can work."),
    ("contrib", "Scripts. Not built, not shipped, and some of them are very useful."),
    ("gcc/*", "The middle end and the driver, loose in the directory with no subdirectory."),
    ("gcc/config", "Every target. The port for your machine is one directory in here."),
    ("gcc/testsuite", "The tests. More files than the rest of the tree, and where to look first."),
    ("gcc/c", "The C front end proper, mostly one very large parser."),
    ("gcc/c-family", "The parts of C the C and C++ front ends share, including the warnings."),
    ("gcc/cp", "The C++ front end. Templates alone are a third of it."),
    ("gcc/fortran", "The Fortran front end."),
    ("gcc/ada", "The Ada front end. The rest of it is written in Ada and not counted here."),
    ("gcc/d", "The D front end."),
    ("gcc/go", "The Go front end."),
    ("gcc/rust", "The Rust front end, the newest one in the tree."),
    ("gcc/m2", "The Modula-2 front end, mostly written in Modula-2 and not counted here."),
    ("gcc/cobol", "The COBOL front end, added in GCC 15."),
    ("gcc/algol68", "The Algol 68 front end, added in GCC 16."),
    ("gcc/objc", "The Objective C front end, on top of the C one."),
    ("gcc/objcp", "Objective C++, which is four files of glue over the other two."),
    ("gcc/analyzer", "The static analyzer behind -fanalyzer. A whole abstract interpreter."),
    ("gcc/lto", "Link time optimization: reading and writing the on disk representation."),
    ("gcc/rtl-ssa", "SSA over RTL, which is newer than you think and used by few passes."),
    ("gcc/diagnostics", "How an error message gets printed, including the SARIF output."),
    ("gcc/text-art", "Drawing diagrams in a terminal, for the analyzer's output."),
    ("gcc/jit", "libgccjit, which lets a program build code with GCC at run time."),
    ("gcc/common", "Per target bits the driver needs before it knows what it is compiling."),
    ("gcc/doc", "The manuals, in Texinfo, so this count sees none of it. Read them anyway."),
    ("gcc/po", "Translations of the diagnostics, in .po files, which this count does not see."),
    ("gcc/ginclude", "The headers GCC installs itself, like stddef.h and stdarg.h."),
    ("gcc/sym-exec", "A small symbolic execution helper used by one optimization pass."),
    ("gcc/custom-sarif-properties", "Schemas for the machine readable diagnostics output."),
    ("gcc/topics", "One file. Sorting for the documentation index."),
)

#: The file extensions GCC gives its own meaning to. A reader who does not know these opens a
#: 33,000 line `.md` file and thinks it is markdown.
KINDS: tuple[dict, ...] = (
    {
        "suffix": ".cc",
        "name": "C++ source",
        "about": "The compiler itself. GCC was C until 2012 and still reads like it in places.",
        "example": "gcc/tree-ssa-ccp.cc",
        "line": 3083,
        "cite": "gcc/tree-ssa-ccp.cc:3083@releases/gcc-16.2.0",
    },
    {
        "suffix": ".h",
        "name": "C++ header",
        "about": "Declarations, and a lot of the accessor macros that are the real API.",
        "example": "gcc/tree-pass.h",
        "line": 45,
        "cite": "gcc/tree-pass.h:45@releases/gcc-16.2.0",
    },
    {
        "suffix": ".def",
        "name": "X macro list",
        "about": "A list included several times with the macro defined differently each time.",
        "example": "gcc/tree.def",
        "line": 295,
        "cite": "gcc/tree.def:295@releases/gcc-16.2.0",
    },
    {
        "suffix": ".md",
        "name": "machine description",
        "about": "Patterns in a Lisp like language saying what a target can do. Not markdown.",
        "example": "gcc/config/aarch64/aarch64.md",
        "line": 2965,
        "cite": "gcc/config/aarch64/aarch64.md:2965@releases/gcc-16.2.0",
    },
    {
        "suffix": ".opt",
        "name": "option list",
        "about": "Every command line flag. The build turns this into options.cc and options.h.",
        "example": "gcc/common.opt",
        "line": 3220,
        "cite": "gcc/common.opt:3220@releases/gcc-16.2.0",
    },
    {
        "suffix": ".pd",
        "name": "pattern description",
        "about": "There is exactly one, match.pd, and it is where most folding lives.",
        "example": "gcc/match.pd",
        "line": 239,
        "cite": "gcc/match.pd:239@releases/gcc-16.2.0",
    },
)

#: The programs in the tree that write source during the build, and what they read. Open one
#: of their outputs and you are reading a program's output, which is why the interesting line
#: is never in the file the error message named.
GENERATORS: tuple[tuple[str, str, str], ...] = (
    ("gcc/genmatch.cc", "gimple-match-N.cc and generic-match-N.cc", "gcc/match.pd"),
    ("gcc/genrecog.cc", "insn-recog.cc", "the target's .md files"),
    ("gcc/genemit.cc", "insn-emit.cc", "the target's .md files"),
    ("gcc/genoutput.cc", "insn-output.cc", "the target's .md files"),
    ("gcc/genattrtab.cc", "insn-attrtab.cc", "the target's .md files"),
    ("gcc/genopinit.cc", "insn-opinit.cc", "the target's .md files"),
    ("gcc/genpreds.cc", "tm-preds.h and insn-preds.cc", "the target's .md files"),
    ("gcc/genmodes.cc", "insn-modes.cc and insn-modes.h", "the target's modes.def"),
    ("gcc/gengtype.cc", "gtype-desc.cc", "every GTY marker in the tree"),
    ("gcc/gencheck.cc", "tree-check.h", "gcc/tree.def"),
    ("gcc/genflags.cc", "insn-flags.h", "the target's .md files"),
    ("gcc/gencodes.cc", "insn-codes.h", "the target's .md files"),
)

#: Files worth knowing by name, whether or not they are the largest. Two of these are here so
#: a reader knows to stay away for now, and the rest are the short ones you can actually read.
NOTABLE: tuple[tuple[str, str], ...] = (
    ("gcc/passes.def", "The whole pass pipeline in order and nothing else. Start here."),
    ("gcc/tree-pass.h", "What a pass is. Read pass_data at the top and stop."),
    ("gcc/tree.def", "Every tree code, one per line, with a comment. A good afternoon."),
    ("gcc/tree-ssa-ccp.cc", "A whole real optimization pass that fits in your head."),
    ("gcc/cfgloop.cc", "Loops, discovered and printed. Small, and it prints things you see."),
    ("gcc/tree-cfg.cc", "The control flow graph over GIMPLE. Large but readable in pieces."),
    ("gcc/match.pd", "Thousands of rewrite rules in a small language. Read a hundred lines."),
    ("gcc/combine.cc", "Instruction combining. Wisdom, accumulated. Not for your first month."),
    ("gcc/dwarf2out.cc", "Debug info. A standards document in disguise. Same advice."),
)

#: One sentence for each of the largest files in `gcc/`. Which files are largest is measured,
#: so if the next release reshuffles the top of the list the recorder stops and asks for a
#: sentence rather than shipping a table with a blank column in it.
BIG_ABOUT: dict[str, str] = {
    "gcc/cp/parser.cc": "The C++ parser, by hand, no generator. C++ is hard to parse.",
    "gcc/config/arm/arm.cc": "The 32 bit Arm port, carrying twenty years of Arm variants.",
    "gcc/config/aarch64/aarch64.cc": "The 64 bit Arm port, including SVE, which is most of it.",
    "gcc/cp/pt.cc": "C++ templates. Substitution, deduction, and the errors you have seen.",
    "gcc/dwarf2out.cc": "Debug info generation. Effectively a standards document in code.",
    "gcc/config/i386/sse.md": "Every x86 vector instruction as a pattern. Machine written feel.",
    "gcc/c/c-parser.cc": "The C parser, also by hand, also with the extensions in it.",
    "gcc/config/i386/i386.md": "The rest of x86, in patterns, since 1988.",
    "gcc/config/rs6000/rs6000.cc": "The PowerPC port.",
    "gcc/config/i386/i386.cc": "The x86 port proper: costs, ABI, and target hooks.",
    "gcc/config/aarch64/arm_neon.h": "The NEON intrinsics header. Generated feel, checked in.",
    "gcc/config/i386/i386-expand.cc": "Turning x86 intrinsics and patterns into insns.",
    "gcc/m2/mc-boot/Gdecl.cc": "Modula-2 bootstrap output, checked in so you can build at all.",
    "gcc/cp/module.cc": "C++20 modules, which is a compiler inside the compiler.",
    "gcc/fortran/trans-intrinsic.cc": "Every Fortran intrinsic, lowered to the middle end.",
    "gcc/config/riscv/riscv.cc": "The RISC-V port, growing fastest of any port in the tree.",
}

#: The six items in the boss fight. `dump` is text a real gcc-16 printed, `path` and `line` are
#: where it came from, and `route` is the way to get from one to the other. Two of them carry a
#: commit, which means the checkout alone cannot answer them and you need the history.
HUNT: tuple[dict, ...] = (
    {
        "key": "loops",
        "dump": ";; 2 loops found",
        "route": "grep",
        "path": "gcc/cfgloop.cc",
        "line": 163,
        "expect": "loops found",
        "about": "The plain case. Take the numbers out, search the rest, one hit.",
        "cite": "gcc/cfgloop.cc:163@releases/gcc-16.2.0",
    },
    {
        "key": "merge",
        "dump": "Merging blocks 2 and 8",
        "route": "grep",
        "path": "gcc/tree-cfg.cc",
        "line": 1980,
        "expect": "Merging blocks",
        "about": "Also plain, but note which file it is in. Nobody would guess tree-cfg.cc.",
        "cite": "gcc/tree-cfg.cc:1980@releases/gcc-16.2.0",
    },
    {
        "key": "simulate",
        "dump": "Simulating statement: _1 = i_3 * 2;",
        "route": "grep",
        "path": "gcc/tree-ssa-propagate.cc",
        "line": 486,
        "expect": "Simulating statement",
        "about": "It was in the ccp1 dump, and it is not in tree-ssa-ccp.cc. The engine that "
        "drives ccp prints it, and three other passes share that engine.",
        "cite": "gcc/tree-ssa-propagate.cc:486@releases/gcc-16.2.0",
    },
    {
        "key": "ccp",
        "dump": "hunt.c.114t.ccp2",
        "route": "passes",
        "path": "gcc/tree-ssa-ccp.cc",
        "line": 3083,
        "expect": "make_pass_ccp",
        "about": "A file name, not a message, so there is nothing to grep for. The name after "
        "the number is the pass, the 2 says it is the second run, and the pass table gets you "
        "the rest of the way.",
        "cite": "gcc/tree-ssa-ccp.cc:3083@releases/gcc-16.2.0",
    },
    {
        "key": "block",
        "dump": "Removing basic block 8",
        "route": "history",
        "path": "gcc/tree-cfg.cc",
        "line": 2193,
        "expect": "Removing basic block",
        "about": "Easy to find and worth asking about. It arrived with the whole GIMPLE and "
        "SSA middle end, in one merge, on one day.",
        "cite": "gcc/tree-cfg.cc:2193@releases/gcc-16.2.0",
        "commit": "6de9cd9a886e",
        "date": "2004-05-13",
        "author": "Diego Novillo",
        "subject": "Merge tree-ssa-20020619-branch into mainline.",
    },
    {
        "key": "pattern",
        "dump": "Applying pattern match.pd:239, gimple-match-6.cc:11451",
        "route": "generated",
        "path": "gcc/match.pd",
        "line": 239,
        "expect": "non_lvalue",
        "about": "There is no gimple-match-6.cc in the tree. The message names its own answer "
        "first and a generated file second, and the commit that put the rule there is the one "
        "that invented match.pd.",
        "cite": "gcc/match.pd:239@releases/gcc-16.2.0",
        "commit": "e0ee10ed5af1",
        "date": "2014-10-24",
        "author": "Richard Biener",
        "subject": "genmatch.c (expr::gen_transform): Use fold_buildN_loc and build_call_expr_loc.",
    },
)

#: A dozen spans of the tree, cut the same way Z01 cuts its snippets and for the same reason.
#: The lesson has to show what a `.md` file looks like and what the line behind a dump message
#: looks like, and a notebook in Colab has no checkout to show it from.
SPANS: tuple[dict, ...] = (
    {
        "name": "def",
        "path": "gcc/tree.def",
        "first": 295,
        "last": 298,
        "cite": "gcc/tree.def:295@releases/gcc-16.2.0",
        "about": "Two tree codes. The file is included several times with DEFTREECODE "
        "defined differently, which is how one list becomes an enum and a table of names.",
    },
    {
        "name": "md",
        "path": "gcc/config/aarch64/aarch64.md",
        "first": 2965,
        "last": 2979,
        "cite": "gcc/config/aarch64/aarch64.md:2965@releases/gcc-16.2.0",
        "about": "One instruction pattern. The RTL it matches, then the assembly to print, "
        "with the register class constraints in a table.",
    },
    {
        "name": "opt",
        "path": "gcc/common.opt",
        "first": 3220,
        "last": 3226,
        "cite": "gcc/common.opt:3220@releases/gcc-16.2.0",
        "about": "Two options. The name, then the flags line, then the help text.",
    },
    {
        "name": "pd",
        "path": "gcc/match.pd",
        "first": 236,
        "last": 239,
        "cite": "gcc/match.pd:236@releases/gcc-16.2.0",
        "about": "One rewrite rule, over five operators at once. x op 0 becomes x.",
    },
    {
        "name": "pass-data",
        "path": "gcc/tree-pass.h",
        "first": 39,
        "last": 47,
        "cite": "gcc/tree-pass.h:39@releases/gcc-16.2.0",
        "about": "The struct every pass fills in, and the comment that documents the whole "
        "chain from a dump file name back to a pass.",
    },
    {
        "name": "passes",
        "path": "gcc/passes.def",
        "first": 80,
        "last": 88,
        "cite": "gcc/passes.def:80@releases/gcc-16.2.0",
        "about": "Nine lines of the pipeline, including the first run of ccp.",
    },
    {
        "name": "make",
        "path": "gcc/tree-ssa-ccp.cc",
        "first": 3082,
        "last": 3086,
        "cite": "gcc/tree-ssa-ccp.cc:3082@releases/gcc-16.2.0",
        "about": "The other end of the chain. passes.def names this function and this file "
        "is the pass.",
    },
    {
        "name": "loops",
        "path": "gcc/cfgloop.cc",
        "first": 160,
        "last": 166,
        "cite": "gcc/cfgloop.cc:160@releases/gcc-16.2.0",
        "about": "Where the loop count at the top of half your dumps comes from.",
    },
    {
        "name": "merge",
        "path": "gcc/tree-cfg.cc",
        "first": 1979,
        "last": 1981,
        "cite": "gcc/tree-cfg.cc:1979@releases/gcc-16.2.0",
        "about": "Three lines, and one of them is a message you have read a hundred times.",
    },
    {
        "name": "simulate",
        "path": "gcc/tree-ssa-propagate.cc",
        "first": 484,
        "last": 488,
        "cite": "gcc/tree-ssa-propagate.cc:484@releases/gcc-16.2.0",
        "about": "Printed by the propagation engine, not by the pass whose dump it lands in.",
    },
    {
        "name": "block",
        "path": "gcc/tree-cfg.cc",
        "first": 2191,
        "last": 2196,
        "cite": "gcc/tree-cfg.cc:2191@releases/gcc-16.2.0",
        "about": "Removing a basic block, and the detail dump behind TDF_DETAILS.",
    },
    {
        "name": "genmatch",
        "path": "gcc/genmatch.cc",
        "first": 911,
        "last": 915,
        "cite": "gcc/genmatch.cc:911@releases/gcc-16.2.0",
        "about": "A program printing the source of a program that prints the message. This is "
        "the only place in the tree the words Applying pattern appear.",
    },
)

_PASS_DATA = re.compile(r"\bpass_data\s+(\w+)\s*(?:=|$)")
_TEMPLATED = re.compile(r"\bpass_data\s+(pass_\w+)\s*<[^>]*>\s*::\s*\w+\s*=")
_LITERAL = re.compile(r'"([^"\n]*)"')
_CLASS = re.compile(r"^\s*class\s+(pass_\w+)\s*:")
_CTOR = re.compile(r":\s*\w+\s*\(\s*(\w+)\s*,")
_MAKE = re.compile(r"^\s*(?:\w+\s+)*make_(pass_\w+)\s*\(")
_USES = re.compile(r"\b(pass_data_\w+)\b")
_NEW = re.compile(r"\bnew\s+(pass_\w+)\s*[(<]")
_NEXT = re.compile(r"NEXT_PASS \((\w+)")


def counted(paths) -> tuple[int, int]:
    """How many source files are under here, and how many lines they hold."""
    files = lines = 0
    for path in paths:
        if path.is_file() and path.suffix in SRC:
            files += 1
            lines += path.read_bytes().count(b"\n")
    return files, lines


def walk(where: str):
    """The files one entry in PLACES covers. `gcc/*` means loose files and no subdirectory."""
    if where == "gcc/*":
        return (GCC_ROOT / "gcc").iterdir()
    return (GCC_ROOT / where).rglob("*")


#: The top level rows in PLACES are the ones worth learning by name, and they are not all of
#: the tree. This row is everything else at the top level added together, so the total in the
#: lesson is the real total and not a total over a list somebody curated.
REST = (
    "the rest",
    "Twenty odd more runtimes, one per language, plus the build machinery. Rarely read.",
)


def places() -> list[dict]:
    rows = []
    for path, about in PLACES:
        files, lines = counted(walk(path))
        rows.append({"path": path, "files": files, "lines": lines, "about": about})

    named = {path for path, _ in PLACES if "/" not in path}
    others = (p for p in GCC_ROOT.iterdir() if p.name not in named and not p.name.startswith("."))
    files, lines = counted(part for entry in others for part in walk(entry.name))
    rows.append({"path": REST[0], "files": files, "lines": lines, "about": REST[1]})
    return rows


def kinds() -> list[dict]:
    """The extension census, over `gcc/` and not counting the testsuite."""
    rows = []
    for spec in KINDS:
        count = sum(
            1 for p in (GCC_ROOT / "gcc").rglob(f"*{spec['suffix']}") if "testsuite" not in p.parts
        )
        rows.append(
            {
                "suffix": spec["suffix"],
                "count": count,
                "name": spec["name"],
                "about": spec["about"],
                "example": f"{spec['example']}:{spec['line']}",
            }
        )
    return rows


def ports() -> tuple[list[str], list[str]]:
    """Every directory under gcc/config, split by whether it has a machine description.

    A directory with a .md file is a target you can compile for. The three without are shared
    operating system support that a real port includes, which is worth seeing rather than
    being told, because the count everybody quotes is the wrong one either way.
    """
    config = GCC_ROOT / "gcc" / "config"
    real, shared = [], []
    for entry in sorted(p for p in config.iterdir() if p.is_dir()):
        (real if any(entry.glob("*.md")) else shared).append(entry.name)
    return real, shared


def passes() -> list[dict]:
    """Every pass in passes.def, resolved to its dump name and the line that defines it.

    GCC has no such table. The dump name is a string inside a `pass_data` initializer and the
    definition is a `make_pass_foo` function, and the two are tied together four different
    ways depending on how old the pass is and whether it is a template. All four are tried.
    """
    dumps: dict[str, str] = {}
    templated: dict[str, dict[str, str]] = {}
    uses: dict[str, str] = {}
    made: dict[str, tuple[str, int]] = {}
    built: dict[str, str] = {}
    news: dict[str, str] = {}

    def name_strings(lines: list[str], start: int) -> tuple[str, ...]:
        """Every string on the first line of the initializer that has one.

        Usually there is one and it is the dump name. A templated pass writes the field as
        `O0 ? "sancov_O0" : "sancov"`, so there are two and which one is right depends on the
        instantiation, and the caller decides.
        """
        for line in lines[start : start + 14]:
            found = _LITERAL.findall(line)
            if found:
                return tuple(found)
        return ()

    def first_string(lines: list[str], start: int) -> str:
        found = name_strings(lines, start)
        return found[0] if found else ""

    for path in sorted((GCC_ROOT / "gcc").rglob("*.cc")):
        if "testsuite" in path.parts:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        where = str(path.relative_to(GCC_ROOT))
        current = ""
        for n, line in enumerate(lines):
            plain = _PASS_DATA.search(line)
            if plain:
                dumps[plain.group(1)] = first_string(lines, n)
            member = _TEMPLATED.search(line)
            if member:
                templated.setdefault(where, {})[member.group(1)] = name_strings(lines, n)
            klass = _CLASS.match(line)
            if klass:
                current = klass.group(1)
            base = _CTOR.search(line)
            if base and current and current not in uses:
                uses[current] = base.group(1)
            maker = _MAKE.match(line)
            if maker and maker.group(1) not in made:
                made[maker.group(1)] = (where, n + 1)
                for body in lines[n : n + 8]:
                    named = _USES.search(body)
                    if named:
                        built[maker.group(1)] = named.group(1)
                        break
                    fresh = _NEW.search(body)
                    if fresh:
                        news[maker.group(1)] = fresh.group(1)
                        break

    def dump_name(name: str) -> str:
        indirect = uses.get(news.get(name, ""))
        for candidate in (
            uses.get(name),
            built.get(name),
            indirect,
            "pass_data_" + name[len("pass_") :],
        ):
            if candidate and dumps.get(candidate):
                return dumps[candidate]
        where = made.get(name, ("", 0))[0]
        for klass, choices in templated.get(where, {}).items():
            if name != klass and not name.startswith(klass + "_"):
                continue
            wants = name.endswith("_O0")
            for choice in choices:
                if choice.endswith("_O0") == wants:
                    return choice
            return choices[0] if choices else ""
        return ""

    order = _NEXT.findall((GCC_ROOT / "gcc" / "passes.def").read_text(encoding="utf-8"))
    rows = []
    for name in sorted(set(order)):
        if name not in made:
            print(f"{name} is in passes.def and has no make_{name} anywhere")
            return []
        where, line = made[name]
        rows.append({"name": name, "dump": dump_name(name), "path": where, "line": line})
    return rows


def biggest(how_many: int = 12) -> list[dict]:
    sized = []
    for path in (GCC_ROOT / "gcc").rglob("*"):
        if path.is_file() and path.suffix in SRC and "testsuite" not in path.parts:
            sized.append((path.read_bytes().count(b"\n"), str(path.relative_to(GCC_ROOT))))
    sized.sort(reverse=True)
    rows = []
    for n, path in sized[:how_many]:
        if path not in BIG_ABOUT:
            print(f"{path} is now in the largest {how_many} and BIG_ABOUT has no line for it")
            return []
        rows.append({"path": path, "lines": n, "about": BIG_ABOUT[path]})
    return rows


def notable() -> list[dict]:
    rows = []
    for path, about in NOTABLE:
        rows.append(
            {
                "path": path,
                "lines": (GCC_ROOT / path).read_bytes().count(b"\n"),
                "about": about,
            }
        )
    return rows


def hunt() -> list[dict]:
    """The six items, with the line each one points at checked against the tree."""
    rows = []
    for spec in HUNT:
        spec = dict(spec)
        written = spec.pop("cite")
        expect = spec.pop("expect")
        want = f"{spec['path']}:{spec['line']}@{PINNED_TAG}"
        if written != want:
            print(f"{spec['key']}: cite says {written}, the answer says {want}")
            return []
        text = (GCC_ROOT / spec["path"]).read_text(encoding="utf-8", errors="replace")
        line = text.split("\n")[spec["line"] - 1]
        if expect not in line:
            print(f"{spec['key']}: {want} does not contain {expect!r}, it is {line.strip()!r}")
            return []
        spec["text"] = line.expandtabs(8).strip()
        rows.append(spec)
    return rows


def pinned_commit() -> str:
    """The commit the submodule is checked out at, so the map says which tree it measured."""
    got = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=GCC_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return got.stdout.strip()


def spans() -> dict:
    """Cut the twelve spans, checking each one's citation against the span it describes."""
    specs = []
    for spec in SPANS:
        spec = dict(spec)
        written = spec.pop("cite")
        want = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if written != want:
            print(f"{spec['name']}: cite says {written}, the span says {want}")
            return {}
        specs.append(spec)
    return source.extract(GCC_ROOT, specs, PINNED_TAG)


def check_kinds() -> bool:
    for spec in KINDS:
        want = f"{spec['example']}:{spec['line']}@{PINNED_TAG}"
        if spec["cite"] != want:
            print(f"{spec['suffix']}: cite says {spec['cite']}, the example says {want}")
            return False
    return True


def main() -> int:
    if not (GCC_ROOT / "gcc" / "passes.def").exists():
        print(f"no GCC tree at {GCC_ROOT}. Run `just gcc-src` first.")
        return 1
    if not check_kinds():
        return 1

    for name in (spec[0] for spec in GENERATORS):
        if not (GCC_ROOT / name).exists():
            print(f"{name} is in GENERATORS and not in the tree")
            return 1

    real, shared = ports()
    table = passes()
    items = hunt()
    large = biggest()
    cuts = spans()
    if not table or not items or not large or not cuts:
        return 1

    body = {
        "tag": PINNED_TAG,
        "commit": pinned_commit(),
        "places": places(),
        "kinds": kinds(),
        "ports": real,
        "portless": shared,
        "generators": [
            {"program": program, "writes": writes, "reads": reads}
            for program, writes, reads in GENERATORS
        ],
        "passes": table,
        "biggest": large,
        "notable": notable(),
        "hunt": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    CUTS.parent.mkdir(parents=True, exist_ok=True)
    CUTS.write_text(json.dumps(cuts, indent=1) + "\n", encoding="utf-8")

    tree = layout.load()
    shown = source.load_extract("z02")
    named = sum(1 for one in tree.passes if one.dump)
    print(f"wrote {OUT.relative_to(ROOT)} at {tree.tag}")
    print(f"wrote {CUTS.relative_to(ROOT)}, {len(shown)} spans, {shown.lines()} lines")
    print(f"{tree.files} source files, {tree.lines} lines, {len(tree.places)} places")
    print(f"{len(tree.ports)} ports with a machine description, {len(tree.portless)} without")
    print(f"{len(tree.passes)} passes in passes.def, {named} of them resolve to a dump name")
    print(f"{len(tree.hunt)} hunt items, {sum(c.historic for c in tree.hunt)} needing history")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
