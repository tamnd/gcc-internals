"""Read the pinned tree, then induce six stage comparison outcomes on purpose.

    just corpus-b02
    python lessons/b02-the-bootstrap/record.py [gcc-16]

Two halves, and the second one is the unusual part.

The first half is the same shape as B01's recorder. It reads `Makefile.def`, `Makefile.tpl`,
`configure.ac` and `config/` through `tools.bpc.bootstrap`, which is the reader BP-BOOTSTRAP
generates its tables from, and writes the stage list, the module split, the six exclusion
patterns and the nineteen build configurations. It also cuts nine spans of the real makefile
and configure script into `corpora/source/b02.json`.

The second half compiles a small C file twelve times and keeps the object files. A real
stage comparison walks tens of thousands of them at the end of a four hour build, and the
lesson cannot do that. What it can do is take the six things that can happen to one file and
make each of them happen, once, with a real GCC:

    identical            compiled twice, changing nothing
    differs by directory the one the stage renaming exists to prevent
    differs by content   what a miscompiled stage one actually looks like
    forgiven by name     a checksum, which is supposed to differ
    forgiven by date     the M2 version module, which records when it was built
    absent upstream      a file stage three has and stage two does not

The object files go into the corpus base64 encoded, because `.gitignore` excludes `*.o` for
good reasons and these six pairs are the exception. They are about two kilobytes each.

The comparison itself is not recorded. `gxray.bootstrap.compare` runs GCC's rule over these
files in the notebook, so what the reader sees is an oracle firing rather than a transcript
of one that fired here.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import bootstrap, source  # noqa: E402
from tools.bpc import bootstrap as parse  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "bootstrap" / "gcc.json"
CUTS = ROOT / "corpora" / "source" / "b02.json"

#: `tools.bpc.bootstrap` calls `.parent` on what it is given, because everything else in
#: `bpc` reads `gcc/` and none of a bootstrap is in there.
COMPILER = GCC_ROOT / "gcc"

#: The one source file every recorded object is compiled from. It has a loop in it because
#: the content difference below is induced with an optimisation level, and a straight line
#: function compiles to the same thing at -O1 and -O2.
PROGRAM = """\
/* Compiled twelve times by lessons/b02-the-bootstrap/record.py. Nothing about it matters
   except that -O1 and -O2 disagree about it, which a straight line function would not. */
#ifndef STAMP
#define STAMP "unset"
#endif

const char *build_stamp (void) { return STAMP; }

