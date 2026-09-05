"""The B03 boss fight: eight questions about stopping the compiler and about the counter.

    python lessons/b03-the-debugger/grade.py
    python lessons/b03-the-debugger/grade.py --says 'driver; 351; ignore; ...'

Answers are separated by semicolons, matching B01 and B02.

Five of the eight are computed from `corpora/replay/cc1.json` and `corpora/replay/counters.json`,
which are the two recordings the notebook read, so an answer cannot drift away from the session
it was written against. The pass count in question two is read out of gdb's own hit count, and
the number of probes in question seven is the bisection running.

The other three are the ones worth thinking about. Question five gives a symptom with no error
message in it, question six is about what a limit actually means, and question eight is the
property of a debug counter that makes it useful and dangerous in the same breath.

Marking is lenient about spelling and strict about the answer. Whitespace, case, a trailing
period, a leading `a `, `the ` or `-` and the order of a comma separated list are all ignored.
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import replay  # noqa: E402

#: Where the answer and the explanation sit, under the number the question was asked with.
INDENT = " " * 7


def tidy(said: str) -> str:
    """One answer, with everything that is not the answer taken off it."""
    out = re.sub(r"\s+", " ", said.strip().lower()).strip(" .!")
    for prefix in ("a ", "an ", "the ", "-", "gdb ", "it is "):
        out = out.removeprefix(prefix)
    return out.strip()


def listed(said: str) -> str:
    """A comma separated answer, sorted, so the order it was typed in does not matter."""
    return ",".join(sorted(part for part in re.split(r"[,\s]+", tidy(said)) if part))


def paragraph(text: str, indent: str = INDENT, first: str | None = None) -> str:
    """One long line of prose, wrapped to fit a terminal and indented under its question."""
    return textwrap.fill(
        " ".join(text.split()),
        width=88,
        initial_indent=indent if first is None else first,
        subsequent_indent=indent,
    )


@dataclass(frozen=True)
class Question:
    #: The question, as one unwrapped paragraph. Wrapping happens when it is printed.
    ask: str

    #: The right answer, computed from the recordings rather than typed.
    answer: str

    #: What the reader should take away when they got it wrong, unwrapped.
    about: str

    #: How to compare. `list` ignores the order of a comma separated answer, and the default
    #: is exact once both sides have been through `tidy`.
    compare: str = "exact"

    #: A nudge, printed only with --hints.
    hint: str = ""

    #: Other wordings that are the same answer.
    accepts: tuple[str, ...] = field(default_factory=tuple)

    def marks(self, said: str) -> bool:
        if self.compare == "list":
            return listed(said) == listed(self.answer)
        got = tidy(said)
        return got == tidy(self.answer) or got in tuple(tidy(a) for a in self.accepts)

    def first(self) -> str:
        """The opening clause, for the one line summary at the end."""
        words = self.ask.split()
        short = " ".join(words[:11])
        return short + (" ..." if len(words) > 11 else "")


def executions(session: replay.Session) -> int:
    """How many times the pass manager ran, out of gdb's own hit count in the recording."""
    counted = [one for one in session.steps if one.command == "info breakpoints"][-1]
    found = re.search(r"breakpoint already hit (\d+) times", counted.output)
    if not found:
        raise SystemExit("the recorded session has no hit count in it any more")
    return int(found.group(1))


