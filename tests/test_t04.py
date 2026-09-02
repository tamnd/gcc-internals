"""The facts T04 is built on, so that re-recording the corpus cannot quietly rewrite it.

The lesson is mostly counting, and the counts are in the prose as well as in the cells because
a sentence that says 281 reads better than one that says however many there are. All of them
are computed in the notebook rather than typed in, which means a new recording could move one
without anybody noticing until a reader is confused. These tests are the noise that gets made
instead.
"""

from __future__ import annotations

import pytest
from conftest import grader

from gxray import corpus_store, passes, tape

LESSON = "t04-three-hundred-and-ninety-five-passes"


@pytest.fixture
def record():
    return corpus_store.load("t04-tape")


@pytest.fixture
def cells(record) -> list[tape.Cell]:
    return grader(LESSON).build()


def test_the_number_in_the_title_is_the_number_in_the_recording(record):
    assert passes.parse(record.pass_texts["-O2"]).counts()["total"] == 395


def test_the_five_levels_turn_on_what_the_table_says_they_do(record):
    on = {name: len(passes.parse(text).enabled) for name, text in record.pass_texts.items()}
    assert on == {"-O0": 140, "-O1": 228, "-O2": 281, "-O3": 289, "-Os": 274}


def test_the_optimization_levels_are_not_a_slider(record):
    """The point of that whole section. -Os is not -O2 with things taken away, it turns one
    pass on that -O2 leaves off, and a reader who only sees 274 against 281 misses it."""
    levels = {name: passes.parse(text) for name, text in record.pass_texts.items()}

    def only_in(a, b):
        off = {p.name for p in levels[b].enabled}
        return sorted(p.name for p in levels[a].enabled if p.name not in off)

    assert only_in("-Os", "-O2") == ["rtl-hoist"]
    assert len(only_in("-O3", "-O2")) == 8
    assert len(only_in("-O2", "-Os")) == 8


def test_the_pipeline_is_a_tree_and_two_containers_hold_more_than_half_of_it(record):
    pipeline = passes.parse(record.pass_texts["-O2"])
    biggest = sorted(pipeline.all, key=lambda p: -len(list(p.walk())))[:2]
    assert [p.name for p in biggest] == ["all_optimizations", "rest_of_compilation"]
    assert sum(len(list(p.walk())) - 1 for p in biggest) > len(pipeline.all) / 2
    assert max(p.depth for p in pipeline.all) == 4


def test_a_pass_can_print_on_inside_a_container_that_printed_off(record):
    """The reason the lesson refuses to read the listing as a record of what ran. At -O0 the
    optimizer container says OFF and 38 of the passes inside it still say ON."""
    pipeline = passes.parse(record.pass_texts["-O0"])
    container = pipeline.find("all_optimizations")
    assert not container.enabled
    inside = [p for p in container.walk() if p is not container]
    assert len(inside) == 122
    assert len([p for p in inside if p.enabled]) == 38


def test_none_of_the_passes_shut_in_by_a_closed_gate_left_a_dump(record):
    """Which is the only evidence available that they did not run, and it is good evidence
    for the tree ones, because every tree dump of this compilation is in the recording."""
    pipeline = passes.parse(record.pass_texts["-O2"])
    shut = []

    def walk(node, closed):
        if node.enabled and closed:
            shut.append(node)
        for kid in node.children:
            walk(kid, closed or not node.enabled)

    for root in pipeline.roots:
        walk(root, False)

    assert len(shut) == 60
    assert [p.name for p in shut if p.dump_key in record.dump_texts] == []


def test_the_tape_is_mostly_empty(cells):
    """The headline. 281 cells and 25 of them did anything at all."""
    assert len(cells) == 281
    assert len([c for c in cells if c.changed is True]) == 25
    assert len([c for c in cells if c.changed is False]) == 109
    assert len([c for c in cells if c.changed is None]) == 147


def test_the_first_two_passes_to_change_anything_are_the_ones_the_prose_names(cells):
    """`tree-cfg` is where the blocks appear and `tree-ssa` is where the names appear, which
    is what T03 promised and what T05 picks up."""
    changed = [c.name for c in cells if c.changed]
    assert changed[:3] == ["tree-lower", "tree-cfg", "tree-ssa"]
    assert changed[-1] == "tree-optimized"

    blocks = {c.name: c.stats["blocks"] for c in cells if c.stats}
    assert blocks["tree-lower"] == 1
    assert blocks["tree-cfg"] == 4

    names = {c.name: c.stats["names"] for c in cells if c.stats}
    assert names["tree-fixup_cfg1"] == 0
    assert names["tree-ssa"] == 8


def test_the_grader_marks_the_answer_the_lesson_leads_you_to(cells):
    """A boss fight nobody has watched pass is a boss fight that might be waving everything
    through, so the right answer is checked here as well as in CI."""
    key = grader(LESSON).answers(cells)
    assert key["pass"] == "ccp1"
    assert key["changed"] == 25
    assert key["only_os"] == ["hoist"]
