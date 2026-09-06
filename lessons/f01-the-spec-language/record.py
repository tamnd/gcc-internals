"""Record two real spec tables, four specs files that move a chain, and the driver's own code.

    python lessons/f01-the-spec-language/record.py
    python lessons/f01-the-spec-language/record.py --check

`gcc -dumpspecs` prints the program the driver runs. It is target specific, so the lesson
wants more than one of them: the local GCC 16.2.0 for this machine, and the same release for
x86-64 Linux through Compiler Explorer. Both go in `corpora/specs/f01.json` whole, and
`gxray.specs` reads them back.

The four overrides are the part a reader cannot take on trust. Each one is a pair of `-###`
runs that differ by a single text file, so whatever moved between them moved because of the
strings in that file:

  argument    `*cc1` with `+ -fverbose-asm`, and cc1 gets one more argument
  assembler   `*invoke_as` naming a program that does not exist, and the chain runs it
  guard       `*invoke_as` with `%{!S:` deleted, and `gcc -S` assembles anyway
  suffix      a `.frob` entry, and a file GCC would not compile compiles

Nothing is executed. `-###` prints the chain and stops, which is what makes it safe to
record a compiler chain with `my-own-assembler` in it.

Two of the four are derived from the local `-dumpspecs` rather than written out here, because
`invoke_as` differs between targets and a hand-copied Darwin string would not be a fair test
on anything else. `guard` finds the `%{!S:...}` with `specs.walk` and takes it off.

The twelve source spans are the driver's own code: the reference for the language, the
compiler table, the two static arrays, `read_specs`, `-dumpspecs`, and `do_spec_1` itself.
They need `vendor/gcc`, so they are cut here and committed, and a Colab reader gets them out
of `corpora/source/f01.json`.

`--check` re-asserts every fact the notebook states against what is already committed,
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

from gxray import source, specs  # noqa: E402
from gxray.driver import CEBackend  # noqa: E402
from tools.cecache import Cache  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "specs" / "f01.json"
CUTS = ROOT / "corpora" / "source" / "f01.json"

#: The program every chain in this lesson compiles. L1, because the lesson is about which
#: programs run and not about what they produce, and L1 is the one every reader has met.
PROGRAM = ROOT / "corpora" / "programs" / "l1.c"

#: The local compiler. The recording committed here was made by the Homebrew GCC 16.2.0,
#: which is the same release as the pinned tree, so a line cited from `vendor/gcc` is a line
#: in the compiler that printed these specs.
GCC = os.environ.get("GXRAY_GCC", "gcc-16")

#: The other one. Same GCC release, x86-64 Linux, reached through the Compiler Explorer API,
#: which serves `-dumpspecs` on stdout like any other compilation.
CE_COMPILER = "cg162"

#: Where each span comes from. `first` and `last` are inclusive lines in the pinned tree and
#: `cite` is asserted against `first`, so a span that moves cannot keep a citation that now
#: points at the wrong code. `refcheck` pins the same lines from the notebook's side.
SPANS: tuple[dict, ...] = (
    {
        "name": "language",
        "path": "gcc/gcc.cc",
        "first": 473,
        "last": 487,
        "about": "The reference for the whole language, and it lives in a comment",
        "cite": "gcc/gcc.cc:473@releases/gcc-16.2.0",
    },
    {
        "name": "struct",
        "path": "gcc/gcc.cc",
        "first": 1419,
        "last": 1435,
        "about": "A row of the compiler table: a suffix, a spec, and three flags",
        "cite": "gcc/gcc.cc:1419@releases/gcc-16.2.0",
    },
    {
        "name": "c-suffix",
        "path": "gcc/gcc.cc",
        "first": 1479,
        "last": 1481,
        "about": "How .c becomes C: one row whose whole spec is the name of another row",
        "cite": "gcc/gcc.cc:1479@releases/gcc-16.2.0",
    },
    {
        "name": "c-spec",
        "path": "gcc/gcc.cc",
        "first": 1482,
        "last": 1494,
        "about": "The other row. Compiling a C file is this string, and nothing else",
        "cite": "gcc/gcc.cc:1482@releases/gcc-16.2.0",
    },
    {
        "name": "static-specs",
        "path": "gcc/gcc.cc",
        "first": 1738,
        "last": 1749,
        "about": "The head of the list every target starts from, before it adds its own",
        "cite": "gcc/gcc.cc:1738@releases/gcc-16.2.0",
    },
    {
        "name": "functions",
        "path": "gcc/gcc.cc",
        "first": 1806,
        "last": 1833,
        "about": "The escape hatch: names a spec may call, the C behind each one, and a port's",
        "cite": "gcc/gcc.cc:1806@releases/gcc-16.2.0",
    },
    {
        "name": "read-specs",
        "path": "gcc/gcc.cc",
        "first": 2634,
        "last": 2657,
        "about": "Reading a -specs= file. A name without a star is a new compiler table row",
        "cite": "gcc/gcc.cc:2634@releases/gcc-16.2.0",
    },
    {
        "name": "dumpspecs",
        "path": "gcc/gcc.cc",
        "first": 4236,
        "last": 4245,
        "about": "Why link_command is in the output but not in the spec list",
        "cite": "gcc/gcc.cc:4236@releases/gcc-16.2.0",
    },
    {
        "name": "interpreter",
        "path": "gcc/gcc.cc",
        "first": 6174,
        "last": 6180,
        "about": "The whole interpreter is this loop and the switch under it",
        "cite": "gcc/gcc.cc:6174@releases/gcc-16.2.0",
    },
    {
        "name": "arguments",
        "path": "gcc/gcc.cc",
        "first": 6223,
        "last": 6234,
        "about": "Where an argument ends. A space is not punctuation, it is a statement",
        "cite": "gcc/gcc.cc:6223@releases/gcc-16.2.0",
    },
    {
        "name": "braces",
        "path": "gcc/gcc.cc",
        "first": 7288,
        "last": 7293,
        "about": "The grammar of %{...}, written down where somebody had to implement it",
        "cite": "gcc/gcc.cc:7288@releases/gcc-16.2.0",
    },
    {
        "name": "lookup",
        "path": "gcc/gcc.cc",
        "first": 9398,
        "last": 9438,
        "about": "Choosing a row for a file, backwards, so a -specs= entry wins",
        "cite": "gcc/gcc.cc:9398@releases/gcc-16.2.0",
    },
)


class Watched(Cache):
    """The ordinary cache, keeping a note of which entries went through it.

    `tools.tier0.orphans` insists the registry accounts for the store exactly, and it works
    out what an ordinary experiment asked for from its corpus entry. This one asks for a spec
    dump, which is not a corpus entry, so the list has to come from here instead.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self.used: list[str] = []

    def fetch(self, key: str, send) -> dict:
        self.used.append(key)
        return super().fetch(key, send)


