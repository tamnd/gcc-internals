"""The facts T09 is built on, so that re-recording the corpus cannot quietly rewrite it.

The lesson makes one claim over and over in different words: everything about the last mile
is printed, and you can join it up. The uid in the annotation is the uid in the RTL dump. The
pattern name in the annotation is a pattern in the machine description. The number after the
slash is a row of that pattern's table. If any of those joins breaks, most of the lesson is
still true looking and completely wrong, so each one is a test here.

`t09-final` and `t09-sections` are Compiler Explorer at GCC 16.1.0 for aarch64 Linux.
`t09-local` is the local compiler, 16.2.0 for aarch64 Darwin. The machine description extract
is `corpora/mdesc/aarch64.json`, taken from the pinned checkout at `releases/gcc-16.2.0`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from conftest import grader

from gxmanim import mobjects, svg
from gxray import asm, corpus_store, mdesc, rtl
from gxray.driver import CE_FILTERS, CE_RAW, CEBackend
from gxwidgets.asmlisting import AsmListing, chosen, reading, shown

LESSON = "t09-the-last-mile"

#: The three recordings, and what each one is for. `t09-final` is the lesson's main exhibit,
#: `t09-sections` adds nine variables so there is something to put in a section, and
#: `t09-local` is the same program through a different target so the packaging can be
#: compared against the instructions.
ENTRIES = ("t09-final", "t09-sections", "t09-local")

#: What each recording is made of. The instruction count is the same three times and nothing
#: else is, which is the whole of the packaging argument in one table.
COUNTS = {
    "t09-final": {"total": 46, "instruction": 12, "directive": 14, "label": 5, "comment": 14},
    "t09-sections": {"total": 99, "instruction": 12, "directive": 60, "label": 14, "comment": 12},
    "t09-local": {"total": 56, "instruction": 12, "directive": 33, "label": 11, "comment": 0},
}

#: Which patterns emitted the twelve instructions of `t09-final`, and how many each.
USES = {
    "*movsi_aarch64": 4,
    "cmpsi": 2,
    "aarch64_bcond": 2,
    "*addsi3_aarch64": 2,
    "*do_return": 2,
}


def load(entry: str) -> asm.Listing:
    return asm.parse(corpus_store.load(entry).asm, entry)


@pytest.fixture
def final() -> asm.Listing:
    return load("t09-final")


@pytest.fixture
def sections() -> asm.Listing:
    return load("t09-sections")


@pytest.fixture
def local() -> asm.Listing:
    return load("t09-local")


@pytest.fixture
def machine() -> dict:
    return mdesc.load_extract("aarch64")


# The counting argument


@pytest.mark.parametrize("entry", ENTRIES)
def test_the_file_is_mostly_not_instructions(entry):
    """The number the lesson opens on. Twelve instructions in forty six lines is the reason
    the widget defaults to showing everything rather than to the filtered view."""
    counts = load(entry).counts()
    for kind, want in COUNTS[entry].items():
        assert counts[kind] == want, kind
    assert counts["instruction"] < counts["total"] / 3


def test_the_same_twelve_instructions_come_in_different_packaging(final, local):
    """Two targets, one architecture, one program. If the instructions ever stop matching
    then the two recordings have drifted apart and the comparison in the lesson is comparing
    the compilers rather than the packaging."""

    def code(listing):
        return [(x.name, x.args.lstrip(".")) for x in listing.instructions]

    assert code(final) == code(local)
    assert final.counts()["total"] != local.counts()["total"]
    assert final.mark == "//"
    assert local.mark == ";"


# The joins


def test_every_annotated_line_names_an_insn_that_is_in_the_rtl_dump(final):
    """The uid join. This is the one that makes the lesson checkable rather than a story,
    because it is what lets a reader start at a line of assembly and walk backwards."""
    record = corpus_store.load("t09-final")
    insns = rtl.parse(record.dump_texts["rtl-final"], "t09-final").only()
    uids = {x.uid for x in insns.code}
    assert len(insns) == 31
    assert len(insns.code) == 16
    for line in final.insns:
        assert line.uid in uids
        assert insns.at(line.uid).name == line.pattern


def test_four_insns_emit_nothing_at_all(final):
    """Sixteen code insns and twelve lines. The four that print nothing are `use` insns,
    which exist to tell earlier passes a register is live and have no instruction to their
    name. A reader who counts annotations is counting insns, not instructions."""
    record = corpus_store.load("t09-final")
    insns = rtl.parse(record.dump_texts["rtl-final"], "t09-final").only()
    silent = [x for x in insns.code if final.by_uid(x.uid) is None]
    assert [x.uid for x in silent] == [23, 52, 59, 61]
    assert all(x.icode == -1 for x in silent)


def test_every_pattern_the_recordings_name_is_in_the_committed_extract(machine):
    """A reader in Colab has no GCC tree, so the ten patterns the lesson needs travel with
    the repository. A recording that names an eleventh needs `record.py` run again."""
    named = set()
    for entry in ENTRIES:
        named |= set(load(entry).patterns())
    assert named <= set(machine["patterns"])
    assert machine["tag"] == "releases/gcc-16.2.0"


def test_five_patterns_emitted_the_twelve_instructions(final):
    """Twelve instructions from five patterns, and `mov` on its own is a third of them."""
    assert {name: len(uses) for name, uses in final.patterns().items()} == USES
    assert sum(USES.values()) == 12


# The slash rule


def test_the_slash_is_printed_exactly_when_there_is_a_row_to_number(machine):
    """`output_asm_name` tests `n_alternatives > 1` and nothing else, so this holds over
    every annotated instruction in every recording or the reader's rule is wrong."""
    checked = 0
    for entry in ENTRIES:
        for name, uses in load(entry).patterns().items():
            rows = len(machine["patterns"][name]["alternatives"])
            for line in uses:
                assert (line.alternative is not None) == (rows > 1), f"{entry} {name}"
                checked += 1
    assert checked == 36


