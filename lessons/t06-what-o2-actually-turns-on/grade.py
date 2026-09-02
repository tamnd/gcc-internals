"""The T06 boss fight, graded.

Rebuild `-O2` out of `-O1` for L1 first, then run this. It says which of the three you got
right and prints the evidence either way, so a wrong answer is something you can go and look
at rather than something you have to take on trust.

    python lessons/t06-what-o2-actually-turns-on/grade.py
    python lessons/t06-what-o2-actually-turns-on/grade.py --flags 4 --switches-only 86

Nothing here is hardcoded. The candidate flags come from diffing two recorded help tables and
the answers come from recorded assembly, so re-recording the corpus against a newer compiler
or a different target cannot leave the grader marking against a stale answer key.
"""

from __future__ import annotations

import argparse
import sys

from gxray import corpus_store, options

ENTRY = "t06-levels"

#: What the reader is trying to reproduce. Everything in this file is measured against the
#: assembly recorded for this one command line.
GOAL = "-O2"

#: The flags that are about where code sits rather than what the code is. Three of the four
#: in the answer are one of these, which is what makes the fourth the interesting question.
ALIGNMENT = "-falign-"


def candidates(record) -> tuple[list[str], list[str]]:
    """The 55 differences between -O1 and -O2, as flags, in two piles.

    The same two piles the lesson builds, and in the same order, because the recorded
    command lines were built from this and a different order would not find them.
    """
    level = options.by_level(record.option_texts)
    switches, values = [], []
    for change in options.diff(level["-O1"], level["-O2"]):
        flag = change.as_flag()
        if flag is None:
            continue
        (switches if change.kind == "on" else values).append(flag)
    return switches, values


def answers() -> dict:
    """Every answer, read off the recording rather than written down."""
    record = corpus_store.load(ENTRY)
    switches, values = candidates(record)
    goal = record.asm_texts[GOAL]

    matched = [k for k in record.asm_texts if k.startswith("-O1 ") and record.asm_texts[k] == goal]
    smallest = min(matched, key=len)
    needed = smallest.split()[1:]

    switches_only = " ".join(["-O1", *switches])
    return {
        "candidates": len(switches) + len(values),
        "needed": needed,
        "odd": [f for f in needed if not f.startswith(ALIGNMENT)],
        "switches_only": len(record.asm_texts[switches_only].splitlines()),
        "lines": {
            "-O1": len(record.asm_texts["-O1"].splitlines()),
            "-O2": len(goal.splitlines()),
            "-O1 plus 48 switches": len(record.asm_texts[switches_only].splitlines()),
            "the irreducible set": len(record.asm_texts[smallest].splitlines()),
        },
    }


def ask(question: str, given: str | None) -> str:
    """Take the answer from the command line, or ask for it if it was not given."""
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def number(text: str) -> int:
    return int(text) if text.strip().isdigit() else -1


def flagged(said: str, wanted: list[str]) -> bool:
    """A flag answer, forgiving about whether the value was typed out.

    `-freorder-blocks-algorithm=stc` and `-freorder-blocks-algorithm` are the same answer to
    the question being asked, and the reader may have copied either.
    """
    given = said.strip()
    return any(given in (flag, flag.split("=")[0]) for flag in wanted)


def glue(argv: list[str]) -> list[str]:
    """Join `--odd-one-out -fsomething` into one token before argparse sees it.

    The answer to the second question is itself a flag, and argparse reads anything starting
    with a dash as the next option no matter what came before it. Rewriting the pair as
    `--odd-one-out=-fsomething` is the usual way around that, and it means the reader can type
    the answer the way the lesson quotes it instead of learning an argparse rule first.
    """
    out: list[str] = []
    pending = None
    for word in argv:
        if pending is not None:
            out.append(f"{pending}={word}")
            pending = None
        elif word == "--odd-one-out":
            pending = word
        else:
            out.append(word)
    if pending is not None:
        out.append(pending)
    return out


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--flags", help="how many flags are in the irreducible set for L1")
    parser.add_argument("--odd-one-out", dest="odd", help="the one that is not an alignment flag")
    parser.add_argument("--switches-only", dest="switches", help="lines from -O1 plus the 48")
    args = parser.parse_args(glue(sys.argv[1:] if argv is None else argv))

    key = answers()
    print(f"{key['candidates']} flags between -O1 and -O2, on {ENTRY}")

    said_flags = ask("How many flags does L1 need?", args.flags)
    said_odd = ask("Which of them is not an alignment flag?", args.odd)
    said_switches = ask("How many lines does -O1 plus the 48 switches give?", args.switches)

    scored = [
        mark(
            "the size of the irreducible set for L1",
            number(said_flags) == len(key["needed"]),
            str(len(key["needed"])),
            [" ".join(key["needed"])],
        ),
        mark(
            "the one that is not an alignment flag",
            flagged(said_odd, key["odd"]),
            " or ".join(key["odd"]),
            ["the other three move code around without changing an instruction"],
        ),
        mark(
            "lines from -O1 plus the 48 switches and nothing else",
            number(said_switches) == key["switches_only"],
            str(key["switches_only"]),
            [f"{label}: {n} lines" for label, n in key["lines"].items()],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The one to sit with is the third. Asking for every switch -O2 turns on, and")
        print("none of the values it sets, is not a smaller -O2. It is a request nobody would")
        print("type on purpose, and GCC does exactly what you asked for.")
        return 0
    print("\nThe candidates are one call away if you want to look again:")
    print("    from grade import candidates; candidates(corpus_store.load('t06-levels'))")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