def scrub(text: str) -> str:
    """Take the recording machine out of the recording.

    Two things leak: the directory the recorder ran from, and the private temporary directory
    the driver picked for the assembler's input, whose name is different on every run and
    would make two recordings of the same command look like a difference.

    The compiler's own installation path stays. It is where `cc1` actually is, T01 shows the
    same path, and a chain with the real libexec directory in it is the thing being taught.
    Every replacement here is space free, because these strings get parsed back into a chain.
    """
    text = text.replace(str(ROOT) + "/", "").replace(str(ROOT), ".")
    return re.sub(r"/(?:var/folders|tmp)/[^\s'\"]*", "/tmp/f01/scratch.s", text)


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)


def dumpspecs() -> str:
    """What the local driver has to say about itself."""
    done = run([GCC, "-dumpspecs"], ROOT)
    if done.returncode != 0 or not done.stdout.strip():
        raise SystemExit(f"{GCC} -dumpspecs printed nothing:\n{done.stderr}")
    return done.stdout


def elsewhere(back: CEBackend) -> str:
    """The same question asked of a different target, through somebody else's machine.

    Compiler Explorer runs `gcc -dumpspecs` like any other compilation and hands back stdout,
    which is the whole trick. The answer is cached in `tools/cecache/store` and committed, so
    this is a live request once and a file lookup thereafter.
    """
    result = back.compile(PROGRAM.read_text(encoding="utf-8"), "-dumpspecs")
    if not result.stdout.strip():
        raise SystemExit(f"{CE_COMPILER} returned no specs:\n{result.stderr[:2000]}")
    return result.stdout


