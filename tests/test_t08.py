"""The facts T08 is built on, so that re-recording the corpus cannot quietly rewrite it.

The lesson is one argument, that the machine has a fixed number of registers and the expander
does not care, and every step of it is a number a cell computed. Re-record against a newer GCC
and any of those numbers can move without a single test going red, unless the numbers are
written down somewhere. This is where.

The x86-64 and aarch64 Linux numbers come from Compiler Explorer at GCC 16.1.0. The Darwin
numbers come from a local `gcc-16`, which is 16.2.0 on `aarch64-apple-darwin24`. The lesson
says which is which and so does the corpus.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from conftest import grader

from gxmanim import mobjects, svg
from gxray import corpus_store, regalloc
from gxwidgets.regalloc import RegAlloc, home, summary

LESSON = "t08-registers-are-a-lie-until-they-are-not"

#: Every function in the corpus, in the order the source has them, which is also increasing
#: register pressure. The names say how many values the loop keeps in flight.
FUNCTIONS = ["p04", "p10", "p14", "p20", "p30"]

#: The three configurations, and what each one hands the allocator out of GENERAL_REGS.
AVAILABLE = {"t08-x86-64": 15, "t08-aarch64": 30, "t08-local": 29}


def load(entry: str):
    return regalloc.parse(corpus_store.load(entry).dump_texts["rtl-ira"], entry).functions


@pytest.fixture
def x86():
    return load("t08-x86-64")


@pytest.fixture
def arm():
    return load("t08-aarch64")


@pytest.fixture
def darwin():
    return load("t08-local")


def test_the_ramp_is_a_ramp(x86):
    """Five functions, pressure going up by roughly the number in the name, and nothing else
    changing. If this stops holding then the corpus program has drifted and every comparison
    in the lesson is comparing two things at once."""
    assert [x86[fn].peak() for fn in FUNCTIONS] == [6, 12, 16, 22, 32]
    assert [len(x86[fn].pseudos) for fn in FUNCTIONS] == [10, 22, 30, 42, 62]


def test_x86_hands_out_fifteen_and_p14_is_the_function_that_catches_you(x86):
    """Sixteen general registers in the architecture and fifteen available, because the stack
    pointer is one of them. p14 has pressure sixteen, so a reader who counted sixteen
    registers predicts it fits and a reader who counted fifteen predicts it does not."""
    assert x86["p14"].available() == 15
    assert x86["p14"].peak() == 16
    assert x86["p14"].spilled == [142]


def test_the_three_functions_that_spill_on_x86_are_the_three_over_the_limit(x86):
    """The whole boss fight in one line, and the reason it is a fair question rather than a
    memory test: the answer is arithmetic the reader can do before looking."""
    spilling = [fn for fn in FUNCTIONS if not x86[fn].fits]
    assert spilling == ["p14", "p20", "p30"]
    assert [fn for fn in FUNCTIONS if x86[fn].over() > 0] == spilling


@pytest.mark.parametrize("entry", sorted(AVAILABLE))
def test_the_count_in_memory_is_exactly_the_count_over_the_limit(entry):
    """Fifteen measurements across three targets and the rule holds in all of them. The
    lesson says it out loud and then says why it is not a general rule, so this test is
    holding down the observation and not a law."""
    functions = load(entry)
    for fn in FUNCTIONS:
        alloc = functions[fn]
        assert alloc.available() == AVAILABLE[entry]
        assert len(alloc.spilled) == max(0, alloc.over())


def test_the_same_source_comes_out_differently_on_two_machines(x86, arm):
    """The point of the lesson. Nothing about the C changed, nothing about the flags changed,
    and three of five answers changed, because one machine has twice the registers."""
    assert [len(x86[fn].spilled) for fn in FUNCTIONS] == [0, 0, 1, 7, 17]
    assert [len(arm[fn].spilled) for fn in FUNCTIONS] == [0, 0, 0, 0, 2]
    differ = [fn for fn in FUNCTIONS if len(x86[fn].spilled) != len(arm[fn].spilled)]
    assert differ == ["p14", "p20", "p30"]


def test_the_third_machine_is_the_same_architecture_and_still_disagrees(arm, darwin):
    """aarch64 twice, Linux and Darwin, and Apple reserves x18 as the platform register. One
    register fewer, one more value in memory in p30, and this is the cleanest evidence in the
    book that the answer belongs to a configuration and not to an architecture."""
    assert arm["p30"].available() - darwin["p30"].available() == 1
    assert darwin["p30"].spilled == [129, 159, 193]
    assert arm["p30"].spilled == [159, 193]
    for fn in ["p04", "p10", "p14", "p20"]:
        assert arm[fn].fits and darwin[fn].fits


def test_p20_is_the_worked_example_and_its_numbers_are_what_the_prose_says(x86):
    """The middle of the lesson reads one function closely. Every number in that section is
    here, because prose that quotes a number is prose that goes stale."""
    p20 = x86["p20"]
    assert len(p20.pseudos) == 42
    assert len(p20.allocnos) == 64
    counts = {}
    for group in p20.pseudos.values():
        counts[len(group)] = counts.get(len(group), 0) + 1
    assert counts == {1: 20, 2: 22}
    assert p20.compression == (142, 45)
    graph = p20.graph(level=0)
    assert max(len(peers) for peers in graph.values()) == 39
    assert [p for p, peers in graph.items() if not peers] == [140]


def test_the_longest_lived_value_in_p20_keeps_a_register_in_both_regions(x86):
    """The example the allocno section opens on. It is the value that is alive nearly
    everywhere, it has two allocnos because it crosses the loop boundary, and it wins, which
    is the useful half of the point: pressure decides how many lose, not which."""
    group = x86["p20"].pseudos[134]
    assert [a.level for a in group] == [0, 1]
    assert [a.ranges for a in group] == [((4, 42),), ((43, 44),)]
    assert [a.where for a in group] == ["reg 2", "reg 2"]
    assert 134 in x86["p20"].kept


def test_the_memory_cost_is_the_second_thing_the_targets_disagree_about(x86, arm):
    """Counting spills understates it, because a value in memory in a loop is charged every
    time round. p30 is the only function both machines pay for and the bills are not close."""
    assert x86["p30"].totals.mem == 485260
    assert arm["p30"].totals.mem == 25774
    assert x86["p30"].totals.mem // arm["p30"].totals.mem == 18
    paid = [fn for fn in FUNCTIONS if x86[fn].totals.mem and arm[fn].totals.mem]
    assert paid == ["p30"]


def test_the_widget_sees_two_targets_and_the_same_five_functions():
    """The widget takes the intersection, so a target that recorded a different set of
    functions would silently shrink the table rather than show a hole."""
    allocations = {
        "x86-64": load("t08-x86-64"),
        "aarch64": load("t08-aarch64"),
    }
    widget = RegAlloc(allocations)
    assert widget.targets == ["x86-64", "aarch64"]
    assert widget.functions == FUNCTIONS
    assert widget.selected == "p04"
    # p30 spills on both, so it is not a divergence about whether the function fits even
    # though the two targets sent very different numbers of values to memory.
    assert widget.divergence() == ["p14", "p20"]


def test_the_widget_summary_says_it_fits_in_words_rather_than_as_a_number(x86):
    """A column of numbers where one of them is a negative count of how far under the limit
    a function came is a column nobody reads correctly."""
    assert summary(x86["p04"])["over"] == "none, it fits"
    assert summary(x86["p20"])["over"] == "7"
    assert summary(x86["p20"])["spilled"] == "7"


def test_a_pseudo_in_memory_in_one_region_reads_as_in_memory(x86):
    """The widget filter has to agree with the lesson's arithmetic, so both fold the regions
    together the same way."""
    p20 = x86["p20"]
    assert home(p20, 116) == "memory"
    assert home(p20, 134) == "register"
    assert home(p20, 9999) == "nowhere"
    inside = [p for p in p20.pseudos if home(p20, p) == "memory"]
    assert inside == p20.spilled


def test_the_widget_renders_without_a_target_selected():
    """Colab hands the notebook no query string, so the first render is the default one and
    it has to pick a function on its own."""
    widget = RegAlloc({"x86-64": load("t08-x86-64")})
    body = widget.render()
    assert "p04" in body and "p30" in body
    assert widget.data()["diverges"] == []


def test_both_stills_draw(x86, arm):
    """A scene that will not render is a layout bug and it is worth catching here rather
    than the first time the notebook runs."""
    allocations = {"x86-64": x86, "aarch64": arm}
    both = mobjects.spill_map({t: fns["p20"] for t, fns in allocations.items()}, title="p20")
    rows = {fn: {t: fns[fn] for t, fns in allocations.items()} for fn in FUNCTIONS}
    ramp = mobjects.pressure_ramp(rows, "x86-64")
    for scene in (both, ramp):
        assert ET.fromstring(svg.document(scene)) is not None
        assert scene.describe()


def test_the_spill_map_marks_exactly_the_values_that_went_to_memory(x86, arm):
    """Colour is never the only carrier, so the cells that changed have to be the spilled
    ones and the state string has to say so in words."""
    scene = mobjects.spill_map({"x86-64": x86["p20"], "aarch64": arm["p20"]})
    lanes = {p.shape.name: p.shape for p in scene.placed}
    x = lanes["x86-64"]
    assert len(x.cards) == 42
    marked = [c.name for c in x.cards if c.changed]
    assert marked == [f"r{p}" for p in x86["p20"].spilled]
    assert {c.state for c in x.cards} == {"in a register", "in memory"}
    assert not any(c.changed for c in lanes["aarch64"].cards)


def test_the_ramp_draws_one_cell_per_live_value_and_marks_the_ones_with_nowhere_to_go(x86, arm):
    """The supply and demand picture. The count of marked cells in a lane is how far that
    function is over the limit, which is the number the lesson keeps coming back to."""
    rows = {fn: {"x86-64": x86[fn], "aarch64": arm[fn]} for fn in FUNCTIONS}
    scene = mobjects.pressure_ramp(rows, "x86-64")
    lanes = {p.shape.name: p.shape for p in scene.placed}
    assert [len(lanes[fn].cards) for fn in FUNCTIONS] == [6, 12, 16, 22, 32]
    over = [len([c for c in lanes[fn].cards if c.changed]) for fn in FUNCTIONS]
    assert over == [0, 0, 1, 7, 17]
    assert "15 registers" in scene.title


def test_the_grader_marks_the_answer_the_lesson_leads_you_to():
    """A boss fight nobody has watched pass is a boss fight that might be waving everything
    through, so the right answer is checked here as well as in CI."""
    module = grader(LESSON)
    functions = module.allocation()
    assert module.spillers(functions) == ["p14", "p20", "p30"]
    assert functions["p20"].available() == 15
    assert len(functions["p20"].spilled) == 7


def test_the_grader_wants_all_three_answers():
    """Two of three right is not right. The third question is the one that needs the dump."""
    module = grader(LESSON)
    right = ["--spills", "p14,p20,p30", "--available", "15", "--p20-memory", "7"]
    assert module.main(right) == 0
    assert module.main(["--spills", "p20,p30", "--available", "15", "--p20-memory", "7"]) == 1
    assert module.main(["--spills", "p14,p20,p30", "--available", "16", "--p20-memory", "7"]) == 1
    assert module.main(["--spills", "p14,p20,p30", "--available", "15", "--p20-memory", "6"]) == 1


def test_the_grader_reads_a_list_however_the_reader_punctuates_it():
    """`p20,p14` and `p14 p20` are the same prediction, and marking them differently would
    be marking punctuation."""
    module = grader(LESSON)
    assert module.named("p20,p14", FUNCTIONS) == ["p14", "p20"]
    assert module.named("p14 p20 p30", FUNCTIONS) == ["p14", "p20", "p30"]
    assert module.named("p14, p99", FUNCTIONS) == ["p14"]
    assert module.named("", FUNCTIONS) == []


def test_the_grader_finds_a_number_in_a_sentence():
    """Somebody is going to type `15 of them` and mean fifteen."""
    module = grader(LESSON)
    assert module.number("15") == 15
    assert module.number("15 of them") == 15
    assert module.number("fifteen") is None
    assert module.number("") is None
