"""The facts T03 is built on, so that re-recording the corpus cannot quietly rewrite it.

The lesson makes several counted statements about what gimplification did to seven
expressions. All of them are computed from the recording rather than typed into the prose,
which means a new recording could change them without anybody noticing until a reader is
confused. These tests are the noise that gets made instead.
"""

from __future__ import annotations

import pytest
from conftest import grader

from gxray import corpus_store, gimple

LESSON = "t03-gimple-is-c-with-the-fun-removed"


@pytest.fixture
def bench() -> gimple.GimpleDump:
    record = corpus_store.load("t03-bench")
    return gimple.parse(record.dump_texts["tree-gimple"])


def test_the_bench_is_the_seven_functions_the_lesson_walks_through(bench):
    assert list(bench.functions) == [
        "flat",
        "nested",
        "deeper",
        "calls",
        "shortcircuit",
        "ternary",
        "compound",
    ]


def test_the_dump_is_the_one_taken_before_the_cfg_exists(bench):
    """The whole last section of the lesson is about this, and it is also the reason the
    parser had to learn a second dump shape."""
    assert all(fn.pre_cfg for fn in bench.functions.values())
    assert all(list(fn.blocks) == [gimple.PRE_CFG_BLOCK] for fn in bench.functions.values())


def test_no_right_hand_side_has_more_than_one_operator(bench):
    """Three address form, which is the claim the lesson opens with."""
    for fn in bench.functions.values():
        for stmt in fn.code:
            if stmt.kind == "assign":
                assert len(stmt.rhs.split()) <= 3, stmt.text


def test_one_line_of_c_becomes_between_two_and_eleven_statements(bench):
    sizes = {name: len(fn.code) for name, fn in bench.functions.items()}
    assert min(sizes.values()) == 2
    assert max(sizes.values()) == 11
    assert sizes["deeper"] == 8


def test_the_operators_come_out_bottom_up_and_left_to_right(bench):
    """The point of the boss fight. The first statement is the deepest leftmost operator,
    not the one you read first."""
    fn = bench.functions["deeper"]
    assert [s.operator for s in fn.code if s.operator] == ["+", "-", "*", "+", "-", "*", "+"]


def test_the_short_circuit_kept_no_operator_at_all(bench):
    """`a > 0 && b > 0` has three operators in C and none on any right hand side here,
    because both comparisons went into conditional jumps."""
    fn = bench.functions["shortcircuit"]
    assert [s.operator for s in fn.code if s.operator] == []
    assert sorted({s.kind for s in fn.code}) == ["assign", "cond", "goto", "label", "return"]


def test_the_ternary_writes_one_variable_on_two_paths(bench):
    """The shape SSA was invented for, met here for the first time."""
    fn = bench.functions["ternary"]
    written = [str(s.lhs) for s in fn.code if s.kind == "assign"]
    assert written == ["D.4648", "D.4648"]


def test_a_compound_assignment_needs_no_temporary(bench):
    """Because the place to keep the result already had a name."""
    fn = bench.functions["compound"]
    assert [s.text for s in fn.code] == ["a = a + b;", "D.4653 = a * c;", "return D.4653;"]


def test_the_grader_marks_the_answer_the_lesson_leads_you_to(bench):
    """A boss fight nobody has watched pass is a boss fight that might be waving everything
    through, so the right answer is checked here as well as in CI."""
    key = grader(LESSON).answers(bench)
    assert key["ops"] == ["+", "-", "*", "+", "-", "*", "+"]
    assert key["temps"] == 6
    assert key["most"] == ["shortcircuit"]
