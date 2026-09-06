"""Record what the preprocessor does, on two targets, and the libcpp code that does it.

    python lessons/f02-tokens-not-text/record.py
    python lessons/f02-tokens-not-text/record.py --check

Four kinds of evidence go into `corpora/cpp/f02.json`:

  macros      `-dM -E` on an empty file, here and on x86-64 Linux, and again under four
              flags, because the table a compiler starts from is target specific and the
              things that change it are not the things a reader expects
  expansions  five small files through `-E -P`, each one an expansion rule that text
              substitution cannot produce, recorded on both targets so the reader can see
              that the rules travel and the vocabulary does not
  probes      every pair in `gxray.cpp.PASTES` put next to each other through an empty
              macro, plus nine pairs that need nothing, which is the half that makes it a
              rule and not a habit
  headers     `-H` on one `#include <stdio.h>`, here and there, and on four headers of the
              lesson's own that differ by one line after the `#endif`

Nothing here needs a linker and nothing writes an object file. `-E` stops after the
preprocessor, which is what makes it safe to record a file with `\\x` and `1.` in it.

The x86-64 half goes through the Compiler Explorer API and is cached in
`tools/cecache/store`, so this is a live request once and a file lookup afterwards.

`--check` re-asserts every fact the notebook states, against what is already committed and
without running a compiler, which is what the test suite calls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import cpp, source  # noqa: E402
from gxray.driver import CEBackend  # noqa: E402
from tools.cecache import Cache  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "cpp" / "f02.json"
CUTS = ROOT / "corpora" / "source" / "f02.json"

#: The local compiler, the same Homebrew GCC 16.2.0 that F01 recorded, so a line cited from
#: `vendor/gcc` is a line in the program that produced this output.
GCC = os.environ.get("GXRAY_GCC", "gcc-16")

#: The other one. Same release, x86-64 Linux, reached through Compiler Explorer.
CE_COMPILER = "cg162"

#: The flag sets the macro table is dumped under. Empty first, because that is the baseline
#: every other one is a difference from.
FLAGS: tuple[tuple[str, str, str], ...] = (
    ("local", "", "Nothing asked for. This is what an empty file already knows"),
    ("elsewhere", "", "The same GCC release, built for x86-64 Linux by other people"),
    ("optimized", "-O2", "One flag, and the table is not one longer"),
    ("c23", "-std=c23", "The flag that names a language standard, and does not change it"),
    ("fast", "-ffast-math", "The flag that tells the library your arithmetic is a lie"),
)

#: The five expansion demonstrations. Each source is a whole file, run through `-E -P` so
#: that what comes back is the expansion and nothing else.
DEMOS: tuple[tuple[str, str, str], ...] = (
    (
        "spacing",
        "A space in the output that is in none of the input, twice over",
        """\
#define EMPTY
#define PLUS +
a+EMPTY+b
a PLUS +b
a+ +b
""",
    ),
    (
        "prescan",
        "Why stringifying a macro takes two macros, and what the first one is for",
        """\
#define PLUS +
#define STR(x) #x
#define XSTR(x) STR(x)
STR(PLUS)
XSTR(PLUS)
""",
    ),
    (
        "paste",
        "The one operator that makes two tokens into one, and what it costs",
        """\
#define CAT(x, y) x ## y
#define PLUS +
CAT(a, b)
CAT(PLUS, PLUS)
""",
    ),
    (
        "paint",
        "A macro that names itself, and one that names a macro that names it back",
        """\
#define foo foo + 1
#define A B
#define B A
foo
A
""",
    ),
    (
        "invocation",
        "A function-like macro is not expanded unless the next token is an open bracket",
        """\