def test_the_two_movs_used_two_different_rows_of_one_table(final, machine):
    """The point of the alternatives section. One pattern, twenty one rows, and the operands
    decide which. `mov w0, w1` is row 1 and `mov w0, 0` is row 3, and the rows differ in one
    constraint letter."""
    mov = machine["patterns"]["*movsi_aarch64"]
    assert len(mov["alternatives"]) == 21
    assert [x.alternative for x in final.patterns()["*movsi_aarch64"]] == [1, 3, 3, 3]
    assert mov["alternatives"][1]["cons"] == ["r k", "r"]
    assert mov["alternatives"][3]["cons"] == ["r", "M"]


def test_the_add_pattern_is_written_with_an_iterator_and_found_by_the_expanded_name(machine):
    """`-dp` prints `*addsi3_aarch64` and the file says `*add<mode>3_aarch64`. Searching the
    machine description for what the annotation printed finds nothing, which is the single
    most common way to get stuck in this lesson."""
    add = machine["patterns"]["*addsi3_aarch64"]
    assert add["written"] == "*add<mode>3_aarch64"
    assert add["citation"] == "gcc/config/aarch64/aarch64.md:2694@releases/gcc-16.2.0"
    assert len(add["alternatives"]) == 8
    assert add["alternatives"][0]["template"] == "add\\t%w0, %w1, %2"
    assert add["alternatives"][0]["written"] == "add\\t%<w>0, %<w>1, %2"


# Sections and alignment


def test_nine_names_land_in_five_different_sections(sections):
    """Nothing in the C says which section anything goes in. It is worked out from whether
    there is an initialiser, whether it is all zero, and whether it needs a relocation."""
    where = {name: sym.section for name, sym in sections.symbols.items()}
    assert where == {
        "sum": ".text",
        "letter": ".text",
        "counter": ".data",
        "total": ".bss",
        "pending": ".bss",
        "wide": ".bss",
        "limit": ".rodata",
        "tag": ".rodata",
        "message": ".data.rel.local",
    }
    assert len(set(where.values())) == 5
    assert len(sections.sections) == 8


def test_an_uninitialised_variable_and_a_zero_initialised_one_are_the_same_thing(sections):
    """`int total = 0;` and `int pending;` produce byte for byte the same assembly, because
    `bss_initializer_p` is true for both. It is the clearest thing in the section rules."""
    total, pending = sections.symbols["total"], sections.symbols["pending"]
    assert total.section == pending.section == ".bss"
    assert total.size == pending.size == 4
    assert total.exported and pending.exported


def test_a_local_variable_is_the_one_symbol_with_no_globl(sections):
    """`static const int tag` is the only name in the program with internal linkage, and the
    only difference in the assembly is a missing `.globl`."""
    local_names = [name for name, sym in sections.symbols.items() if not sym.exported]
    assert local_names == ["tag"]
    assert sections.symbols["tag"].section == ".rodata"


