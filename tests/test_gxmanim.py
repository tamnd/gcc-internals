"""The visual grammar, the scenes built out of it, and the SVG they turn into.

Two things get held down here. The nine primitives stay nine, because a visual language
with thirty symbols is not a language. And semantics are never carried by colour alone, so
every role has to reach the drawing as a glyph and a border style too, which is checked by
reading the SVG back rather than by trusting the renderer.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from gxmanim import mobjects, svg
from gxmanim.palette import EDGES, ROLES
from gxmanim.primitives import (
    PRIMITIVES,
    Badge,
    Block,
    Card,
    Cell,
    Edge,
    Node,
    Point,
    Rung,
    Slot,
    Thread,
)
from gxmanim.scene import Scene
from gxray import cfg, gimple, locs, passes, rtl, tape

CORPUS = Path(__file__).resolve().parents[1] / "corpora" / "dumps" / "l1-O2.json"


@pytest.fixture
def recorded():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


@pytest.fixture
def fn(recorded):
    return gimple.parse(recorded["dumps"]["tree-optimized"]).only()


@pytest.fixture
def graph(recorded):
    return cfg.parse(recorded["dumps"]["tree-optimized-graph"])["f"]


@pytest.fixture
def ladder(recorded):
    return locs.ladder(
        recorded["source"],
        generic=recorded["dumps"]["tree-original"],
        gimple=recorded["dumps"]["tree-optimized"],
        rtl=recorded["dumps"]["rtl-expand"],
        asm=recorded["asm"],
        function="f",
    )


@pytest.fixture
def expand(recorded):
    return rtl.parse(recorded["dumps"]["rtl-expand"], "l1-O2").only()


def parsed(scene: Scene) -> ET.Element:
    """The rendered scene, read back as XML. A drawing that will not parse is not a drawing."""
    return ET.fromstring(svg.render(scene))


# The grammar


def test_there_are_nine_primitives_and_no_more():
    """Introducing a tenth means amending the visual system spec in the same pull request."""
    assert len(PRIMITIVES) == 9
    assert set(PRIMITIVES) == {
        "card",
        "block",
        "edge",
        "badge",
        "thread",
        "cell",
        "rung",
        "node",
        "slot",
    }


def test_a_shape_refuses_a_role_that_is_not_one_of_the_seven():
    with pytest.raises(KeyError) as exc:
        Card(text="x", role="turquoise")
    assert "neutral" in str(exc.value)


def test_an_edge_refuses_a_kind_gcc_does_not_have():
    with pytest.raises(KeyError) as exc:
        Edge(src="a", dst="b", kind="sideways")
    assert "fallthrough" in str(exc.value)


def test_a_card_leaves_room_for_its_glyph():
    """Without this the glyph lands on the last character, in the one case where a reader
    needs both the text and the role at once."""
    plain = Card(text="s_5 = s_9 + i_11;", role="neutral")
    marked = Card(text="s_5 = s_9 + i_11;", role="focus")
    assert marked.w > plain.w


def test_a_card_is_at_least_as_wide_as_its_badges():
    card = Card(text="x", badges=(Badge("s_1"), Badge("i_2")))
    assert card.w >= Badge("s_1").w + Badge("i_2").w


def test_a_lane_wraps_rather_than_growing_forever():
    """Six RTL insns on one source line is normal, and a lane two thousand across is a
    picture nobody scrolls to the end of."""
    cards = tuple(Card(text="(insn 15 14 16 2 (set (reg:CC 66 cc)", id=f"c{i}") for i in range(6))
    lane = Rung(name="RTL", cards=cards)
    assert len(lane.rows()) > 1
    assert lane.w <= Rung.max_w


def test_an_empty_lane_is_still_a_lane():
    lane = Rung(name="assembly")
    assert lane.h > 0
    assert lane.describe() == "assembly, nothing"


def test_a_slot_fills_its_bar_whatever_the_units_are():
    slot = Slot(name="frame", parts=(("saved", 16), ("locals", 8)), id="frame")
    boxes = [box for _, _, box in slot.part_boxes(Point(0, 0))]
    assert sum(b.w for b in boxes) == pytest.approx(Slot.bar_w)
    assert boxes[0].w == pytest.approx(2 * boxes[1].w)


def test_walking_a_tree_gives_parents_before_children():
    leaf = Node("const_int 1", id="c")
    root = Node("set", id="a", children=(Node("plus", id="b", children=(leaf,)),))
    assert [n.id for n in root.walk()] == ["a", "b", "c"]


# Scenes


def test_a_scene_knows_where_a_card_inside_a_block_ended_up():
    scene = Scene(title="t")
    scene.add(Block(index=2, cards=(Card(text="x", id="stmt"),), id="bb2"), 10, 10)
    inner, outer = scene.box("stmt"), scene.box("bb2")
    assert outer.x <= inner.x and inner.right <= outer.right
    assert inner.y > outer.y


def test_a_scene_knows_where_a_badge_on_a_card_ended_up():
    scene = Scene(title="t")
    scene.add(Card(text="x", id="c", badges=(Badge("s_1", id="b"),)), 0, 0)
    assert scene.box("b").y > scene.box("c").y


def test_asking_for_something_that_is_not_there_says_what_is():
    scene = Scene(title="t")
    scene.add(Card(text="x", id="here"), 0, 0)
    with pytest.raises(KeyError) as exc:
        scene.box("elsewhere")
    assert "here" in str(exc.value)


def test_a_link_to_nothing_is_caught_before_it_is_drawn():
    """An arrow pointing at an id nothing has produces a picture rather than an error, and
    a silently missing arrow is the worst kind of wrong diagram."""
    scene = Scene(title="t")
    scene.add(Card(text="x", id="a"), 0, 0)
    scene.link(Edge(src="a", dst="ghost"))
    assert any("ghost" in p for p in scene.check())
    with pytest.raises(ValueError, match="ghost"):
        svg.render(scene)


def test_a_scene_with_no_title_does_not_draw():
    assert any("no title" in p for p in Scene(title="").check())


def test_an_empty_scene_is_a_small_empty_box():
    bounds = Scene(title="nothing yet").bounds()
    assert bounds.w > 0 and bounds.h > 0


def test_what_a_scene_says_in_words_covers_everything_in_it():
    scene = Scene(title="One PHI", caption="two ways in")
    scene.add(Card(text="s_5 = s_9 + i_11;", id="a"), 0, 0)
    scene.add(Card(text="s_9 = 0;", id="b"), 0, 60)
    scene.link(Thread(src="b", dst="a", name="s_9"))
    said = scene.describe()
    assert said.startswith("One PHI\ntwo ways in")
    assert "s_5 = s_9 + i_11;" in said
    assert "s_9 from b to a" in said


# The SVG


def test_a_rendered_scene_is_well_formed_xml():
    scene = Scene(title="t")
    scene.add(Card(text="if (n_3(D) > 0)", id="a"), 0, 0)
    assert parsed(scene).tag.endswith("svg")


def test_dump_text_with_angle_brackets_in_it_survives():
    """Almost every line of a GIMPLE dump has a `<bb 3>` or a `>` in it, so this is not a
    corner case, it is the common case."""
    scene = Scene(title="t")
    scene.add(Card(text="goto <bb 3>; [89.00%]", id="a"), 0, 0)
    texts = [e.text for e in parsed(scene).iter() if e.tag.endswith("text")]
    assert "goto <bb 3>; [89.00%]" in texts


def test_the_drawing_says_what_it_is():
    scene = Scene(title="s_9 in f", caption="defined once, used twice")
    scene.add(Card(text="x", id="a"), 0, 0)
    root = parsed(scene)
    assert root.get("role") == "img"
    assert root.get("aria-label") == "s_9 in f"


def test_a_standalone_file_carries_its_own_description():
    scene = Scene(title="s_9 in f", caption="defined once, used twice")
    scene.add(Card(text="x", id="a"), 0, 0)
    root = ET.fromstring(svg.document(scene))
    tags = {e.tag.split("}")[-1]: e.text for e in root}
    assert tags["title"] == "s_9 in f"
    assert "defined once, used twice" in tags["desc"]


def test_every_role_reaches_the_drawing_as_a_glyph_and_not_only_as_a_colour():
    """The rule the whole palette exists for, checked by reading the picture back."""
    scene = Scene(title="every role")
    for i, name in enumerate(ROLES):
        scene.add(Card(text=name, role=name, id=name), 0, i * 50)
    texts = [e.text for e in parsed(scene).iter() if e.tag.endswith("text")]
    for role in ROLES.values():
        if role.glyph:
            assert role.glyph in texts, f"{role.name} reached the drawing as colour alone"


def test_a_dotted_role_is_drawn_dotted():
    scene = Scene(title="t")
    scene.add(Card(text="varying", role="unknown", id="a"), 0, 0)
    rects = [e for e in parsed(scene).iter() if e.tag.endswith("rect")]
    assert any(r.get("stroke-dasharray") == "2 3" for r in rects)


def test_a_doubled_border_is_drawn_as_two_rectangles():
    scene = Scene(title="t")
    scene.add(Card(text="changed", role="changed", id="a"), 0, 0)
    rects = [e for e in parsed(scene).iter() if e.tag.endswith("rect")]
    assert len(rects) == 2


def test_every_edge_kind_draws_something_a_reader_can_tell_apart():
    """Colour is not in the edge table at all, so the dash pattern, the weight, the glyph
    and the arrowhead have to carry all seven kinds between them."""
    seen = set()
    for kind in EDGES:
        scene = Scene(title="t")
        scene.add(Card(text="a", id="a"), 0, 0)
        scene.add(Card(text="b", id="b"), 0, 80)
        scene.link(Edge(src="a", dst="b", kind=kind))
        root = parsed(scene)
        # Top level only. The arrowheads in `<defs>` are paths too, and they are the same
        # two paths in every drawing.
        (path,) = [e for e in root if e.tag.endswith("path")]
        glyphs = [e.text for e in root.iter() if e.tag.endswith("text")]
        seen.add(
            (
                path.get("stroke-dasharray"),
                path.get("stroke-width"),
                path.get("marker-end"),
                tuple(glyphs),
            )
        )
    assert len(seen) == len(EDGES)


def test_a_probability_is_printed_as_well_as_drawn_as_weight():
    scene = Scene(title="t")
    scene.add(Card(text="a", id="a"), 0, 0)
    scene.add(Card(text="b", id="b"), 0, 80)
    scene.link(Edge(src="a", dst="b", kind="true", prob=0.89))
    texts = [e.text for e in parsed(scene).iter() if e.tag.endswith("text")]
    assert any("89%" in t for t in texts)


def test_a_marked_tape_cell_is_findable_without_reading_colour():
    scene = Scene(title="t")
    scene.add(Cell(name="ccp", role="changed", id="c", changed=True), 0, 0)
    texts = [e.text for e in parsed(scene).iter() if e.tag.endswith("text")]
    assert "|" in texts


# The mobjects, against the recorded corpus


def test_the_ladder_draws_the_lanes_that_have_nothing_in_them(ladder):
    """Line 8 is the whole reason to draw a ladder. `return s;` reaches GIMPLE and then
    disappears, because the value was already in the return register."""
    scene = mobjects.ir_ladder(ladder, 8)
    said = scene.describe()
    assert "RTL, nothing" in said
    assert "assembly, nothing" in said
    assert "GIMPLE, 1: return s_10;" in said


def test_the_busiest_line_in_l1_wraps_into_more_than_one_row(ladder):
    scene = mobjects.ir_ladder(ladder, 6)
    rtl = next(p.shape for p in scene.placed if getattr(p.shape, "id", "") == "rung-rtl")
    assert len(rtl.rows()) > 1
    assert scene.bounds().w <= Rung.max_w + 100


def test_a_long_insn_is_cut_and_says_so():
    long = "(insn 24 23 25 5 (set (reg/v:SI 101 [ i ]) (plus:SI (reg/v:SI 101) (const_int 1)))"
    assert mobjects.one_line(long, 40).endswith("...")
    assert len(mobjects.one_line(long, 40)) == 40


def test_a_multi_line_insn_becomes_its_first_line():
    assert mobjects.one_line("(insn 2 7 3 2 (set (reg:SI 1)\n  (const_int 0))") == (
        "(insn 2 7 3 2 (set (reg:SI 1)"
    )


def test_the_tape_has_one_cell_per_enabled_pass(passes_text):
    pipeline = passes.parse(passes_text)
    scene = mobjects.pass_tape(tape.cells(pipeline))
    assert len(scene.placed) == len(pipeline.enabled)


def test_the_tape_says_out_loud_how_many_cells_it_knows_nothing_about(passes_text):
    """Most of them. Claiming a pass changed nothing when there is no dump either side of
    it would be the tape inventing evidence."""
    pipeline = passes.parse(passes_text)
    scene = mobjects.pass_tape(tape.cells(pipeline))
    assert "nothing to compare against" in scene.caption
    assert all(p.shape.role == "unknown" for p in scene.placed)
    assert all("nothing is claimed" in p.shape.describe() for p in scene.placed)


def test_the_web_runs_a_thread_from_the_definition_to_every_use(fn):
    web = fn.ssa_web("s_9")
    scene = mobjects.ssa_web(fn, "s_9")
    assert len(scene.links) == len(web["uses"])
    assert scene.check() == []
    assert all(isinstance(link, Thread) for link in scene.links)


def test_a_name_with_no_definition_here_gets_no_threads(fn):
    """`n_3(D)` is the value f was called with, so nothing in f defines it and there is no
    end to draw a thread from."""
    scene = mobjects.ssa_web(fn, "n_3")
    assert scene.links == []
    assert "comes in as an argument" in scene.caption


def test_a_phi_gets_one_predecessor_block_per_argument(fn):
    phi = next(p for b in fn.ordered_blocks for p in b.phis)
    scene = mobjects.phi_node(fn, phi)
    assert len(scene.links) == len(phi.args)
    assert scene.check() == []


def test_a_constant_coming_into_a_phi_is_called_a_constant(fn):
    """`# s_9 = PHI <s_5(3), 0(2)>` says the loop starts at zero, and zero is not a name
    that anything defines."""
    phi = next(p for b in fn.ordered_blocks for p in b.phis if any("_" not in v for v, _ in p.args))
    scene = mobjects.phi_node(fn, phi)
    assert "a constant on this edge" in scene.describe()


def test_every_kind_of_edge_gcc_can_draw_has_somewhere_to_go_in_the_palette(
    graph, loops_graph, setjmp_graph
):
    """The two vocabularies have to line up, or a real dump renders as an exception.

    `gxray.cfg` cannot import the palette, since the palette lives on the drawing side, so
    nothing but this test is holding the two lists together.
    """
    graphs = [graph, cfg.parse(loops_graph)["g"], cfg.parse(setjmp_graph)["k"]]
    kinds = {e.kind for g in graphs for e in g.edges}
    assert kinds <= set(EDGES)
    assert {"fallthrough", "true", "false", "back", "abnormal"} <= kinds


def test_the_control_flow_view_draws_the_edges_the_dump_had(graph):
    scene = mobjects.cfg_view(graph)
    assert len(scene.links) == len(graph.edges)
    assert scene.check() == []
    assert "1 back" in scene.caption


def test_a_block_in_a_loop_is_the_one_thing_the_view_marks(graph):
    """`<bb 3>` is the loop, and in a control flow drawing that is the distinction worth
    spending a role on."""
    scene = mobjects.cfg_view(graph)
    roles = {p.shape.id: p.shape.role for p in scene.placed}
    assert roles["bb3"] == "focus"
    assert roles["bb2"] == "neutral"


def test_the_view_leaves_out_the_debug_markers_and_the_locations(graph):
    """The corpus is recorded with `-g` and `-lineno`, so every statement arrives with a
    marker in front of it and a location on it, and neither belongs in this picture."""
    drawn = mobjects.cfg_view(graph).describe()
    assert "# DEBUG" not in drawn
    assert "l1.c:" not in drawn
    assert "return s_10;" in drawn


def test_a_block_further_down_the_page_is_further_along_the_flow(graph):
    """ENTRY at the top, EXIT at the bottom, and a block below every block that reaches
    it. Laid out by counting forward edges, so a loop does not push its own body down."""
    scene = mobjects.cfg_view(graph)
    boxes = scene.boxes()
    assert boxes["bb0"].y < boxes["bb2"].y < boxes["bb3"].y < boxes["bb4"].y < boxes["bb1"].y


def test_the_dominator_tree_hangs_each_block_off_the_last_one_it_had_to_pass(graph):
    scene = mobjects.dom_tree(graph)
    assert scene.check() == []
    # ENTRY over <bb 2> over both <bb 3> and <bb 4>, and <bb 4> over EXIT.
    assert scene.box("dom0").bottom < scene.box("dom2").y
    assert scene.box("dom2").bottom < scene.box("dom3").y
    assert scene.box("dom4").bottom < scene.box("dom1").y


def test_the_dominator_tree_is_not_the_control_flow_graph(graph):
    """Worth pinning down, because they look alike and the difference is the lesson.

    Control goes from block 3 to block 4, and block 4 still hangs off block 2, because
    control also gets to block 4 straight from block 2 without going through 3.
    """
    assert (3, 4) in [(e.src, e.dst) for e in graph.edges]
    assert graph.dominators()[4] == 2


def test_a_tree_puts_a_parent_over_its_children():
    root = Node("set", id="a", children=(Node("reg:SI 103", id="b"), Node("plus:SI", id="c")))
    scene = mobjects.tree(root)
    parent, left, right = scene.box("a"), scene.box("b"), scene.box("c")
    assert left.right < right.x
    assert left.cx < parent.cx < right.cx
    assert parent.bottom < left.y


def test_an_rtx_becomes_the_tree_it_was_printed_from(expand):
    scene = mobjects.rtx_tree(expand.at(21))
    said = scene.describe()
    assert "set over reg/v:SI, plus:SI" in said
    assert "plus:SI over reg/v:SI, reg/v:SI" in said
    assert scene.title == "insn 21, opened up"


def test_the_drawing_counts_the_nodes_and_the_operands_separately(expand):
    """Eleven boxes and five of them are nodes, which is the thing the caption has to say."""
    scene = mobjects.rtx_tree(expand.at(21))
    assert "5 nodes and 6 operands that are not nodes, 3 deep" in scene.caption
    assert len(scene.placed) == 11


def test_a_pseudo_is_drawn_as_undecided_and_a_hard_register_is_not(expand):
    roles = {p.shape.text: p.shape.role for p in mobjects.rtx_tree(expand.at(38)).placed}
    assert roles["0"] == "constant"
    assert roles["x0"] == "constant"
    roles = {p.shape.text: p.shape.role for p in mobjects.rtx_tree(expand.at(21)).placed}
    assert roles["102"] == "unknown"
    assert roles["101"] == "unknown"


def test_the_root_of_the_pattern_is_what_the_drawing_is_about(expand):
    scene = mobjects.rtx_tree(expand.at(21))
    focus = [p.shape for p in scene.placed if p.shape.role == "focus"]
    assert [f.text for f in focus] == ["set"]


def test_a_recognised_insn_names_the_pattern_that_claimed_it(expand):
    assert "matched by aarch64_bcond" in mobjects.rtx_tree(expand.at(16)).caption


def test_an_entry_with_no_pattern_draws_nothing_and_says_why(expand):
    note = next(i for i in expand if i.code == "note")
    scene = mobjects.rtx_tree(note)
    assert scene.placed == []
    assert "It is a marker in the chain, not an instruction." in scene.caption


def test_a_tree_node_without_an_id_cannot_be_linked_to():
    with pytest.raises(ValueError, match="reg:SI 103"):
        mobjects.tree(Node("set", id="a", children=(Node("reg:SI 103"),)))


def test_every_mobject_draws(fn, graph, ladder, passes_text, recorded):
    """A scene that will not render is a bug in the layout and not in the renderer, and it
    is worth finding here rather than the first time a lesson tries to use one."""
    phi = next(p for b in fn.ordered_blocks for p in b.phis)
    scenes = [
        mobjects.pass_tape(tape.cells(passes.parse(passes_text))),
        mobjects.ir_ladder(ladder, 6),
        mobjects.ssa_web(fn, "s_9"),
        mobjects.phi_node(fn, phi),
        mobjects.cfg_view(graph),
        mobjects.dom_tree(graph),
        mobjects.tree(Node("set", id="a", children=(Node("reg:SI 103", id="b"),))),
        mobjects.rtx_tree(rtl.parse(recorded["dumps"]["rtl-expand"]).only().at(21)),
    ]
    for scene in scenes:
        assert ET.fromstring(svg.document(scene)) is not None


def test_the_same_input_draws_the_same_picture(fn):
    """Deterministic, because a diagram that changes without the compiler changing makes
    every rebuild a diff nobody can read."""
    assert svg.document(mobjects.ssa_web(fn, "s_9")) == svg.document(mobjects.ssa_web(fn, "s_9"))


def test_the_first_cell_with_a_dump_is_still_drawn_as_unknown():
    """It has a dump and there is nothing in front of it to compare against, so it is one
    cell short of the count of cells with no dump at all. Drawing it as unchanged would be
    the tape claiming the very first pass it can see did nothing."""
    stats = {"statements": 11, "blocks": 4, "names": 8}
    cells = [
        tape.Cell(0, "tree-cfg", "cfg", "tree", 1, "tree-cfg"),
        tape.Cell(1, "tree-ssa", "ssa", "tree", 1, "tree-ssa", changed=None, stats=stats),
        tape.Cell(2, "tree-ccp1", "ccp1", "tree", 2, "tree-ccp1", changed=False, stats=stats),
    ]
    scene = mobjects.pass_tape(cells)
    assert [p.shape.role for p in scene.placed] == ["unknown", "unknown", "neutral"]
    assert "2 of the 3 have nothing to compare against" in scene.caption