#define f(x) [x]
f(1)
f
f (2)
""",
    ),
)

#: The four headers, which differ from each other by one line. `stray.h` is the whole point:
#: one declaration after the `#endif` and the file is opened again on every `#include`.
HEADERS: dict[str, str] = {
    "clean.h": "#ifndef CLEAN_H\n#define CLEAN_H\nint clean_thing;\n#endif\n",
    "untidy.h": (
        "#ifndef UNTIDY_H\n#define UNTIDY_H\nint untidy_thing;\n#endif\n"
        "/* a comment, outside the guard */\n"
    ),
    "stray.h": (
        "#ifndef STRAY_H\n#define STRAY_H\nint stray_thing;\n#endif\ntypedef int stray_t;\n"
    ),
    "bare.h": "int bare_thing;\n",
}

#: The file that includes each of them twice, which is the experiment.
GUARDS_C = "".join(f'#include "{name}"\n#include "{name}"\n' for name in HEADERS) + "int t;\n"

#: The same four, each included once. GCC only names a file as wanting a guard if it read it
#: exactly once (libcpp/files.cc:2217), so the advice arrives for the file you have not yet
#: had trouble with, and never for the one you have.
ONCE_C = "".join(f'#include "{name}"\n' for name in HEADERS) + "int t;\n"

#: One `#include <stdio.h>`, twice, which is the number that surprises people.
STDIO_C = '#include <stdio.h>\n#include <stdio.h>\nint main(void) { return puts("x") < 0; }\n'

#: The program the macro tables are dumped from. A comment rather than an empty file, because
#: the far end refuses a file with nothing in it, and because a comment is the one thing a
#: reader can be sure defines no macros: it is gone before the table is printed.
NOTHING = "/* not one declaration */\n"

#: Where each span comes from. `first` and `last` are inclusive lines in the pinned tree and
#: `cite` is asserted against `first`, so a span that moves cannot keep a citation pointing
#: at code that is no longer there.
SPANS: tuple[dict, ...] = (
    {
        "name": "padding",
        "path": "libcpp/include/cpplib.h",
        "first": 152,
        "last": 164,
        "about": "The end of the token type list, and the one that is whitespace",
        "cite": "libcpp/include/cpplib.h:152@releases/gcc-16.2.0",
    },
    {
        "name": "token",
        "path": "libcpp/include/cpplib.h",
        "first": 261,
        "last": 294,
        "about": "What a token is: a location, a type, some flags, and one union",
        "cite": "libcpp/include/cpplib.h:261@releases/gcc-16.2.0",
    },
    {
        "name": "avoid-paste",
        "path": "libcpp/lex.cc",
        "first": 4723,
        "last": 4791,
        "about": "The whole rule for which two tokens cannot be printed next to each other",
        "cite": "libcpp/lex.cc:4723@releases/gcc-16.2.0",
    },
    {
        "name": "spacing",
        "path": "gcc/c-family/c-ppoutput.cc",
        "first": 244,
        "last": 268,
        "about": "The three reasons a space is printed, and the comment that admits it",
        "cite": "gcc/c-family/c-ppoutput.cc:244@releases/gcc-16.2.0",
    },
    {
        "name": "markers",
        "path": "gcc/c-family/c-ppoutput.cc",
        "first": 618,
        "last": 628,
        "about": "Where a line marker comes from, and the two digits nothing passes in",
        "cite": "gcc/c-family/c-ppoutput.cc:618@releases/gcc-16.2.0",
    },
    {
        "name": "marker-flags",
        "path": "gcc/doc/cpp.texi",
        "first": 4072,
        "last": 4088,
        "about": "What each digit means, from the one place in the tree that says so",
        "cite": "gcc/doc/cpp.texi:4072@releases/gcc-16.2.0",
    },
    {
        "name": "dump",
        "path": "gcc/c-family/c-ppoutput.cc",
        "first": 903,
        "last": 918,
        "about": "Why -dM does not print the five macros everybody can name",
        "cite": "gcc/c-family/c-ppoutput.cc:903@releases/gcc-16.2.0",
    },
    {
        "name": "builtins",
        "path": "libcpp/init.cc",
        "first": 448,
        "last": 476,
        "about": "The macros that are C functions, because no string could be right",
        "cite": "libcpp/init.cc:448@releases/gcc-16.2.0",
    },
    {
        "name": "paint",
        "path": "libcpp/macro.cc",
        "first": 1589,
        "last": 1590,
        "about": "Two lines, and the reason a macro that names itself terminates",
        "cite": "libcpp/macro.cc:1589@releases/gcc-16.2.0",
    },
    {
        "name": "guard",
        "path": "libcpp/files.cc",
        "first": 858,
        "last": 861,
        "about": "The include guard optimization, which is one comment and one condition",
        "cite": "libcpp/files.cc:858@releases/gcc-16.2.0",
    },
    {
        "name": "advice",
        "path": "libcpp/files.cc",
        "first": 2214,
        "last": 2219,
        "about": "Who gets told to write a guard, and the condition that means it is not you",
        "cite": "libcpp/files.cc:2214@releases/gcc-16.2.0",
    },
    {
        "name": "trace",
        "path": "libcpp/line-map.cc",
        "first": 1589,
        "last": 1600,
        "about": "What -H prints, and the reason a skipped file leaves no line",
        "cite": "libcpp/line-map.cc:1589@releases/gcc-16.2.0",
    },
)


class Watched(Cache):
    """The ordinary cache, keeping a note of which entries went through it.

    `tools.tier0.orphans` insists the registry accounts for the store exactly, and it works
    that out from an experiment's corpus entry. This lesson's requests are not corpus
    entries, so the list has to come from here instead.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self.used: list[str] = []

    def fetch(self, key: str, send) -> dict:
        self.used.append(key)
        return super().fetch(key, send)


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)


