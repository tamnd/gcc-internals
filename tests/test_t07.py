"""The facts T07 is built on, so that re-recording the corpus cannot quietly rewrite it.

The lesson is an argument about one node type and four machines, and nearly every sentence in
it names a number that a cell computed. That is the honest way to write it and also the way
that lets a new recording move a number without anybody noticing. These tests are the noise
that gets made instead.

The local numbers are for `gcc-16` on `aarch64-apple-darwin24`. The four target numbers come
from Compiler Explorer at GCC 16.1.0, which is the newest the site has for all four. They are
not claims about GCC in general, and the lesson says so.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import grader

from gxray import corpus_store, rtl
from gxwidgets import english
from gxwidgets.rtxtree import kind_of
from gxwidgets.targetcompare import facts

LESSON = "t07-where-gimple-becomes-rtl"
VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "gcc"

#: The four recordings the lesson puts side by side, in the order it puts them.
TARGETS = ["x86-64", "aarch64", "riscv64", "power64le"]


@pytest.fixture
def listing():
    """L1 at the moment it stops being GIMPLE, from the local compiler."""
    record = corpus_store.load("l1-O2")
    return rtl.parse(record.dump_texts["rtl-expand"], "l1-O2").only()


@pytest.fixture
def four():
    return {
        name: rtl.parse(corpus_store.load(f"t07-{name}").dump_texts["rtl-expand"]).only()
        for name in TARGETS
    }


def test_the_chain_is_mostly_not_instructions(listing):
    """The first count in the lesson and the one that changes how a dump reads. Two thirds of
    what expand produced will never become a byte of machine code."""
    assert len(listing) == 40
    assert len(listing.code) == 13
    assert len([i for i in listing if i.is_debug]) == 15
    assert len(listing) - len(listing.code) == 27


def test_the_first_ten_entries_hold_one_instruction(listing):
    """What the widget shows by default, and the reason the lesson says a reader who feels
    like they are reading noise is reading noise."""
    ten = list(listing)[:10]
    counted = {k: len([i for i in ten if kind_of(i) == k]) for k in ("code", "debug", "other")}
    assert counted == {"code": 1, "debug": 6, "other": 3}


def test_a_four_line_program_needs_thirteen_of_the_two_hundred_and_three_codes(listing):
    """The working vocabulary of everyday RTL being small is the claim, and this is it."""
    codes = listing.codes()
    assert len(codes) == 13
    assert codes["reg"] == 25
    assert list(codes)[:3] == ["reg", "set", "const_int"]


def test_three_pseudos_and_two_hard_registers_and_the_lesson_names_both_hard_ones(listing):
    """Register 0 is where the argument arrives and the result leaves. Register 66 is the
    condition code. Expand had no choice about either, and every other register is invented."""
    pseudos, hard = listing.registers()
    assert pseudos == [101, 102, 103]
    assert hard == [0, 66]


def test_the_modes_are_almost_all_four_byte_integers(listing):
    """SI everywhere, CC only where a compare wrote one, DI only on a label reference."""
    assert listing.modes() == {"SI": 30, "CC": 6, "DI": 2}


def test_almost_nothing_is_recognised_yet(listing):
    """Two of thirteen. Matching the other eleven against target patterns is a later pass."""
    assert [i.uid for i in listing.code if i.recognised] == [16, 42]
    assert listing.at(16).name == "aarch64_bcond"


def test_the_expression_the_lesson_reads_out_loud_says_what_the_lesson_says(listing):
    """The one worked example. If this sentence changes the whole middle of the lesson is
    describing something else."""
    insn = listing.at(21)
    assert str(insn.pattern) == (
        "(set (reg/v:SI 102 [ <retval> ]) "
        "(plus:SI (reg/v:SI 102 [ <retval> ]) (reg/v:SI 101 [ i ])))"
    )
    assert english(insn.pattern) == (
        "pseudo 102, holding <retval> becomes pseudo 102, holding <retval> "
        "plus pseudo 101, holding i"
    )
    assert insn.pattern.size == 5
    assert insn.pattern.depth == 3
    assert sum(len(n.leaves) for n in insn.pattern.walk()) == 6


def test_the_use_at_the_end_produces_no_code_and_the_reading_says_so(listing):
    """The entry that exists to stop a later pass deleting something correct."""
    assert english(listing.at(38).pattern) == "register x0 is still needed here"


def test_the_four_targets_agree_about_nothing(four):
    """Ten measurements on a four line program and not one survives a change of machine. This
    is the sentence the second half of the lesson is built on."""
    table = {name: facts(one) for name, one in four.items()}
    for key in table["x86-64"]:
        assert len({t[key] for t in table.values()}) > 1, key


def test_the_condition_code_lands_in_four_different_places(four):
    """Three targets have a flags register and disagree about it. One has none at all."""
    where = {name: facts(one)["cc"] for name, one in four.items()}
    assert where == {
        "x86-64": "CCNO, CC, CCZ in a fixed register",
        "aarch64": "CC in a fixed register",
        "riscv64": "nowhere, this machine has no flags register",
        "power64le": "CC in a pseudo, the allocator picks which",
    }


def test_only_x86_has_to_say_that_adding_wrecks_something(four):
    """The clobber in the parallel, which is the clearest single thing in the table."""
    wrecks = [n for n, one in four.items() if facts(one)["clobber"].startswith("yes")]
    assert wrecks == ["x86-64"]


def test_only_riscv_fuses_the_compare_into_the_branch(four):
    """One insn where the others need two, because the instruction set has no other option."""
    fused = [n for n, one in four.items() if facts(one)["branch"].startswith("one")]
    assert fused == ["riscv64"]


def test_pseudo_numbering_starts_somewhere_different_on_every_machine(four):
    """Why a pseudo number is never worth quoting without saying which target it came from."""
    assert [facts(one)["first"] for one in four.values()] == ["98", "101", "134", "117"]


def test_only_powerpc_invented_a_counter_and_it_was_not_expand_that_did_it(four):
    """The most interesting row in the table is not an expand difference. Nothing in the C
    counts down, and the countdown came from a middle end pass that asked the target."""

    def counters(one):
        return [n for i in one.code if i.pattern for n in i.pattern.walk() if "doloop" in str(n)]

    assert [name for name, one in four.items() if counters(one)] == ["power64le"]


def test_the_local_compiler_and_compiler_explorer_agree_about_aarch64(listing, four):
    """Two different builds of GCC 16 on two different operating systems. If these ever stop
    matching, one of the two recordings is stale and the lesson is comparing apples to a
    different version of itself."""
    assert facts(listing) == facts(four["aarch64"])


def test_the_grader_marks_the_answer_the_lesson_leads_you_to():
    """A boss fight nobody has watched pass is a boss fight that might be waving everything
    through, so the right answer is checked here as well as in CI."""
    module = grader(LESSON)
    assert module.key() == {"A": 3, "B": 1, "C": 6, "D": 2, "E": 5, "F": 4}
    assert module.clobbers() == ["x86-64"]
    assert module.flagless() == ["riscv64"]


def test_the_grader_wants_all_six_pairs_and_both_targets():
    """Five of six right is not right, because the sixth is the one worth the work."""
    module = grader(LESSON)
    right = ["--answers", "A3", "B1", "C6", "D2", "E5", "F4"]
    targets = ["--clobbers", "x86-64", "--no-flags", "riscv64"]
    assert module.main([*right, *targets]) == 0
    assert module.main(["--answers", "A3", "B1", "C6", "D2", "E5", "F1", *targets]) == 1
    assert module.main([*right, "--clobbers", "aarch64", "--no-flags", "riscv64"]) == 1


def test_the_grader_reads_a_pair_however_the_reader_punctuates_it():
    """`A3`, `a3` and `A:3` are the same answer to the same question."""
    module = grader(LESSON)
    assert module.pairs(["a3", "B:1", "C=6", "nonsense", "D2"]) == {
        "A": 3,
        "B": 1,
        "C": 6,
        "D": 2,
    }


def test_the_six_sentences_are_all_different_and_all_readable():
    """Six expressions matched to six sentences is only a puzzle if no two sentences are the
    same, and only fair if none of them still has RTL in it."""
    module = grader(LESSON)
    said = [text for _, _, text in module.sentences()]
    assert len(set(said)) == 6
    for text in said:
        assert "(" not in text and "[" not in text
        assert not any(code in text for code in ("set ", "plus:", "reg:", "clobber"))


@pytest.mark.skipif(not (VENDOR / "gcc" / "rtl.def").exists(), reason="no vendored gcc tree")
def test_there_are_two_hundred_and_three_codes_and_one_that_means_nothing_yet():
    """The number the lesson quotes twice. The file has 204 entries and the first is a
    sentinel for an expression whose code has not been decided."""
    lines = (VENDOR / "gcc" / "rtl.def").read_text(encoding="utf-8").splitlines()
    # Not `DEF_RTL_EXPR(`, because one entry in the file has a space before the paren and a
    # count that misses it is a count that is quietly one out.
    defined = [line for line in lines if line.startswith("DEF_RTL_EXPR")]
    assert len(defined) == 204
    assert defined[0].startswith("DEF_RTL_EXPR(UNKNOWN,")
    assert len(defined) - 1 == 203


@pytest.mark.skipif(not (VENDOR / "gcc" / "target.def").exists(), reason="no vendored gcc tree")
def test_two_targets_in_the_whole_tree_answer_the_doloop_hook():
    """Why the middle end handed PowerPC different GIMPLE. The hook is shared, the answer is
    not, and only two back ends bother to give one."""
    config = VENDOR / "gcc" / "config"
    answered = sorted(
        p.parent.name
        for p in config.rglob("*.cc")
        if "TARGET_PREDICT_DOLOOP_P" in p.read_text(encoding="utf-8", errors="ignore")
    )
    assert answered == ["arm", "rs6000"]
    assert "predict_doloop_p" in (VENDOR / "gcc" / "target.def").read_text(encoding="utf-8")
