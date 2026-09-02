"""The T07 boss fight, graded.

Six RTX expressions, six English sentences, and they are not in the same order. Match them,
then answer two questions about the four targets that only make sense once you can read the
expressions.

    python lessons/t07-where-gimple-becomes-rtl/grade.py
    python lessons/t07-where-gimple-becomes-rtl/grade.py --answers A3 B1 C6 D2 E5 F4 \\
        --clobbers x86-64 --no-flags riscv64

The sentences are generated from the recordings by the same function the widget uses, and the
two target questions are read off the recordings as well. Nothing here is a written down
answer key, so re-recording the corpus against a newer compiler cannot leave the grader
marking against something that is no longer true.
"""

from __future__ import annotations

import argparse
import sys

from gxray import corpus_store, rtl
from gxwidgets import english
from gxwidgets.targetcompare import clobbering, condition_code

#: The four recordings, in the order the lesson puts them. The first is the local compiler and
#: the other three come from Compiler Explorer, which is why the lesson can ask this question
#: of a reader who has one machine.
TARGETS = {
    "x86-64": "t07-x86-64",
    "aarch64": "t07-aarch64",
    "riscv64": "t07-riscv64",
    "power64le": "t07-power64le",
}

#: The six expressions, by the letter the lesson labels them with. Each one is picked because
#: it is the only place in the four recordings where a particular idea shows up: an argument
#: arriving in a hard register, an increment, an add that wrecks the flags, a branch with no
#: compare in front of it, a counter the middle end invented, and an entry that emits nothing.
EXPRESSIONS = [
    ("A", "l1-O2", 2),
    ("B", "l1-O2", 24),
    ("C", "t07-x86-64", 21),
    ("D", "t07-riscv64", 15),
    ("E", "t07-power64le", 31),
    ("F", "l1-O2", 38),
]

#: Which expression each numbered sentence is about. Fixed rather than shuffled per run, so
#: that two readers comparing notes are talking about the same list and so that the command
#: line in the lesson stays correct.
ORDER = "BDAFEC"


def expression(entry: str, uid: int):
    """One insn out of one recording."""
    listing = rtl.parse(corpus_store.load(entry).dump_texts["rtl-expand"]).only()
    return listing.at(uid)


def sentences() -> list[tuple[int, str, str]]:
    """The numbered list the reader sees: number, the letter it belongs to, the English."""
    found = {letter: expression(entry, uid) for letter, entry, uid in EXPRESSIONS}
    return [(n, letter, english(found[letter].pattern)) for n, letter in enumerate(ORDER, 1)]


def key() -> dict[str, int]:
    """Letter to sentence number, which is the whole answer to the first question.

    Sorted by letter rather than by sentence, because that is the order the reader writes
    their answer in and marking should come back in the order it was given.
    """
    return {letter: n for n, letter, _ in sorted(sentences(), key=lambda s: s[1])}


def clobbers() -> list[str]:
    """Which targets have to say out loud that adding two numbers destroys something."""
    out = []
    for name, entry in TARGETS.items():
        listing = rtl.parse(corpus_store.load(entry).dump_texts["rtl-expand"]).only()
        if clobbering(listing).startswith("yes"):
            out.append(name)
    return out


def flagless() -> list[str]:
    """Which targets have nowhere to put a condition code."""
    out = []
    for name, entry in TARGETS.items():
        listing = rtl.parse(corpus_store.load(entry).dump_texts["rtl-expand"]).only()
        if condition_code(listing).startswith("nowhere"):
            out.append(name)
    return out


def ask(question: str, given: str | None) -> str:
    """Take the answer from the command line, or ask for it if it was not given."""
    if given is not None:
        return given.strip()
    if not sys.stdin.isatty():
        return ""
    return input(f"{question} ").strip()


def pairs(said: list[str] | None) -> dict[str, int]:
    """Read `A3 B1 C6` into a mapping, quietly dropping anything that is not that shape."""
    out: dict[str, int] = {}
    for word in said or []:
        text = word.strip().upper().replace(":", "").replace("=", "")
        if len(text) == 2 and text[0].isalpha() and text[1].isdigit():
            out[text[0]] = int(text[1])
    return out


def matching(said: dict[str, int], answer: dict[str, int]) -> list[str]:
    """A line per expression saying whether the reader put it with the right sentence."""
    lines = []
    for letter in answer:
        gave = said.get(letter)
        got = gave == answer[letter]
        told = f"sentence {gave}" if gave else "no answer"
        verdict = "right" if got else "wrong"
        lines.append(f"{letter} {verdict}, {told}, the answer is {answer[letter]}")
    return lines


def targets_named(said: str) -> list[str]:
    """The targets the reader named, in whatever punctuation they used."""
    words = said.replace(",", " ").split()
    return [w for w in words if w in TARGETS]


def mark(label: str, correct: bool, expected: str, evidence: list[str]) -> bool:
    print(f"\n{'right' if correct else 'wrong'}  {label}")
    if not correct:
        print(f"       the answer is {expected}")
    for line in evidence:
        print(f"       {line}")
    return correct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--answers", nargs="+", help="six pairs, such as A3 B1 C6 D2 E5 F4")
    parser.add_argument("--clobbers", help="which target's add destroys a register")
    parser.add_argument("--no-flags", dest="flagless", help="which target has no flags register")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    numbered = sentences()
    print(
        f"{len(EXPRESSIONS)} expressions and {len(numbered)} sentences, from {len(TARGETS)} targets"
    )
    print()
    for n, _, text in numbered:
        print(f"  {n}. {text}")
    print()

    answer = key()
    said_pairs = pairs(args.answers or ask("Your six pairs?", None).split())
    said_clobbers = ask("Which target's add destroys a register?", args.clobbers)
    said_flagless = ask("Which target has no flags register?", args.flagless)

    wrecks = clobbers()
    bare = flagless()

    scored = [
        mark(
            "the six expressions matched to the six sentences",
            all(said_pairs.get(k) == v for k, v in answer.items()),
            " ".join(f"{k}{v}" for k, v in answer.items()),
            matching(said_pairs, answer),
        ),
        mark(
            "the target whose add has to destroy a register",
            targets_named(said_clobbers) == wrecks,
            ", ".join(wrecks),
            ["its add is a parallel with a clobber in it, the other three add with a plain set"],
        ),
        mark(
            "the target with no condition code register",
            targets_named(said_flagless) == bare,
            ", ".join(bare),
            ["it fuses the compare into the branch, so it has 1 branch insn where others have 2"],
        ),
    ]

    got = sum(scored)
    print(f"\n{got} of 3.")
    if got == 3:
        print("The one to sit with is E. Nothing in the C source counts down, and no other")
        print("target invented a counter. That expression is not the back end disagreeing")
        print("with the others, it is the middle end having run a different pass, because")
        print("the target answered a hook one way and the rest answered it the other way.")
        return 0
    print("\nEvery sentence came out of one function, which you can call yourself:")
    print("    from gxwidgets import english; english(listing.at(21).pattern)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
