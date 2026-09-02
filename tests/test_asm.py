"""The assembly listing reader.

Everything here runs against listings a real compiler wrote, from the three recordings T09
argues from, because a parser checked against text somebody invented is a parser checked
against its own assumptions.

Two of those recordings are the same program on the same architecture, one through Compiler
Explorer on Linux and one from the local compiler on Darwin. That pair is worth having as a
fixture on its own: the instructions are identical and almost nothing else is, so a reader
that quietly assumed ELF would fail on half of it.
"""

from __future__ import annotations

import pytest

from gxray import asm, corpus_store

#: The three recordings T09 reads. Two ELF, one Mach-O, all aarch64.
ENTRIES = ["t09-final", "t09-sections", "t09-local"]


def load(entry: str) -> asm.Listing:
    return asm.parse(corpus_store.load(entry).asm, entry)


@pytest.fixture
def elf():
    return load("t09-final")


@pytest.fixture
def macho():
    return load("t09-local")


@pytest.fixture
def sections():
    return load("t09-sections")


def test_every_line_is_sorted_into_exactly_one_kind(elf):
    kinds = [x.kind for x in elf]
    assert set(kinds) <= set(asm.KINDS)
    assert len(kinds) == len(elf.lines)
    assert sum(elf.counts()[k] for k in asm.KINDS) == elf.counts()["total"]


def test_most_of_a_listing_is_not_instructions(elf):
    """The whole argument of the lesson, as a number. Forty six lines, twelve of them run."""
    c = elf.counts()
    assert c["total"] == 46
    assert c["instruction"] == 12
    assert c["directive"] + c["label"] + c["comment"] + c["blank"] == 34


def test_the_comment_character_is_worked_out_rather_than_assumed(elf, macho):
    """ELF aarch64 says `//` and Mach-O aarch64 says `;`, out of the same GCC."""
    assert elf.mark == "//"
    assert macho.mark == ";"


def test_two_targets_emit_the_same_instructions_in_different_packaging(elf, macho):
    """The last mile is the same on both. Everything wrapped around it is not.

    The operands match too, except that a local label is `.L4` on ELF and `L4` on Mach-O,
    which is an assembler syntax difference rather than a code generation one.
    """
    mine = [(x.name, x.args.lstrip(".")) for x in elf.instructions]
    theirs = [(x.name, x.args.lstrip(".")) for x in macho.instructions]
    assert mine == theirs
    assert [x.uid for x in elf.insns] == [x.uid for x in macho.insns]
    assert [x.slot for x in elf.insns] == [x.slot for x in macho.insns]
    assert elf.counts()["directive"] != macho.counts()["directive"]


def test_an_annotation_gives_up_all_four_of_its_fields(elf):
    add = elf.by_uid(12)
    assert (add.name, add.args) == ("add", "w0, w0, w1")
    assert (add.cost, add.length) == (4, 4)
    assert add.pattern == "*addsi3_aarch64"
    assert add.alternative == 1
    assert add.slot == "*addsi3_aarch64/1"


def test_verbose_asm_puts_a_second_comment_on_the_line_and_is_not_mistaken_for_the_annotation(elf):
    """Compiler Explorer turns `-fverbose-asm` on and will not turn it off, so a line can
    carry two comments, and the annotation is the one at the end."""
    assert elf.by_uid(12).note == "<retval>, <retval>, i"
    assert elf.by_uid(12).pattern == "*addsi3_aarch64"


def test_a_target_without_verbose_asm_leaves_the_note_empty_rather_than_eating_the_annotation(
    macho,
):
    """There is nothing between the operands and the annotation here, and a reader that
    subtracted its way to a slice would take a bite out of the pattern name."""
    add = macho.by_uid(12)
    assert add.note == ""
    assert add.slot == "*addsi3_aarch64/1"


def test_the_slash_only_appears_when_the_pattern_has_something_to_choose_between(elf):
    """`output_asm_name` prints the alternative only when there is more than one, so the
    absence of a slash is a fact about the pattern rather than a gap in the annotation."""
    slots = {x.pattern: x.alternative for x in elf.insns}
    assert slots["*do_return"] is None
    assert slots["aarch64_bcond"] is None
    assert slots["*movsi_aarch64"] is not None


def test_a_section_switching_directive_belongs_to_the_section_it_switches_to(sections):
    """`.bss` reads as the heading of the block under it, and a reader that filed it under
    the previous section would put every section heading in the wrong place."""
    assert [x.section for x in sections if x.name == ".bss"] == [".bss"]
    assert sections.sections[".text"].instructions


def test_elf_section_flags_come_apart_into_letters(sections):
    strings = sections.sections[".rodata.str1.8"]
    assert strings.letters == "aMS"
    assert not strings.writable
    assert sections.sections[".data.rel.local"].writable


def test_mach_o_writes_a_segment_and_a_section_and_is_not_read_as_elf(macho):
    """Both spellings are `.section` and they have to be told apart on sight."""
    assert any("," in name and name.startswith("__") for name in macho.sections)
    assert all(s.letters == "" for s in macho.sections.values())


def test_the_symbols_of_a_listing_say_where_each_one_landed(sections):
    known = sections.symbols
    assert known["counter"].section == ".data"
    assert known["total"].section == ".bss"
    assert known["limit"].section == ".rodata"
    assert known["message"].section == ".data.rel.local"
    assert known["sum"].function and known["sum"].exported
    assert not known["tag"].exported


def test_a_string_constant_with_a_comment_character_in_it_survives():
    """`.ascii "a;b"` is not a comment on Mach-O and `.string "a//b"` is not one on ELF."""
    code, comment = asm.split_comment('\t.ascii\t"a;b"\t; 3', ";")
    assert code.strip() == '.ascii\t"a;b"'
    assert comment.strip() == "3"


def test_an_escaped_quote_does_not_end_the_string():
    code, comment = asm.split_comment('\t.ascii\t"say \\"hi\\"" // done', "//")
    assert code.strip() == '.ascii\t"say \\"hi\\""'
    assert comment.strip() == "done"


def test_a_listing_with_nothing_in_it_is_a_normal_thing_to_be_handed():
    empty = asm.parse("")
    assert len(empty) == 0
    assert empty.counts()["total"] == 0
    assert empty.patterns() == {}


def test_every_pattern_the_corpus_names_is_reported_once_with_all_its_uses(elf):
    used = elf.patterns()
    assert list(used) == [
        "*movsi_aarch64",
        "cmpsi",
        "aarch64_bcond",
        "*addsi3_aarch64",
        "*do_return",
    ]
    assert len(used["*movsi_aarch64"]) == 4
    assert sum(len(v) for v in used.values()) == elf.counts()["annotated"]


@pytest.mark.parametrize("entry", ENTRIES)
def test_every_directive_in_the_corpus_has_a_sentence_about_it(entry):
    """The widget shows one of these for every line a reader can click, so a directive with
    no entry is a blank panel."""
    listing = load(entry)
    for line in listing.of("directive"):
        assert asm.explain(line) != "A directive. It tells the assembler something."


def test_a_directive_nobody_wrote_a_sentence_for_gets_an_honest_answer():
    line = asm.Line(number=1, kind="directive", text="\t.tls_thing", section=".text", name=".tls")
    assert asm.explain(line).startswith("A directive.")


def test_an_instruction_is_left_alone_because_the_annotation_already_answers_it(elf):
    assert asm.explain(elf.by_uid(12)) == ""
    assert asm.explain(elf.of("label")[0]).startswith("A name for this address")