def without_the_guard(value: str) -> str:
    """`invoke_as` with its `%{!S:...}` taken off and nothing else touched.

    Found rather than typed, because `invoke_as` is not the same string on two targets and a
    Darwin one pasted in here would silently stop being the same experiment anywhere else.
    """
    for token in specs.walk(value):
        if token.kind == "brace" and token.head.strip() == "!S":
            return value.replace(token.text, token.body)
    raise SystemExit("invoke_as on this compiler has no %{!S:...} in it, so the demo is void")


def rename_the_assembler(value: str) -> str:
    """`invoke_as` running a program that is not installed anywhere."""
    changed = re.sub(r"(?m)^(\s*)as ", r"\1my-own-assembler ", value)
    if changed == value:
        raise SystemExit("invoke_as on this compiler does not name `as` at the head of a line")
    return changed


def override(
    work: Path, name: str, about: str, text: str, args: list[str], input_file: str
) -> dict:
    """One pair of `-###` runs that differ by one file.

    `before` is the compiler as it comes. `after` is the same command with `-specs=` in front
    of it. Neither one runs a program: `-###` prints the chain and exits, which is the only
    reason it is safe to record a chain that names an assembler nobody has.
    """
    where = work / f"{name}.specs"
    where.write_text(text, encoding="utf-8")
    plain = [GCC, "-###", *args, input_file]
    with_file = [GCC, "-###", *args, f"-specs={where.name}", input_file]
    before = run(plain, work)
    after = run(with_file, work)
    return {
        "about": about,
        "file": text,
        "argv": [scrub(a) for a in with_file],
        "before": scrub(before.stderr),
        "after": scrub(after.stderr),
    }


def overrides(table: specs.Table) -> dict:
    """The four experiments, run in a scratch directory that is thrown away afterwards."""
    invoke_as = table["invoke_as"].value
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "l1.c").write_text(PROGRAM.read_text(encoding="utf-8"), encoding="utf-8")
        (work / "l1.frob").write_text(PROGRAM.read_text(encoding="utf-8"), encoding="utf-8")
        return {
            "argument": override(
                work,
                "argument",
                "One line appends one argument to every cc1 this driver runs",
                "*cc1:\n+ -fverbose-asm\n\n",
                ["-O2", "-S"],
                "l1.c",
            ),
            "assembler": override(
                work,
                "assembler",
                "The assembler's name is a word in a string, and a string can be edited",
                f"*invoke_as:\n{rename_the_assembler(invoke_as)}\n\n",
                ["-O2", "-c"],
                "l1.c",
            ),
            "guard": override(
                work,
                "guard",
                "Deleting %{!S: from one spec makes -S assemble, because -S is that guard",
                f"*invoke_as:\n{without_the_guard(invoke_as)}\n\n",
                ["-O2", "-S"],
                "l1.c",
            ),
            "suffix": override(
                work,
                "suffix",
                "Two lines teach the driver a file extension it has never heard of",
                ".frob:\n@c\n\n",
                ["-O2", "-c"],
                "l1.frob",
            ),
        }


def builtin() -> dict:
    """The two static arrays and the compiler table, counted in the pinned tree.

    These are the numbers the notebook states, and they are read out of the source rather
    than typed, so a GCC bump that adds a spec function changes the recording instead of
    making a sentence quietly wrong. The spans committed alongside show the same code.
    """
    text = (GCC_ROOT / "gcc" / "gcc.cc").read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    def initializer(needle: str) -> str:
        start = next(i for i, line in enumerate(lines) if needle in line)
        depth, i = 0, start
        while True:
            depth += lines[i].count("{") - lines[i].count("}")
            if depth == 0 and i > start and "{" in "\n".join(lines[start : i + 1]):
                return "\n".join(lines[start : i + 1])
            i += 1

    static_specs = re.findall(r'INIT_STATIC_SPEC\s*\(\s*"([^"]*)"', initializer("static_specs[]"))
    functions = re.findall(r'\{\s*"([^"]*)"', initializer("static_spec_functions[]"))
    rows = re.findall(r'\{\s*"([^"]*)"\s*,', initializer("default_compilers[]"))
    return {
        "static_specs": static_specs,
        "functions": functions,
        "suffixes": [row for row in rows if row.startswith(".")],
        "languages": [row for row in rows if row.startswith("@")],
    }