def scrub(text: str, work: Path) -> str:
    """Take the recording machine out of the recording.

    Only the directory the recorder ran in, which is a temporary one with a different name
    on every run and would make two recordings of the same command look like a difference.
    On this platform the same directory has two names, one of them a symbolic link, and GCC
    prints whichever one it resolved, so both go.

    The SDK and compiler paths stay. Where your headers actually are is the subject of one
    of the sections, and a lesson that hid it would be teaching nothing.
    """
    for where in (str(work.resolve()), str(work)):
        text = text.replace(where + "/", "").replace(where, ".")
    return text


def preprocess(work: Path, name: str, text: str, *args: str) -> str:
    """One file through `-E`, with the result on stdout and nothing else run."""
    (work / name).write_text(text, encoding="utf-8")
    done = run([GCC, "-E", *args, name], work)
    if done.returncode != 0:
        raise SystemExit(f"{GCC} -E {' '.join(args)} {name} failed:\n{done.stderr}")
    return done.stdout


def macro_text(work: Path, flags: str) -> str:
    """Every macro defined before a line of the program is read."""
    args = ["-dM", "-E", "-x", "c", "-", *flags.split()]
    done = subprocess.run(
        [GCC, *args], cwd=work, input=NOTHING, capture_output=True, text=True, check=False
    )
    if done.returncode != 0 or not done.stdout.strip():
        raise SystemExit(f"{GCC} -dM printed nothing:\n{done.stderr}")
    return done.stdout


def probe_source() -> tuple[str, list[tuple[str, str, str, str]]]:
    """A file that puts every pair next to each other, and the list of what it asked.

    `ID(x) x` rather than an empty macro, because an empty macro between two identifiers is
    not between anything: `xEy` is one identifier and the preprocessor never sees a pair at
    all. Wrapping each side in a macro call is the only way to make two tokens adjacent
    without a character of whitespace anywhere in the line.
    """
    asked = [(one.left, one.right, one.case, one.about) for one in cpp.PASTES]
    kept = "nothing, and that is the point"
    asked += [(left, right, "", kept) for left, right in cpp.KEPT_TOGETHER]
    lines = ["#define ID(x) x"] + [f"ID({left})ID({right})" for left, right, _, _ in asked]
    return "\n".join(lines) + "\n", asked


