"""The facts T10 is built on, so that re-recording the corpus cannot quietly rewrite it.

T10 is the lesson that adds no new machinery. Everything in it was built in T01 through T09,
and what is new is that all of it is pointed at one function at once. That makes it the lesson
most exposed to drift: it asserts about forty numbers, and every one of them comes out of a
recording rather than out of the prose. If a re-record moves any of them, the notebook goes on
reading perfectly well and starts being wrong, which is the worst failure a book like this has.
So the numbers live here too.

`t10-whole` is the wide recording: every tree dump of L2 at -O2, five named RTL dumps, the pass
list, and the assembly with `-dp`. `t10-ladder` is the narrow one, recorded separately because
the ladder needs the `-lineno` modifier and one dump cannot be two dumps. Both are the local
compiler, GCC 16.2.0 for aarch64 Darwin.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from conftest import grader

from gxmanim import mobjects, svg
from gxray import asm, cfg, corpus_store, diff, gimple, locs, passes, rtl, tape
from gxwidgets import IRLadder, PassTape, PredictGate

LESSON = "t10-the-whole-map"

#: The two recordings. The lesson needs both and neither one can be folded into the other.
ENTRIES = ("t10-whole", "t10-ladder")

#: The one function everything in the lesson is about. `dist2` is static and inlined away, so
#: after the second dump there is nothing else in the file.
FUNCTION = "nearest"

#: The counting argument, which is the number the lesson opens on and closes on. These five
#: have to keep adding up: 36 and 98 are the passes we could compare, 147 had no dump on one
#: side or the other, and 135 wrote a dump at all, one more than 36 plus 98 because the very
#: first dump has nothing before it to be compared against.
TAPE = {"enabled": 281, "with_stats": 135, "changed": 36, "unchanged": 98, "unknown": 147}

#: The nine of the fourteen stages that are passes, and where each one sits in the enabled
#: list. The five stages that are missing from this table are the point of the table.
ANCHORS = {
    "tree-cfg": 5,
    "tree-ssa": 13,
    "tree-early_optimizations": 24,
    "ipa-inline": 71,
    "tree-optimized": 206,
    "rtl-expand": 207,
    "rtl-combine": 234,
    "rtl-ira": 248,
    "rtl-final": 279,
}

#: How many insns have a multiply sitting inside an add, at each RTL stage the lesson dumps.
#: The step from zero to two is the whole of the combine section.
FUSED = {"rtl-expand": 0, "rtl-combine": 2, "rtl-ira": 2, "rtl-reload": 2, "rtl-final": 2}

#: A statement that multiplies a name by itself. The back reference is what makes it a square,
#: and it is the same expression the grader looks for.
SQUARE = re.compile(r"= (\S+) \* \1;")


@pytest.fixture(scope="module")
def whole():
    return corpus_store.load("t10-whole")


@pytest.fixture(scope="module")
def pipeline(whole):
    return passes.parse(whole.pass_texts["-O2"])


@pytest.fixture(scope="module")
def dumps(whole) -> dict[str, gimple.Function]:
    """Every tree dump in the wide recording that holds a body for `nearest`."""
    found = {}
    for key, text in whole.dump_texts.items():
        if not key.startswith("tree-") or key.endswith("-graph"):
            continue
        body = gimple.parse(text).functions.get(FUNCTION)
        if body is not None:
            found[key] = body
    return found


@pytest.fixture(scope="module")
def order(pipeline, dumps) -> list[str]:
    """The dumps in the order the passes that wrote them ran."""
    return [p.name for p in pipeline.enabled if p.name in dumps]


@pytest.fixture(scope="module")
def ladder(whole):
    record = corpus_store.load("t10-ladder")
    return locs.ladder(
        record.source,
        generic=record.dump_texts["tree-original"],
        gimple=record.dump_texts["tree-optimized"],
        rtl=record.dump_texts["rtl-expand"],
        asm=record.asm,
        function=FUNCTION,
    )


def statements(f: gimple.Function) -> list:
    return [s for b in f.ordered_blocks for s in b.stmts if not s.is_debug]


def squares(f: gimple.Function) -> tuple[str, ...]:
    return tuple(s.text.strip() for s in statements(f) if SQUARE.search(s.text))


def flow():
    """The control flow graph of the finished function, off the graph dump."""
    graph_dump = corpus_store.load("t10-ladder").dump_texts["tree-optimized-graph"]
    return cfg.parse(graph_dump)[FUNCTION]


# The counting argument


def test_the_numbers_on_the_tape_add_up(pipeline, dumps):
    """The five numbers the lesson repeats in words, in the gates and in the diagram. They
    are one arithmetic identity, and if a re-record breaks it then either the tape is wrong
    or the prose is, and there is no way to tell which from the notebook alone."""
    cells = tape.cells(pipeline, dumps)
    assert len(pipeline.all) == 395
    assert len(cells) == len(pipeline.enabled) == TAPE["enabled"]
    assert len([c for c in cells if c.stats]) == TAPE["with_stats"]
    assert len([c for c in cells if c.changed]) == TAPE["changed"]
    assert len([c for c in cells if c.changed is False]) == TAPE["unchanged"]
    assert len([c for c in cells if c.changed is None]) == TAPE["unknown"]
    assert TAPE["changed"] + TAPE["unchanged"] + TAPE["unknown"] == TAPE["enabled"]


def test_most_passes_that_could_be_measured_did_nothing(pipeline, dumps):
    """The claim the lesson is really making. Not that optimization is cheap, but that a
    pass is a question and most questions have the answer no. Two thirds is the shape of it,
    and a build where most measured passes changed something would mean the tape is comparing
    the wrong pairs of dumps."""
    cells = tape.cells(pipeline, dumps)
    measured = [c for c in cells if c.changed is not None]
    assert len(measured) == TAPE["changed"] + TAPE["unchanged"]
    assert len([c for c in measured if not c.changed]) > 2 * len(measured) / 3


def test_the_unknown_cells_are_a_third_state_and_not_a_gap(pipeline, dumps):
    """Half the tape is `?` and that is honest rather than broken. Those passes have no dump
    on one side or the other, so there is nothing to compare, and every widget in the book has
    to be able to say so. A tape that guessed would be more than half made up."""
    cells = tape.cells(pipeline, dumps)
    unknown = [c for c in cells if c.changed is None]
    assert len(unknown) > len(cells) / 2
    assert len([c for c in unknown if c.stats]) == 1
    assert [c.name for c in unknown if c.stats] == ["tree-omplower"]


# The fourteen stages


def test_nine_of_the_fourteen_stages_are_passes_and_five_are_not(pipeline):
    """The lesson's opening move. A reader who learns the pipeline from `-fdump-passes` never
    sees the driver, the preprocessor, the parser, the gimplifier or the assembler, because
    none of the five is in `passes.def` and four of them run before the pass manager exists."""
    assert len(ANCHORS) == 9
    for name, position in ANCHORS.items():
        at = [i for i, p in enumerate(pipeline.enabled, start=1) if p.name == name]
        assert at == [position], name


def test_the_stages_are_in_the_order_the_lesson_lists_them(pipeline):
    """The table is only worth printing if the positions run upwards. Two stages out of order
    would mean the lesson is teaching a pipeline the recording does not have."""
    positions = list(ANCHORS.values())
    assert positions == sorted(positions)
    assert positions[-1] < len(pipeline.enabled)


def test_expand_is_the_pass_immediately_after_the_last_tree_dump(pipeline):
    """Where GIMPLE stops. `tree-optimized` and `rtl-expand` are adjacent in the enabled list,
    so there is no room between them for anything to happen, and the reader can be told that
    one pass is the whole of the boundary."""
    assert ANCHORS["rtl-expand"] == ANCHORS["tree-optimized"] + 1


# The ladder


def test_the_ladder_has_a_rung_for_every_line_with_code_on_it(ladder):
    """Fourteen rungs for a twenty eight line file. The rungs the ladder does not have are as
    informative as the ones it does: a blank line and a declaration produce nothing."""
    assert ladder.file == "l2.c"
    assert ladder.levels == ("generic", "gimple", "rtl", "asm")
    assert len(ladder.rungs) == 14
    assert ladder.lines == [8, 9, 10, 15, 16, 17, 18, 19, 20, 21, 23, 24, 27, 28]


def test_three_rungs_are_source_lines_that_belong_to_the_other_function(ladder):
    """The inlining, seen from the source rather than from a dump. Lines 8 to 10 are the body
    of `dist2`, which is a different function in the file, and they have rows in the ladder of
    `nearest` because that is where their statements ended up."""
    inside = [r for r in ladder.rungs if 5 <= r.line <= 11]
    assert [r.line for r in inside] == [8, 9, 10]
    assert all(not r.at("generic") for r in inside)
    assert all(r.at("gimple") and r.at("rtl") for r in inside)


def test_the_line_the_boss_fight_follows_is_the_widest_rung_in_gimple(ladder):
    """Line 10 is `return dx * dx + dy * dy`, and it is the line with the most GIMPLE against
    it because it was inlined twice and each copy is three statements. The lesson picks that
    line for the trace and this is the reason it is the right one to pick."""
    rung = ladder.rung(10)
    assert rung.source.strip() == "return dx * dx + dy * dy;"
    assert len(rung.at("gimple")) == 6
    assert len(rung.at("rtl")) == 6


def test_two_source_lines_disappear_by_the_end(ladder):
    """Lines 19 and 20 have GENERIC against them and nothing after it. Line 20 is the second
    call to `dist2`, and the call is gone because the body replaced it, which is what inlining
    looks like from this angle."""
    gone = [r.line for r in ladder.rungs if r.at("generic") and not r.at("gimple")]
    assert gone == [15, 19, 20]
    assert ladder.rung(20).source.strip() == "int d = dist2 (&pts[i], &q);"


# One pass, two dumps


def test_release_ssa_changed_everything_and_changed_nothing(dumps, order):
    """The lesson's favourite pass. Twenty three lines different, every one of them only a
    version number, nothing added and nothing removed. It is the cleanest example in the book
    of a diff that is large and means nothing, and the reason the differ separates renumbering
    from real change at all."""
    before = order[order.index("tree-release_ssa") - 1]
    d = diff.compare(
        dumps[before], dumps["tree-release_ssa"], before_name=before, after_name="release_ssa"
    )
    assert d.counts["changed"] == 23
    assert d.counts["added"] == d.counts["removed"] == 0
    assert len(d.renumbered) == 23
    assert len(d.of("changed")) == len(d.renumbered)


def test_einline_is_the_largest_single_change_and_none_of_it_is_renumbering(dumps, order):
    """The other half of the pair. Twenty lines added, nothing renumbered, and it is the
    biggest single event in the tree half of the run. Set beside `release_ssa` it makes the
    point that a diff's size and a diff's meaning are unrelated."""
    before = order[order.index("tree-einline") - 1]
    d = diff.compare(dumps[before], dumps["tree-einline"], before_name=before, after_name="einline")
    assert d.counts["added"] == 20
    assert d.counts["removed"] == 0
    assert d.renumbered == []
    assert "einline" in str(d)


def test_the_ir_grows_before_it_shrinks(dumps):
    """The shape of the whole run in two numbers. The peak is not at the start and not at the
    end, because the inliner copies before the optimizers take it apart, and `ifcvt` copies
    again so the vectorizer has something branch free to measure."""
    sizes = {key: len(statements(f)) for key, f in dumps.items()}
    peak = max(sizes, key=lambda k: sizes[k])
    assert peak == "tree-ifcvt"
    assert sizes[peak] == 58
    assert sizes["tree-optimized"] == 34


# Following one expression


def test_five_tree_passes_changed_the_squares(dumps, order):
    """The first boss fight answer, derived the way the grader derives it. Two of the five are
    the interesting ones: `release_ssa` only renumbered them and `ifcvt` made copies that
    `vect` threw away, so three of the five are not optimizations of this expression at all."""
    events, seen = [], None
    for name in order:
        now = squares(dumps[name])
        if seen is not None and now != seen:
            events.append(name.removeprefix("tree-"))
        seen = now
    assert events == ["einline", "release_ssa", "sink1", "ifcvt", "vect"]


def test_inlining_twice_makes_four_squares_and_the_count_comes_back_to_four(dumps):
    """Two call sites times two squares each. `ifcvt` briefly makes it six and `vect` puts it
    back, which is the counting argument behind the second gate in the notebook."""
    assert len(squares(dumps["tree-einline"])) == 4
    assert len(squares(dumps["tree-ifcvt"])) == 6
    assert len(squares(dumps["tree-vect"])) == 4


def test_combine_is_where_the_multiply_and_the_add_became_one_insn(whole):
    """Zero fused insns in the expand dump and two in the next one. Everything after combine
    carries the same two, so the fusing happened once and was not undone, and no pass after it
    can be the answer."""
    for key, want in FUSED.items():
        body = rtl.parse(whole.dump_texts[key], key).only()
        patterns = [str(i.pattern) for i in body.code]
        assert len([p for p in patterns if "mult" in p and "plus" in p]) == want, key


def test_the_assembly_names_the_pattern_that_printed_the_fused_instruction(whole):
    """The end of the trace. `-dp` puts the machine description pattern in a comment on every
    line, so the reader never has to be told which pattern fused it. `mulsi3` is here too,
    because two of the four multiplies did not find an add to fuse with."""
    listing = asm.parse(whole.asm_texts["-O2 -dp"], "t10-whole")
    used = {line.pattern for line in listing.insns if line.pattern}
    assert "maddsi" in used
    assert "mulsi3" in used
    assert len([line for line in listing.insns if line.pattern == "maddsi"]) == 2


def test_thirty_four_statements_became_twenty_five_instructions(whole, dumps):
    """The last join in the lesson, and the last sanity check on the two recordings agreeing.
    A file with more instructions than the final GIMPLE had statements would mean the assembly
    and the dumps came from different compilations."""
    listing = asm.parse(whole.asm_texts["-O2 -dp"], "t10-whole")
    assert len(statements(dumps["tree-optimized"])) == 34
    assert len(listing.insns) == 25
    assert listing.counts()["total"] == 69


# The widgets


def test_the_tape_widget_agrees_with_the_counts_in_the_prose(pipeline, dumps, whole):
    """The widget and the text cell next to it are two renderings of one computation, and the
    notebook prints both so that a reader with no JavaScript still gets the numbers. If they
    ever disagree the page contradicts itself in front of the reader."""
    widget = PassTape(pipeline, dumps=dumps, function=FUNCTION, options=" ".join(whole.args))
    facts = widget.data()
    assert len(facts["cells"]) == TAPE["enabled"]
    assert len(facts["panels"]) == TAPE["with_stats"]
    marks = {"1": TAPE["changed"], "0": TAPE["unchanged"], "?": TAPE["unknown"]}
    for mark, want in marks.items():
        assert len([c for c in facts["cells"] if c["changed"] == mark]) == want, mark


def test_the_ladder_widget_carries_the_same_fourteen_rows(ladder):
    """The ladder is the same run seen from the source, so it has to be the same run. The
    totals are what the notebook prints under the widget and they are the per level counts
    added up, not a second measurement."""
    shape = IRLadder(ladder, line=10).data()
    assert shape["lines"] == ladder.lines
    assert set(shape["totals"]) == set(ladder.levels)
    for level in ladder.levels:
        assert shape["totals"][level] == sum(len(r.at(level)) for r in ladder.rungs)


def test_the_ten_gates_are_ten_separate_widgets():
    """Every widget defaults its id to its kind, so ten gates on one page would be ten copies
    of one id, and clicking any of them would move all of them. The lesson passes an explicit
    id to each and this is the test that says why it has to."""
    gates = [
        PredictGate(
            f"Question {n}?",
            [("right", ""), ("wrong", "because")],
            answer="right",
            id=f"t10-q{n}",
        )
        for n in range(1, 11)
    ]
    assert len({g.id for g in gates}) == 10
    assert PredictGate("q?", [("a", ""), ("b", "why")], answer="a").id == "predictgate"


# The pictures


def test_both_stills_draw(pipeline, dumps):
    """A scene that will not render is a layout bug, and the notebook is the wrong place to
    find out. The tape still is 281 cells wide, which is the one in the book most likely to
    break a layout."""
    cells = tape.cells(pipeline, dumps)
    for scene in (mobjects.pass_tape(cells, title="nearest"), mobjects.cfg_view(flow())):
        assert scene.check() == []
        assert ET.fromstring(svg.document(scene)) is not None
        assert scene.describe()


def test_the_control_flow_of_the_finished_function_is_a_loop_with_a_test_in_it():
    """The CFG the still draws. Eight blocks and ten edges, which is a loop with an `if` in
    the body, and it is worth pinning because a graph that came out as a straight line would
    mean the loop had been unrolled and the picture is of a different program."""
    graph = flow()
    assert len(graph.blocks) == 8
    assert len(graph.edges) == 10
    assert any(e.back for e in graph.edges)


def test_the_diagram_is_in_the_repository_and_parses():
    """The excalidraw file is checked in rather than built on the fly, because the T0 exercise
    is to open it and edit it. `just lesson-diagrams` regenerates it and the CI job fails if
    the checked in copy has drifted from `diagram.py`."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "lessons" / LESSON
    scene = json.loads((path / "diagrams" / "the-whole-map.excalidraw").read_text())
    assert scene["type"] == "excalidraw"
    assert len(scene["elements"]) > 20