def record() -> dict:
    local = dumpspecs()
    table = specs.parse(local)
    version = run([GCC, "--version"], ROOT).stdout.splitlines()[0]
    target = run([GCC, "-dumpmachine"], ROOT).stdout.strip()
    watched = Watched()
    back = CEBackend(CE_COMPILER, cache=watched)
    tables = {
        "local": {
            "text": local,
            "compiler": version,
            "target": target,
            "about": "The compiler this lesson was recorded on, answering for itself",
        },
        "elsewhere": {
            "text": elsewhere(back),
            "compiler": back.version(),
            "target": back.target(),
            "about": "The same GCC release built for a different machine by other people",
        },
    }
    return {
        "recorded": date.today().isoformat(),
        "tag": PINNED_TAG,
        "compiler": version,
        "target": target,
        # Which Compiler Explorer entries this recording stands for. Written by the code that
        # made the requests, because a hand-kept list would be a second answer to that.
        "cache": sorted(set(watched.used)),
        "source": PROGRAM.read_text(encoding="utf-8"),
        "tables": tables,
        "overrides": overrides(table),
        "builtin": builtin(),
    }


def spans() -> dict:
    for spec in SPANS:
        want = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if spec["cite"] != want:
            print(f"{spec['name']}: cite says {spec['cite']}, the span starts at {want}")
            raise SystemExit(1)
    wanted = [{k: v for k, v in spec.items() if k != "cite"} for spec in SPANS]
    return source.extract(GCC_ROOT, wanted, PINNED_TAG)