def probes(work: Path, back: CEBackend) -> list[dict]:
    """Every pair, run, with the output line each one produced kept next to it."""
    text, asked = probe_source()
    got = [line for line in preprocess(work, "probe.c", text, "-P").split("\n") if line.strip()]
    if len(got) != len(asked):
        raise SystemExit(f"probed {len(asked)} pairs and got {len(got)} lines back")
    return [
        {"left": left, "right": right, "case": case, "about": about, "output": line}
        for (left, right, case, about), line in zip(asked, got, strict=True)
    ]


def elsewhere_output(back: CEBackend, text: str, *args: str) -> str:
    """The same file through the x86-64 Linux compiler.

    Compiler Explorer hands preprocessed output back in the field it would otherwise put
    assembly in, because from its side `-E` is a compilation whose output file happens to
    contain C.
    """
    result = back.compile(text, *args)
    if not result.asm.strip():
        raise SystemExit(f"{CE_COMPILER} returned nothing for {args}:\n{result.stderr[:2000]}")
    return result.asm if result.asm.endswith("\n") else result.asm + "\n"


def builtin() -> dict:
    """The macros libcpp defines in C rather than in a string, counted in the pinned tree.

    `array` is `builtin_array`, the ones with a C function behind them. `fixed` is the ones
    `cpp_init_builtins` defines with a value it can write down, which is why `__STDC__` is
    in a dump of every macro and `__FILE__` is not.
    """
    text = (GCC_ROOT / "libcpp" / "init.cc").read_text(encoding="utf-8", errors="replace")
    block = text[text.index("static const struct builtin_macro builtin_array[]") :]
    block = block[: block.index("\n};")]
    array = re.findall(r'B\s*\(\s*"([^"]+)"', block)
    fixed = re.findall(r'_cpp_define_builtin\s*\(\s*pfile,\s*"(\w+)', text)
    return {"array": array, "fixed": sorted(set(fixed))}


def record() -> dict:
    version = run([GCC, "--version"], ROOT).stdout.splitlines()[0]
    target = run([GCC, "-dumpmachine"], ROOT).stdout.strip()
    watched = Watched()
    back = CEBackend(CE_COMPILER, cache=watched)
    remote_version, remote_target = back.version(), back.target()

    with tempfile.TemporaryDirectory(prefix="f02-") as tmp:
        work = Path(tmp)
        for name, text in HEADERS.items():
            (work / name).write_text(text, encoding="utf-8")

        macros = {}
        for label, flags, about in FLAGS:
            if label == "elsewhere":
                text = elsewhere_output(back, NOTHING, "-dM", "-E")
                macros[label] = {
                    "text": text,
                    "flags": flags,
                    "compiler": remote_version,
                    "target": remote_target,
                    "about": about,
                }
                continue
            macros[label] = {
                "text": macro_text(work, flags),
                "flags": flags,
                "compiler": version,
                "target": target,
                "about": about,
            }

        expansions = {}
        for name, about, text in DEMOS:
            expansions[name] = {
                "about": about,
                "source": text,
                "output": preprocess(work, f"{name}.c", text, "-P"),
                "elsewhere": elsewhere_output(back, text, "-E", "-P"),
            }
        markers_c = '#include "clean.h"\nint before;\n#include "stray.h"\nint after;\n'
        expansions["markers"] = {
            "about": "The same file with the line markers left in, which is the default",
            "source": markers_c,
            "output": scrub(preprocess(work, "markers.c", markers_c), work),
            "elsewhere": "",
        }

        traces = {
            "local": {
                "text": scrub(trace(work, "stdio.c", STDIO_C), work),
                "about": "One #include <stdio.h>, on a machine with an Apple SDK on it",
            },
            "elsewhere": {
                "text": back.compile(STDIO_C, "-H", "-E").stderr,
                "about": "The same two lines on x86-64 Linux, where the headers are glibc's",
            },
            "guards": {
                "text": scrub(trace(work, "guards.c", GUARDS_C), work),
                "about": "Four headers of this lesson's own, each one included twice",
            },
            "once": {
                "text": scrub(trace(work, "once.c", ONCE_C), work),
                "about": "The same four, each included once, which is when GCC gives advice",
            },
        }

        return {
            "recorded": date.today().isoformat(),
            "tag": PINNED_TAG,
            "compiler": version,
            "target": target,
            # Which Compiler Explorer entries this recording stands for, written by the code
            # that made the requests rather than kept by hand next to it.
            "cache": sorted(set(watched.used)),
            "headers_source": HEADERS,
            "macros": macros,
            "expansions": expansions,
            "probes": probes(work, back),
            "headers": traces,
            "builtin": builtin(),
        }


