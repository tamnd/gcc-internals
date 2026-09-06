"""Build five plugins against a real GCC 16.2, load each one, and keep every byte.

    python lessons/b05-the-plugin/record.py
    python lessons/b05-the-plugin/record.py --check

A plugin cannot be built on Compiler Explorer and cannot be built in a notebook. It needs
GCC's private headers, a C++ compiler, and the same GCC that will load it, and a reader on
Colab has a shallow clone and a Python kernel. What they do have is the plugin sources,
because `gxplug/examples/` is in this repository, and this recording of what those sources
do when a compiler runs them.

So the recorder is the Tier 1 half of B05 executed once, on a machine that has a real GCC,
with everything it printed written to `corpora/plug/b05.json`. Five plugins:

  hello      the smallest thing that is still a plugin, one callback per function
  countpass  a pass of the reader's own, inserted after `ssa`, with its own dump file
  gate       the same mechanism used to switch one of GCC's passes off from outside
  nolicence  refused, because the GPL symbol is missing
  wrongver   refused, because it claims to have been built by a different compiler

Plus the `gxplug` event stream itself, the pipeline with the new pass in it, and the
assembly on both sides of the gate, which is the one recording where the compiler's output
is meant to differ.

Absolute paths are scrubbed on the way out. A corpus with somebody's home directory in it is
a corpus that says who recorded it, and every string here goes into a notebook a stranger
reads.

`--check` re-asserts every fact the lesson states against what is already committed, without
building or compiling anything, which is what the test suite of this repository calls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import plug, source  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "plug" / "b05.json"
CUTS = ROOT / "corpora" / "source" / "b05.json"
GXPLUG = ROOT / "gxplug"
EXAMPLES = GXPLUG / "examples"

#: The program every recording compiles. L2 because it is the one with a static function, a
#: struct and a loop, so `countpass` has phis to count and `ivopts` has work to skip.
PROGRAM = ROOT / "corpora" / "programs" / "l2.c"

#: The other one, for the event stream. L1 is small enough that a reader can hold the whole
#: pass tape in their head, which is the point of showing the stream at all.
LADDER = ROOT / "corpora" / "programs" / "l1.c"

#: The compiler. Overridable, but the recording committed here was made by the Homebrew
#: GCC 16.2.0, which is the same release as the pinned tree, so a line number cited from
#: `vendor/gcc` is a line number in the compiler that produced this output.
GCC = os.environ.get("GXPLUG_GCC", "gcc-16")

#: The pass `gate` switches off. Chosen by trying the obvious candidates and keeping the one
#: whose absence is visible in the assembly of L2: induction variable optimization, which
#: rewrites the loop's addressing. `check()` below insists it still is.
GATED = "ivopts"

#: And the one that changes nothing when you switch it off, which is the more instructive
#: half. Early inlining is not the inliner that matters here.
UNGATED = "einline"

#: Where each span comes from. `first` and `last` are inclusive line numbers in the pinned
#: tree, and `cite` is asserted against them so a span that moves cannot quietly keep a
#: citation that now points at the wrong code.
SPANS: tuple[dict, ...] = (
    {
        "name": "dlopen",
        "path": "gcc/plugin.cc",
        "first": 699,
        "last": 708,
        "about": "How a plugin is loaded, and the one flag that decides what a mismatch does",
        "cite": "gcc/plugin.cc:699@releases/gcc-16.2.0",
    },
    {
        "name": "licence",
        "path": "gcc/plugin.cc",
        "first": 713,
        "last": 717,
        "about": "The licence check: a symbol looked up by name, and a fatal error if absent",
        "cite": "gcc/plugin.cc:713@releases/gcc-16.2.0",
    },
    {
        "name": "initcall",
        "path": "gcc/plugin.cc",
        "first": 731,
        "last": 740,
        "about": "Calling plugin_init, and what a non-zero return does to the compilation",
        "cite": "gcc/plugin.cc:731@releases/gcc-16.2.0",
    },
    {
        "name": "version",
        "path": "gcc/plugin.cc",
        "first": 1004,
        "last": 1025,
        "about": "The default version check, which compares five fields and not one",
        "cite": "gcc/plugin.cc:1004@releases/gcc-16.2.0",
    },
    {
        "name": "defevent",
        "path": "gcc/plugin.def",
        "first": 20,
        "last": 39,
        "about": "The event list is a file of one-line macro calls, and the order is the ABI",
        "cite": "gcc/plugin.def:20@releases/gcc-16.2.0",
    },
    {
        "name": "pseudo",
        "path": "gcc/plugin.cc",
        "first": 450,
        "last": 469,
        "about": "register_callback, where three of the events are handled and never fired",
        "cite": "gcc/plugin.cc:450@releases/gcc-16.2.0",
    },
    {
        "name": "dispatch",
        "path": "gcc/plugin.cc",
        "first": 582,
        "last": 592,
        "about": "What firing an event actually is: a linked list walked in registration order",
        "cite": "gcc/plugin.cc:582@releases/gcc-16.2.0",
    },
    {
        "name": "info",
        "path": "gcc/tree-pass.h",
        "first": 328,
        "last": 344,
        "about": "The four fields that decide where a plugin's pass goes",
        "cite": "gcc/tree-pass.h:328@releases/gcc-16.2.0",
    },
    {
        "name": "position",
        "path": "gcc/passes.cc",
        "first": 1377,
        "last": 1401,
        "about": "The match: same pass type, same name, and the right instance",
        "cite": "gcc/passes.cc:1377@releases/gcc-16.2.0",
    },
    {
        "name": "gatecall",
        "path": "gcc/passes.cc",
        "first": 2597,
        "last": 2608,
        "about": "The gate, and the one event that is handed a pointer to write through",
        "cite": "gcc/passes.cc:2597@releases/gcc-16.2.0",
    },
)


def scrub(text: str) -> str:
    """Take the recording machine out of the recording.

    Three things leak: the repository's own path, the Homebrew prefix in the include flags,
    and the temporary directory the compilations run in. All three are replaced with
    something a reader can recognize, and none of them carries information the lesson needs.
    """
    text = text.replace(str(ROOT) + "/", "").replace(str(ROOT), ".")
    text = re.sub(r"/opt/homebrew|/home/linuxbrew/\.linuxbrew", "$(brew --prefix)", text)
    text = re.sub(r"/(?:var/folders|tmp)/[^\s'\"]*", "/tmp/b05", text)
    return text


def run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, cwd=cwd or ROOT, capture_output=True, text=True, timeout=300, check=False
    )


def compile_one(name: str, about: str, args: list[str], keep_asm: bool = True) -> dict:
    """One compilation, recorded whole. `args` is everything after the compiler's name."""
    out = ROOT / "b05-scratch.s"
    argv = [GCC, *args, "-o", str(out)]
    done = run(argv)
    asm = None
    if keep_asm and out.is_file():
        asm = out.read_text(encoding="utf-8")
    out.unlink(missing_ok=True)
    return {
        "about": scrub(about),
        "argv": [scrub(a) for a in argv],
        "returncode": done.returncode,
        "stdout": scrub(done.stdout),
        "stderr": scrub(done.stderr),
        **({"asm": scrub(asm)} if asm is not None else {}),
    }


