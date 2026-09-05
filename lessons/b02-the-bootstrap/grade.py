"""The B02 boss fight: eight questions about stages, comparisons and what they prove.

    python lessons/b02-the-bootstrap/grade.py
    python lessons/b02-the-bootstrap/grade.py --says '2; 3; no; ...'

Answers are separated by semicolons, matching B01, because two of them are lists.

Six of the eight are computed from `corpora/bootstrap/gcc.json`, which is the recording the
notebook read, so an answer cannot drift away from the tree the lesson was written against.

The other two are the interesting ones and they are not lookups. Question one is the fixed
point argument, which the notebook argues rather than prints, and question eight asks what
the comparison would say about a bug it cannot see. Both are one word answers that are only
one word if you followed the reasoning.

Marking is lenient about spelling and strict about the answer. Whitespace, case, a trailing
period, a leading `make ` or `--` and the order of a comma separated list are all ignored.
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

from gxray import bootstrap, toolchain  # noqa: E402

#: Where the answer and the explanation sit, under the number the question was asked with.
INDENT = " " * 7


def tidy(said: str) -> str:
    """One answer, with everything that is not the answer taken off it."""
    out = re.sub(r"\s+", " ", said.strip().lower()).strip(" .!")
    return out.removeprefix("make ").removeprefix("--").removeprefix("stage")


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


def questions() -> list[Question]:
    boot = bootstrap.load()
    compares = boot.compared[0]
    checksum = "gcc/cc1-checksum.o"
    hours = toolchain.plan("boot").minutes // 60

    return [
        Question(
            ask=(
                "You build GCC twice: stage one with your distribution's compiler, stage two"
                " with stage one. Why is comparing stage one against stage two not a test of"
                " anything? One word: what do they legitimately have that stage two and stage"
                " three do not?"
            ),
            answer="different builders",
            accepts=(
                "different compilers",
                "different builders",
                "they were built by different compilers",
                "different parents",
                "different builder",
                "different compiler",
            ),
            about=(
                "Stage one was compiled by a compiler you do not control and stage two by"
                " stage one, so they have every right to differ in inlining, register"
                " allocation and library version. Stage two and stage three were compiled by"
                " compilers that are supposed to be the same program, which is what makes a"
                " difference between them evidence of something."
            ),
            hint="the answer is about who compiled each of them, not about what is in them",
        ),
        Question(
            ask=(
                f"GCC declares {len(boot.stages)} bootstrap stages. How many of them compare"
                " their output against anything?"
            ),
            answer=str(len(boot.compared)),
            accepts=("two", f"{len(boot.compared)} of them"),
            about=(
                f"Only stage{compares.id} and stage4, and stage4 is not built by default. The"
                " profile guided stages are never compared, because a profiled compiler is"
                " deliberately not the same program as an unprofiled one."
            ),
            hint=f"fewer than you would like, out of {len(boot.stages)}",
        ),
        Question(
            ask=(
                "You want to know whether the compiler you just built can compile GCC, and you"
                f" do not have {hours} hours. Which make target builds two stages and stops?"
            ),
            answer=boot.stage("2").target,
            about=(
                f"{boot.stage('2').target} builds stage one and stage two and compares"
                " nothing, because there is nothing worth comparing yet. It is a much better"
                " smoke test than compiling hello world and it costs about two thirds of a"
                " full bootstrap."
            ),
            hint="it is named after the stage it stops at",
        ),
        Question(
            ask=(
                "Every stage builds in a directory called gcc, renamed from stageN-gcc before"
                " it starts and back afterwards. What breaks if you skip the renaming? Name"
                " the part of the object file that differs."
            ),
            answer="the debug information",
            accepts=(
                "debug info",
                "debug information",
                "the debug info",
                "dwarf",
                "the directory in the debug info",
                "dw_at_comp_dir",
                "the compilation directory",
            ),
            about=(
                "GCC records the directory it was invoked in as DW_AT_comp_dir, so the same"
                " source compiled in stage2-gcc and in stage3-gcc gives two object files that"
                " differ in a string. Every file would fail, for a reason that has nothing to"
                " do with compilers. Makefile.tpl:1747 says exactly this in a comment."
            ),
            hint="it is not the code, and it is why -g is involved",
        ),
        Question(
            ask=(
                "Stage three has an object file that stage two does not have, because a front"
                " end was enabled in between. What does the comparison say about it?"
            ),
            answer="nothing",
            accepts=(
                "it skips it",
                "it is skipped",
                "nothing at all",
                "it says nothing",
                "skipped",
                "silence",
            ),
            about=(
                "`if test ! -f $$f1; then continue; fi`. Not a warning, not a failure, not a"
                " line of output. The comparison passes, and one of the things it passed on is"
                " a file it never opened."
            ),
            hint="count the lines of output it produces",
        ),
        Question(
            ask=(
                f"The compare rule finds that {checksum} differs between the two stages. Does"
                " the build fail? Answer yes or no, and say why in a few words."
            ),
            answer=f"no, {boot.forgives(checksum)} forgives it",
            accepts=(
                "no",
                "no, it is on the exclusion list",
                "no, it is forgiven",
                "no, it is excluded",
                "no, checksums are excluded",
                "no it is an exclusion",
            ),
            about=(
                "It is on the compare_exclusions list at configure.ac:4405, matched after make"
                f" expands $(objext), so the pattern that catches it is {boot.forgives(checksum)}."
                " You get `warning: ... differs` and the build carries on. That one is honest:"
                " the checksum is a function of the stage and must differ."
            ),
            hint="there are six patterns and this is one of them",
        ),
        Question(
            ask=(
                "A real bootstrap fails and .bad_compare has one name in it. `cmp -l` says the"
                " first difference is at byte 60. Is that more likely to be a compiler bug or a"
                " reproducibility problem, and why?"
            ),
            answer="a compiler bug, because byte 60 is in the code",
            accepts=(
                "a compiler bug",
                "compiler bug",
                "a real bug",
                "a bug, it is in the code section",
                "compiler bug, it is code not strings",
                "a compiler bug, it is too early to be debug info",
            ),
            about=(
                "An offset that early is in the text section, which means the two compilers"
                " emitted different instructions for the same source. A path or a timestamp"
                " leaking in shows up a kilobyte or more into the file, in readable ASCII,"
                " which is what the induced pair in the lesson looks like."
            ),
            hint="where in an object file do strings live, and where does code live",
        ),
        Question(
            ask=(
                "Your compiler has a bug that mangles one construct, the same way, every single"
                " time, including when it compiles GCC's own source. Does the stage comparison"
                " catch it? Yes or no."
            ),
            answer="no",
            accepts=("no it does not", "no, it passes", "nope"),
            about=(
                "Stage two and stage three both have the bug and both apply it identically, so"
                " they are byte identical and the comparison is happy. It is a fixed point"
                " test, not a correctness test, and Ken Thompson's paper is about arranging"
                " exactly this on purpose. The comparison catches inconsistency."
            ),
            hint="what exactly is the comparison comparing",
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

    print(f"{bootstrap.load()}.")
    print(f"{len(asked)} questions about building it three times. Semicolons between answers.")

    answers = []
    for n, question in enumerate(asked, start=1):
        if typed:
            answers.append(typed[n - 1] if n <= len(typed) else "")
        else:
            answers.append(put(n, question, args.hints))

    print()
    scored = 0
    for question, said in zip(asked, answers, strict=True):
        right = question.marks(said)
        scored += right
        print(f"{'right' if right else 'wrong':<7}{question.first()}")
        print(f"{INDENT}{question.answer}")
        if not right:
            print(f"{INDENT}you said: {said or '(nothing)'}")
            print(paragraph(question.about))

    print(f"\n{scored} of {len(asked)}.")
    if scored == len(asked):
        print("You know what four hours buys and what it does not. If you want to spend them,")
        print("--enable-bootstrap and come back tomorrow. If you want two thirds of the answer")
        print("for two thirds of the time, make bootstrap2.")
        print("B03 next: a debugger attached to cc1, and how to stop on the pass you care about.")
        return 0
    print("\nEverything except the reasoning questions is in the notebook. To reread:")
    print("    from gxray import bootstrap")
    print("    boot = bootstrap.load()")
    print("    print(*boot.stages, sep='\\n')")
    print("    print(boot.compare().report())")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
