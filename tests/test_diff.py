"""Lining two dumps up.

Almost all of this is about the normalizing. A diff that reports every line of a GIMPLE dump
as changed is correct about the text and useless to a reader, so the tests below are mostly
about which differences the model is supposed to swallow and which ones it must not.

The last section is the invariant the module docstring claims: the diff and the Pass Tape
decide "did this pass change anything" off the same fingerprint, so they cannot disagree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gxray import gimple, tape
from gxray.diff import Diff, Row, compare, normalize, pair

CORPUS = Path(__file__).resolve().parent.parent / "corpora" / "dumps" / "l1-O2.json"


@pytest.fixture
def recorded():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


@pytest.fixture
def ssa(ssa_dump):
    return gimple.parse(ssa_dump).only()


@pytest.fixture
def ends(recorded):
    """L1 as it enters SSA and as it leaves the tree passes."""
    dumps = recorded["dumps"]
    return (
        gimple.parse(dumps["tree-ssa"]).only(),
        gimple.parse(dumps["tree-optimized"]).only(),
    )


# What normalizing takes off


def test_a_source_location_is_not_a_change():
    assert normalize("  s_3 = s_1 + 1; [l1.c:7:12]") == normalize("  s_3 = s_1 + 1; [l1.c:9:12]")


def test_the_three_ways_gcc_writes_a_branch_probability_all_come_out_the_same():
    """`[INV]` before the profile is guessed, a percentage after, a count after that."""
    goto = "  goto <bb 3>;"
    forms = [f"{goto} [INV]", f"{goto} [89.00%]", f"{goto} [count: 10737418]", goto]
    assert len({normalize(f) for f in forms}) == 1


def test_a_local_count_is_a_profile_annotation_too():
    assert normalize("  <bb 4> [local count: 118111600]") == normalize("  <bb 4>")


def test_an_ssa_version_number_is_not_a_change():
    assert normalize("  s_3 = s_1 + 1;") == normalize("  s_9 = s_7 + 1;")


def test_an_anonymous_temporary_has_its_number_taken_off_too():
    """GCC writes one as `_6`, with nothing in front of the underscore."""
    assert normalize("  _6 = s_1 * 2;") == normalize("  _11 = s_4 * 2;")


def test_a_name_the_loop_optimizer_invented_normalizes_like_any_other():
    """`ivtmp.7_3` has a dot in the name part and a version after the underscore."""
    assert normalize("  ivtmp.7_3 = ivtmp.7_9 - 1;") == normalize("  ivtmp.7_2 = ivtmp.7_8 - 1;")
    assert "#" in normalize("  ivtmp.7_3 = 4;")


def test_the_block_a_phi_argument_arrives_from_is_left_alone():
    """`s_3(2)` and `s_3(4)` are different statements, whatever the version numbers say."""
    one = normalize("  # s_1 = PHI <0(2), s_5(3)>")
    other = normalize("  # s_1 = PHI <0(4), s_5(3)>")
    assert one != other


def test_the_block_a_goto_names_is_left_alone():
    """Threading a jump is exactly this, so a diff that hides it hides the pass."""
    assert normalize("  goto <bb 5>; [INV]") != normalize("  goto <bb 4>; [INV]")


def test_a_number_that_is_not_a_version_survives():
    """The `2` in `s_1 + 2` is the constant, and a pass folding it is the whole story."""
    assert normalize("  s_3 = s_1 + 2;") != normalize("  s_3 = s_1 + 4;")


def test_a_struct_field_is_not_an_ssa_name():
    """`p_2->next` has an underscore in it but `next` has no version to take off."""
    assert normalize("  _1 = p_2->next;") == "_# = p_#->next;"


def test_indentation_is_not_part_of_the_comparison():
    """It comes off with the locations, and a pass that moves a statement reindents it."""
    assert normalize("    s_3 = 1;") == normalize("  s_3 = 1;")


# Rows


def test_a_row_that_only_moved_its_numbers_says_so():
    row = Row("changed", before="  s_3 = s_1 + 1;", after="  s_9 = s_7 + 1;")
    assert row.renumbered
    assert row.label.startswith("renumbered,")


def test_a_row_where_the_statement_is_different_is_not_renumbering():
    row = Row("changed", before="  s_3 = s_1 + 1;", after="  s_3 = s_1 * 2;")
    assert not row.renumbered
    assert row.label.startswith("changed,")


def test_only_a_changed_row_can_be_renumbering():
    """An added line has nothing to have been renumbered from."""
    assert not Row("added", after="  s_3 = 1;").renumbered
    assert not Row("neutral", before="  s_3 = 1;", after="  s_3 = 1;").renumbered


def test_the_text_of_a_row_is_the_later_side_when_there_is_one():
    assert Row("changed", before="old", after="new").text == "new"
    assert Row("removed", before="old").text == "old"


def test_every_row_says_something_a_screen_reader_can_read():
    rows = [
        Row("added", after="a"),
        Row("removed", before="b"),
        Row("changed", before="c", after="d"),
        Row("neutral", before="e", after="e"),
    ]
    assert all(r.label and not r.label.endswith(" ") for r in rows)


# Runs of lines that were replaced


def test_a_replaced_run_is_laid_out_two_abreast():
    rows = pair(["a", "b"], ["c", "d"], 0, 0)
    assert [r.role for r in rows] == ["changed", "changed"]
    assert [(r.before, r.after) for r in rows] == [("a", "c"), ("b", "d")]


def test_the_surplus_of_a_longer_before_side_reads_as_removed():
    rows = pair(["a", "b", "c"], ["d"], 0, 0)
    assert [r.role for r in rows] == ["changed", "removed", "removed"]
    assert [r.after for r in rows[1:]] == ["", ""]


def test_the_surplus_of_a_longer_after_side_reads_as_added():
    rows = pair(["a"], ["b", "c"], 0, 0)
    assert [r.role for r in rows] == ["changed", "added"]


def test_a_row_carries_the_line_it_came_from_on_each_side():
    rows = pair(["a", "b"], ["c", "d"], 10, 20)
    assert [(r.before_line, r.after_line) for r in rows] == [(10, 20), (11, 21)]


# Comparing two real dumps


def test_a_function_against_itself_has_no_rows_worth_reading(ssa):
    got = compare(ssa, ssa)
    assert not got
    assert got.moved == []
    assert got.counts == {"neutral": len(got.rows), "added": 0, "removed": 0, "changed": 0}


def test_a_function_against_itself_still_has_a_row_per_line(ssa):
    """An empty diff means nothing moved, not that the widget has nothing to draw."""
    assert len(compare(ssa, ssa).rows) == len(tape.fingerprint(ssa))


def test_the_two_ends_of_the_tree_pipeline_differ(ends):
    before, after = ends
    got = compare(before, after, before_name="tree-ssa", after_name="tree-optimized")
    assert got
    assert got.counts["added"] and got.counts["removed"] and got.counts["changed"]


def test_most_of_what_differs_across_the_tree_passes_is_renumbering(ends):
    """The point of the whole module. Half the marked rows are the SSA names moving."""
    got = compare(*ends)
    assert len(got.renumbered) >= len(got.of("changed")) / 4


def test_a_renumbered_row_is_counted_as_changed_and_not_as_its_own_role(ends):
    got = compare(*ends)
    assert set(r.role for r in got.renumbered) == {"changed"}
    assert sum(got.counts.values()) == len(got.rows)


def test_every_line_of_both_dumps_is_on_the_diff_somewhere(ends):
    before, after = ends
    got = compare(before, after)
    assert [r.before for r in got.rows if r.before] == list(tape.fingerprint(before))
    assert [r.after for r in got.rows if r.after] == list(tape.fingerprint(after))


def test_the_names_of_the_two_sides_are_carried_through(ends):
    got = compare(*ends, before_name="tree-ssa", after_name="tree-optimized")
    assert str(got).startswith("tree-ssa to tree-optimized:")


def test_an_empty_diff_is_falsey_and_a_diff_with_a_row_in_it_is_not():
    assert not Diff(rows=(Row("neutral", before="a", after="a"),))
    assert Diff(rows=(Row("added", after="a"),))


# The invariant against the pass tape


def test_when_the_tape_says_a_pass_changed_nothing_the_diff_finds_nothing(ssa):
    """The two read the same fingerprint, so this is a check that they still both do.

    A tape cell is marked unchanged when the fingerprint on either side of a pass matches.
    If that holds and the diff finds a row anyway, one of them is looking at something the
    other is not, and the lesson would be showing a change the tape says did not happen.
    """
    again = gimple.parse((Path(__file__).parent / "fixtures" / "l1-O2-tree-ssa.txt").read_text())
    assert tape.fingerprint(ssa) == tape.fingerprint(again.only())
    assert not compare(ssa, again.only())


def test_when_the_diff_finds_something_the_tape_agrees_it_changed(ends):
    before, after = ends
    assert tape.fingerprint(before) != tape.fingerprint(after)
    assert compare(before, after)