def build() -> str:
    """Build the plugin and the five examples, and return what the probe decided.

    A failure here is not something to work around. It means the reader following the same
    four commands in the lesson would fail too, and the lesson would be wrong.
    """
    probe = run(["make", "-C", str(GXPLUG), "probe", f"GCC={GCC}"])
    if probe.returncode != 0:
        raise SystemExit(f"make probe failed:\n{probe.stdout}{probe.stderr}")
    for target in ("all", "examples"):
        made = run(["make", "-C", str(GXPLUG), target, f"GCC={GCC}"])
        if made.returncode != 0:
            raise SystemExit(f"make {target} failed:\n{made.stdout}{made.stderr}")
    return scrub(probe.stdout)


def pipeline() -> dict:
    """`-fdump-passes` with the reader's pass in it, and where it landed.

    The list is four hundred lines long and the lesson wants six of them. The six are picked
    by finding the new pass rather than by line number, so this keeps working when GCC adds
    a pass above it.
    """
    done = run(
        [
            GCC,
            "-O2",
            "-S",
            f"-fplugin={EXAMPLES / 'countpass.so'}",
            "-fdump-passes",
            str(PROGRAM),
            "-o",
            os.devnull,
        ]
    )
    lines = [line.rstrip() for line in done.stderr.splitlines() if ":" in line]
    where = next((i for i, line in enumerate(lines) if "gxcount" in line), -1)
    if where < 0:
        raise SystemExit(f"gxcount is not in -fdump-passes:\n{done.stderr[:2000]}")
    return {
        "total": len(lines),
        "index": where,
        "around": lines[max(0, where - 3) : where + 4],
    }


