"""Read the pinned checkout once and write what B01 needs to talk about configuring it.

    just corpus-b01
    python lessons/b01-the-build/record.py

This needs `vendor/gcc` and nothing else. It writes two files. `corpora/configure/gcc.json` is
the structured part, which `gxray.configure` reads, and `corpora/source/b01.json` is eleven
spans of the real thing, which `gxray.source` reads. Between them the notebook runs in Colab
against a tree it does not have.

Everything counted here is counted. The front end table comes from the `config-lang.in`
files, the checking levels from the loop in `gcc/configure.ac`, the library minimums from
the two `AC_TRY_COMPILE` blocks per library, and the option counts from the help text of the
generated `configure` scripts, which is what a reader actually sees when they run
`./configure --help`.

What is typed in is the one sentence of what each span is showing. The parsers reuse
`tools.bpc.buildsys`, which is the same reader BP-BUILD generates its tables from, so the
lesson and the blueprint cannot drift into disagreeing about how many front ends there are.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import configure, source  # noqa: E402
from tools.bpc import buildsys  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "configure" / "gcc.json"
CUTS = ROOT / "corpora" / "source" / "b01.json"

#: The top of the checkout, which is where citations are relative to and where the configure
#: script a reader runs lives, and the compiler directory inside it, which is where the
#: second configure script and every front end declaration live.
TOP = GCC_ROOT
COMPILER = GCC_ROOT / "gcc"

#: A version test in `configure.ac`, which is written as a macro call with three numbers in
#: it. Each library gets two of these, a hard minimum and a recommended one, in that order.
VERSION = re.compile(r"(?P<macro>GCC_GMP|MPFR|MPC)_VERSION_NUM\((?P<a>\d+),(?P<b>\d+),(?P<c>\d+)\)")

#: What the error message says, when the check fails. Quoted separately from the check
#: itself because the two do not have to agree and for GMP they do not.
SAID = re.compile(
    r"Building GCC requires GMP (?P<gmp>[\d.]+)\+, "
    r"MPFR (?P<mpfr>[\d.]+)\+ and MPC (?P<mpc>[\d.]+)\+"
)

#: One option in the help text of a generated `configure`. Autoconf indents each one by two
#: spaces and wraps the description under it, so the anchor is the indentation.
OPTION = re.compile(r"^  --(?:enable|with)-(?P<name>[\w-]+)", re.MULTILINE)

#: The two placeholders autoconf puts at the top of each list. They are not options, they
#: are the syntax, and counting them would overstate every total by one.
BOILERPLATE = ("FEATURE", "PACKAGE")

#: The spans of real source the lesson prints, in the order it prints them. The `about` is
#: the caption, and the citation next to it is what `refcheck` pins, which is why each one
#: is written out as a literal rather than built from the numbers.
SPANS: tuple[dict, ...] = (
    {
        "name": "intree",
        "path": "configure.ac",
        "first": 222,
        "last": 226,
        "about": "Build in the source tree once and you can never build out of it again",
        "cite": "configure.ac:222@releases/gcc-16.2.0",
    },
    {
        "name": "gmp",
        "path": "configure.ac",
        "first": 1790,
        "last": 1804,
        "about": "Two thresholds for one library, and a third answer between them",
        "cite": "configure.ac:1790@releases/gcc-16.2.0",
    },
    {
        "name": "message",
        "path": "configure.ac",
        "first": 1880,
        "last": 1884,
        "about": "The error you get, and a comment asking somebody to keep it honest",
        "cite": "configure.ac:1880@releases/gcc-16.2.0",
    },
    {
        "name": "languages",
        "path": "configure.ac",
        "first": 2310,
        "last": 2321,
        "about": "How the default language set is worked out, by sourcing every front end",
        "cite": "configure.ac:2310@releases/gcc-16.2.0",
    },
    {
        "name": "always",
        "path": "configure.ac",
        "first": 2407,
        "last": 2407,
        "about": "C is not a language you enable, it is the one you cannot turn off",
        "cite": "configure.ac:2407@releases/gcc-16.2.0",
    },
    {
        "name": "release",
        "path": "gcc/configure.ac",
        "first": 640,
        "last": 645,
        "about": "One empty file decides how slow your compiler is",
        "cite": "gcc/configure.ac:640@releases/gcc-16.2.0",
    },
    {
        "name": "default",
        "path": "gcc/configure.ac",
        "first": 646,
        "last": 663,
        "about": "The checking flag, its default, and the word prepended to whatever you pass",
        "cite": "gcc/configure.ac:646@releases/gcc-16.2.0",
    },
    {
        "name": "declaration",
        "path": "gcc/rust/config-lang.in",
        "first": 27,
        "last": 33,
        "about": "A front end declaring itself, in five lines of shell",
        "cite": "gcc/rust/config-lang.in:27@releases/gcc-16.2.0",
    },
    {
        "name": "version",
        "path": "gcc/gcc.cc",
        "first": 7728,
        "last": 7737,
        "about": "Where `gcc -v` gets the configure line it reads back to you",
        "cite": "gcc/gcc.cc:7728@releases/gcc-16.2.0",
    },
    {
        "name": "plugin",
        "path": "gcc/plugin.cc",
        "first": 1012,
        "last": 1023,
        "about": "Why the configure line is not trivia: a plugin has to match it exactly",
        "cite": "gcc/plugin.cc:1012@releases/gcc-16.2.0",
    },
    {
        "name": "stamp",
        "path": "gcc/Makefile.in",
        "first": 2803,
        "last": 2807,
        "about": "A generator program running, and the empty file that records that it did",
        "cite": "gcc/Makefile.in:2803@releases/gcc-16.2.0",
    },
)


def pinned_commit() -> str:
    """The commit the submodule is actually at, so the recording says what it read."""
    done = subprocess.run(
        ["git", "-C", str(TOP), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def resolve(value: str, fields: dict[str, str], depth: int = 0) -> str:
    """Substitute `$name` from the same declaration, because two of them do that.

    The D front end writes `target_libs="$phobos_target_libs"` and sets that variable four
    lines earlier. A reader that does not follow the reference reports D as needing a
    library called `$phobos_target_libs`, which is not a thing.
    """
    if depth > 4 or "$" not in value:
        return value
    out = re.sub(r"\$(\w+)", lambda m: fields.get(m.group(1), m.group(0)), value)
    return out if out == value else resolve(out, fields, depth + 1)


def languages() -> list[dict]:
    """Every front end, from its own declaration rather than from a list somebody keeps.

    `build_by_default` is the field that decides whether a plain `./configure` builds it,
    and a declaration that does not mention it is opting in, which is why the default here
    is yes and not no.
    """
    rows = []
    for front in buildsys.declarations(COMPILER):
        libs = resolve(front.get("target_libs"), front.fields).replace("target-", "").split()
        program = resolve(front.get("compilers"), front.fields).replace("$(exeext)", "").split()
        rows.append(
            {
                "name": front.get("language"),
                "directory": front.directory,
                "compiler": program[0] if program else "",
                "default": front.get("build_by_default", "yes").strip('"') != "no",
                "boot": front.get("boot_language", "no").strip('"') == "yes",
                "libs": [lib for lib in libs if not lib.startswith("$")],
            }
        )
    return rows


def checking() -> dict:
    """The four levels, every individual flag, and which default this tree gets."""
    turns_on, _, _ = buildsys.checking(COMPILER)
    flags = sorted(name for name in turns_on if name not in buildsys.LEVELS)
    phase = (COMPILER / "DEV-PHASE").read_text(encoding="utf-8").strip()
    return {
        "levels": [buildsys.label(level).replace("`", "") for level in buildsys.LEVELS],
        "flags": flags,
        "default": "release" if phase != "experimental" else "yes,extra",
        "development": "yes,extra",
        "release": phase != "experimental",
    }


def requires() -> list[dict]:
    """The three libraries, each with the version it refuses below and the one it likes."""
    text = (TOP / "configure.ac").read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    for m in VERSION.finditer(text):
        key = m.group("macro").removeprefix("GCC_").lower()
        found.setdefault(key, []).append(f"{m.group('a')}.{m.group('b')}.{m.group('c')}")
    said = SAID.search(text)
    if said is None:
        raise SystemExit("configure.ac no longer says which versions it requires")
    rows = []
    for key in ("gmp", "mpfr", "mpc"):
        pair = found.get(key, [])
        if len(pair) != 2:
            raise SystemExit(f"{key} has {len(pair)} version tests in configure.ac, expected 2")
        rows.append({"library": key, "hard": pair[0], "good": pair[1], "said": said.group(key)})
    return rows


def knobs() -> list[dict]:
    """How many options each generated `configure` offers, counted from its own help text.

    Counted from the generated script rather than from `AC_ARG_ENABLE` in the `.ac` file,
    because a good few of GCC's options come from m4 macros and never appear as one of
    those calls, and because the help text is the list a reader is actually shown.
    """
    rows = []
    for where, path in (("the top level", TOP / "configure"), ("gcc/", COMPILER / "configure")):
        text = path.read_text(encoding="utf-8", errors="replace")
        names = [m for m in OPTION.finditer(text) if m.group("name") not in BOILERPLATE]
        rows.append(
            {
                "where": where,
                "enable": sum(1 for m in names if m.group(0).startswith("  --enable")),
                "with": sum(1 for m in names if m.group(0).startswith("  --with")),
            }
        )
    return rows


def spans() -> dict:
    """Cut every snippet, after checking each citation says what the span says."""
    for spec in SPANS:
        want = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if spec["cite"] != want:
            print(f"{spec['name']}: cite says {spec['cite']}, the span starts at {want}")
            raise SystemExit(1)
    wanted = [{k: v for k, v in spec.items() if k != "cite"} for spec in SPANS]
    return source.extract(TOP, wanted, PINNED_TAG)


def main() -> int:
    if not (TOP / "configure").exists():
        print(f"no GCC tree at {TOP}. Run `just gcc-src` first.")
        return 1

    body = {
        "tag": PINNED_TAG,
        "commit": pinned_commit(),
        "version": (COMPILER / "BASE-VER").read_text(encoding="utf-8").strip(),
        "languages": languages(),
        "checking": checking(),
        "requires": requires(),
        "knobs": knobs(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    CUTS.parent.mkdir(parents=True, exist_ok=True)
    CUTS.write_text(json.dumps(spans(), indent=1) + "\n", encoding="utf-8")

    build = configure.load()
    shown = source.load_extract("b01")
    print(f"wrote {OUT.relative_to(ROOT)} at {build.tag}")
    print(f"wrote {CUTS.relative_to(ROOT)}, {len(shown)} spans, {shown.lines()} lines")
    print(f"{len(build.languages)} front ends, {len(build.default_languages)} on by default")
    print(f"{len(build.checking.flags)} checking flags, default {build.checking.default}")
    print(f"{build.options} configure options across {len(build.knobs)} scripts")
    for one in build.requires:
        print(f"{one.library:<6}refuses below {one.hard}, happy at {one.good}, says {one.said}+")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
