"""Source locations, and the ladder built out of them.

Every parser test here runs against text a real `gcc-16` produced. The four levels each
spell a location differently and each of them has an awkward case, so text invented to make
a regular expression pass would prove nothing at all.
"""

from __future__ import annotations

import pytest

from gxray import corpus_store, locs
from gxray.dumps import split_spec
from gxray.programs import L1

# Real lines, copied out of a build of corpora/programs/l1.c at -O2 -g.
TREE = """
;; Function f (f, funcdef_no=0, decl_uid=4594, cgraph_uid=1, symbol_order=0)

int f (int n)
{
  int i;
  int s;

  <bb 2> [local count: 118111600]:
  [l1.c:5:3] # DEBUG BEGIN_STMT
  [l1.c:6:21 discrim 2] if (n_3(D) > 0)
    goto <bb 3>; [89.00%]

  <bb 3> [local count: 955630224]:
  # s_9 = PHI <s_5(3), [l1.c:5:7] 0(2)>
  [l1.c:7:7] s_5 = s_9 + i_11;
  [l1.c:6:27 discrim 1] i_6 = i_11 + 1;

}
"""

RTL = """(note 1 0 7 NOTE_INSN_DELETED)
(insn 2 7 3 2 (set (reg/v:SI 103 [ n ])
        (reg:SI 0 x0 [ n ])) "l1.c":4:1 -1
     (nil))
(debug_insn 9 3 10 2 (debug_marker) "l1.c":5:3 -1
     (nil))
(insn 15 14 16 2 (set (reg:CC 66 cc)
        (compare:CC (reg/v:SI 103 [ n ])
            (const_int 0 [0]))) "l1.c":6:21 discrim 2 -1
     (nil))
"""

ASM = """\t.file 1 "l1.c"
_f:
\t.loc 1 6 21 discriminator 2
\tcmp\tw0, 0
\tble\tL4
\t.loc 1 7 7 is_stmt 0
\tadd\tw0, w0, w1
"""

# The real program, not a copy of it, so a rung's source line is the line a reader sees.
SOURCE = L1


# The locations themselves


def test_a_tree_location_has_a_file_a_line_and_a_column():
    (loc,) = locs.locs_in("[l1.c:7:7] s_5 = s_9 + i_11;")
    assert (loc.file, loc.line, loc.col, loc.discrim) == ("l1.c", 7, 7, 0)


def test_a_discriminator_is_kept():
    """Dropping it merges the loop increment into the loop test, and telling those two
    apart is most of what a reader is trying to do in a `for` header."""
    (loc,) = locs.locs_in("[l1.c:6:27 discrim 1] i_6 = i_11 + 1;")
    assert loc.discrim == 1
    assert loc != locs.Loc(line=6, col=27, file="l1.c")


def test_two_locations_on_one_line_come_back_in_order():
    found = locs.locs_in("# s_9 = PHI <s_5(3), [l1.c:5:7] 0(2)>, [l1.c:9:1] x")
    assert [loc.line for loc in found] == [5, 9]


def test_a_block_header_is_not_a_location():
    """`[local count: 118111600]` is in square brackets and has a colon in it."""
    assert locs.locs_in("  <bb 2> [local count: 118111600]:") == []
    assert locs.locs_in("    goto <bb 3>; [INV]") == []


def test_an_rtl_location_is_quoted_instead():
    (loc,) = locs.locs_in('(insn 2 7 3 2 (set (pc)) "l1.c":4:1 -1', "rtl")
    assert (loc.file, loc.line, loc.col) == ("l1.c", 4, 1)


def test_a_location_prints_the_way_gcc_talks_about_it():
    assert str(locs.Loc(line=6, col=27, discrim=1, file="l1.c")) == "l1.c:6:27 discrim 1"
    assert str(locs.Loc(line=6, col=27)) == "6:27"


def test_taking_the_leading_location_keeps_the_indentation():
    """The GIMPLE parser reads indentation. A declaration is a line indented by two."""
    loc, rest = locs.take_loc("  [l1.c:7:7] s_5 = s_9 + i_11;")
    assert loc.line == 7
    assert rest == "  s_5 = s_9 + i_11;"


def test_taking_a_location_off_a_line_that_has_none_changes_nothing():
    loc, rest = locs.take_loc("  s_5 = s_9 + i_11;")
    assert loc is None
    assert rest == "  s_5 = s_9 + i_11;"


def test_stripping_closes_the_gap_a_middle_location_leaves():
    """`if ([l1.c:6:21] i < n)` must not come back as `if ( i < n)`."""
    assert locs.strip_locs("[l1.c:6:21] if ([l1.c:6:21] i < n)") == "if (i < n)"


def test_stripping_rtl_keeps_the_indentation_because_it_is_the_nesting():
    text = '(insn 2 7 3 2 (set (reg:SI 1)\n        (const_int 0)) "l1.c":4:1 -1'
    assert (
        locs.strip_locs(text, "rtl") == "(insn 2 7 3 2 (set (reg:SI 1)\n        (const_int 0)) -1"
    )


# The levels


def test_tree_items_are_the_lines_that_have_a_location():
    items = locs.tree_items(TREE, "gimple")
    assert [i.loc.line for i in items] == [5, 6, 5, 7, 6]
    assert items[1].text == "if (n_3(D) > 0)"


def test_a_debug_marker_is_marked_as_one():
    items = locs.tree_items(TREE, "gimple")
    assert [i.debug for i in items] == [True, False, False, False, False]


def test_a_phi_lands_on_the_first_location_its_arguments_carry():
    """It has no location of its own, since each incoming value came from somewhere else."""
    items = locs.tree_items(TREE, "gimple")
    phi = [i for i in items if "PHI" in i.text]
    assert phi and phi[0].loc.line == 5