def check(rec: specs.Recording) -> list[str]:
    """Every fact the notebook states about the recording, asserted here instead of in prose.

    Most of these are statements about GCC 16.2.0 and will not all survive GCC 17. That is
    what this function is for: the paragraph next door cannot notice it has gone stale, and
    this can.
    """
    wrong: list[str] = []

    def want(condition: bool, saying: str) -> None:
        if not condition:
            wrong.append(saying)

    local, remote = rec.table("local"), rec.table("elsewhere")
    for label, table in (("local", local), ("elsewhere", remote)):
        want(len(table) > 40, f"the {label} table has {len(table)} blocks, which is too few")
        want(
            table.unknown() == [],
            f"the {label} table has forms this module cannot read: {table.unknown()[:4]}",
        )
        want(
            "invoke_as" in table,
            f"the {label} table has no invoke_as, so the lesson has no spine",
        )
        want(
            "link_command" in table,
            f"-dumpspecs on {label} no longer prints link_command, which the section reads",
        )

    want(
        len(local) != len(remote),
        f"both tables have {len(local)} blocks, which makes the comparison pointless",
    )
    want(
        local["invoke_as"].value != remote["invoke_as"].value,
        "invoke_as is now identical on both targets, and the section compares them",
    )

    #: The call graph. Every name the compiler table's `@c` entry reaches has to be defined,
    #: or the driver would fail on the first C file it was handed.
    at_c = ["trad_capable_cpp", "cpp_options", "cc1_options", "invoke_as"]
    for name in at_c:
        want(name in local, f"{name} is not in the local table, and the @c spec calls it")
    want(
        local.dangling(*at_c) == [],
        f"the @c spec reaches names nothing defines: {local.dangling(*at_c)}",
    )
    want(
        len(local.reach(*at_c)) > 10,
        f"compiling a C file reaches {len(local.reach(*at_c))} specs, which is suspiciously few",
    )

    built = rec.builtin
    want(
        len(built.static_specs) == 45,
        f"static_specs has {len(built.static_specs)} entries, not 45",
    )
    want(len(built.functions) == 21, f"there are {len(built.functions)} spec functions, not 21")
    want(
        len(built.suffixes) == 44,
        f"the compiler table has {len(built.suffixes)} suffixes, not 44",
    )
    want(
        len(built.languages) == 5,
        f"the compiler table has {len(built.languages)} languages, not 5",
    )
    want(".c" in built.suffixes and "@c" in built.languages, "the .c and @c rows have moved")
    #: `-dumpspecs` prints link_command, but it is not one of the 45. It has a variable of
    #: its own and a case of its own, which is the section's whole point.
    want(
        "link_command" not in built.static_specs,
        "link_command is in static_specs now, and the section says it is the one that is not",
    )
    want(
        "compare-debug-dump-opt" in built.functions,
        "the spec function invoke_as calls is no longer in the list",
    )
    #: A port may register spec functions of its own through EXTRA_SPEC_FUNCTIONS, so the
    #: twenty-one are a floor and not a total. Both of these targets prove it.
    for label, table in (("local", local), ("elsewhere", remote)):
        called = {name for spec in table for name in spec.functions}
        outside = sorted(name for name in called if name not in built.functions)
        want(
            outside != [],
            f"the {label} table calls no spec function of its own, and the section says it does",
        )
    for table in (local, remote):
        want(
            built.missing_from(table) == [],
            f"a built-in spec is missing from {table.target}: {built.missing_from(table)}",
        )
    want(
        len(built.added_by(local)) > 0,
        "this target adds no specs of its own, which the lesson claims it does",
    )

    #: The four experiments. Each one is a claim about what moved, and the pair of chains is
    #: the evidence, so a change that stops the demo working has to be caught here.
    for one in rec.overrides.values():
        want(one.moved, f"the {one.name} specs file changed nothing about the chain")

    argument = rec["argument"]
    steps = argument.chain_after.steps
    want(len(steps) == 1, f"the argument demo runs {len(steps)} programs, and it wants one")
    added = set(steps[0].argv) - set(argument.chain_before.steps[0].argv)
    want(added == {"-fverbose-asm"}, f"the specs file added {sorted(added)}, not -fverbose-asm")

    assembler = rec["assembler"]
    want(
        assembler.programs() == (["cc1", "as"], ["cc1", "my-own-assembler"]),
        f"the assembler demo now goes {assembler.programs()[0]} to {assembler.programs()[1]}",
    )

    guard = rec["guard"]
    want(
        guard.programs() == (["cc1"], ["cc1", "as"]),
        f"deleting the !S guard now goes {guard.programs()[0]} to {guard.programs()[1]}",
    )
    want(
        "-S" in guard.argv,
        "the guard demo is no longer run with -S, which is the whole point of it",
    )

    suffix = rec["suffix"]
    want(
        suffix.programs() == ([], ["cc1", "as"]),
        f"the .frob demo now goes {suffix.programs()[0]} to {suffix.programs()[1]}",
    )
    want(
        "linker input file unused" in suffix.before,
        "GCC no longer refuses a .frob file, so teaching it the suffix proves nothing",
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
        if not (GCC_ROOT / "gcc" / "gcc.cc").is_file():
            print(f"no GCC tree at {GCC_ROOT}. Run `just gcc-src` first.")
            return 1
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(record(), indent=1) + "\n", encoding="utf-8")
        CUTS.parent.mkdir(parents=True, exist_ok=True)
        CUTS.write_text(json.dumps(spans(), indent=1) + "\n", encoding="utf-8")

    rec = specs.load("f01")
    shown = source.load_extract("f01")
    wrong = check(rec)
    for line in wrong:
        print(f"  {line}")
    verb = "checked" if args.check else "wrote"
    blocks = ", ".join(f"{label} {len(table)}" for label, table in rec.tables.items())
    print(
        f"{verb} {OUT.relative_to(ROOT)}, {len(rec.tables)} spec tables ({blocks}), "
        f"{len(rec.overrides)} overrides, recorded {rec.recorded}"
    )
    print(f"{verb} {CUTS.relative_to(ROOT)}, {len(shown)} spans, {shown.lines()} lines")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
