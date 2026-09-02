"""The RTL parser.

Same two jobs as the GIMPLE parser tests. That it reads a real dump correctly, and that it
never throws on one it does not understand, because a parser that throws takes the rest of
the book down with it the day GCC prints an insn one field wider.

The real dumps are the committed corpus rather than a hand written sample, and there are
four of them from four targets, because a reader who only ever tests against one target
writes a parser that only works on one target.
"""

from __future__ import annotations

import pytest

from gxray import corpus_store, rtl

TARGETS = ["t07-x86-64", "t07-aarch64", "t07-riscv64", "t07-power64le"]


@pytest.fixture
def expand() -> rtl.Listing:
    """L1 at the moment it becomes RTL, from the pinned local compiler."""
    return rtl.parse(corpus_store.load("l1-O2").dump_texts["rtl-expand"]).only()


# Reading a dump


def test_reads_the_function_out_of_the_banner(expand):
    assert expand.function == "f"
    assert "funcdef_no=0" in expand.detail


def test_keeps_the_prose_that_comes_before_the_insns(expand):
    """The expander narrates itself, and the narration is where the answer to why two blocks
    are missing lives. It is not parseable and it is not throwaway either."""
    assert "Generating RTL for gimple basic block 2" in expand.preamble
    assert "Merging block 3 into block 2" in expand.preamble
    assert "(insn" not in expand.preamble


def test_most_of_a_dump_is_not_instructions(expand):
    """Forty entries, thirteen of which become machine instructions. A reader who counts
    lines and thinks they counted instructions is off by a factor of three."""
    assert len(expand) == 40
    assert len(expand.code) == 13
    assert len([i for i in expand if i.is_debug]) == 15
    assert len([i for i in expand if i.code == "note"]) == 8
    assert len([i for i in expand if i.code in ("code_label", "barrier")]) == 4


def test_the_blocks_are_the_ones_left_after_the_expander_cleaned_up(expand):
    """Blocks 3 and 8 were merged away by `try_optimize_cfg`, which the preamble says out
    loud, so the numbering has holes in it before any optimization pass has run."""
    assert expand.blocks == [2, 4, 5, 6, 7, 9]


# One insn


def test_reads_the_header_of_an_insn(expand):
    insn = expand.at(21)
    assert (insn.code, insn.uid, insn.prev, insn.next, insn.bb) == ("insn", 21, 20, 22, 5)
    assert insn.loc == "l1.c:7:7"
    assert insn.icode == rtl.UNRECOGNISED
    assert not insn.recognised


def test_reads_the_pattern_as_a_tree(expand):
    """`s += i` at this level. A set of a register to the sum of two registers, which is four
    nodes and three of them are leaves."""
    pattern = expand.at(21).pattern
    assert pattern.code == "set"
    assert pattern.depth == 3
    assert pattern.size == 5
    assert [n.code for n in pattern.walk()] == ["set", "reg", "plus", "reg", "reg"]
    # A `set` carries no mode of its own. It is the only node here that does not, because
    # what it moves is whatever the two sides agreed on, and the sides say so themselves.
    assert pattern.mode == ""
    assert {n.mode for n in pattern.walk() if n is not pattern} == {"SI"}


def test_the_flags_on_a_node_are_kept(expand):
    """`reg/v` is `REG_USERVAR_P`, a register that came from something the user wrote. It is
    the difference between a name a reader recognises and a temporary, and dropping it would
    make two different registers print the same."""
    dest = expand.at(21).sets
    assert dest.flags == ("v",)
    assert dest.head == "reg/v:SI"
    assert expand.at(37).sets.flags == ("i",)


def test_a_register_is_a_number_and_the_name_says_it_is_a_real_one(expand):
    """The whole pseudo register idea in one assertion. 102 printed no name, so it is one of
    the ones the expander invented. 0 printed `x0`, so it is a register the chip has."""
    made_up = expand.at(21).sets
    assert (made_up.register, made_up.pseudo) == (102, True)
    real = expand.at(38).pattern.children[0]
    assert (real.register, real.pseudo) == (0, False)
    assert "x0" in real.leaves


def test_a_constant_reads_as_an_integer(expand):
    assert expand.at(24).pattern.children[1].children[1].value == 1
    assert expand.at(4).pattern.children[1].value == 0


def test_an_insn_that_is_not_a_set_has_no_destination(expand):
    """`(use (reg/i:SI 0 x0))` is not an assignment. It exists to tell later passes the return
    register is live, and asking it what it sets is a question with no answer."""
    use = expand.at(38)
    assert use.pattern.code == "use"
    assert use.sets is None


def test_a_note_carries_no_pattern_and_is_not_code(expand):
    """What a note has instead of a pattern is a kind, and the kind is a word the reader has
    to go and look up. It lands in `extra` because that is where anything the reader cannot
    place goes, next to the `[bb 2]` the printer repeats for people."""
    note = expand.at(7)
    assert note.code == "note"
    assert not note.is_code
    assert note.pattern is None
    assert note.extra == ("[bb 2]", "NOTE_INSN_BASIC_BLOCK")


def test_a_jump_knows_where_it_goes(expand):
    jump = expand.at(16)
    assert jump.code == "jump_insn"
    assert jump.target == 45
    assert jump.name == "aarch64_bcond"
    assert jump.icode == 59
    assert jump.recognised