def trace(work: Path, name: str, text: str) -> str:
    """`-H` on one file. The tree goes to stderr and the preprocessed output is thrown away."""
    (work / name).write_text(text, encoding="utf-8")
    done = run([GCC, "-H", "-E", "-o", os.devnull, name], work)
    if done.returncode != 0:
        raise SystemExit(f"{GCC} -H -E {name} failed:\n{done.stderr}")
    return done.stderr


def spans() -> dict:
    for spec in SPANS:
        want = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if spec["cite"] != want:
            print(f"{spec['name']}: cite says {spec['cite']}, the span starts at {want}")
            raise SystemExit(1)
    wanted = [{k: v for k, v in spec.items() if k != "cite"} for spec in SPANS]
    return source.extract(GCC_ROOT, wanted, PINNED_TAG)


def check(rec: cpp.Recording) -> list[str]:
    """Every fact the notebook states about the recording, asserted here instead of in prose.

    Most of these are statements about GCC 16.2.0 on two targets and not about C. That is
    what this function is for: the paragraph next door cannot notice it has gone stale.
    """
    wrong: list[str] = []

    def want(condition: bool, saying: str) -> None:
        if not condition:
            wrong.append(saying)

    local, remote = rec.macros("local"), rec.macros("elsewhere")
    for label in ("local", "elsewhere", "optimized", "c23", "fast"):
        table = rec.macros(label)
        want(len(table) > 300, f"the {label} table has {len(table)} macros, which is too few")
        want("__GNUC__" in table, f"the {label} table has no __GNUC__, so it is not GCC's")
    want(
        len(local) != len(remote),
        f"both targets define {len(local)} macros, which makes the comparison pointless",
    )
    want(
        local.only_in(remote) != [] and remote.only_in(local) != [],
        "the two targets now agree on every macro name, and a section compares them",
    )
    want(
        local.differing(remote) != [],
        "no macro is defined on both targets to a different value, and a section shows some",
    )

    #: The flag deltas. Each one is a claim in the notebook about what a flag did.
    optimized = rec.macros("optimized")
    want(
        optimized.only_in(local) == ["__OPTIMIZE__"],
        f"-O2 now adds {optimized.only_in(local)}, and the section says it adds __OPTIMIZE__",
    )
    want(
        local.only_in(optimized) == ["__NO_INLINE__"],
        f"-O2 now removes {local.only_in(optimized)}, and the section says __NO_INLINE__",
    )
    want(
        len(optimized) == len(local),
        f"-O2 changes the count from {len(local)} to {len(optimized)}, and the section says"
        " counting is the wrong question",
    )
    c23 = rec.macros("c23")
    want(
        c23.only_in(local) == ["__STRICT_ANSI__"],
        f"-std=c23 now adds {c23.only_in(local)}, and the section says only __STRICT_ANSI__",
    )
    want(
        c23.differing(local) == [],
        f"-std=c23 now changes {c23.differing(local)}, and the section says it changes no value",
    )
    want(
        local["__STDC_VERSION__"].body == c23["__STDC_VERSION__"].body == "202311L",
        "__STDC_VERSION__ is no longer 202311L with and without -std=c23, and a section says"
        " asking for C23 is not what put it there",
    )
    fast = rec.macros("fast")
    want(
        "__FAST_MATH__" in fast,
        "-ffast-math no longer defines __FAST_MATH__, which is how a header hears about it",
    )
    want(
        len(fast.only_in(local)) > 3 and fast.differing(local) != [],
        f"-ffast-math now adds {len(fast.only_in(local))} macros and changes"
        f" {len(fast.differing(local))}, and the section says one flag moves a great many",
    )

    #: The builtins. Twenty of them are C functions, and a dump of every macro prints one,
    #: which is the section about the list that is not the list.
    built = rec.builtin
    want(len(built.array) == 20, f"builtin_array has {len(built.array)} entries, not 20")
    for name in ("__FILE__", "__LINE__", "__COUNTER__", "__has_include", "_Pragma"):
        want(name in built.array, f"{name} is no longer one of libcpp's built-in macros")
    missing = built.missing_from(local)
    want(
        len(missing) == 19,
        f"{len(missing)} of the built-ins are missing from a dump of every macro, not 19",
    )
    want(
        "__STDC__" not in missing,
        "__STDC__ is now missing from the dump too, and the section says it is the exception",
    )

    #: The spacing rule, which is the lesson.
    spacing = rec.expansion("spacing")
    lines = spacing.pairs()
    want(len(lines) == 3, f"the spacing demo has {len(lines)} lines in it, not 3")
    glued = [(was, now) for was, now in lines if "+ +" in now]
    want(len(glued) == 3, f"{len(glued)} of the spacing lines came out with a gap in, not 3")
    want(
        any(" " not in was and "+ +" in now for was, now in lines),
        "no line in the spacing demo gained a space it did not have, which is the whole demo",
    )
    want(
        lines[0] == ("a+EMPTY+b", "a+ +b"),
        f"a+EMPTY+b now comes out as {lines[0][1]!r}, and the section says a+ +b",
    )
    want(
        lines[1:] == [("a PLUS +b", "a + +b"), ("a+ +b", "a+ +b")],
        f"the other two spacing lines now come out as {lines[1:]}",
    )

    prescan = rec.expansion("prescan")
    want(
        prescan.pairs()[-2][1].strip() == '"PLUS"',
        f"STR(PLUS) now comes out as {prescan.pairs()[-2][1]!r}, not the name unexpanded",
    )
    want(
        prescan.pairs()[-1][1].strip() == '"+"',
        f"XSTR(PLUS) now comes out as {prescan.pairs()[-1][1]!r}, not the expansion",
    )

    paint = rec.expansion("paint")
    want(
        paint.pairs()[-2][1].strip() == "foo + 1",
        f"a macro naming itself now expands to {paint.pairs()[-2][1]!r}",
    )
    want(
        paint.pairs()[-1][1].strip() == "A",
        f"two macros naming each other now expand to {paint.pairs()[-1][1]!r}",
    )

    invocation = rec.expansion("invocation")
    want(
        [now.strip() for _, now in invocation.pairs()][-3:] == ["[1]", "f", "[2]"],
        f"the invocation demo now gives {[n.strip() for _, n in invocation.pairs()][-3:]}",
    )

    for name in ("spacing", "prescan", "paste", "paint", "invocation"):
        want(
            rec.expansion(name).agrees,
            f"the {name} demo expands differently on the two targets, which cannot be right",
        )

    #: Every pair, and the nine that get nothing.
    want(
        len(rec.probes) == len(cpp.PASTES) + len(cpp.KEPT_TOGETHER),
        f"{len(rec.probes)} pairs were probed, and the table asks for"
        f" {len(cpp.PASTES) + len(cpp.KEPT_TOGETHER)}",
    )
    for one in rec.probes:
        if one.case:
            want(one.spaced, f"{one.left!r} next to {one.right!r} came out as {one.output!r}")
        else:
            want(
                not one.spaced,
                f"{one.left!r} and {one.right!r} were separated, and nothing should separate them",
            )
    want(
        len(rec.spaced) == len(cpp.PASTES),
        f"{len(rec.spaced)} pairs got a space, and the table lists {len(cpp.PASTES)}",
    )
    cases = {one.case for one in cpp.PASTES}
    want(len(cases) == 17, f"the table covers {len(cases)} case labels, and the section says 17")
    for one in rec.probes:
        if one.case:
            want(
                cpp.inserted_spaces(one.left + one.right, one.output.strip()) == 1,
                f"{one.left}{one.right} came out as {one.output.strip()!r}, which is not the"
                " same two tokens with one space between them",
            )

    #: Line markers.
    found = cpp.markers(rec.expansion("markers").output)
    want(len(found) > 4, f"the marker demo has {len(found)} markers in it, which is too few")
    want(
        any(one.entering for one in found) and any(one.returning for one in found),
        "no marker in the demo says it is entering a file, or none says it is returning",
    )
    want(
        [one.file for one in found].count("clean.h") == 1,
        "clean.h is no longer entered exactly once in the marker demo",
    )

    #: The include trees.
    stdio = rec.headers("local")
    want(len(stdio.files) > 20, f"one #include <stdio.h> opened {len(stdio.files)} files, not many")
    want(stdio.depth >= 4, f"the stdio tree is {stdio.depth} deep, which is not a tree")
    want(
        rec.headers("elsewhere").files != stdio.files,
        "the two targets now include the same header files, which cannot be right",
    )

    guards = rec.headers("guards")
    want(
        guards.opened_twice == ["bare.h", "stray.h"],
        f"the headers opened twice are {guards.opened_twice}, not bare.h and stray.h",
    )
    want(
        [one.path for one in guards].count("clean.h") == 1,
        "a properly guarded header is now opened twice, and the section says it is not",
    )
    want(
        guards.guards_wanted == (),
        f"-H now suggests a guard for {list(guards.guards_wanted)} in the file that includes"
        " everything twice, and the section says it suggests nothing there",
    )

    once = rec.headers("once")
    want(
        once.opened_twice == [],
        f"including each header once opened {once.opened_twice} twice, which is not once",
    )
    want(
        sorted(one.rsplit("/", 1)[-1] for one in once.guards_wanted) == ["bare.h", "stray.h"],
        f"-H now suggests guards for {list(once.guards_wanted)}, not bare.h and stray.h",
    )
    return wrong


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="assert against what is already there")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.check:
        if shutil.which(GCC) is None:
            print(f"no {GCC} on PATH. Set GXRAY_GCC, or read B01 and build one.")
            return 1
        if not (GCC_ROOT / "libcpp" / "init.cc").is_file():
            print(f"no GCC tree at {GCC_ROOT}. Run `just gcc-src` first.")
            return 1
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(record(), indent=1) + "\n", encoding="utf-8")
        CUTS.parent.mkdir(parents=True, exist_ok=True)
        CUTS.write_text(json.dumps(spans(), indent=1) + "\n", encoding="utf-8")

    rec = cpp.load("f02")
    shown = source.load_extract("f02")
    wrong = check(rec)
    for line in wrong:
        print(f"  {line}")
    verb = "checked" if args.check else "wrote"
    sizes = ", ".join(f"{label} {len(table)}" for label, table in rec.tables.items())
    print(
        f"{verb} {OUT.relative_to(ROOT)}, {len(rec.tables)} macro tables ({sizes}), "
        f"{len(rec.expansions)} expansions, {len(rec.probes)} pairs, recorded {rec.recorded}"
    )
    print(f"{verb} {CUTS.relative_to(ROOT)}, {len(shown)} spans, {shown.lines()} lines")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