def test_asking_for_sixty_four_byte_alignment_is_one_directive(sections):
    """`aligned (64)` on a four byte int. The variable is still four bytes and the section it
    sits in is aligned to two to the sixth, which is the whole of the change."""
    assert sections.symbols["wide"].size == 4
    aligns = [
        x.args
        for x in sections.sections[".bss"].lines
        if x.kind == "directive" and x.name == ".align"
    ]
    assert "6" in aligns


# The widget


def test_the_widget_opens_on_an_instruction_rather_than_the_first_line(final, machine):
    """The first line of the file is a directive and nobody arrives wanting to read about
    `.arch`. The default selection is the first line that has an annotation on it."""
    widget = AsmListing(final, machine)
    assert widget.selected == str(final.insns[0].number)
    assert final.by_uid(final.insns[0].uid).annotated


def test_the_widget_reports_the_same_numbers_the_lesson_prints(final, machine):
    """The lesson prints `data()` next to the rendered widget, so that the cell proves
    something in a reader whose front end does not render HTML."""
    facts = AsmListing(final, machine).data()
    assert facts["counts"]["total"] == 46
    assert facts["patterns"] == USES
    assert facts["tag"] == "releases/gcc-16.2.0"
    assert len(facts["sections"]) == 3


def test_the_widget_reads_without_javascript(final, machine):
    """Every line and every panel is in the HTML. The filters and the selection are the only
    things script does, and a reader with none still gets the whole file."""
    body = AsmListing(final, machine).render()
    for line in final.lines:
        if line.kind != "blank":
            assert shown(line).split()[0] in body
    assert "gcc/config/aarch64/aarch64.md:2694" in body


def test_the_panel_says_which_row_and_why(final, machine):
    """The sentence a reader gets when they click an instruction. It has to name the pattern
    as the file writes it, the citation, and the row, or it is not doing anything the
    annotation did not already do."""
    line = final.patterns()["*addsi3_aarch64"][0]
    pattern = machine["patterns"][line.pattern]
    said = reading(line, pattern, chosen(pattern, line))
    assert "*add<mode>3_aarch64" in said
    assert "aarch64.md:2694" in said
    assert "row 1 of 8" in said


def test_a_pattern_that_picks_its_text_in_c_says_so_rather_than_inventing_a_row(final, machine):
    """`*do_return` has no table, so there is nothing to number and the panel has to explain
    the missing slash instead of quietly showing row zero."""
    line = final.patterns()["*do_return"][0]
    pattern = machine["patterns"]["*do_return"]
    assert chosen(pattern, line) is None
    assert "in C rather than" in reading(line, pattern, None)


def test_a_pattern_the_extract_does_not_have_is_an_honest_gap(final):
    """The extract holds ten patterns and GCC has thousands. A recording naming an eleventh
    should say the extract is short, not pretend the pattern does not exist."""
    line = final.insns[0]
    widget = AsmListing(final, {"patterns": {}, "tag": "releases/gcc-16.2.0"})
    assert widget.pattern(line) is None
    assert "not in the committed extract" in reading(line, None, None)


# The pictures


def test_both_stills_draw(final, machine):
    """A scene that will not render is a layout bug, and it is worth catching here rather
    than the first time somebody opens the notebook."""
    tape = mobjects.asm_tape(final)
    path = mobjects.emit_path(final.by_uid(12), machine["patterns"]["*addsi3_aarch64"])
    for scene in (tape, path):
        assert scene.check() == []
        assert ET.fromstring(svg.document(scene)) is not None
        assert scene.describe()


def test_the_tape_has_one_cell_per_line_and_marks_the_instructions(final):
    """The counting argument as a picture. The marked cells are the instructions and there
    are twelve of them, the same twelve the text cell counted."""
    scene = mobjects.asm_tape(final)
    cells = [p.shape for p in scene.placed]
    assert len(cells) == len(final)
    assert len([c for c in cells if c.changed]) == 12
    assert "12 of them instructions" in scene.title


def test_every_cell_of_the_tape_says_in_words_what_its_colour_says(final):
    """Colour is never the only carrier. A directive cell has to read as a directive with
    the stylesheet turned off."""
    states = {p.shape.state for p in mobjects.asm_tape(final).placed}
    assert "directive" in states
    assert "label" in states
    assert all(state for state in states)