def test_the_two_recognised_insns_are_the_two_the_preamble_says_it_redirected(expand):
    """Everything the expander emits comes out with `-1` in the pattern slot, because matching
    is a later pass. The two exceptions here are the two jumps `try_optimize_cfg` rewrote, and
    rewriting a jump means checking the result still matches something."""
    assert [i.uid for i in expand if i.recognised] == [16, 42]
    assert "Redirecting jump 42" in expand.preamble
    assert "Edge 2->4 redirected" in expand.preamble


# The chain


def test_the_printed_order_and_the_linked_order_agree(expand):
    """They normally do, and a dump where they do not is worth stopping at. Following `next`
    is the only way to know, because the printed order is just the printed order."""
    assert [i.uid for i in expand.chain()] == [i.uid for i in expand]


def test_the_chain_stops_instead_of_looping_on_a_broken_link():
    """A dump that lost an insn should give a short answer, not hang the notebook."""
    text = "(insn 1 0 2 2 (use (reg:SI 0)) -1 (nil))\n(insn 2 1 1 2 (use (reg:SI 0)) -1 (nil))\n"
    listing = rtl.parse(text).only()
    assert [i.uid for i in listing.chain()] == [1, 2]


def test_counts_the_modes_and_the_codes(expand):
    """What the lesson calls the vocabulary of a function. Nine RTX codes and three modes is
    the whole of it for a four line loop, which is the reassuring number."""
    assert expand.modes() == {"SI": 30, "CC": 6, "DI": 2}
    assert list(expand.codes())[:4] == ["reg", "set", "const_int", "debug_marker"]
    assert expand.codes()["reg"] == 25


def test_sorts_the_registers_into_the_real_ones_and_the_invented_ones(expand):
    pseudo, hard = expand.registers()
    assert pseudo == [101, 102, 103]
    assert hard == [0, 66]


# Four targets


@pytest.mark.parametrize("entry", TARGETS)
def test_every_recorded_target_parses_into_one_function(entry):
    listing = rtl.parse(corpus_store.load(entry).dump_texts["rtl-expand"]).only()
    assert listing.function == "f"
    assert listing.insns
    assert all(i.raw.startswith("(") for i in listing)


def test_a_dump_with_several_functions_keeps_them_apart():
    """The uids restart at 1 in every function, so a parser that concatenates them produces a
    chain that loops. This is the test that caught that."""
    text = "\n".join(
        f";; Function {name} ({name}, funcdef_no={n})\n"
        ";;\n;; Full RTL generated for this function:\n;;\n"
        f"(insn 1 0 2 2 (set (reg:SI 10{n}) (const_int {n})) -1 (nil))\n"
        f"(insn 2 1 0 2 (use (reg:SI 10{n})) -1 (nil))\n"
        for n, name in enumerate(["a", "b", "c"])
    )
    dump = rtl.parse(text, "three")
    assert list(dump.functions) == ["a", "b", "c"]
    assert len(dump) == 3
    assert dump["b"].at(1).pattern.children[1].value == 1
    assert str(dump) == "three: a, b, c"
    with pytest.raises(ValueError, match="expected one function, found 3"):
        dump.only()


# Not throwing


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n\n",
        "not a dump at all",
        "(",
        "()",
        "(insn",
        "(insn 1)",
        "(insn 1 0 2 2",
        "(insn one two three four (nil))",
        '(insn 1 0 2 2 (set (mem:SI (symbol_ref:DI ("x(y)"))) (const_int 0)) "a(b).c":1:1 -1',
        ";; Function f (f)\n",
    ],
)
def test_never_throws(text):
    rtl.parse(text)


def test_an_unfamiliar_field_is_kept_rather_than_dropped():
    """A dump format that shifts should cost one number in one lesson, not the whole book, so
    anything the reader cannot place goes in `extra` and the original text stays in `raw`."""
    text = '(insn 1 0 2 2 (use (reg:SI 0)) "a.c":1:1 -1 SOMETHING_NEW (nil))'
    insn = rtl.parse(text).only().at(1)
    assert insn.extra == ("SOMETHING_NEW",)
    assert insn.raw == text
    assert insn.loc == "a.c:1:1"


def test_a_filename_with_a_bracket_in_it_does_not_split_the_insn():
    """The splitter counts parentheses, and a source path is allowed to contain one."""
    text = '(insn 1 0 2 2 (use (reg:SI 0)) "d(1)/a.c":3:4 -1 (nil))'
    listing = rtl.parse(text).only()
    assert len(listing) == 1
    assert listing.at(1).loc == "d(1)/a.c:3:4"


def test_printing_a_node_puts_it_back_on_one_line(expand):
    """The dump wraps a pattern over four lines and indents it. A widget wants it as one
    string, and a reader comparing two of them side by side wants that even more."""
    assert str(expand) == "f: 40 insns, 13 of them code"
    assert str(expand.at(21).pattern.children[1]) == (
        "(plus:SI (reg/v:SI 102 [ <retval> ]) (reg/v:SI 101 [ i ]))"
    )
    assert str(expand.at(38)) == "(insn 38 37 0 (use (reg/i:SI 0 x0)))"
