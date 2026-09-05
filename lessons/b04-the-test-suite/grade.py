"""The B04 boss fight: nine questions about directives, command lines and `.sum` files.

    python lessons/b04-the-test-suite/grade.py
    python lessons/b04-the-test-suite/grade.py --says '4; dg-additional-options; ...'

Answers are separated by semicolons, matching B01, B02 and B03.

Four of the nine are computed from `corpora/testsuite/b04.json`, which is the recording the
notebook read, so an answer cannot drift away from the compilations it was written against.
Question one counts the results the model produces from a real file and a real compiler
output, and question six counts the torture option sets out of the pinned tree.

The other five are the ones worth thinking about. Two of them give you a change to a test file
and ask what the verdict becomes, which is the skill the lesson is for. The last two are about
reading a run rather than reading a test, and both have an answer that most people get wrong
in the same direction: they look at the counts.

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

from gxray import dejagnu  # noqa: E402

#: Where the answer and the explanation sit, under the number the question was asked with.
INDENT = " " * 7


def tidy(said: str) -> str:
    """One answer, with everything that is not the answer taken off it."""
    out = re.sub(r"\s+", " ", said.strip().lower()).strip(" .!")
    for prefix in ("a ", "an ", "the ", "-", "it is ", "state "):
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

    #: The right answer, computed from the recording where it can be.
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
    corpus = dejagnu.load()
    flex = corpus["flex"]
    results = dejagnu.check(flex.test, flex.stderr)
    sets = len(dejagnu.torture_list(corpus["torture-0"].text))

    return [
        Question(
            ask=(
                "A file in gcc.dg has three dg-error directives, and the compiler printed"
                " exactly those three errors and nothing else. How many lines does that one"
                " compilation put in the .sum?"
            ),
            answer=str(len(results)),
            accepts=("four", f"{len(results)} lines", f"{len(results)} results"),
            about=(
                "Four. One per directive, and one more that nothing in the file asked for:"
                " `(test for excess errors)`. Every compiled test gets that line, and it is the"
                " one that makes the suite catch things nobody predicted. Counting directives"
                " and expecting that many results is the first thing that surprises people"
                " reading a .sum against a test file."
            ),
            hint="count the directives, then count again",
        ),
        Question(
            ask=(
                'A test in gcc.dg needs -O2. Its author writes dg-options "-O2" and the test'
                " starts failing for reasons that have nothing to do with -O2. Which directive"
                " should they have used?"
            ),
            answer="dg-additional-options",
            accepts=("dg-additional-options", "additional options"),
            about=(
                "`dg-options` replaces the directory's default flags rather than adding to"
                ' them, so a test in gcc.dg that writes `dg-options "-O2"` has quietly given'
                " up `-ansi -pedantic-errors` and is now compiled as GNU C with warnings where"
                " it used to get errors. `dg-additional-options` is the one that adds. This is"
                " the single most common misreading of a GCC test."
            ),
            hint="what happened to the flags the directory was going to pass",
        ),
        Question(
            ask=(
                "Three words, and they are the name of a result rather than a description: what"
                " does a GCC test check that its author never wrote down?"
            ),
            answer="excess errors",
            accepts=(
                "test for excess errors",
                "excess errors",
                "unexpected output",
                "excess output",
            ),
            about=(
                "Every diagnostic is matched against the expectations, each satisfying at most"
                " one, and what is left over after pruning is reported as excess errors. That"
                " is what makes a GCC test subtractive: three dg-error directives mean these"
                " three and nothing else. It is also why a test can pass every directive it"
                " contains and fail anyway."
            ),
            hint="it is the fourth line in the answer to question one",
        ),
        Question(
            ask=(
                "A test prints an error it expects and a note that no directive mentions, and it"
                " passes. Add one directive anywhere in the file and the same compiler output"
                " now fails the test. Which directive?"
            ),
            answer="dg-note",
            accepts=("dg-note", "note"),
            about=(
                "Notes are pruned before excess errors are counted, unless the file used"
                " `dg-note` at least once, which sets `prune_notes` to zero for the whole file."
                " So a per line directive changes the meaning of every note in the file, and a"
                " test that accounts for one note has signed up to account for all of them."
                ' `dg-message "note: [...]"` is the way to check one without that.'
            ),
            hint="the switch is per file and the directive is per line",
        ),
        Question(
            ask=(
                'A test has dg-final { scan-tree-dump-times "Replaced " 6 "fre1" } and'
                " somebody edits its dg-options and drops the -fdump-tree-fre1 flag. One word:"
                " which state appears in the .sum?"
            ),
            answer="unresolved",
            accepts=("unresolved", "unresolved not fail"),
            about=(
                "`UNRESOLVED`, not `FAIL`. A missing dump is a check that could not be decided"
                " rather than a check that failed, and `scan-dump-times` returns before it ever"
                " looks for the pattern. It is worth knowing because UNRESOLVED is one of the"
                " states people have trained themselves to skip, and a whole directory of dump"
                " scans can go quiet this way without anything turning red."
            ),
            hint="the harness cannot say the test failed, because it never read anything",
        ),
        Question(
            ask=(
                "gcc.dg/torture holds about four hundred small C files. Roughly how many"
                " compilations does running that one directory cost? A number."
            ),
            answer=str(sets * 400),
            compare="near",
            accepts=(),
            about=(
                f"About {sets * 400}. Every file in a torture directory is compiled once per"
                f" option set and there are {sets} of them, from -O0 to -Os. That multiplication"
                " is most of the answer to why `make check` takes hours, and it is also why a"
                " torture failure is reported with the option set in the test name: the same"
                " file passed five times and failed once."
            ),
            hint="the file is compiled more than once",
        ),
        Question(
            ask=(
                "You want to run gcc.dg/pr87309.c and nothing else. Write the value of"
                " RUNTESTFLAGS, exactly, that does it."
            ),
            answer="dg.exp=pr87309.c",
            accepts=('"dg.exp=pr87309.c"', "dg.exp=pr87309*", "dg.exp=pr87309.c "),
            about=(
                '`make check-gcc RUNTESTFLAGS="dg.exp=pr87309.c"`. The part before the equals'
                " sign names the .exp file, which is to say the directory, and the part after is"
                " a glob matched against the base name of each test. The .exp still runs in"
                " full, works out the target's capabilities and walks the directory before the"
                " filter drops anything, so this takes seconds rather than no time at all."
            ),
            hint="two parts, one equals sign, and the left half is a file name",
        ),
        Question(
            ask=(
                "You compare yesterday's .sum with today's. Same number of passes, same number"
                " of failures, and four tests changed. Which of the four kinds of change should"
                " worry you most? Name the kind, not the test."
            ),
            answer="a test that stopped being run",
            accepts=(
                "a test that stopped being run",
                "test that stopped being run",
                "gone",
                "a test that vanished",
                "a missing test",
                "tests that disappeared",
                "a test that is no longer run",
            ),
            about=(
                "A name in the old file and not in the new one. It did not fail, it stopped"
                " being run, usually because an effective target check changed its answer or a"
                " dg-skip-if grew a target. The counts cannot show you that, because some other"
                " test appeared and made the total up again, and a regression at least turns"
                " something red. This is why contrib/compare_tests exists and why comparing"
                " summary blocks is not comparing runs."
            ),
            hint="one of the four is invisible to every count in the file",
        ),
        Question(
            ask=(
                "make check -j16 starts sixteen runtest processes and each one walks the whole"
                " list of tests, racing to create a marker file per batch of ten. All sixteen"
                " must enumerate the tests in the same order. One word: what in GCC verifies"
                " that they did?"
            ),
            answer="nothing",
            accepts=("nothing", "no", "none", "nothing does", "it does not"),
            about=(
                "Nothing. The assumption is written in a comment in lib/gcc-defs.exp and checked"
                " by no code anywhere. When it is violated, one process claims the marker for"
                " batch 3 and another honours it for a different ten files, so some tests are"
                " never run and others are run twice, and the totals still look right. GCC's"
                " own answer is a five step manual recipe in the same comment, ending in"
                " md5sum. This is invariant I4 in BP-TESTSUITE."
            ),
            hint="read the comment above the code, then look for the code that enforces it",
        ),
    ]


def marks(question: Question, said: str) -> bool:
    """One answer, marked. `near` is the numeric one, where a factor of two either way is fine."""
    if question.compare != "near":
        return question.marks(said)
    found = re.search(r"-?\d[\d,]*", said.replace(" ", ""))
    if not found:
        return False
    got = int(found.group(0).replace(",", ""))
    want = int(question.answer)
    return want // 2 <= got <= want * 2


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

    print(f"{dejagnu.load().banner}.")
    print(f"{len(asked)} questions about reading one of them. Semicolons between.")

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
        print("You can read a GCC test, work out what it will actually be compiled with, say")
        print("what its verdict will be, run it on its own, and tell a real regression from a")
        print("test that quietly stopped running.")
        print("B05 next: a pass of your own, in a plugin, with no patch to GCC.")
        return 0
    print("\nEverything except the reasoning questions is in the notebook. To reread:")
    print("    from gxray import dejagnu")
    print("    corpus = dejagnu.load()")
    print("    flex = corpus['flex']")
    print("    print(*dejagnu.check(flex.test, flex.stderr), sep='\\n')")
    print("    print(*dejagnu.excess(corpus['flex-c90'].test, corpus['flex-c90'].stderr))")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
