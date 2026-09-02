"""The machine description reader.

Most of these run against pieces of `gcc/config/aarch64/aarch64.md` copied into the test with
nothing changed, because a parser test written against text somebody invented to make the
parser pass is worth nothing. The pieces are short because the patterns are short.

The ones that read the whole pinned tree are marked `needs_tree` and skip when the submodule
is not checked out. The ones that read the committed extract always run, because the extract
is in the repository and a lesson in Colab reads exactly that file.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gxray import mdesc

ROOT = Path(__file__).resolve().parent.parent
TREE = ROOT / "vendor" / "gcc"
START = "gcc/config/aarch64/aarch64.md"
HAVE_TREE = (TREE / START).is_file()
needs_tree = pytest.mark.skipif(not HAVE_TREE, reason="vendor/gcc is not checked out")

#: A pattern in the compact alternative syntax GCC 16 uses, verbatim. Three rows, and the row
#: index is the number `-dp` prints after the slash.
CMP = r"""
(define_insn "cmp<mode>"
  [(set (reg:CC CC_REGNUM)
	(compare:CC (match_operand:GPI 0 "register_operand")
		    (match_operand:GPI 1 "aarch64_plus_operand")))]
  ""
  {@ [ cons: 0 , 1 ; attrs: type ]
     [ rk      , r ; alus_sreg   ] cmp\t%<w>0, %<w>1
     [ rk      , I ; alus_imm    ] cmp\t%<w>0, %1
     [ rk      , J ; alus_imm    ] cmn\t%<w>0, #%n1
  }
)
"""

#: The older style, where the constraints are in the operands and the template is one string.
#: One alternative, so `-dp` prints no slash for it, and the reader still has to report it.
LOSYM = r"""
(define_insn "add_losym_<mode>"
  [(set (match_operand:P 0 "register_operand" "=r")
	(lo_sum:P (match_operand:P 1 "register_operand" "r")
		  (match_operand 2 "aarch64_valid_symref" "S")))]
  ""
  "add\\t%<w>0, %<w>1, :lo12:%c2"
  [(set_attr "type" "alu_imm")]
)
"""

#: A pattern whose text is C rather than a template. This is the shape that makes the reader
#: need a brace counter instead of a string scanner, because there is a `;` and a `"` in it.
RETURN = r"""
(define_insn "*do_return"
  [(return)]
  ""
  {
    const char *ret = NULL;
    if (aarch64_return_address_signing_enabled ())
      ret = "retaa";
    else
      ret = "ret";
    output_asm_insn (ret, operands);
    return "";
  }
  [(set_attr "type" "branch")]
)
"""

#: The iterators the names above need, as `iterators.md` writes them.
ITERATORS = """
(define_mode_iterator GPI [SI DI])
(define_mode_iterator P [(SI "ptr_mode == SImode") (DI "ptr_mode == DImode")])
(define_mode_attr w [(QI "w") (HI "w") (SI "w") (DI "x")])
"""


def read(*texts: str) -> mdesc.Machine:
    """Parse a few snippets as one description, the way `load` would after an include."""
    return mdesc.parse(textwrap.dedent("\n".join(texts)), "aarch64.md")


@pytest.fixture
def machine():
    return read(ITERATORS, CMP, LOSYM, RETURN)


@pytest.fixture
def extract():
    return mdesc.load_extract("aarch64")


# The tokenizer


def test_a_semicolon_inside_a_c_block_is_not_a_comment(machine):
    """A Lisp reader would stop at the first `;` and lose the rest of the pattern."""
    do_return = machine.get("*do_return")
    assert "output_asm_insn" in do_return.template
    assert do_return.form == "code"


def test_a_quoted_string_inside_a_c_block_does_not_end_the_block(machine):
    assert '"retaa"' in machine.get("*do_return").template


def test_a_pattern_carries_the_line_it_starts_on_so_a_citation_can_be_written(machine):
    """A lesson that says a pattern is at a line and is wrong is worse than one that does
    not say. The line is the only thing here a reader can check by hand."""
    assert machine.get("cmp<mode>").line == 7
    assert machine.get("cmp<mode>").citation == "aarch64.md:7"


# The alternative table


def test_the_compact_table_comes_apart_into_rows_in_the_order_dp_numbers_them(machine):
    cmp = machine.get("cmp<mode>")
    assert cmp.form == "table"
    assert [a.index for a in cmp.alternatives] == [0, 1, 2]
    assert cmp.cons_heads == ("0", "1")
    assert cmp.attr_heads == ("type",)


def test_a_data_row_is_read_by_position_because_only_the_header_is_labelled(machine):
    """The header says `cons:` and `attrs:` and the rows say nothing, so a reader that went
    looking for the labels again would put every attribute in the constraints."""
    second = machine.get("cmp<mode>").alternatives[1]
    assert second.cons == ("rk", "I")
    assert second.attrs == ("alus_imm",)
    assert second.template == r"cmp\t%<w>0, %1"


def test_an_old_style_pattern_still_reports_its_one_alternative(machine):
    """The constraints are in the `match_operand`s here rather than in a table, and the
    lesson asks the same question of it, so the reader has to answer the same way."""
    losym = machine.get("add_losym_<mode>")
    assert losym.form == "string"
    assert len(losym.alternatives) == 1
    assert losym.alternatives[0].cons == ("=r", "r", "S")


def test_the_condition_and_the_template_are_not_the_same_string(machine):
    """Both are quoted strings in a row and the condition here is empty, which is exactly
    the case where a reader that counted strings would read the template as the condition."""
    losym = machine.get("add_losym_<mode>")
    assert losym.condition == ""
    assert losym.template.startswith("add")


# Iterators


def test_a_name_with_an_iterator_in_it_is_found_by_the_name_dp_printed(machine):
    found = machine.find("cmpsi")
    assert found.pattern.name == "cmp<mode>"
    assert found.modes == (("GPI", "SI"),)
    assert found.mode == "SI"
    assert found.modes_said == "GPI is SI"


def test_the_same_form_answers_to_both_of_its_modes(machine):
    assert machine.find("cmpsi").mode == "SI"
    assert machine.find("cmpdi").mode == "DI"
    assert machine.find("cmphi") is None


def test_resolving_a_placeholder_uses_the_mode_that_was_pinned_down(machine):
    found = machine.find("cmpdi")
    row = found.alternative(0)
    assert found.resolve(row.template, machine) == r"cmp\t%x0, %x1"


def test_a_placeholder_the_reader_cannot_resolve_is_left_exactly_as_written(machine):
    """A wrong substitution in a lesson is indistinguishable from the truth, so the reader
    does not guess."""
    found = machine.find("cmpsi")
    assert found.resolve(r"%<vas>0", machine) == r"%<vas>0"


def test_an_exact_name_wins_over_an_iterator(machine):
    assert machine.find("*do_return").modes == ()


# The committed extract, which is what a notebook actually reads


def test_the_extract_holds_every_pattern_the_recordings_named(extract):
    """If this fails then a recording was refreshed and `record.py` was not rerun."""
    from gxray import asm, corpus_store

    for entry in ["t09-final", "t09-sections", "t09-local"]:
        listing = asm.parse(corpus_store.load(entry).asm, entry)
        for name in listing.patterns():
            assert name in extract["patterns"], name


def test_every_extracted_pattern_says_where_it_came_from(extract):
    for name, p in extract["patterns"].items():
        assert p["citation"].endswith(f"@{extract['tag']}"), name
        assert p["file"].startswith("gcc/config/aarch64/"), name
        assert p["line"] > 0, name


def test_the_extract_resolves_the_placeholders_a_generic_pattern_was_written_with(extract):
    add = extract["patterns"]["*addsi3_aarch64"]
    assert add["written"] == "*add<mode>3_aarch64"
    assert add["modes"] == [["GPI", "SI"]]
    assert add["alternatives"][1]["written"] == r"add\t%<w>0, %<w>1, %<w>2"
    assert add["alternatives"][1]["template"] == r"add\t%w0, %w1, %w2"


def test_a_name_with_two_iterators_in_it_is_resolved_to_both(extract):
    """`*zero_extend<SHORT:mode><GPI:mode>2_aarch64` has two holes with nothing between them,
    so only the real mode names say where one ends and the next starts."""
    both = extract["patterns"]["*zero_extendqisi2_aarch64"]
    assert both["modes"] == [["SHORT", "QI"], ["GPI", "SI"]]
    assert extract["patterns"]["*zero_extendqidi2_aarch64"]["modes"] == [
        ["SHORT", "QI"],
        ["GPI", "DI"],
    ]


def test_the_number_of_alternatives_is_what_decides_whether_dp_prints_a_slash(extract):
    """`output_asm_name` prints the alternative only when the pattern has more than one, so
    this is the rule the lesson teaches and it holds over every pattern in the corpus."""
    from gxray import asm, corpus_store

    seen = 0
    for entry in ["t09-final", "t09-sections", "t09-local"]:
        listing = asm.parse(corpus_store.load(entry).asm, entry)
        for line in listing.insns:
            p = extract["patterns"].get(line.pattern)
            if p is None:
                continue
            seen += 1
            assert (line.alternative is not None) == (len(p["alternatives"]) > 1), line.slot
    assert seen == 36


def test_asking_for_an_extract_nobody_wrote_says_which_ones_exist():
    with pytest.raises(FileNotFoundError, match="aarch64"):
        mdesc.load_extract("vax")


# The real tree


@needs_tree
def test_the_whole_aarch64_description_reads_without_falling_over():
    machine = mdesc.load(TREE, START)
    assert len(machine) > 1000
    assert len(machine.files) > 1
    assert "GPI" in machine.iterators


@needs_tree
def test_the_extract_in_the_repository_matches_the_tree_it_says_it_came_from():
    """The committed file is generated, and this is the check that it was regenerated."""
    committed = mdesc.load_extract("aarch64")
    machine = mdesc.load(TREE, START)
    fresh = mdesc.extract(machine, list(committed["patterns"]), committed["tag"])
    assert fresh["patterns"] == committed["patterns"]


@needs_tree
def test_a_citation_in_the_extract_points_at_the_line_it_says_it_does():
    committed = mdesc.load_extract("aarch64")
    for name, p in committed["patterns"].items():
        lines = (TREE / p["file"]).read_text(encoding="utf-8").splitlines()
        assert p["written"] in lines[p["line"] - 1], name
