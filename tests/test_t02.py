"""The facts T02 is built on, so that re-recording the corpus cannot quietly rewrite it.

The lesson makes three concrete statements about where the code for a line of C ends up. All
three are computed from the recording rather than typed into the prose, which means a new
recording could change them without anybody noticing until a reader is confused. These tests
are the noise that gets made instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gxray import corpus_store, locs

LESSON = Path(__file__).resolve().parent.parent / "lessons" / "t02-five-faces"


@pytest.fixture
def ladder() -> locs.Ladder:
    record = corpus_store.load("l1-O2")
    return locs.ladder(
        record.source,
        generic=record.dump_texts["tree-original"],
        gimple=record.dump_texts["tree-optimized"],
        rtl=record.dump_texts["rtl-expand"],
        asm=record.asm,
        function="f",
    )


def test_the_return_statement_has_nothing_below_gimple(ladder):
    """The headline of the lesson. `return s;` reaches GIMPLE and stops."""
    rung = ladder.rung(8)
    assert rung.source.strip() == "return s;"
    assert rung.empty_levels == ["rtl", "asm"]
    assert rung.at("gimple")


def test_the_closing_brace_owns_the_return_instructions(ladder):
    """And the other half of it: the code went somewhere, just not where you would look."""
    rung = ladder.rung(9)
    assert rung.source.strip() == "}"
    assert rung.empty_levels == ["generic", "gimple"]
    assert [item.text for item in rung.at("asm")] == ["ret", "ret"]


def test_one_assignment_became_two_instructions_because_there_are_two_exits(ladder):
    """`int s = 0;` is one statement and two instructions, which is worth a sentence in the
    lesson rather than looking like the counter is broken."""
    rung = ladder.rung(5)
    assert rung.source.strip() == "int s = 0;"
    assert rung.counts()["generic"] == 1
    assert [item.text for item in rung.at("asm")] == ["mov\tw0, 0", "mov\tw0, 0"]


def test_the_grader_marks_the_answer_the_lesson_leads_you_to(ladder):
    """A boss fight nobody has watched pass is a boss fight that might be waving everything
    through, so the right answer is checked here as well as in CI."""
    sys.path.insert(0, str(LESSON))
    try:
        import grade  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    key = grade.answers(ladder)
    assert key["asm"] == {5: 2, 6: 6, 7: 1, 8: 0}
    assert key["vanished"] == [8]
    assert key["appeared"] == [9]
