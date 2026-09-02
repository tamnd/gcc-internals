"""The facts T06 is built on, so that re-recording the corpus cannot quietly rewrite it.

The lesson is an argument made out of counts. 55 differences, 114 rows, 48 switches that get
you 86 lines of the wrong answer, 4 flags that get you the right one. Every one of those is
computed in a cell, which is the honest way to write it and also the way that lets a new
recording move a number without anybody noticing. These tests are the noise that gets made
instead.

The numbers here are for `gcc-16` on `aarch64-apple-darwin24`, because that is the compiler
the recording came from. They are not claims about GCC in general, and the lesson says so.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import grader

from gxray import corpus_store, options

LESSON = "t06-what-o2-actually-turns-on"
VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "gcc"

#: One row of `default_options_table`. The array is C, so this is a regex rather than a parse,
#: and the notebook uses the same one. It is here as well because a test that shells out to the
#: notebook is not a test, it is a second copy of the notebook.
ROW = re.compile(r"\{\s*(OPT_LEVELS_\w+),\s*(OPT_\w+),")


@pytest.fixture
def record():
    return corpus_store.load("t06-levels")


@pytest.fixture
def levels(record) -> dict[str, options.Table]:
    return options.by_level(record.option_texts)


def test_the_recording_covers_every_level_a_reader_might_try(levels):
    assert list(levels) == list(options.LEVELS)


def test_the_table_is_switches_and_valued_options_and_the_lesson_counts_both(levels):
    table = levels["-O2"]
    assert len(table) == 295
    assert len(table.booleans) == 244
    assert len(table.valued) == 49


def test_the_famous_number_is_fifty_five_and_none_of_it_is_a_switch_going_off(levels):
    """The whole first half of the lesson. -O1 to -O2 adds and never subtracts, which is what
    makes the -Os and -Og sections land later."""
    changes = options.diff(levels["-O1"], levels["-O2"])
    kinds = {k: len([c for c in changes if c.kind == k]) for k in ("on", "off", "value")}
    assert len(changes) == 55
    assert kinds == {"on": 48, "off": 0, "value": 7}


def test_os_is_not_o2_with_the_volume_down(levels):
    """Seven switches off and five options set to something else, which is a different claim
    from -Os being a weaker -O2 and reads differently on the page."""
    changes = options.diff(levels["-O2"], levels["-Os"])
    kinds = {k: len([c for c in changes if c.kind == k]) for k in ("on", "off", "value")}
    assert kinds == {"on": 0, "off": 7, "value": 5}
    assert [c.name for c in changes if c.kind == "off"] == [
        "-falign-functions",
        "-falign-jumps",
        "-falign-labels",
        "-falign-loops",
        "-foptimize-strlen",
        "-ftree-loop-vectorize",
        "-ftree-slp-vectorize",
    ]


def test_os_and_oz_are_indistinguishable_from_out_here(record, levels):
    """Both set `optimize_size`, the table reads it as a yes or no, and so the two print the
    same thing. The lesson makes a point of this being a limit of the printout rather than a
    statement that the two levels are the same."""
    assert record.option_texts["optimizers -Os"] == record.option_texts["optimizers -Oz"]
    assert record.option_texts["params -Os"] == record.option_texts["params -Oz"]
    assert record.asm_texts["-Os"] == record.asm_texts["-Oz"]
    assert options.diff(levels["-Os"], levels["-Oz"]) == []


def test_og_is_not_a_weak_o1(levels):
    """Thirteen switches -O1 has that -Og drops, and one going the other way. A slider cannot
    do that, and this is the cleanest evidence in the lesson that the levels are not one."""
    changes = options.diff(levels["-O1"], levels["-Og"])
    kinds = {k: len([c for c in changes if c.kind == k]) for k in ("on", "off", "value")}
    assert kinds == {"on": 1, "off": 13, "value": 0}
    assert [c.name for c in changes if c.kind == "on"] == ["-funreachable-traps"]


def test_ofast_gives_up_four_things_and_only_three_are_about_floating_point(levels):
    """The fourth is -fsemantic-interposition, which is about symbol interposition and got
    into -Ofast because -Ofast is where the unsafe things live rather than because it is a
    floating point option."""
    off = [c.name for c in options.diff(levels["-O3"], levels["-Ofast"]) if c.kind == "off"]
    assert off == [
        "-fmath-errno",
        "-fsemantic-interposition",
        "-fsigned-zeros",
        "-ftrapping-math",
    ]


def test_the_levels_disagree_about_less_than_half_the_switches(levels):
    """What the flag grid draws. 129 of the 244 are the same everywhere, so the picture is
    115 columns wide and the reader is not asked to scan the ones that never move."""
    names = {o.name for o in levels["-O2"].booleans}
    varies = [
        n
        for n in names
        if len({bool(t[n].on) for t in levels.values() if n in t and t[n].boolean}) > 1
    ]
    assert len(varies) == 115


@pytest.mark.skipif(not (VENDOR / "gcc" / "opts.cc").exists(), reason="no vendored gcc tree")
def test_the_table_in_the_source_is_the_size_the_lesson_says_it_is():
    """The one number in the lesson that comes out of the source rather than out of a run.
    The notebook has a fallback for readers with no submodule, and this checks the fallback
    still agrees with the tree it was copied from."""
    text = (VENDOR / "gcc" / "opts.cc").read_text(encoding="utf-8")
    array = text.split("default_options_table[] =", 1)[1].split("\n};", 1)[0]
    rows = [m for m in ROW.findall(array) if m[0] != "OPT_LEVELS_NONE"]
    words = {w for w, _ in rows}

    assert len(rows) == 114
    assert len(words) == 6
    assert len([r for r in rows if r[0] == "OPT_LEVELS_2_PLUS_SPEED_ONLY"]) == 10


@pytest.mark.skipif(not (VENDOR / "gcc" / "opts.cc").exists(), reason="no vendored gcc tree")
def test_the_flag_that_is_not_in_the_table_is_still_in_the_file():
    """The third mechanism, and the reason the lesson stops short of saying a level is the
    table. -funreachable-traps is set by hand, a few hundred lines further down, off the same
    two integers the table reads."""
    lines = (VENDOR / "gcc" / "opts.cc").read_text(encoding="utf-8").splitlines()
    hand = "\n".join(lines[1225:1240])
    assert "flag_unreachable_traps" in hand
    assert "x_optimize_debug" in hand


def test_the_rebuild_needs_the_valued_options_and_the_switches_are_not_enough(record):
    """The boss fight in one line. Asking for all 48 switches and none of the seven values is
    not a smaller -O2, it is a worse one, and 86 against 56 is how much worse."""
    lines = {k: len(v.splitlines()) for k, v in record.asm_texts.items()}
    assert lines["-O1"] == 54
    assert lines["-O2"] == 56
    switches_only = next(k for k, n in lines.items() if k.startswith("-O1 ") and n == 86)
    assert record.asm_texts[switches_only] != record.asm_texts["-O2"]


def test_three_programs_need_one_four_and_eight_of_the_fifty_five(record):
    """How few of a level any one function notices, which is the point the lesson ends on."""
    needed = {}
    for name, entry in (("L0", "t06-l0"), ("L1", "t06-levels"), ("L2", "t06-l2")):
        stored = corpus_store.load(entry)
        goal = stored.asm_texts["-O2"]
        matched = [
            k for k in stored.asm_texts if k.startswith("-O1 ") and stored.asm_texts[k] == goal
        ]
        needed[name] = len(min(matched, key=len).split()) - 1
    assert needed == {"L0": 1, "L1": 4, "L2": 8}


def test_ofast_vectorizes_a_loop_that_o3_will_not_touch():
    """The one place in the lesson where a flag difference turns into a different instruction
    you can point at, which is worth more than any count."""
    record = corpus_store.load("t06-fast")
    assert "fadd\ts0, s0, s31" in record.asm_texts["-O3"]
    assert "fadd\tv3.4s" in record.asm_texts["-Ofast"]
    assert "faddp" not in record.asm_texts["-O3"]
    assert len(record.asm_texts["-O3"].splitlines()) == 52
    assert len(record.asm_texts["-Ofast"].splitlines()) == 85


def test_the_grader_marks_the_answer_the_lesson_leads_you_to():
    """A boss fight nobody has watched pass is a boss fight that might be waving everything
    through, so the right answer is checked here as well as in CI."""
    key = grader(LESSON).answers()
    assert key["candidates"] == 55
    assert key["needed"] == [
        "-falign-functions=32:16",
        "-falign-jumps=4",
        "-falign-loops=32:16",
        "-freorder-blocks-algorithm=stc",
    ]
    assert key["odd"] == ["-freorder-blocks-algorithm=stc"]
    assert key["switches_only"] == 86


def test_the_grader_takes_the_flag_answer_with_or_without_its_value():
    """`-freorder-blocks-algorithm=stc` is what the table prints and what the reader is likely
    to paste, but the name on its own is the same answer to the question being asked."""
    module = grader(LESSON)
    right = ["--flags", "4", "--switches-only", "86", "--odd-one-out"]
    assert module.main([*right, "-freorder-blocks-algorithm=stc"]) == 0
    assert module.main([*right, "-freorder-blocks-algorithm"]) == 0
    assert module.main([*right, "-falign-jumps=4"]) == 1