def questions() -> list[Question]:
    session = replay.load("cc1")
    bisect = replay.load_bisect("counters")
    ran = executions(session)
    probes = len(bisect.narrow().probes)

    return [
        Question(
            ask=(
                "You want to stop inside the compiler while it compiles one C file, so you run"
                " gdb on gcc and set a breakpoint. Nothing you want to see ever happens. One"
                " word: what is the program called gcc?"
            ),
            answer="a driver",
            accepts=("driver", "wrapper", "a wrapper", "the driver"),
            about=(
                "It computes a command line and executes cc1 as a separate process, so a"
                " breakpoint in it stops in a program that does no compiling. `gcc -### -O2"
                " file.c` prints the command line to run under gdb yourself, and `gcc -wrapper"
                " gdb,--args` puts a debugger in front of every subprocess instead."
            ),
            hint="it is the same word Part I used for it, and BP-DRIVER is named after it",
        ),
        Question(
            ask=(
                "A breakpoint on execute_one_pass, with `ignore $bpnum 1000000` so it counts"
                " instead of stopping. Nine lines of C, at -O2, one function. How many times"
                " does it fire? Within fifty is right."
            ),
            answer=str(ran),
            compare="near",
            about=(
                f"{ran}. That is one function and nine lines. A real translation unit multiplies"
                " it by the number of functions, which is why a conditional breakpoint here,"
                " where gdb evaluates the condition and therefore stops and resumes the inferior"
                " on every hit, can take minutes to get anywhere."
            ),
            hint="more than a hundred, fewer than a thousand",
        ),
        Question(
            ask=(
                "Which gdb command turns a breakpoint into a counter, so that it records every"
                " hit and never stops the program? One word."
            ),
            answer="ignore",
            accepts=("ignore count", "ignore $bpnum"),
            about=(
                "`ignore $bpnum 1000000`. The count comes back out of `info breakpoints` as"
                " `breakpoint already hit N times`. It is the cheapest way to find out how bad a"
                " breakpoint is going to be before you rely on it, and it is worth reaching for"
                " before any conditional breakpoint in a hot function."
            ),
            hint="it takes a breakpoint number and a very large number",
        ),
        Question(
            ask=(
                "`break-on-pass ccp` prints two lines and then never fires, and the pass"
                " definitely ran. What should you have typed instead?"
            ),
            answer="break-on-pass pass_ccp",
            accepts=("pass_ccp", "the class name", "break on pass pass_ccp"),
            about=(
                "The argument is interpolated into `(anonymous namespace)::%s::execute` with"
                " nothing added and nothing checked, so it has to be the class name. Tab"
                " completion offers the right one, because it reads passes.def and collects"
                " class names. The word that tells you it went wrong is `pending`."
            ),
            hint="what does gdbhooks.py do with the string you gave it",
        ),
        Question(
            ask=(
                "A colleague says every command in this lesson reports `Undefined command` in"
                " their build tree, and that gdb printed no errors at startup. What happened?"
                " Two or three words."
            ),
            answer="auto-loading was declined",
            accepts=(
                "auto load declined",
                "auto-load declined",
                "autoload declined",
                "gdb declined to load .gdbinit",
                "it did not load .gdbinit",
                "the gdbinit was not loaded",
                "auto-loading has been declined",
                "safe path",
                "the auto-load safe path",
            ),
            about=(
                "gdb refuses to source a .gdbinit from the current directory unless the"
                " directory is on the auto-load safe path, and it says so as a warning rather"
                " than an error, so it scrolls past. Every command, every printer and all four"
                " breakpoints are then missing. The fix goes in ~/.config/gdb/gdbinit, and on a"
                " command line it needs -iex rather than -ex, because the local file is read"
                " before any -ex runs."
            ),
            hint="the word error does not appear anywhere in the message they missed",
        ),
        Question(
            ask=(
                "You compile with -fdbg-cnt=match:20. Which calls of the match counter are"
                " allowed to do their transformation? Give the range."
            ),
            answer="1 to 20",
            accepts=(
                "1-20",
                "the first 20",
                "first 20",
                "1 through 20",
                "the first twenty",
                "one to twenty",
                "calls 1 to 20",
            ),
            about=(
                "A bare number is the high end of a range whose low end is one, so :20 means the"
                " first twenty and not the twentieth. :0 is the one case where the low end is"
                " zero, which is how a counter is turned off entirely. Ranges can be given"
                " directly as :2-3, and overlapping ones are an error."
            ),
            hint="it is a range and not a single value, and there are two numbers in it",
        ),
        Question(
            ask=(
                f"The match counter fires {bisect.total} times on your file and you have no"
                " debug build, so you bisect it with -fdbg-cnt. In the recorded sweep, how many"
                " compilations does the bisection need to land on one transformation?"
            ),
            answer=str(probes),
            accepts=(f"{probes} compilations", f"{probes} probes"),
            about=(
                f"{probes}, against {len(bisect.trials)} for sweeping every limit one at a time."
                " That is the whole argument for bisecting rather than sweeping, and on a real"
                " bug where one compilation is a build rather than nine lines it is the"
                " difference between an afternoon and a coffee. The answer is only meaningful if"
                " every limit above the culprit is good, which gxray.replay checks and calls"
                " monotone."
            ),
            hint="halve the range each time and count the halvings",
        ),
        Question(
            ask=(
                "A debug counter's value is a position in what? Not the pass, and not the"
                " function. Two or three words, and the consequence is the point."
            ),
            answer="the whole compilation",
            accepts=(
                "whole compilation",
                "the translation unit",
                "translation unit",
                "the compilation",
                "the whole translation unit",
                "the file",
            ),
            about=(
                "`count` is file static and is never reset, so it counts calls across every"
                " function in the order the functions are compiled. The consequence is that a"
                " number you bisected yesterday means nothing today if anything moved: a"
                " function added to the file, an inlining decision changed, LTO turned on. Write"
                " the number down with the exact source it came from or do not write it down."
            ),
            hint="what would happen to your bisected number if you added a function to the file",
        ),
    ]


