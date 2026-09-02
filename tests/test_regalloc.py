"""The IRA dump reader.

Everything here runs against text a real compiler wrote, either the recorded dumps in
`corpora/dumps` or a few lines lifted out of one, because a parser tested against text
somebody invented is a parser tested against its own assumptions.

The reader has one job that is easy to get wrong and it gets its own tests: an allocno is not
a pseudo, and every question a lesson asks is about pseudos. A function where a value is live
across a loop boundary has two allocnos for it, they can end up in different places, and the
answer to "did this value get a register" has to fold them back together.
"""

from __future__ import annotations

import pytest

from gxray import corpus_store, regalloc

#: The three recordings T08 argues from. Same source, same flags, three register files.
ENTRIES = ["t08-x86-64", "t08-aarch64", "t08-local"]

#: Two lines of a real dump, kept short so the test can say what it is checking.
COSTS_LINE = "    a0(r106,l0) costs: GENERAL_REGS:0,0 FP_REGS:1100,14450 MEM:660,9560"


def load(entry: str) -> regalloc.IraDump:
    return regalloc.parse(corpus_store.load(entry).dump_texts["rtl-ira"], entry)


@pytest.fixture
def x86():
    return load("t08-x86-64")


@pytest.fixture
def arm():
    return load("t08-aarch64")


def test_five_functions_come_out_of_one_dump(x86):
    """The dump has five chunks in it and the allocno numbers restart at zero in each one,
    so a reader that merged them would have every function overwriting the last."""
    assert list(x86.functions) == ["p04", "p10", "p14", "p20", "p30"]
    assert len(x86) == 5
    assert {a.num for a in x86["p04"]} & {a.num for a in x86["p30"]}


def test_an_empty_dump_produces_no_functions_and_does_not_raise():
    """The reader is pointed at whatever a lesson happens to have recorded, and a dump with
    no allocation in it is a normal thing to be handed."""
    assert len(regalloc.parse("")) == 0
    assert len(regalloc.parse("nothing here that looks like a dump\n")) == 0


def test_only_asking_for_one_function_when_there_are_five_is_an_error(x86):
    with pytest.raises(ValueError, match="found 5"):
        x86.only()


def test_a_costs_line_gives_up_the_allocno_the_pseudo_and_the_region():
    """Three numbers on one line and all three matter. The memory cost is the last of the
    pair, which is the total rather than the cost at this one point."""
    alloc = regalloc.parse(f";; Function f (f)\n{COSTS_LINE}\n").only()
    a = alloc.allocnos[0]
    assert (a.num, a.pseudo, a.level) == (0, 106, 0)
    assert a.mem_cost == 9560


def test_a_pseudo_live_in_two_regions_has_two_allocnos(x86):
    """The single fact the reader exists to handle. r116 in p20 is one value in the C and
    two entries in every table IRA prints."""
    p20 = x86["p20"]
    assert len(p20.pseudos[116]) == 2
    assert [a.level for a in p20.pseudos[116]] == [0, 1]
    assert len(p20.allocnos) == 64
    assert len(p20.pseudos) == 42


def test_a_value_counts_as_spilled_if_any_of_its_regions_is(x86):
    """Folding two allocnos back into one answer. The honest reading is that the value gets
    stored and reloaded somewhere, so it counts, even if it kept a register elsewhere."""
    p20 = x86["p20"]
    assert p20.spilled == [116, 118, 119, 120, 121, 136, 160]
    assert set(p20.spilled) | set(p20.kept) == set(p20.pseudos)
    assert not set(p20.spilled) & set(p20.kept)
    assert all(a.spilled for a in p20.pseudos[116])


def test_an_allocno_with_no_disposition_entry_is_undecided_rather_than_spilled():
    """`placed` and `hard` are two different things, and collapsing them would report every
    allocno in a dump that was cut short as having ended up in memory."""
    alloc = regalloc.parse(f";; Function f (f)\n{COSTS_LINE}\n").only()
    a = alloc.allocnos[0]
    assert not a.placed
    assert not a.spilled
    assert a.where == "undecided"


def test_the_last_disposition_block_wins():
    """IRA prints one per iteration of its spill and restore loop, and only the last one
    describes the code that gets generated. Reading the first is reading a draft."""
    text = (
        ";; Function f (f)\n"
        "    a0(r106,l0) costs: GENERAL_REGS:0,0 MEM:660,9560\n"
        "Disposition:\n"
        "    0:r106 l0   mem\n"
        "\n"
        "Disposition:\n"
        "    0:r106 l0     3\n"
    )
    a = regalloc.parse(text).only().allocnos[0]
    assert a.placed
    assert a.hard == 3
    assert a.where == "reg 3"


def test_pressure_is_the_worst_region_and_not_the_last_one(x86):
    """The dump prints a pressure line per region and a lesson wants the busiest point in
    the function, so the reader keeps the maximum rather than whatever came last."""
    counts = [alloc.peak() for alloc in x86]
    assert counts == [6, 12, 16, 22, 32]
    assert sorted(counts) == counts