int sum_squares (const int *a, int n)
{
  int total = 0;
  for (int i = 0; i < n; i++)
    total += a[i] * a[i];
  return total;
}
"""

#: What each pair is called, what was done to the two halves, and one sentence of why. The
#: names are real GCC object files, because the exclusion patterns are matched against the
#: name and a made up one would not exercise them.
PAIRS: tuple[dict, ...] = (
    {
        "name": "gcc/tree-ssa-ccp.o",
        "about": "Compiled twice with nothing changed, like the other thirty thousand",
        "left": {},
        "right": {},
    },
    {
        "name": "gcc/gimplify.o",
        "about": "The same source and flags, compiled in stage2-gcc and in stage3-gcc",
        "left": {"where": "stage2-gcc"},
        "right": {"where": "stage3-gcc"},
    },
    {
        "name": "gcc/fold-const.o",
        "about": "Different code from the same source, as a miscompiled stage one produces",
        "left": {"opt": "-O1"},
        "right": {"opt": "-O2"},
    },
    {
        "name": "gcc/cc1-checksum.o",
        "about": "A checksum of the stage that built it, so it is supposed to differ",
        "left": {"stamp": "stage2-a1b2c3d4"},
        "right": {"stamp": "stage3-e5f6a7b8"},
    },
    {
        "name": "gcc/m2/gm2-compiler-boot/M2Version.o",
        "about": "GetGM2Date, the date of the build, which cannot survive being built twice",
        "left": {"stamp": "2026-09-05"},
        "right": {"stamp": "2026-09-06"},
    },
    {
        "name": "gcc/rust/rust-lang.o",
        "about": "A file stage three has and stage two does not, which the rule skips",
        "left": None,
        "right": {},
    },
)

#: The spans of the real makefile and configure script the lesson prints, in order.
SPANS: tuple[dict, ...] = (
    {
        "name": "wanted",
        "path": "configure.ac",
        "first": 1549,
        "last": 1572,
        "about": "A native build bootstraps unless you say otherwise, and a cross build does not",
        "cite": "configure.ac:1549@releases/gcc-16.2.0",
    },
    {
        "name": "stage1",
        "path": "configure.ac",
        "first": 4344,
        "last": 4352,
        "about": "Stage one gets -g and no optimisation, on every host but one",
        "cite": "configure.ac:4344@releases/gcc-16.2.0",
    },
    {
        "name": "exclusions",
        "path": "configure.ac",
        "first": 4405,
        "last": 4413,
        "about": "The object files a bootstrap is allowed to find different",
        "cite": "configure.ac:4405@releases/gcc-16.2.0",
    },
    {
        "name": "why",
        "path": "Makefile.tpl",
        "first": 1747,
        "last": 1756,
        "about": "GCC's own comment on why every stage builds in a directory called gcc",
        "cite": "Makefile.tpl:1747@releases/gcc-16.2.0",
    },
    {
        "name": "start",
        "path": "Makefile.tpl",
        "first": 1767,
        "last": 1782,
        "about": "Unpacking a stage, which is renaming every bootstrap module into place",
        "cite": "Makefile.tpl:1767@releases/gcc-16.2.0",
    },
    {
        "name": "bubble",
        "path": "Makefile.tpl",
        "first": 1797,
        "last": 1815,
        "about": "Why it is one dependency chain and not a script, which GCC calls bubbling",
        "cite": "Makefile.tpl:1797@releases/gcc-16.2.0",
    },
    {
        "name": "compare",
        "path": "Makefile.tpl",
        "first": 1824,
        "last": 1857,
        "about": "The oracle itself, in thirty four lines of shell inside a makefile",
        "cite": "Makefile.tpl:1824@releases/gcc-16.2.0",
    },
    {
        "name": "exports",
        "path": "Makefile.tpl",
        "first": 278,
        "last": 284,
        "about": "Where every stage after the first gets its compiler from",
        "cite": "Makefile.tpl:278@releases/gcc-16.2.0",
    },
    {
        "name": "skip",
        "path": "config/acx.m4",
        "first": 468,
        "last": 496,
        "about": "Three ways to ignore sixteen bytes, because not every cmp can do it the same way",
        "cite": "config/acx.m4:468@releases/gcc-16.2.0",
    },
)


def pinned_commit(top: Path) -> str:
    done = subprocess.run(
        ["git", "-C", str(top), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def version(gcc: str) -> str:
    done = subprocess.run([gcc, "--version"], capture_output=True, text=True, check=True)
    return done.stdout.splitlines()[0].strip()


def triple(gcc: str) -> str:
    done = subprocess.run([gcc, "-dumpmachine"], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def compile_one(gcc: str, build: Path, how: dict) -> bytes:
    """Compile the one program once, in the directory and with the flags this half wants.

    The directory matters and is the whole of the second pair. GCC records the directory it
    compiled in, in the debug information, so the same source built in two directories with
    different names produces two object files that differ in a string.
    """
    where = build / how.get("where", "gcc")
    where.mkdir(parents=True, exist_ok=True)
    out = where / "one.o"
    flags = [how.get("opt", "-O2"), "-g", f'-DSTAMP="{how.get("stamp", "unset")}"']
    subprocess.run(
        [gcc, *flags, "-c", str(build / "one.c"), "-o", "one.o"],
        cwd=where,
        check=True,
        capture_output=True,
    )
    body = out.read_bytes()
    out.unlink()
    return body


def objects(gcc: str) -> list[dict]:
    """Compile the twelve object files, and check that each pair did what it was meant to.

    Under a fixed directory rather than a `mkdtemp` one, because the whole point of the second
    pair is that the directory name is inside the object file. A random name would make the
    recording different every time it was made, and a corpus that changes when nothing changed
    is a corpus nobody can review.

    `/tmp` rather than `tempfile.gettempdir()`, which on macOS is a per user directory with a
    hash in the name. That path would be committed inside the object file, and a recording
    should not carry anything about the machine that made it beyond the triple it names.
    """
    rows = []
    build = Path("/tmp") / "gcc-internals-b02" / "build"
    shutil.rmtree(build.parent, ignore_errors=True)
    build.mkdir(parents=True)
    try:
        (build / "one.c").write_text(PROGRAM, encoding="utf-8")
        for spec in PAIRS:
            right = compile_one(gcc, build, spec["right"])
            left = None if spec["left"] is None else compile_one(gcc, build, spec["left"])
            rows.append(
                {
                    "name": spec["name"],
                    "about": spec["about"],
                    "left": base64.b64encode(left).decode() if left is not None else "",
                    "right": base64.b64encode(right).decode(),
                }
            )
    finally:
        shutil.rmtree(build.parent, ignore_errors=True)
    return rows


def stages() -> list[dict]:
    """The nine declared stages, with the flags the template gives each one."""
    every = parse.flags(COMPILER)
    rows = []
    for one in parse.stages(COMPILER):
        id = one.one("id")
        rows.append(
            {
                "id": id,
                "previous": one.one("prev"),
                # A stage that has a compare target compares itself against its previous.
                "compares": one.one("prev") if one.has("compare_target") else "",
                "target": one.one("bootstrap_target"),
                "cflags": [f"{what} {op} {value}" for what, op, value in every.get(id, [])],
            }
        )
    return rows


def spans() -> dict:
    for spec in SPANS:
        want = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if spec["cite"] != want:
            print(f"{spec['name']}: cite says {spec['cite']}, the span starts at {want}")
            raise SystemExit(1)
    wanted = [{k: v for k, v in spec.items() if k != "cite"} for spec in SPANS]
    return source.extract(GCC_ROOT, wanted, PINNED_TAG)


def check(boot: bootstrap.Bootstrap) -> int:
    """Every pair has to have done what its `about` says, or the lesson is telling a story.

    Worth the twenty lines. An induced difference that quietly stopped happening, because a
    compiler got better at reproducibility or because a flag changed meaning, would leave a
    notebook whose prose says a file differs and whose output says it does not.
    """
    wrong = []
    result = boot.compare()
    if result.same != ("gcc/tree-ssa-ccp.o",):
        wrong.append(f"expected exactly one identical pair, got {result.same}")
    if result.skipped != ("gcc/rust/rust-lang.o",):
        wrong.append(f"expected exactly one skipped pair, got {result.skipped}")
    bad = tuple(d.name for d in result.bad)
    if bad != ("gcc/gimplify.o", "gcc/fold-const.o"):
        wrong.append(f"expected two unforgiven differences, got {bad}")
    forgave = tuple(d.name for d in result.differences if d.forgiven)
    if len(forgave) != 2:
        wrong.append(f"expected two forgiven differences, got {forgave}")
    for line in wrong:
        print(f"  {line}")
    return 1 if wrong else 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    gcc = args[0] if args else "gcc-16"

    if not (GCC_ROOT / "Makefile.def").exists():
        print(f"no GCC tree at {GCC_ROOT}. Run `just gcc-src` first.")
        return 1
    if shutil.which(gcc) is None:
        print(f"no {gcc} on your PATH. Pass the name of a GCC 16 as the one argument.")
        return 1
    said = version(gcc)
    if not re.search(r"\b16\.", said):
        print(f"{gcc} is {said}, and the recorded object files should come from a GCC 16.")
        return 1

    inside, outside = parse.modules(COMPILER)
    staged, once = parse.target_modules(COMPILER)
    body = {
        "tag": PINNED_TAG,
        "commit": pinned_commit(GCC_ROOT),
        "host": triple(gcc),
        "compiler": said,
        "stages": stages(),
        "inside": inside,
        "outside": outside,
        "target_inside": staged,
        "target_outside": once,
        "exclusions": parse.exclusions(COMPILER),
        "configs": parse.config_names(COMPILER),
        "objects": objects(gcc),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
    CUTS.parent.mkdir(parents=True, exist_ok=True)
    CUTS.write_text(json.dumps(spans(), indent=1) + "\n", encoding="utf-8")

    boot = bootstrap.load()
    shown = source.load_extract("b02")
    print(f"wrote {OUT.relative_to(ROOT)} at {boot.tag}")
    print(f"wrote {CUTS.relative_to(ROOT)}, {len(shown)} spans, {shown.lines()} lines")
    print(f"{len(boot.stages)} stages, {len(boot.compared)} compared, {len(boot.configs)} configs")
    print(f"{len(boot.inside)} host modules inside the loop, {len(boot.outside)} outside")
    print(f"{len(boot.target_inside)} target libraries staged, {len(boot.target_outside)} not")
    print(f"{len(boot.objects)} object pairs from {boot.compiler} on {boot.host}")
    print()
    print(boot.compare().report())
    print()
    return check(boot)


if __name__ == "__main__":
    raise SystemExit(main())
