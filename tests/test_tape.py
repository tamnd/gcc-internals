"""The pass tape model.

The widget and the animation both draw these cells, so this is where the rules about what
counts as a pass having changed something get pinned down.
"""

from __future__ import annotations

import pytest

from gxray import gimple, passes, tape


@pytest.fixture
def pipeline(passes_text):
    return passes.parse(passes_text)


@pytest.fixture
def ssa(ssa_dump):
    return gimple.parse(ssa_dump).only()


def test_a_fingerprint_ignores_the_dump_header(ssa, ssa_dump):
    again = gimple.parse(ssa_dump).only()
    assert tape.fingerprint(ssa) == tape.fingerprint(again)


def test_measure_counts_what_the_summary_quotes(ssa):
    got = tape.measure(ssa)
    assert got["statements"] == len(ssa.stmts)
    assert got["blocks"] == len(ssa.blocks)
    assert got["names"] > 0


def test_there_is_one_cell_per_enabled_pass(pipeline):
    assert len(tape.cells(pipeline)) == len(pipeline.enabled)


def test_a_cell_with_no_dump_claims_nothing(pipeline):
    """Most of them. GCC writes a dump for a pass only when the pass has one and it ran."""
    blind = [c for c in tape.cells(pipeline) if c.stats is None]
    assert len(blind) > 200
    assert all(c.changed is None for c in blind)
    assert "nothing recorded to compare" in blind[0].label


def test_the_first_measured_cell_has_nothing_to_compare_against(pipeline, ssa):
    measured = [c for c in tape.cells(pipeline, {"tree-ssa": ssa}) if c.stats is not None]
    assert len(measured) == 1
    assert measured[0].changed is None
    assert "11 statements" in measured[0].label


def test_two_identical_dumps_read_as_a_pass_that_changed_nothing(pipeline, ssa):
    keys = [p.dump_key for p in pipeline.enabled if p.dump_key][:2]
    same = dict.fromkeys(keys, ssa)
    measured = [c for c in tape.cells(pipeline, same) if c.stats is not None]
    assert [c.changed for c in measured] == [None, False]
