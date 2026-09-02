"""The T09 boss fight, graded.

Three lines of assembly with the annotation taken off. Name the pattern that emitted each
one, then two questions about the rule that decides whether the annotation prints a slash.

    python lessons/t09-the-last-mile/grade.py
    python lessons/t09-the-last-mile/grade.py \\
        --patterns '*movsi_aarch64,*addsi3_aarch64,*do_return' --no-slash 2 --rows 21

The answers are read out of the recording and out of the machine description extract, so
there is no written down answer key. Re-record the corpus against a newer compiler and the
grader marks against whatever that compiler printed.

Quote the pattern names on the command line. A leading `*` is a glob to the shell and an
unquoted `*movsi_aarch64` will either expand to nothing useful or fail outright.
"""

from __future__ import annotations

import argparse
import sys

from gxray import asm, corpus_store, mdesc

#: The recording the questions are about. Four lines of C, forty six lines of assembly.
ENTRY = "t09-final"

#: The target whose machine description the extract came from.
TARGET = "aarch64"

#: The three lines the reader has to place, in the order they are asked about. Each one is
#: the instruction text with the annotation and the `-fverbose-asm` comment cut off, which
#: is exactly what a reader looking at an ordinary `-S` output would have.
QUESTIONS = ("mov     w0, 0", "add     w1, w1, 1", "ret")

#: The pattern the last question is about. Twenty one alternatives, which is the largest
#: table in this lesson's extract and the reason `mov` is the pattern worth looking at.
SUBJECT = "*movsi_aarch64"


def listing() -> asm.Listing:
    record = corpus_store.load(ENTRY)
    return asm.parse(record.asm, ENTRY)


def emitted(lines: asm.Listing, text: str) -> str:
    """The pattern that emitted the first instruction whose text matches."""
    wanted = " ".join(text.split())
    for line in lines.insns:
        if " ".join(f"{line.name} {line.args}".split()) == wanted:
            return line.pattern
    return ""


def ask(question: str, given: str | None) -> str:
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def names(said: str) -> list[str]:
    """The pattern names the reader typed, in the order they typed them."""
    return [w.strip() for w in said.replace(",", " ").split() if w.strip()]


def number(said: str) -> int | None:
    for word in said.replace(",", " ").split():
        if word.lstrip("-").isdigit():
            return int(word)
    return None


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--patterns", help="the three pattern names, in order, comma separated")
    parser.add_argument("--no-slash", dest="quiet", help="how many patterns print no alternative")
    parser.add_argument("--rows", help=f"how many alternatives {SUBJECT} has")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    lines = listing()
    machine = mdesc.load_extract(TARGET)
    used = lines.patterns()

    print(f"{ENTRY}: {lines.counts()['total']} lines, {len(lines.insns)} instructions")
    print(f"{len(used)} patterns emitted them. Three of the lines, with the margin cut off:")
    for text in QUESTIONS:
        print(f"        {text}")
    print()

    said_patterns = ask("Which pattern emitted each, in that order?", args.patterns)
    said_quiet = ask("How many of the five patterns print no alternative?", args.quiet)
    said_rows = ask(f"How many alternatives does {SUBJECT} have?", args.rows)

    answer = [emitted(lines, text) for text in QUESTIONS]
    quiet = [name for name, uses in used.items() if all(x.alternative is None for x in uses)]
    rows = len(machine["patterns"][SUBJECT]["alternatives"])

    scored = [
        mark(
            "which pattern emitted each line",
            names(said_patterns) == answer,
            ", ".join(answer),
            [
                f"{' '.join(text.split()):<20} {name}"
                for text, name in zip(QUESTIONS, answer, strict=True)
            ],
        ),
        mark(
            "how many patterns print no alternative",
            number(said_quiet) == len(quiet),
            str(len(quiet)),
            [
                f"{', '.join(quiet)} print no slash",
                "both of them emit a C block rather than a table, so there is one of it",
            ],
        ),
        mark(
            f"how many alternatives {SUBJECT} has",
            number(said_rows) == rows,
            str(rows),
            [
                f"{machine['patterns'][SUBJECT]['citation']}",
                f"this function used {sorted({x.alternative for x in used[SUBJECT]})} of them",
            ],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        rets = " and ".join(str(x.uid) for x in lines.insns if x.pattern == "*do_return")
        print("The third line is the one worth a sentence. This function has two `ret`")
        print(f"instructions, from insns {rets}, one for the loop exit and one for the case")
        print("where the loop never ran. Neither carries a slash, and that is not because")
        print("they are the same instruction. It is because `*do_return` emits a C block,")
        print("so there is no table and nothing to number.")
        return 0
    print("\nEvery answer here is printed in the file, if you compile with -dp:")
    print("    from gxray import asm, corpus_store")
    print("    lines = asm.parse(corpus_store.load('t09-final').asm)")
    print("    [x.slot for x in lines.insns]")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
