"""The gate that says the parsers still understand what they understood yesterday.

Nothing here compiles anything. Every number comes out of the corpus committed in this
repository, so this file runs in a second and runs with the network off.
"""

from __future__ import annotations

import json

import pytest

from gxray import corpus_store, gimple, rtl
from tools.dumpparse import (
    BASELINE,
    DumpParseError,
    Reading,
    compare,
    load,
    parser_for,
    read,
    readings,
    save,
    snapshot,
    totals,
)

FOUND = readings()
RECORDED = load()


def test_the_baseline_matches_the_corpus():
    assert compare(FOUND, RECORDED) == []


def test_nothing_in_the_corpus_is_unreadable():
    """The milestone asks for a baseline, not for zero. Zero is where the baseline landed.

    If a future dump format costs us a statement, the right move is to fix the parser. If it
    cannot be fixed today, record the new baseline and this test tells everybody what it
    cost, which is the whole point of writing the number down.
    """
    bad = [r.id for r in FOUND if r.missed]
    assert bad == [], f"{len(bad)} dumps have something the parser cannot read"


def test_every_dump_in_the_corpus_is_in_the_baseline():
    have = {f"{e}/{d}" for e in corpus_store.entries() for d in corpus_store.load(e).dump_texts}
    assert have == set(RECORDED["dumps"])


def test_the_totals_are_the_sum_of_the_parts():
    t = totals(FOUND)
    assert t == RECORDED["totals"]
    assert t["dumps"] == len(FOUND)
    for key in ("functions", "items", "missed", "unread"):
        assert t[key] == sum(r.counts[key] for r in FOUND)


def test_the_corpus_is_big_enough_for_this_to_mean_something():
    t = totals(FOUND)
    assert t["dumps"] > 300
    assert t["items"] > 15000


@pytest.mark.parametrize(
    ("dump", "expected"),
    [
        ("rtl-expand", "rtl"),
        ("rtl-ira", "rtl"),
        ("tree-optimized", "gimple"),
        ("tree-original", "gimple"),
        ("ipa-inline", "gimple"),
        ("something-new", "gimple"),
    ],
)
def test_a_dump_goes_to_the_parser_its_name_calls_for(dump, expected):
    assert parser_for(dump) == expected


def test_a_rise_in_unreadable_says_so_plainly():
    """The one failure with its own message, because it is the one that means a regression."""
    one = FOUND[0]
    worse = Reading(
        entry=one.entry,
        dump=one.dump,
        parser=one.parser,
        functions=one.functions,
        items=one.items,
        missed=one.missed + 3,
        unread=one.unread,
    )
    problems = compare([worse], snapshot([one]))
    assert len(problems) == 1
    assert "changed shape" in problems[0]
    assert str(one.missed + 3) in problems[0]


def test_a_number_that_moves_the_other_way_is_still_a_difference():
    """A drop is good news and still fails, because a baseline nobody re-records is a lie."""
    one = next(r for r in FOUND if r.unread)
    better = Reading(
        entry=one.entry,
        dump=one.dump,
        parser=one.parser,
        functions=one.functions,
        items=one.items,
        missed=one.missed,
        unread=one.unread - 1,
    )
    problems = compare([better], snapshot([one]))
    assert problems == [f"{one.id} unread is {one.unread - 1} and the baseline says {one.unread}"]


def test_a_dump_on_one_side_and_not_the_other_is_a_difference():
    one, two = FOUND[0], FOUND[1]
    assert compare([one], snapshot([one, two])) == [
        f"{two.id} is in the baseline and not in the corpus"
    ]
    assert compare([one, two], snapshot([one])) == [
        f"{two.id} is in the corpus and not in the baseline"
    ]


def test_a_missing_baseline_says_which_command_writes_one(tmp_path):
    with pytest.raises(DumpParseError, match="dumpparse-record"):
        load(tmp_path / "nope.json")


def test_recording_the_baseline_round_trips(tmp_path):
    p = save(FOUND, tmp_path / "baseline.json")
    assert json.loads(p.read_text(encoding="utf-8")) == snapshot(FOUND)
    assert compare(FOUND, load(p)) == []


def test_the_committed_baseline_is_the_one_this_code_writes(tmp_path):
    """Formatting counts. A baseline reviewed as a diff has to be written the same way twice."""
    p = save(FOUND, tmp_path / "baseline.json")
    assert p.read_text(encoding="utf-8") == BASELINE.read_text(encoding="utf-8")


def test_the_gimple_parser_says_what_it_walked_past():
    """The optimized dump prints "Removing basic block N" between the banner and the blocks.

    That line is prose and belongs nowhere, and before this counter existed it vanished with
    no trace. Now it is a number, and a format change that turns real statements into prose
    moves the number instead of moving nothing.
    """
    text = corpus_store.load("t05-boss-O2").dump_texts["tree-optimized"]
    parsed = gimple.parse(text)
    assert any(line.startswith("Removing basic block") for line in parsed.dropped)
    assert parsed.unparsed == []


def test_the_rtl_parser_tells_prose_from_an_insn_it_could_not_read():
    """The IRA report is thousands of parenthesised lines and not one of them is an insn.

    Counting them as failures would drown the one number worth watching, so the reader looks
    at the code in front of the list and only calls it a miss when that code is an insn code.
    """
    text = corpus_store.load("t08-x86-64").dump_texts["rtl-ira"]
    parsed = rtl.parse(text)
    assert parsed.unread > 1000
    assert parsed.missed == []
    assert sum(len(listing.insns) for listing in parsed.functions.values()) > 900


def test_an_insn_the_reader_cannot_build_is_counted_as_a_miss():
    """Hand written, because the corpus has none. This is the failure the counter exists for."""
    text = (
        ";; Function f (f)\n\n"
        "(insn 3 2)\n"
        "(insn 4 3 5 2 (set (reg:SI 100) (const_int 1)) -1\n     (nil))\n"
    )
    parsed = rtl.parse(text)
    assert [i.uid for i in parsed.only()] == [4]
    assert parsed.missed == ["(insn 3 2)"]
    # The `(f)` in the banner. A dump with no `Full RTL generated` marker in it has no line
    # saying where the insns start, so the banner is inside the region the reader walks.
    assert parsed.unread == 1


def test_reading_a_dump_twice_gives_the_same_answer():
    entry, dump = "l1-O2", "tree-ssa"
    text = corpus_store.load(entry).dump_texts[dump]
    assert read(entry, dump, text) == read(entry, dump, text)
