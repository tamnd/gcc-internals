"""The control flow graph, out of GCC's own graph dump.

Everything here runs against dot files a real `gcc-16` wrote. The whole point of reading the
graph dump rather than the text dump is that the text dump is missing edges, so a test
written against text somebody made up would miss the same ones.
"""

from __future__ import annotations

import pytest

from gxray import cfg


@pytest.fixture
def loops(loops_graph):
    return cfg.parse(loops_graph)["g"]


@pytest.fixture
def jumper(setjmp_graph):
    return cfg.parse(setjmp_graph)["k"]


# What the dump says


def test_the_graph_has_the_fallthrough_edges_the_text_dump_does_not(loops):
    """This is the reason this module exists.

    Block 10 ends with no `goto` at all, so a graph built by reading gotos out of the text
    dump has nothing leaving it. GCC's own edge list says it falls through to block 11, and
    block 11 is the loop header, so getting this wrong loses the loop.
    """
    (edge,) = loops.successors(10)
    assert (edge.dst, edge.kind, edge.fallthrough) == (11, "fallthrough", True)


def test_the_invisible_entry_to_exit_edge_is_not_an_edge(loops):
    """GCC adds it so graphviz stacks the graph nicely. Nothing goes that way at runtime."""
    assert not [e for e in loops.edges if e.src == cfg.ENTRY and e.dst == cfg.EXIT]


def test_every_edge_names_a_block_the_dump_declared(loops, jumper):
    assert loops.check() == []
    assert jumper.check() == []


def test_the_kind_comes_back_from_the_style_gcc_chose():
    """The mapping in `graph.cc`, read backwards. The order matters: red is applied last
    there and overwrites the colour whatever kind had already set it."""
    assert cfg.edge_kind({"color": "forestgreen"}) == "true"
    assert cfg.edge_kind({"color": "darkorange"}) == "false"
    assert cfg.edge_kind({"color": "blue", "style": '"dotted,bold"'}) == "back"
    assert cfg.edge_kind({"color": "green", "style": "dotted", "weight": "0"}) == "fake"
    assert cfg.edge_kind({"color": "red", "style": '"dotted,bold"'}) == "abnormal"
    assert cfg.edge_kind({"color": "black", "weight": "100"}) == "fallthrough"


def test_a_real_fallthrough_is_told_apart_from_a_plain_edge(loops):
    """Both are a plain black line, and the weight is the only thing separating them.

    Block 12 returns, so the edge to EXIT is not a fallthrough even though it is the only
    way out. Block 5 really does fall into block 10.
    """
    (to_exit,) = loops.successors(12)
    (from_five,) = loops.successors(5)
    assert to_exit.kind == "fallthrough" and not to_exit.fallthrough
    assert from_five.kind == "fallthrough" and from_five.fallthrough


def test_an_abnormal_back_edge_keeps_both_facts(jumper):
    """The setjmp receiver. Red paint hides that it is a back edge, so `back` carries it."""
    (edge,) = [e for e in jumper.edges if e.kind == "abnormal" and e.back]
    assert (edge.src, edge.dst) == (3, 2)
    assert "abnormal and a back edge" in str(edge)


def test_the_back_edges_include_the_ones_drawn_as_something_else(jumper, loops):
    assert [(e.src, e.dst) for e in jumper.back_edges] == [(3, 2)]
    assert [(e.src, e.dst) for e in loops.back_edges] == [(8, 8), (9, 11)]


def test_a_probability_comes_through_as_a_fraction(loops):
    edges = {(e.src, e.dst): e.prob for e in loops.edges}
    assert edges[(2, 3)] == 0.75
    assert edges[(2, 5)] == 0.25


# Blocks


def test_a_statement_survives_the_dot_escaping(loops):
    """Everything dot would read as structure is escaped, so a PHI is mostly backslashes."""
    assert "# t_8 = PHI <20(2), 10(4), 70(3)>" in loops.blocks[5].lines


