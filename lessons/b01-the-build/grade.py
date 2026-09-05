"""The B01 boss fight: eight questions about a configure line and a build.

    python lessons/b01-the-build/grade.py
    python lessons/b01-the-build/grade.py --says '2; c,c++,fortran,objc; d; ...'

Answers are separated by semicolons rather than commas, because two of the answers have
commas in them and a language list is exactly the kind of thing this lesson is about getting
right.

Nothing here is a memory test. Every expected answer is computed from `corpora/configure/gcc.json`
and `containers/matrix.toml`, which are the same two files the notebook read, so an answer
cannot drift away from the tree the lesson was written against. Six of the questions you can
answer from the notebook. One wants two rules from two different sections put together. One is
about your own machine, and the grader looks at your machine to mark it.

Marking is lenient about spelling and strict about the answer. Whitespace, case, a trailing
period, a leading `--enable-` and the order of a comma separated list are all ignored.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import configure, toolchain  # noqa: E402

#: Where the answer and the explanation sit, under the number the question was asked with.
INDENT = " " * 7


def tidy(said: str) -> str:
    """One answer, with everything that is not the answer taken off it."""
    out = re.sub(r"\s+", " ", said.strip().lower()).strip(" .")
    return out.removeprefix("--enable-").removeprefix("--")


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

    #: The right answer, computed from the recording rather than typed.
    answer: str

    #: What the reader should take away when they got it wrong, unwrapped.
    about: str

    #: How to compare. `list` ignores the order of a comma separated answer, and the default
    #: is exact once both sides have been through `tidy`.
    compare: str = "exact"

    #: A nudge, printed only with --hints.
    hint: str = ""

    #: Set when the grader could not work out an expected answer on this machine, in which
    #: case the question is a free mark and this says why.
    skip: str = ""

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


def machine() -> tuple[str, str]:
    """What this machine's own gcc calls itself, and why not, when it will not say."""
    found = shutil.which("gcc") or shutil.which("cc")
    if not found:
        return ("", "no gcc or cc on your PATH, so this one is a free mark")
    try:
        done = subprocess.run(
            [found, "-dumpmachine"], capture_output=True, text=True, timeout=20, check=True
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return ("", f"{found} would not answer -dumpmachine: {exc}")
    printed = done.stdout.strip()
    return (printed, "") if printed else ("", f"{found} printed nothing for -dumpmachine")


def questions() -> list[Question]:
    build = configure.load()
    gmp = build.requires[0]
    every = [toolchain.plan(name) for name in toolchain.names()]
    cheapest = min(
        (plan for plan in every if plan.config.from_source), key=lambda plan: plan.minutes
    )
    between = f"{gmp.hard.rsplit('.', 1)[0]}.9"
    triple, why = machine()

    return [
        Question(
            ask=(
                "You configure with --enable-languages=c++ and nothing else."
                " How many front ends does that build?"
            ),
            answer="2",
            accepts=("two", "c and c++", "c, c++"),
            about=(
                "C is appended to the list unconditionally at configure.ac:2407, so the"
                " shortest language list you can ask for is still two front ends."
            ),
            hint=f"one of the {len(build.languages)} is not optional",
        ),
        Question(
            ask=(
                "You configure with no --enable-languages at all. Which front ends do you get?"
                " Name them, comma separated."
            ),
            answer=",".join(build.default_languages),
            compare="list",
            about=(
                "Nothing keeps this list. The top level configure sources all"
                f" {len(build.languages)} config-lang.in files and takes the ones whose"
                " build_by_default is not no."
            ),
            hint=f"{len(build.default_languages)} of the {len(build.languages)}",
        ),
        Question(
            ask=(
                "A backtrace names a program called d21 and you have never heard of it."
                " Which language is that the front end for?"
            ),
            answer=build.language("d").name,
            about=(
                "The word, the directory and the program are three different spellings and"
                " none of them has to match. c++ lives in gcc/cp and its program is cc1plus."
            ),
            hint="it is in the front end table in the lesson",
        ),
        Question(
            ask=(
                "You unpack the GCC 16.2 release tarball and configure it with no"
                " --enable-checking. Which checking level do you get?"
            ),
            answer=build.checking.default,
            about=(
                "gcc/DEV-PHASE is empty on a release tag and says experimental on a"
                " development branch, and gcc/configure.ac:640 reads it. The same configure"
                f" line against a git checkout of master gets {build.checking.development}."
            ),
            hint="one of: " + ", ".join(build.checking.levels),
        ),
        Question(
            ask=(
                "You pass --enable-checking=tree. Which checking words end up applied?"
                " Comma separated."
            ),
            answer="release,tree",
            compare="list",
            about=(
                "The loop at gcc/configure.ac:661 reads `for check in release"
                " $ac_checking_flags`, so release goes on first whatever you asked for."
                " Naming one flag does not turn the release checks off."
            ),
            hint="it is not one word",
        ),
        Question(
            ask=(
                f"Your distribution ships GMP {between}, which is above the version configure"
                " refuses and below the one it wants. What does configure print for gmp.h?"
            ),
            answer="buggy but acceptable",
            about=(
                f"gmp refuses below {gmp.hard} and says yes at {gmp.good}. Between the two it"
                " prints that, keeps going, and you will not notice it in four hundred lines"
                " of log."
            ),
            hint="four words, and it is in the excerpt in the lesson",
        ),
        Question(
            ask=(
                "Of this project's configurations that build GCC from source, which is the"
                " quickest, and how many minutes?"
            ),
            answer=f"{cheapest.id} {cheapest.minutes}",
            accepts=(
                f"{cheapest.id}, {cheapest.minutes}",
                f"{cheapest.id} {cheapest.minutes} minutes",
                f"{cheapest.id}, {cheapest.minutes} minutes",
            ),
            about=(
                f"{cheapest.id} at {cheapest.minutes} minutes, which is"
                f" {cheapest.config.purpose[0].lower()}{cheapest.config.purpose[1:]}"
                " plug is quicker at 5 minutes and compiles no GCC at all, which is why the"
                " question said from source."
            ),
            hint="not plug, which builds nothing",
        ),
        Question(
            ask=(
                "About your own machine. What does `gcc -dumpmachine` print here?"
                " That is the target triple your compiler was configured for."
            ),
            answer=triple,
            skip=why,
            about=(
                "A triple is not always three parts, and the one your distribution's compiler"
                " was built for is the default target of anything you build yourself unless"
                " you say --target. B04 is where that stops being a formality."
            ),
            hint="run it",
        ),
    ]


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

    print(f"{configure.load()}.")
    print(f"{len(asked)} questions about configuring it. Semicolons between answers.")

    answers = []
    for n, question in enumerate(asked, start=1):
        if typed:
            answers.append(typed[n - 1] if n <= len(typed) else "")
        else:
            answers.append(put(n, question, args.hints))

    print()
    scored = 0
    for question, said in zip(asked, answers, strict=True):
        if question.skip:
            print(f"free   {question.first()}")
            print(paragraph(question.skip))
            scored += 1
            continue
        right = question.marks(said)
        scored += right
        print(f"{'right' if right else 'wrong':<7}{question.first()}")
        print(f"{INDENT}{question.answer}")
        if not right:
            print(f"{INDENT}you said: {said or '(nothing)'}")
            print(paragraph(question.about))

    print(f"\n{scored} of {len(asked)}.")
    if scored == len(asked):
        print("Now go and build one. The rel route is twenty two minutes and the commands are")
        print("at the end of the notebook, and if it fails the devcontainer is one click.")
        print("B02 next: what --disable-bootstrap turned off, and why anybody would wait.")
        return 0
    print("\nEverything except the last question is in the notebook. The tables to reread:")
    print("    from gxray import configure")
    print("    build = configure.load()")
    print("    print(build.languages, build.checking, build.requires, sep='\\n')")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