def stream() -> str:
    """The gxplug event stream for L1 at -O2, as newline delimited JSON."""
    events = ROOT / "b05-events.ndjson"
    done = run(
        [
            GCC,
            "-O2",
            "-S",
            f"-fplugin={GXPLUG / 'gxplug.so'}",
            f"-fplugin-arg-gxplug-out={events}",
            str(LADDER),
            "-o",
            os.devnull,
        ]
    )
    if done.returncode != 0 or not events.is_file():
        raise SystemExit(f"gxplug produced nothing:\n{done.stderr}")
    text = events.read_text(encoding="utf-8")
    events.unlink()
    return text


def record() -> dict:
    probe = build()
    program, plain = str(PROGRAM), ["-O2", "-S", str(PROGRAM)]
    runs = {
        "plain": compile_one("plain", f"{program}, no plugin at all", plain),
        "hello": compile_one(
            "hello",
            "the smallest plugin, one callback per function and one at the end",
            ["-O2", "-S", f"-fplugin={EXAMPLES / 'hello.so'}", program],
        ),
        "hello-arg": compile_one(
            "hello-arg",
            "the same plugin, given an argument",
            [
                "-O2",
                "-S",
                f"-fplugin={EXAMPLES / 'hello.so'}",
                "-fplugin-arg-hello-who=reader",
                program,
            ],
            keep_asm=False,
        ),
        "countpass": compile_one(
            "countpass",
            "a pass of your own, running after ssa on every function",
            ["-O2", "-S", f"-fplugin={EXAMPLES / 'countpass.so'}", program],
        ),
        "gated": compile_one(
            "gated",
            f"{GATED} switched off from outside, and the assembly moves",
            [
                "-O2",
                "-S",
                f"-fplugin={EXAMPLES / 'gate.so'}",
                f"-fplugin-arg-gate-off={GATED}",
                program,
            ],
        ),
        "ungated": compile_one(
            "ungated",
            f"{UNGATED} switched off the same way, and nothing moves",
            [
                "-O2",
                "-S",
                f"-fplugin={EXAMPLES / 'gate.so'}",
                f"-fplugin-arg-gate-off={UNGATED}",
                program,
            ],
        ),
        "gate-dumpname": compile_one(
            "gate-dumpname",
            "the same request with a dump name instead of a pass name, which matches nothing",
            [
                "-O2",
                "-S",
                f"-fplugin={EXAMPLES / 'gate.so'}",
                "-fplugin-arg-gate-off=cddce1",
                program,
            ],
            keep_asm=False,
        ),
        "nolicence": compile_one(
            "nolicence",
            "refused before plugin_init runs, for a symbol that is not there",
            ["-O2", "-S", f"-fplugin={EXAMPLES / 'nolicence.so'}", program],
            keep_asm=False,
        ),
        "wrongver": compile_one(
            "wrongver",
            "refused by its own version check, which is the plugin's job and not GCC's",
            ["-O2", "-S", f"-fplugin={EXAMPLES / 'wrongver.so'}", program],
            keep_asm=False,
        ),
        "missing": compile_one(
            "missing",
            "a plugin that is not there, which is a dlopen error and not a driver error",
            ["-O2", "-S", "-fplugin=./no-such-plugin.so", program],
            keep_asm=False,
        ),
        "badarg": compile_one(
            "badarg",
            "a mistyped -fplugin-arg, which gxplug refuses rather than ignoring",
            [
                "-O2",
                "-S",
                f"-fplugin={GXPLUG / 'gxplug.so'}",
                "-fplugin-arg-gxplug-bogus=1",
                program,
            ],
            keep_asm=False,
        ),
    }
    version = run([GCC, "--version"]).stdout.splitlines()[0]
    return {
        "recorded": date.today().isoformat(),
        "tag": PINNED_TAG,
        "compiler": version,
        "target": run([GCC, "-dumpmachine"]).stdout.strip(),
        "probe": probe,
        "pipeline": pipeline(),
        "stream": stream(),
        "runs": runs,
    }


def spans() -> dict:
    for spec in SPANS:
        want = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if spec["cite"] != want:
            print(f"{spec['name']}: cite says {spec['cite']}, the span starts at {want}")
            raise SystemExit(1)
    wanted = [{k: v for k, v in spec.items() if k != "cite"} for spec in SPANS]
    return source.extract(GCC_ROOT, wanted, PINNED_TAG)