# The recordings the lesson needs


@pytest.mark.parametrize("entry", ENTRIES)
def test_both_recordings_are_the_same_compiler_on_the_same_program(entry):
    """Two recordings of one compilation, split only because one dump cannot carry both the
    plain and the `-lineno` form of a tree dump. If the compiler or the source ever differed
    then the tape and the ladder would be describing different runs and the lesson's central
    claim, that these are two views of one thing, would be false."""
    record = corpus_store.load(entry)
    assert record.target == "aarch64-apple-darwin24"
    assert "16.2.0" in record.compiler
    assert "dist2" in record.source
    assert record.source == corpus_store.load("t10-whole").source


def test_the_wide_recording_has_the_dumps_the_lesson_reads(whole):
    """The five RTL dumps are named one at a time rather than asked for with `rtl-all`,
    because `rtl-all` is a hundred megabytes and the lesson needs five stages of it."""
    for key in FUSED:
        assert key in whole.dump_texts
    assert "-O2" in whole.pass_texts
    assert "-O2 -dp" in whole.asm_texts


def test_l2_is_the_program_because_l1_gives_the_ipa_passes_nothing_to_do(whole):
    """Why this lesson does not use L1 like the nine before it. A single function file has no
    call to inline, so `einline` does nothing, the trace has no first step, and a lesson about
    the whole pipeline would show a quarter of it with no work in it."""
    assert "static int" in whole.source
    assert whole.source.count("dist2") >= 3
    assert FUNCTION in gimple.parse(whole.dump_texts["tree-gimple"]).functions
    assert "dist2" in gimple.parse(whole.dump_texts["tree-gimple"]).functions