def test_rtl_insns_are_split_on_the_first_column():
    insns = locs.rtl_insns(RTL)
    assert len(insns) == 4
    assert insns[1].startswith("(insn 2 7 3 2")
    assert insns[1].endswith("(nil))")


def test_a_note_carries_no_location_and_is_dropped():
    items = locs.rtl_items(RTL)
    assert all("NOTE_INSN_DELETED" not in i.text for i in items)
    assert [i.loc.line for i in items] == [4, 5, 6]


def test_a_debug_insn_is_kept_but_marked():
    items = locs.rtl_items(RTL)
    assert [i.debug for i in items] == [False, True, False]


def test_an_asm_loc_opens_a_run_rather_than_labelling_one_instruction():
    items = locs.asm_items(ASM)
    assert [(i.text.split()[0], i.loc.line) for i in items] == [
        ("cmp", 6),
        ("ble", 6),
        ("add", 7),
    ]


def test_asm_directives_and_labels_are_not_instructions():
    assert all(not i.text.startswith((".", "_")) for i in locs.asm_items(ASM))


def test_the_asm_file_number_is_resolved_through_the_file_directive():
    assert {i.loc.file for i in locs.asm_items(ASM)} == {"l1.c"}


def test_an_absolute_path_in_a_file_directive_is_cut_down_to_the_name():
    """GCC writes the full path when the source was not in the working directory, and the
    tree dumps write the bare name, so the two ends have to be made to agree."""
    text = '\t.file 1 "/tmp/whatever/l1.c"\n\t.loc 1 7 7\n\tret\n'
    (item,) = locs.asm_items(text)
    assert item.loc.file == "l1.c"


# The ladder


def test_a_ladder_has_one_rung_per_source_line_with_anything_on_it():
    lad = locs.ladder(SOURCE, gimple=TREE, rtl=RTL, asm=ASM)
    assert lad.lines == [4, 5, 6, 7]
    assert lad.file == "l1.c"


def test_a_rung_carries_its_own_source_line():
    lad = locs.ladder(SOURCE, gimple=TREE)
    assert lad.rung(7).source.strip() == "s += i;"


def test_debug_items_are_left_out_by_default():
    """There are more of them than there is code, and what they are for is building the
    line table this module is reading, so a ladder full of them is a picture of itself."""
    plain = locs.ladder(SOURCE, gimple=TREE, rtl=RTL)
    noisy = locs.ladder(SOURCE, gimple=TREE, rtl=RTL, debug=True)
    assert [i.text for i in plain.rung(5).at("rtl")] == []
    assert [i.debug for i in noisy.rung(5).at("rtl")] == [True]


def test_a_rung_says_which_levels_left_nothing_behind():
    lad = locs.ladder(SOURCE, gimple=TREE, rtl=RTL, asm=ASM)
    assert lad.rung(4).empty_levels == ["generic", "gimple", "asm"]
    assert lad.rung(6).empty_levels == ["generic"]
    assert lad.rung(7).empty_levels == ["generic", "rtl"]


def test_asking_for_a_line_with_nothing_on_it_says_which_lines_have_something():
    lad = locs.ladder(SOURCE, gimple=TREE)
    with pytest.raises(KeyError) as exc:
        lad.rung(99)
    assert "5, 6, 7" in str(exc.value)


def test_an_empty_build_gives_an_empty_ladder():
    lad = locs.ladder(SOURCE)
    assert lad.rungs == []
    assert "0 source line" in str(lad)


# The dump spec, which is what gets a dump recorded with locations in the first place


def test_a_dump_modifier_belongs_on_the_flag_and_not_in_the_key():
    assert split_spec("tree-ssa-lineno") == ("tree-ssa", ("lineno",))
    assert split_spec("tree-optimized-lineno-details") == ("tree-optimized", ("lineno", "details"))


def test_a_dump_with_no_modifier_is_left_alone():
    assert split_spec("tree-ssa") == ("tree-ssa", ())
    assert split_spec("rtl-expand") == ("rtl-expand", ())


def test_a_dump_actually_named_all_is_not_mistaken_for_a_modifier():
    assert split_spec("tree-all") == ("tree-all", ())
    assert split_spec("tree-all-lineno") == ("tree-all", ("lineno",))


# The recorded corpus, which is the one that has to keep working


def test_the_recorded_corpus_carries_all_four_levels():
    """If this fails the corpus was recorded without -g or without the lineno modifier,
    and the ladder in every lesson quietly loses half its rungs."""
    record = corpus_store.load("l1-O2")
    assert {"tree-original", "tree-optimized", "rtl-expand"} <= set(record.dump_texts)
    assert record.asm
    assert "-g" in record.args


def test_the_recorded_corpus_builds_a_ladder_with_all_four_levels_on_it():
    record = corpus_store.load("l1-O2")
    lad = locs.ladder(
        record.source,
        generic=record.dump_texts["tree-original"],
        gimple=record.dump_texts["tree-optimized"],
        rtl=record.dump_texts["rtl-expand"],
        asm=record.asm,
        function="f",
    )
    assert lad.file == "l1.c"
    assert all(any(r.at(level) for r in lad.rungs) for level in locs.LEVELS)


def test_the_loop_header_is_the_busiest_line_in_l1():
    """One line of C, and it is most of the function at every level. That is the whole
    reason the ladder is worth drawing."""
    record = corpus_store.load("l1-O2")
    lad = locs.ladder(
        record.source,
        generic=record.dump_texts["tree-original"],
        gimple=record.dump_texts["tree-optimized"],
        rtl=record.dump_texts["rtl-expand"],
        asm=record.asm,
        function="f",
    )
    busiest = max(lad.rungs, key=lambda r: sum(r.counts().values()))
    assert busiest.source.strip().startswith("for (")