def test_entry_and_exit_are_blocks_with_no_statements_in_them(loops):
    assert loops.blocks[cfg.ENTRY].entry and loops.blocks[cfg.ENTRY].name == "ENTRY"
    assert loops.blocks[cfg.EXIT].exit and loops.blocks[cfg.EXIT].lines == ()


def test_a_profile_count_is_read_off_the_header(loops):
    assert loops.blocks[2].count == 14598063
    assert loops.blocks[cfg.ENTRY].count is None


def test_a_debug_marker_is_not_code_even_behind_its_own_location():
    """A dump built with both `-g` and `-lineno` prints the location first, and a marker
    hiding behind one is still a marker."""
    block = cfg.Block(
        index=2,
        lines=("[l1.c:5:3] # DEBUG BEGIN_STMT;", "# DEBUG i => 0;", "[l1.c:5:7] s_3 = 0;"),
    )
    assert block.code == ("[l1.c:5:7] s_3 = 0;",)
    assert "1 statement" in str(block)


def test_the_blocks_come_back_with_entry_first_and_exit_last(loops):
    order = loops.indices
    assert order[0] == cfg.ENTRY
    assert order[-1] == cfg.EXIT
    assert order[1:-1] == sorted(order[1:-1])


# Loops


def test_the_loop_tree_comes_out_of_the_nested_clusters(loops):
    """Two loops, and the inner one is a cluster inside the outer one's cluster."""
    assert loops.loops == {1: [7, 9, 11], 2: [8]}
    assert loops.blocks[8].depth == 2
    assert loops.blocks[7].depth == 1
    assert loops.blocks[2].loop is None


# Dominators


def test_the_dominator_tree_is_the_one_the_definition_gives(loops):
    """Every path to a block goes through its immediate dominator and nothing nearer.

    Block 10 is dominated by block 2 and not by block 5 or block 6, because control reaches
    it from both, and that is the fact the whole tree is built to answer.
    """
    idom = loops.dominators()
    assert idom[10] == 2
    assert idom[3] == 2
    assert idom[4] == 3
    assert cfg.ENTRY not in idom


def test_a_block_in_a_loop_is_dominated_by_the_header(loops):
    idom = loops.dominators()
    assert idom[8] == 7
    assert idom[7] == 11


def test_depth_counts_the_steps_back_up_to_entry(loops):
    assert loops.depth_of(cfg.ENTRY) == 0
    assert loops.depth_of(2) == 1
    assert loops.depth_of(3) == 2


def test_reverse_postorder_is_the_same_on_every_run(loops):
    assert loops.reverse_postorder() == loops.reverse_postorder()
    assert loops.reverse_postorder()[0] == cfg.ENTRY


def test_an_unreachable_block_gets_no_dominator_rather_than_a_tidy_one():
    """Nothing dominates a block ENTRY cannot reach, and inventing a parent to make the
    tree connected would be a lie about the graph."""
    graph = cfg.CFG(
        function="f",
        blocks={0: cfg.Block(0), 1: cfg.Block(1), 2: cfg.Block(2), 9: cfg.Block(9)},
        edges=(cfg.Edge(0, 2), cfg.Edge(2, 1), cfg.Edge(9, 1)),
    )
    assert 9 not in graph.dominators()
    assert graph.dominators() == {2: 0, 1: 2}


# The file


def test_two_functions_in_one_file_stay_apart(loops_graph, setjmp_graph):
    """GCC appends every function to the same dot file, so one file can hold several."""
    both = cfg.parse(loops_graph + setjmp_graph)
    assert sorted(both) == ["g", "k"]
    assert len(both["g"].blocks) == 13
    assert len(both["k"].blocks) == 7


def test_handing_the_dot_parser_a_text_dump_says_so(ssa_dump):
    """An empty graph and no complaint is a much worse thing to debug than a sentence."""
    with pytest.raises(ValueError, match="not a graph dump"):
        cfg.parse(ssa_dump)


def test_the_summary_says_what_is_in_it(loops):
    assert str(loops) == "g (13 blocks, 19 edges, 2 loops)"