# The boss fight


def test_the_grader_marks_the_answer_the_lesson_leads_you_to():
    """A boss fight nobody has watched pass is a boss fight that might be waving everything
    through, so the right answer is run here as well as in the notebook."""
    module = grader(LESSON)
    right = [
        "--trace",
        "einline,release_ssa,sink1,ifcvt,vect",
        "--fused",
        "combine",
        "--pattern",
        "maddsi",
        "--changed",
        "36",
    ]
    assert module.main(right) == 0


def test_the_grader_wants_all_four_answers():
    """Three of four is not four. Each question is checked on its own so that a grader which
    had stopped looking at one of them would show up here rather than in a reader's terminal."""
    module = grader(LESSON)

    def run(**kw):
        answers = {
            "trace": "einline,release_ssa,sink1,ifcvt,vect",
            "fused": "combine",
            "pattern": "maddsi",
            "changed": "36",
        }
        answers.update(kw)
        return module.main([a for k, v in answers.items() for a in (f"--{k}", v)])

    assert run() == 0
    assert run(changed="40") == 1
    assert run(pattern="mulsi3") == 1
    assert run(fused="ira") == 1
    assert run(trace="einline,sink1,ifcvt,vect") == 1


def test_the_grader_cares_what_order_the_passes_come_in():
    """The answer is a trace, so the same five names in a different order is a different and
    wrong answer. Somebody who lists them alphabetically has not read the dumps in order."""
    module = grader(LESSON)
    right = "einline,release_ssa,sink1,ifcvt,vect"
    shuffled = "einline,sink1,release_ssa,ifcvt,vect"
    assert module.names(right) != module.names(shuffled)
    rest = ["--fused", "combine", "--pattern", "maddsi", "--changed", "36"]
    assert module.main(["--trace", right, *rest]) == 0
    assert module.main(["--trace", shuffled, *rest]) == 1


def test_the_grader_forgives_the_prefix_the_dumps_use():
    """`tree-einline` in the dump file names and `einline` in the pass list are the same pass.
    Which of the two a reader types says which file they read, not whether they got it right."""
    module = grader(LESSON)
    assert module.names("tree-einline, tree-vect") == ["einline", "vect"]
    assert module.names("einline vect") == ["einline", "vect"]
    assert module.names("") == []


def test_the_grader_finds_a_number_in_a_sentence():
    """Somebody is going to type `36 of them` and mean thirty six."""
    module = grader(LESSON)
    assert module.number("36") == 36
    assert module.number("36 of them") == 36
    assert module.number("thirty six") is None
    assert module.number("") is None


def test_the_grader_has_no_answer_key_in_it():
    """Every answer is derived from the recording, so re-recording against a newer compiler
    re-derives the marking instead of silently marking against last year's GCC. A literal
    answer in the source would be the one thing that could not survive that."""
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "lessons" / LESSON / "grade.py").read_text()
    body = source.split('"""', 2)[2]
    for answer in ("sink1", "maddsi", "36"):
        assert answer not in body, answer