def marks(question: Question, said: str) -> bool:
    """One answer, marked. `near` is the numeric one, where fifty either way is right."""
    if question.compare != "near":
        return question.marks(said)
    found = re.search(r"-?\d+", said)
    return bool(found) and abs(int(found.group(0)) - int(question.answer)) <= 50


def put(n: int, question: Question, hints: bool) -> str:
    """Ask one question, and read the answer if there is somebody there to give one."""
    print()
    print(paragraph(question.ask, indent="   ", first=f"{n}. "))
    if hints and question.hint:
        print(f"   ({question.hint})")
    if not sys.stdin.isatty():
        return ""
    return input("   > ").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--says", help="the answers, semicolon separated, in the order asked")
    parser.add_argument("--hints", action="store_true", help="print a nudge with each question")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    asked = questions()
    typed = [part.strip() for part in args.says.split(";")] if args.says else []

    print(f"{replay.load('cc1')}.")
    print(f"{len(asked)} questions about stopping it and looking at it. Semicolons between.")

    answers = []
    for n, question in enumerate(asked, start=1):
        if typed:
            answers.append(typed[n - 1] if n <= len(typed) else "")
        else:
            answers.append(put(n, question, args.hints))

    print()
    scored = 0
    for question, said in zip(asked, answers, strict=True):
        right = marks(question, said)
        scored += right
        print(f"{'right' if right else 'wrong':<7}{question.first()}")
        print(f"{INDENT}{question.answer}")
        if not right:
            print(f"{INDENT}you said: {said or '(nothing)'}")
            print(paragraph(question.about))

    print(f"\n{scored} of {len(asked)}.")
    if scored == len(asked):
        print("You can get a debugger in front of cc1, stop it on the pass you care about, and")
        print("find the transformation that broke your code without a debugger at all.")
        print("B04 next: forty thousand tests, and how to run one of them.")
        return 0
    print("\nEverything except the reasoning questions is in the notebook. To reread:")
    print("    from gxray import replay")
    print("    cc1 = replay.load('cc1')")
    print("    print(*cc1.groups, sep='\\n')")
    print("    print(cc1.transcript('stopping on the pass you care about'))")
    print("    print(replay.load_bisect('counters').narrow().report())")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