def test_the_emit_path_is_four_steps_when_the_pattern_is_known(final, machine):
    """Insn, pattern, alternative, template, text. The middle two are the ones that need the
    machine description, and they are the ones the lesson exists to show."""
    scene = mobjects.emit_path(final.by_uid(12), machine["patterns"]["*addsi3_aarch64"])
    ids = [p.shape.id for p in scene.placed]
    assert ids == ["insn", "pattern", "alternative", "template", "text"]
    assert "aarch64.md:2694" in scene.caption


def test_the_emit_path_drops_a_step_rather_than_guessing_it(final):
    """Without the extract the middle of the chain is unknowable, so the picture is three
    cards instead of five and says where the missing ones would have come from."""
    scene = mobjects.emit_path(final.by_uid(12), None)
    assert [p.shape.id for p in scene.placed] == ["insn", "pattern", "text"]
    assert "the machine description" in scene.caption


def test_a_line_with_no_annotation_has_no_path_to_draw(final):
    """Asking for the chain of a directive is a caller mistake, not something to draw an
    empty box for."""
    directive = final.of("directive")[0]
    with pytest.raises(ValueError, match="no annotation"):
        mobjects.emit_path(directive, None)


# The recordings the lesson needs, and the flag that makes them possible


def test_the_default_filters_would_have_thrown_this_lesson_away():
    """Compiler Explorer hides directives, labels and comments unless asked. The `-dp`
    annotation is a comment, so the default view of a `-dp` compilation shows none of it,
    and every recording this lesson uses had to be taken with `--raw-asm`."""
    assert CE_FILTERS["directives"] and CE_FILTERS["labels"] and CE_FILTERS["commentOnly"]
    assert not CE_RAW["directives"]
    assert not CE_RAW["labels"]
    assert not CE_RAW["commentOnly"]
    assert CE_RAW["intel"] == CE_FILTERS["intel"]


def test_a_backend_with_no_filters_asked_for_gets_the_usual_ones():
    """Passing None is not the same as passing an empty dict. Every caller that does not
    care about filters should get the view Compiler Explorer's own page gives."""
    assert CEBackend("cg162").filters == CE_FILTERS
    assert CEBackend("cg162", filters=CE_RAW).filters == CE_RAW
    assert CEBackend("cg162", filters={}).filters == {}


def test_two_filter_sets_are_two_different_cache_entries():
    """The filtered and the raw view of one compilation are different responses to the same
    source and the same flags. Keying on source and flags alone would serve one for the
    other, and the lesson would silently lose its annotations."""
    from tools.cecache import request_key

    plain = request_key("cg162", "int f;", "-O2 -dp", CE_FILTERS)
    raw = request_key("cg162", "int f;", "-O2 -dp", CE_RAW)
    assert plain != raw


# The boss fight


def test_the_grader_marks_the_answer_the_lesson_leads_you_to():
    """A boss fight nobody has watched pass is a boss fight that might be waving everything
    through, so the right answer is checked here as well as in CI."""
    module = grader(LESSON)
    lines = module.listing()
    assert [module.emitted(lines, q) for q in module.QUESTIONS] == [
        "*movsi_aarch64",
        "*addsi3_aarch64",
        "*do_return",
    ]


def test_the_grader_wants_all_three_answers():
    """Two of three right is not right."""
    module = grader(LESSON)
    right = ["--patterns", "*movsi_aarch64,*addsi3_aarch64,*do_return"]
    assert module.main([*right, "--no-slash", "2", "--rows", "21"]) == 0
    assert module.main([*right, "--no-slash", "3", "--rows", "21"]) == 1
    assert module.main([*right, "--no-slash", "2", "--rows", "8"]) == 1
    wrong = ["--patterns", "*addsi3_aarch64,*movsi_aarch64,*do_return"]
    assert module.main([*wrong, "--no-slash", "2", "--rows", "21"]) == 1


def test_the_grader_cares_what_order_the_patterns_come_in():
    """Unlike T08, where the answer is a set, here each name goes with a line, so the same
    three names in the wrong order is a different and wrong answer."""
    module = grader(LESSON)
    assert module.names("a,b,c") == ["a", "b", "c"]
    assert module.names("c b a") == ["c", "b", "a"]
    assert module.names(" a , b ") == ["a", "b"]
    assert module.names("") == []


def test_the_grader_finds_a_number_in_a_sentence():
    """Somebody is going to type `21 of them` and mean twenty one."""
    module = grader(LESSON)
    assert module.number("21") == 21
    assert module.number("21 of them") == 21
    assert module.number("twenty one") is None
    assert module.number("") is None
