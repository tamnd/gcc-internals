"""Drive a real gdb against a real cc1, keep every byte, then sweep a debug counter.

    just corpus-b03
    python lessons/b03-the-debugger/record.py --build /work/build/gcc
    python lessons/b03-the-debugger/record.py --build /work/build/gcc --docker b03

This is the one recorder in the course that needs something no reader will have. A debugger
session against a compiler built at `-O2` is useless, because the locals the session prints
have been optimised away, so it needs a `cc1` configured with `--enable-checking=yes` and
`CFLAGS=-O0 -g3`. That binary is three hundred megabytes and takes most of an hour to build.
So the recording is made once, here, and committed.

`--build` is the `gcc` subdirectory of such a build tree, the one holding `cc1`, `xgcc` and
the `.gdbinit` that configure wrote next to them. `--docker` runs every command inside a
running container instead of on this machine, which is how the committed recording was made,
because gdb does not run on aarch64-darwin.

Two files come out. `corpora/replay/cc1.json` is one gdb process from the banner to the kill:
twenty six commands, grouped, each with one sentence saying why it is there and with every
byte gdb printed after it. `corpora/replay/counters.json` is fifty compilations of the same
program at fifty limits of the `match` debug counter, reduced to the distinct outputs, plus
the backtrace of the one transformation the bisection lands on.

Nothing here is checked against the pinned tree, and that is the honest shape of the thing: a
transcript is dated, not verified. What the recorder does check is that the session did the
things the lesson says it did, so a rename in GCC that turns a command into an error message
fails the recording rather than quietly producing a lesson full of errors.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import replay, source  # noqa: E402
from tools.refcheck import GCC_ROOT, PINNED_TAG  # noqa: E402

OUT = ROOT / "corpora" / "replay"
CUTS = ROOT / "corpora" / "source" / "b03.json"

#: The program the whole session is about. Nine lines, one loop, one accumulator, and the
#: canonical L1 that half the course already runs on.
PROGRAM = ROOT / "corpora" / "programs" / "l1.c"

#: What separates one command's output from the next. Chosen to be a string that cannot come
#: out of gdb by accident and that survives being echoed through a shell inside a container.
MARK = "@@gxray@@"

#: gdb has to be told to trust the build tree's `.gdbinit` before it reads it, which means
#: `-iex` and not a line in the script. Recording the refusal is the point of `DECLINED`.
TRUST = ["-iex", "set auto-load safe-path /"]

#: The counter swept in the second half. `match` gates every fold that genmatch generated,
#: which is most of the folding GCC does, so on a small program it is the counter with the
#: most to say. `gcc/genmatch.cc:4433` is where the call is written into the generated code.
COUNTER = "match"

#: Prelude, run before the first recorded command and not itself recorded. Only settings that
#: stop gdb behaving like a terminal, never anything that changes what the compiler does.
PRELUDE = [
    "set confirm off",
    "set height 0",
    "set width 0",
]

#: The session. Group, command, and why it is there. `{argv}` is filled in with the real cc1
#: command line the driver would use, which is read out of `xgcc -###` rather than guessed.
SESSION: tuple[tuple[str, str, str], ...] = (
    (
        "what the compiler's gdbinit already did",
        "info breakpoints",
        "Four breakpoints are set before the reader types anything, and gdbinit set them.",
    ),
    (
        "what the compiler's gdbinit already did",
        "info skip",
        "The skip list, which is why `step` does not vanish into a tree accessor.",
    ),
    (
        "what the compiler's gdbinit already did",
        "info pretty-printer global gcc",
        "Twenty one printers, four more than gdbhooks.py registers by name, from the loop.",
    ),
    (
        "how often a pass runs",
        "break execute_one_pass",
        "Every pass execution goes through this one function, so it is the place to count.",
    ),
    (
        "how often a pass runs",
        "ignore $bpnum 1000000",
        "Counting rather than stopping. A million is a number no compilation will reach.",
    ),
    (
        "how often a pass runs",
        "run {argv}",
        "The compilation runs to the end and stops in exit, which gdbinit put a breakpoint on.",
    ),
    (
        "how often a pass runs",
        "info breakpoints",
        "The hit count. This is how many times a pass ran for nine lines of C.",
    ),
    (
        "stopping on the pass you care about",
        "delete",
        "The counting breakpoint has done its work, and so has the one in exit.",
    ),
    (
        "stopping on the pass you care about",
        'break execute_one_pass if $_streq(pass->name, "ccp")',
        "The condition is on the pass name, which is a field of the pass gdb already has.",
    ),
    (
        "stopping on the pass you care about",
        "run",
        "Second run in the same process. The compiler starts over, the breakpoint does not.",
    ),
    (
        "stopping on the pass you care about",
        "print pass",
        "The opt_pass printer, which prints the name and the static pass number and nothing else.",
    ),
    (
        "stopping on the pass you care about",
        "backtrace 6",
        "Six frames is the whole of the pass manager: one pass, inside a list, inside an IPA pass.",
    ),
    (
        "looking at the function",
        "print cfun->decl",
        "The tree printer. A tree is a tagged pointer and this is what makes it readable.",
    ),
    (
        "looking at the function",
        "ptc cfun->decl",
        "The tree code alone, which is the one question worth asking about an unfamiliar tree.",
    ),
    (
        "looking at the function",
        "pdn cfun->decl",
        "The name, through two macros. No inferior call, so this one works in a core dump.",
    ),
    (
        "looking at the function",
        "pcfun",
        "The whole function, in the same syntax the dump files use, printed by the compiler.",
    ),
    (
        "looking at the function",
        "print cfun->cfg->x_n_basic_blocks",
        "Six blocks, two of which are the entry and exit that every function has.",
    ),
    (
        "looking at the function",
        "print (*cfun->cfg->x_basic_block_info)[3]",
        "Indexing the block vector. The vec printer keeps the expression short.",
    ),
    (
        "looking at the function",
        "pgq ((*cfun->cfg->x_basic_block_info)[3])->il.gimple.seq",
        "The statements in that block, which is the loop body and is two statements long.",
    ),
    (
        "looking at the function",
        "print ((*cfun->cfg->x_basic_block_info)[3])->preds",
        "The edges into it. The edge printer prints the block numbers rather than pointers.",
    ),
    (
        "watching the pass work",
        "finish",
        "Run the pass to its end and come back. The return value is whether it ran at all.",
    ),
    (
        "watching the pass work",
        "pcfun",
        "The same function after ccp. Two assignments gone, two PHI arguments now constants.",
    ),
    (
        "when it does not do what you meant",
        "break-on-pass ccp",
        "The argument is a class name, not a pass name, and a wrong one is a pending breakpoint.",
    ),
    (
        "when it does not do what you meant",
        "break-on-pass pass_ccp",
        "The class name. Now it resolves, to the execute method in the anonymous namespace.",
    ),
    (
        "when it does not do what you meant",
        "reload-gdbhooks",
        "A command in the pinned tree that cannot work on any Python newer than 3.11.",
    ),
    (
        "when it does not do what you meant",
        "kill",
        "The compilation is abandoned. Nothing was written, which is what -o /dev/null implies.",
    ),
)

#: Run once with no `-iex`, to record gdb refusing to read the build tree's `.gdbinit`. The
#: refusal is the single most common way a reader's first session goes wrong, and the message
#: gdb prints is long enough that paraphrasing it would not help anyone recognise it.
DECLINED = ["print 1"]

#: The spans of the real source the lesson prints, in order.
SPANS: tuple[dict, ...] = (
    {
        "name": "gdbinit",
        "path": "gcc/configure.ac",
        "first": 7402,
        "last": 7417,
        "about": "Configure writes the .gdbinit, which is why it is not in the source tree",
        "cite": "gcc/configure.ac:7402@releases/gcc-16.2.0",
    },
    {
        "name": "gdbasan",
        "path": "gcc/configure.ac",
        "first": 7419,
        "last": 7425,
        "about": "One more line, only if the compiler was built with the address sanitiser",
        "cite": "gcc/configure.ac:7419@releases/gcc-16.2.0",
    },
    {
        "name": "breakpoints",
        "path": "gcc/gdbinit.in",
        "first": 341,
        "last": 359,
        "about": "The four breakpoints and the type check every session starts with",
        "cite": "gcc/gdbinit.in:341@releases/gcc-16.2.0",
    },
    {
        "name": "pt",
        "path": "gcc/gdbinit.in",
        "first": 83,
        "last": 92,
        "about": "One shorthand, in full. All twenty six have this shape",
        "cite": "gcc/gdbinit.in:83@releases/gcc-16.2.0",
    },
    {
        "name": "passnames",
        "path": "gcc/gdbhooks.py",
        "first": 700,
        "last": 709,
        "about": "break-on-pass completes from passes.def, which holds class names",
        "cite": "gcc/gdbhooks.py:700@releases/gcc-16.2.0",
    },
    {
        "name": "breakonpass",
        "path": "gcc/gdbhooks.py",
        "first": 753,
        "last": 756,
        "about": "And then interpolates whatever it was given, checking nothing",
        "cite": "gcc/gdbhooks.py:753@releases/gcc-16.2.0",
    },
    {
        "name": "gate",
        "path": "gcc/passes.cc",
        "first": 2597,
        "last": 2621,
        "about": "Why a breakpoint here can stop on a pass that is about to decline to run",
        "cite": "gcc/passes.cc:2597@releases/gcc-16.2.0",
    },
    {
        "name": "dbgcnt",
        "path": "gcc/dbgcnt.cc",
        "first": 63,
        "last": 99,
        "about": "The whole of a debug counter: one increment and a range to compare against",
        "cite": "gcc/dbgcnt.cc:63@releases/gcc-16.2.0",
    },
)


class Runner:
    """Run commands either here or inside a container, from one build directory."""

    def __init__(self, build: str, docker: str = "") -> None:
        self.build = build
        self.docker = docker

    def run(self, argv: list[str], merge: bool = False) -> subprocess.CompletedProcess:
        """`merge` puts stderr on stdout in the order it was written.

        Which matters for gdb and for nothing else here. gdb writes its markers and its
        command output to stdout and its warnings and errors to stderr, so reading the two
        pipes separately and concatenating them afterwards moves every error message to the
        end of the session and attributes it to the wrong command.
        """
        if self.docker:
            argv = ["docker", "exec", "-w", self.build, self.docker, *argv]
        return subprocess.run(
            argv,
            cwd=None if self.docker else self.build,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merge else subprocess.PIPE,
            text=True,
            errors="replace",
        )

    def write(self, path: str, body: str) -> None:
        """Put a file where the debugger can read it, on whichever machine that is."""
        if not self.docker:
            Path(path).write_text(body, encoding="utf-8")
            return
        done = subprocess.run(
            ["docker", "exec", "-i", self.docker, "sh", "-c", f"cat > {path}"],
            input=body,
            capture_output=True,
            text=True,
        )
        if done.returncode:
            raise SystemExit(f"could not write {path} in {self.docker}: {done.stderr}")

    def read(self, path: str) -> str:
        done = self.run(["cat", path])
        if done.returncode:
            raise SystemExit(f"could not read {path}: {done.stderr}")
        return done.stdout


def pinned_commit() -> str:
    done = subprocess.run(
        ["git", "-C", str(GCC_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def cc1_argv(run: Runner, program: str, out: str) -> list[str]:
    """The cc1 command line, from the driver rather than from memory.

    `-###` prints what the driver would run without running it, one program per line, with
    every argument quoted the way the driver would quote it. The cc1 line is the one that
    names the compiler proper.
    """
    done = run.run(["./xgcc", "-B.", "-S", "-O2", program, "-o", out, "-###"])
    for line in done.stderr.splitlines():
        if "cc1" in line and line.startswith(" "):
            parts = [p.strip('"') for p in line.split()]
            return parts[1:]
    raise SystemExit(f"no cc1 line in the driver's -### output:\n{done.stderr}")


def gdb_argv(commands: list[str]) -> list[str]:
    """The commands as `-ex` arguments, with a marker echoed before each one.

    `-ex` and not a script file, because gdb abandons a sourced script at the first command
    that errors and two of the commands in the session are there precisely because they
    error. Commands given on the command line keep going, which is also what an interactive
    session does, so this is the more faithful of the two.
    """
    argv = []
    for command in PRELUDE:
        argv += ["-ex", command]
    for n, command in enumerate(commands):
        argv += ["-ex", f"echo \\n{MARK}{n}{MARK}\\n", "-ex", command]
    argv += ["-ex", f"echo \\n{MARK}{len(commands)}{MARK}\\n"]
    return argv


def split(text: str, count: int) -> tuple[str, list[str]]:
    """Everything before the first marker, then the text between consecutive markers."""
    parts = re.split(rf"\n?{re.escape(MARK)}(\d+){re.escape(MARK)}\n?", text)
    startup = parts[0]
    got: dict[int, str] = {}
    for n, body in zip(parts[1::2], parts[2::2], strict=False):
        got[int(n)] = body
    missing = [n for n in range(count) if n not in got]
    if missing:
        raise SystemExit(f"gdb never reached commands {missing}. Output was:\n{text[-3000:]}")
    return startup.strip("\n"), [got[n].strip("\n") for n in range(count)]


def drive(run: Runner, commands: list[str], trust: bool = True) -> tuple[str, list[str]]:
    """One gdb process, in batch mode, running the whole script against cc1."""
    gdb = ["gdb", "-q", "-batch"]
    # Unbuffered, or the two streams interleave differently every run. gdb writes errors to
    # stderr the moment they happen and command output to a block buffered stdout, so without
    # this a Python traceback lands several commands after the command that caused it. That
    # is not a cosmetic problem: the recorder attributes output to commands by position.
    if not run.run(["stdbuf", "--version"]).returncode:
        gdb = ["stdbuf", "-oL", "-eL", *gdb]
    argv = [*gdb, *(TRUST if trust else []), *gdb_argv(commands), "./cc1"]
    done = run.run(argv, merge=True)
    if not done.stdout:
        raise SystemExit("gdb printed nothing. Is there a cc1 in the build directory?")
    return split(done.stdout, len(commands))


def configure_line(run: Runner) -> str:
    """How the debugged compiler was configured, from the compiler itself.

    Worth recording rather than copying out of the build script. `-O0 -g3` is why the session
    can print a local, and a reader whose own session prints `<optimized out>` needs to be
    able to compare their configure line against this one.
    """
    done = run.run(["./xgcc", "-B.", "-v"], merge=True)
    for line in done.stdout.splitlines():
        if line.startswith("Configured with:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def session(run: Runner, argv: list[str]) -> dict:
    """The first half: one gdb process, twenty six commands, every byte kept."""
    filled = [c.replace("{argv}", " ".join(argv)) for _, c, _ in SESSION]
    startup, outputs = drive(run, filled)
    # The refusal is printed before the first command runs, so it is that run's startup and
    # not the output of anything. `DECLINED` exists only to give the run something to do.
    refused, _ = drive(run, DECLINED, trust=False)
    size = run.run(["stat", "-c", "%s", "./cc1"]).stdout.strip()
    uname = run.run(["uname", "-srm"]).stdout.strip()
    gdb = run.run(["gdb", "--version"]).stdout.splitlines()[0].strip()
    triple = run.run(["./xgcc", "-B.", "-dumpmachine"]).stdout.strip()
    return {
        "recorded": date.today().isoformat(),
        "tag": PINNED_TAG,
        "commit": pinned_commit(),
        "host": f"{triple}, {uname}",
        "gdb": gdb,
        "configure": configure_line(run),
        "binary": "cc1",
        "bytes": int(size) if size.isdigit() else 0,
        "program": PROGRAM.name,
        "source": PROGRAM.read_text(encoding="utf-8"),
        "argv": argv,
        "startup": startup,
        "declined": refused,
        "steps": [
            {"group": group, "command": filled[n], "why": why, "output": outputs[n]}
            for n, (group, _, why) in enumerate(SESSION)
        ],
    }


def counter_total(run: Runner, program: str) -> tuple[int, str]:
    """How many times the counter fires with no limit set, and the whole listing."""
    done = run.run(["./xgcc", "-B.", "-S", "-O2", "-fdbg-cnt-list", program, "-o", "/tmp/x.s"])
    listing = done.stderr.strip("\n")
    for line in listing.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == COUNTER and parts[1].isdigit():
            return int(parts[1]), listing
    raise SystemExit(f"no {COUNTER} row in -fdbg-cnt-list:\n{listing}")


def sweep(run: Runner, program: str) -> dict:
    """The second half: compile once per limit, and reduce the results to distinct outputs."""
    total, listing = counter_total(run, program)
    run.run(["./xgcc", "-B.", "-S", "-O2", program, "-o", "/tmp/base.s"])
    variants = [run.read("/tmp/base.s")]
    trials = []
    for limit in range(total + 1):
        capped = f"-fdbg-cnt={COUNTER}:{limit}"
        done = run.run(["./xgcc", "-B.", "-S", "-O2", capped, program, "-o", "/tmp/t.s"])
        text = run.read("/tmp/t.s")
        if text not in variants:
            variants.append(text)
        trials.append(
            {
                "limit": limit,
                "variant": variants.index(text),
                "stderr": done.stderr.strip("\n"),
            }
        )
    first = next(t["limit"] for t in trials if t["variant"] == 0)
    return {
        "total": total,
        "variants": variants,
        "trials": trials,
        "listing": listing,
        "first_good": first,
    }


def culprit(run: Runner, argv: list[str], nth: int) -> list[str]:
    """Where the compiler is when the counter reaches the number the bisection found.

    The condition is on the counter's own storage, before the increment, so `count[index]`
    is one less than the call number being asked about. Nothing else in the session needs a
    static variable by name, and this is the reason `--enable-checking=yes` is not enough on
    its own: an optimised build can put `count` somewhere gdb cannot name.
    """
    script = [
        f"break dbg_cnt if index == {COUNTER} && count[index] == {nth - 1}",
        "run " + " ".join(argv),
        "backtrace 8",
        "kill",
    ]
    _, outputs = drive(run, script)
    frames = [line for line in outputs[2].splitlines() if line.startswith("#")]
    if not frames:
        raise SystemExit(f"the debugger never reached call {nth} of {COUNTER}:\n{outputs[2]}")
    return frames


def spans() -> dict:
    for spec in SPANS:
        want = f"{spec['path']}:{spec['first']}@{PINNED_TAG}"
        if spec["cite"] != want:
            print(f"{spec['name']}: cite says {spec['cite']}, the span starts at {want}")
            raise SystemExit(1)
    wanted = [{k: v for k, v in spec.items() if k != "cite"} for spec in SPANS]
    return source.extract(GCC_ROOT, wanted, PINNED_TAG)


def check(cc1: replay.Session, bisect: replay.Bisect) -> int:
    """Everything the lesson asserts about the recording, asserted here instead of in prose.

    A transcript cannot be regenerated and compared, so this is the only place a rename in
    GCC or a change in gdb can be caught. It is worth the thirty lines: a session where
    `pcfun` has quietly started printing an error is a lesson that teaches an error.
    """
    wrong = []
    if "Successfully loaded GDB hooks for GCC" not in cc1.startup:
        wrong.append("gdbhooks did not load, so none of the pretty printer steps mean anything")
    if "auto-loading has been declined" not in cc1.declined:
        wrong.append("gdb did not decline the .gdbinit, so the recorded refusal is not one")
    for step in cc1.steps:
        if "Undefined command" in step.output:
            wrong.append(f"step {step.n}, {step.command!r}, is not a command any more")
    if "int f (int n)" not in cc1.find("pcfun").output:
        wrong.append("pcfun did not print the function")
    before, after = (s for s in cc1.steps if s.command == "pcfun")
    if "s_3 = 0;" not in before.output or "s_3 = 0;" in after.output:
        wrong.append("ccp did not do the thing the before and after are there to show")
    if "<PENDING>" not in cc1.find("break-on-pass ccp").output.replace("pending", "<PENDING>"):
        wrong.append("break-on-pass on a pass name resolved, so the trap is no longer a trap")
    if "No module named 'imp'" not in cc1.find("reload-gdbhooks").output:
        wrong.append("reload-gdbhooks worked, so this Python is older than the one CI has")
    if not bisect.monotone:
        wrong.append(f"the {bisect.counter} sweep is not a step function, so bisecting it lies")
    if bisect.narrow().answer != bisect.first_good:
        wrong.append("the binary search and the full sweep disagree")
    if not bisect.culprit[0].startswith("#0  dbg_cnt"):
        wrong.append(f"the innermost frame is {bisect.culprit[0]!r}, not dbg_cnt")
    for line in wrong:
        print(f"  {line}")
    return 1 if wrong else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", required=True, help="the gcc/ directory of a -O0 -g3 build tree")
    ap.add_argument("--docker", default="", help="run everything inside this running container")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    if not (GCC_ROOT / "gcc" / "gdbinit.in").exists():
        print(f"no GCC tree at {GCC_ROOT}. Run `just gcc-src` first.")
        return 1
    run = Runner(args.build, args.docker)
    if run.run(["test", "-f", "./cc1"]).returncode:
        print(f"no cc1 in {args.build}. See the lesson for how to build one.")
        return 1

    program = "/tmp/l1.c"
    run.write(program, PROGRAM.read_text(encoding="utf-8"))
    line = cc1_argv(run, program, "/dev/null")

    OUT.mkdir(parents=True, exist_ok=True)
    body = session(run, line)
    (OUT / "cc1.json").write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")

    swept = sweep(run, program)
    swept.update(
        {
            "recorded": body["recorded"],
            "tag": PINNED_TAG,
            "commit": body["commit"],
            "host": body["host"],
            "compiler": run.run(["./xgcc", "-B.", "--version"]).stdout.splitlines()[0].strip(),
            "counter": COUNTER,
            "flags": ["-S", "-O2"],
            "program": PROGRAM.name,
            "source": body["source"],
            "culprit": culprit(run, line, swept["first_good"]),
        }
    )
    del swept["first_good"]
    (OUT / "counters.json").write_text(json.dumps(swept, indent=1) + "\n", encoding="utf-8")

    CUTS.parent.mkdir(parents=True, exist_ok=True)
    CUTS.write_text(json.dumps(spans(), indent=1) + "\n", encoding="utf-8")

    cc1 = replay.load("cc1")
    bisect = replay.load_bisect("counters")
    shown = source.load_extract("b03")
    print(f"wrote corpora/replay/cc1.json, {cc1}")
    print(f"wrote corpora/replay/counters.json, {bisect}")
    print(f"wrote {CUTS.relative_to(ROOT)}, {len(shown)} spans, {shown.lines()} lines")
    print()
    print(bisect.narrow().report())
    print()
    print(bisect.culprit[1])
    print()
    return check(cc1, bisect)


if __name__ == "__main__":
    raise SystemExit(main())