def check(session: plug.Session) -> list[str]:
    """Every behavioural fact the notebook states, asserted here instead of in prose.

    A recording is dated, not verified. If GCC 17 renames a pass, moves the licence check or
    stops firing an event, the paragraph next door is wrong and only this function can say
    so.
    """
    wrong: list[str] = []

    def want(condition: bool, saying: str) -> None:
        if not condition:
            wrong.append(saying)

    plain, hello = session["plain"], session["hello"]
    want(not plain.refused, "the program does not compile without any plugin at all")
    want(not hello.refused, f"hello was refused: {hello.said}")
    greeting = "hello, world: 2 function(s) in this unit"
    want(
        hello.said == ["hello: dist2", "hello: nearest", greeting],
        f"hello now says {hello.said}",
    )
    want(hello.asm == plain.asm, "hello changed the generated code, which no observer may do")
    want(
        "reader" in session["hello-arg"].said[-1],
        "the -fplugin-arg- value no longer reaches the plugin",
    )

    counted = session["countpass"]
    want(not counted.refused, f"countpass was refused: {counted.said}")
    want(counted.asm == plain.asm, "a pass that only reads changed the generated code")
    want(
        [line.split(":")[0] for line in counted.said] == ["gxcount", "gxcount"],
        f"countpass ran on {len(counted.said)} functions, not 2",
    )
    want(
        "6 phi(s)" in counted.said[1],
        f"nearest no longer has six phis after ssa: {counted.said[1]}",
    )

    where = session.pipeline
    want(
        any("gxcount" in line for line in where["around"]),
        "the new pass is no longer in -fdump-passes",
    )
    around = where["around"]
    after = around[around.index(next(line for line in around if "gxcount" in line)) - 1]
    want("ssa" in after, f"the pass before gxcount is now {after.strip()!r}, not tree-ssa")
    want(where["total"] > 300, f"-fdump-passes prints {where['total']} passes, which is too few")

    gated, ungated = session["gated"], session["ungated"]
    want(not gated.refused, f"switching {GATED} off failed the compilation: {gated.said}")
    want(gated.asm != plain.asm, f"switching {GATED} off no longer changes the assembly")
    want(f"refused {GATED} 1 time" in gated.said[-1], f"the gate report is now {gated.said[-1]!r}")
    want(ungated.asm == plain.asm, f"switching {UNGATED} off now changes the assembly")
    want(
        f"refused {UNGATED} 2 time" in ungated.said[-1],
        f"{UNGATED} is no longer gated on twice: {ungated.said[-1]!r}",
    )
    want(
        "refused cddce1 0 time" in session["gate-dumpname"].said[-1],
        "a dump name now matches a pass name, which would make the section pointless",
    )

    for name, saying in (
        ("nolicence", "not licensed under a GPL-compatible license"),
        ("wrongver", "built against GCC 15.1.0, loaded into GCC 16.2.0"),
        ("missing", "cannot load plugin"),
        ("badarg", "unknown argument"),
    ):
        one = session[name]
        want(one.refused, f"{name} compiled successfully, which defeats the point of it")
        want(
            any(saying in line for line in one.said),
            f"{name} no longer says {saying!r}, it says {one.said[:2]}",
        )
    want(
        not any("this line never prints" in line for line in session["nolicence"].said),
        "the plugin without a licence symbol got as far as running its own code",
    )

    events = session.stream
    runs = events.runs
    want(len(runs) > 100, f"the stream has {len(runs)} pass runs in it, which is too few")
    want(
        events.functions == ["_f"] or events.functions == ["f"],
        f"the stream is of {events.functions}, and L1 has one function called f",
    )
    marked = [r for r in runs if r.changed]
    want(
        0 < len(marked) < len(runs) // 2,
        f"{len(marked)} of {len(runs)} runs left a mark, and the lesson says most do not",
    )
    want(
        any(r.name == "expand" for r in runs),
        "expand is not in the stream, so the GIMPLE to RTL step cannot be shown",
    )
    return wrong


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="assert against what is already there")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.check:
        if shutil.which(GCC) is None:
            print(f"no {GCC} on PATH. Set GXPLUG_GCC, or read B01 and build one.")
            return 1
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(record(), indent=1) + "\n", encoding="utf-8")
        CUTS.parent.mkdir(parents=True, exist_ok=True)
        CUTS.write_text(json.dumps(spans(), indent=1) + "\n", encoding="utf-8")

    session = plug.load_session()
    shown = source.load_extract("b05")
    wrong = check(session)
    for line in wrong:
        print(f"  {line}")
    verb = "checked" if args.check else "wrote"
    print(
        f"{verb} {OUT.relative_to(ROOT)}, {len(session.invocations)} compilations by "
        f"{session.compiler}, {len(session.stream.runs)} pass runs, recorded {session.recorded}"
    )
    print(f"{verb} {CUTS.relative_to(ROOT)}, {len(shown)} spans, {shown.lines()} lines")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