def test_available_is_what_the_target_hands_out_and_not_what_it_has(x86, arm):
    """Sixteen registers on x86-64 and fifteen of them available, because the stack pointer
    is not up for grabs. Any prediction that starts from sixteen is off by one."""
    assert {alloc.available() for alloc in x86} == {15}
    assert {alloc.available() for alloc in arm} == {30}
    assert x86["p14"].over() == 1
    assert arm["p14"].over() == -14


def test_ranges_are_the_compressed_ones_because_the_conflicts_are(x86):
    """GCC prints the ranges twice, as measured and again after compression, and the last
    block is the one the conflict graph was built on. Keeping the first would give live
    ranges that do not line up with anything else in the dump."""
    p20 = x86["p20"]
    assert p20.compression == (142, 45)
    highest = max(stop for a in p20 for _, stop in a.ranges)
    assert highest == p20.compression[1] - 1


def test_a_live_range_is_counted_inclusively(x86):
    """A range of `[4..42]` is thirty nine points and not thirty eight. Off by one here
    would move every number the lesson quotes about lifetimes."""
    a = next(a for a in x86["p20"] if a.pseudo == 134 and a.level == 0)
    assert a.ranges == ((4, 42),)
    assert a.live == 39


def test_the_conflict_graph_is_per_region_and_keyed_on_pseudos(x86):
    """Region 0 is the whole function. Conflicts between allocnos in different regions are
    not conflicts, so a graph that mixed the regions would invent edges."""
    graph = x86["p20"].graph(level=0)
    assert len(graph) == 42
    assert max(len(peers) for peers in graph.values()) == 39
    assert [p for p, peers in graph.items() if not peers] == [140]
    for pseudo, peers in graph.items():
        assert pseudo not in peers


def test_the_colouring_trace_is_not_the_answer(arm):
    """The one thing in this dump most likely to be misread. Four allocnos in p30 on aarch64
    swap places between the trace and the disposition, because a later step goes back and
    trades a spilled value for a cheaper victim."""
    p30 = arm["p30"]
    told = {step.allocno for step in p30.spill_steps()}
    ended = {a.num for a in p30 if a.spilled}
    assert len(told) == len(ended) == 4
    assert told != ended
    assert sorted(told ^ ended) == [57, 58, 61, 91]
    assert {p30.allocnos[n].pseudo for n in told - ended} == {129}
    assert {p30.allocnos[n].pseudo for n in ended - told} == {159}


def test_the_order_records_both_halves_of_the_colouring(arm):
    """Push then pop, and the reader keeps the verdict off the pop because that is where the
    algorithm says whether it found a register."""
    order = arm["p30"].order
    assert {step.action for step in order} == {"push", "pop"}
    assert len([s for s in order if s.action == "push"]) == len(
        [s for s in order if s.action == "pop"]
    )
    assert {s.verdict for s in order if s.action == "push"} == {""}


def test_costs_are_read_and_are_zero_when_nothing_went_to_memory(x86):
    """The totals line is IRA pricing its own answer. A function that fits pays nothing for
    memory traffic, which is the check that the field is being read and not invented."""
    assert x86["p04"].totals.mem == 0
    assert x86["p10"].totals.mem == 0
    assert x86["p14"].totals.mem == 10220
    for alloc in x86:
        assert (alloc.totals.mem > 0) == bool(alloc.spilled)


@pytest.mark.parametrize("entry", ENTRIES)
def test_the_same_five_functions_parse_on_every_target(entry):
    """The reader is not reading x86 specific text. Three targets, three register file
    sizes, one set of regexes, and the same five functions come out of all of them."""
    dump = load(entry)
    assert list(dump.functions) == ["p04", "p10", "p14", "p20", "p30"]
    for alloc in dump:
        assert alloc.allocnos
        assert alloc.peak() > 0
        assert alloc.available() > 0
        assert alloc.compression is not None


@pytest.mark.parametrize("entry", ENTRIES)
def test_a_function_fits_exactly_when_nothing_ended_up_in_memory(entry):
    """`fits` is derived from the disposition rather than from the arithmetic, and the two
    agreeing on all fifteen measurements is the whole argument of the lesson."""
    for alloc in load(entry):
        assert alloc.fits == (not alloc.spilled)
        assert alloc.fits == (alloc.over() <= 0)


def test_str_says_the_thing_a_reader_needs_first(x86):
    """Printed in the notebook more than once, so it is worth pinning."""
    assert str(x86["p04"]) == "p04: peak 6 of 15 GENERAL_REGS, 10 pseudos, fits"
    assert str(x86["p20"]) == "p20: peak 22 of 15 GENERAL_REGS, 42 pseudos, 7 in memory"
    assert str(next(iter(x86["p04"]))).startswith("a0(r")
