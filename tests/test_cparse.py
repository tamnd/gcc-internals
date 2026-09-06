"""The parser diagnostic reader.

`gxray.cparse` reads GCC's SARIF diagnostics back into things with names on them, and keeps
two tables transcribed out of the C front end. Most of the tests here are the ordinary kind:
a small input written by hand, an awkward case next to it.

Three are not ordinary, and they are the ones that matter.
`test_the_insertion_table_matches_the_switch_in_the_tree` and
`test_the_suffix_table_has_a_branch_for_every_one_in_the_tree` compare the two transcribed
tables with the source they were transcribed from, because a table that quietly falls behind
the compiler leaves a lesson saying something false with every other test passing.
`test_every_recorded_message_matches_at_least_one_branch` compares them the other direction,
against a recording, because a table can keep its entries and stop describing the output.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import grader

from gxray import cparse

ROOT = Path(__file__).resolve().parent.parent
TREE = ROOT / "vendor" / "gcc"
COMMON = TREE / "gcc" / "c-family" / "c-common.cc"
PARSER = TREE / "gcc" / "c" / "c-parser.cc"
needs_tree = pytest.mark.skipif(not COMMON.is_file(), reason="vendor/gcc is not checked out")

LESSON = "f03-four-tokens"

#: The eight programs that all leave out the same semicolon.
SAME = ("brace", "name", "number", "string", "char", "keyword", "pragma", "eof")


def recorded() -> cparse.Recording:
    return cparse.load("f03")


# ---------------------------------------------------------------------------
# Reading SARIF.


def sarif(*results: dict) -> str:
    return json.dumps({"runs": [{"results": list(results)}]})


def result(message: str, line: int = 1, column: int = 1, end: int = 0, **rest) -> dict:
    region = {"startLine": line, "startColumn": column}
    if end:
        region["endColumn"] = end
    return {
        "level": "error",
        "message": {"text": message},
        "locations": [{"physicalLocation": {"region": region}}],
        **rest,
    }


def test_a_log_with_no_results_in_it_is_a_clean_compilation():
    assert cparse.parse_sarif(sarif()) == []


def test_text_that_is_not_sarif_is_refused_rather_than_read_as_nothing():
    with pytest.raises(cparse.CParseError, match="not a SARIF log"):
        cparse.parse_sarif("error: expected ';' before '}' token")


def test_a_log_with_no_runs_is_refused_too():
    with pytest.raises(cparse.CParseError, match="no runs"):
        cparse.parse_sarif('{"version": "2.1.0"}')


def test_a_result_becomes_a_diagnostic_with_its_place_on_it():
    one = cparse.parse_sarif(sarif(result("expected ';'", line=3, column=11, end=12)))[0]
    assert one.error
    assert one.message == "expected ';'"
    assert (one.at.line, one.at.column, one.at.end) == (3, 11, 12)
    assert str(one.at) == "3:11-12"
    assert str(one) == "3:11-12: error: expected ';'"


def test_a_span_with_no_end_is_one_column_wide():
    assert cparse.Span(1, 5).width == 1
    assert str(cparse.Span(1, 5)) == "1:5"


def test_a_span_is_at_least_one_column_wide_however_the_numbers_come_out():
    """SARIF gives `endColumn` one past the last character, and GCC sometimes gives neither."""
    assert cparse.Span(1, 5, 5).width == 1
    assert cparse.Span(1, 5, 12).width == 7


def test_sarif_doubles_braces_and_undouble_puts_them_back():
    assert cparse.undouble("expected ';' before '}}' token") == "expected ';' before '}' token"
    assert cparse.undouble("a {{ b }} c") == "a { b } c"


def test_undoubling_leaves_a_message_with_no_braces_alone():
    assert cparse.undouble("expected ';' before numeric constant") == (
        "expected ';' before numeric constant"
    )


def test_a_recorded_message_arrives_undoubled():
    one = cparse.parse_sarif(sarif(result("expected ';' before '}}' token")))[0]
    assert one.message == "expected ';' before '}' token"


def test_colour_escapes_come_out_and_nothing_else_does():
    coloured = "\x1b[01m\x1b[Kp.c:1:23:\x1b[m\x1b[K \x1b[01;31m\x1b[Kerror:\x1b[m\x1b[K oops"
    assert cparse.plain(coloured) == "p.c:1:23: error: oops"
    assert cparse.plain("p.c:1:23: error: oops") == "p.c:1:23: error: oops"


def test_a_fix_it_is_read_out_of_the_replacements():
    raw = result(
        "expected ';'",
        fixes=[
            {
                "artifactChanges": [
                    {
                        "replacements": [
                            {
                                "deletedRegion": {"startLine": 1, "startColumn": 23},
                                "insertedContent": {"text": ";"},
                            }
                        ]
                    }
                ]
            }
        ],
    )
    one = cparse.parse_sarif(sarif(raw))[0]
    assert len(one.fixes) == 1
    assert one.fixes[0].insert == ";"
    assert str(one.fixes[0]) == "insert ';' at 1:23"


def test_a_related_location_on_another_column_means_the_caret_moved():
    raw = result(
        "expected ';'",
        column=23,
        relatedLocations=[{"physicalLocation": {"region": {"startLine": 1, "startColumn": 24}}}],
    )
    one = cparse.parse_sarif(sarif(raw))[0]
    assert one.moved


def test_a_related_location_in_the_same_place_does_not():
    """`'x' undeclared` carries a secondary at the caret, and that is not a swap."""
    raw = result(
        "'x' undeclared",
        column=6,
        relatedLocations=[{"physicalLocation": {"region": {"startLine": 1, "startColumn": 6}}}],
    )
    assert not cparse.parse_sarif(sarif(raw))[0].moved


def test_a_diagnostic_with_no_related_locations_did_not_move_either():
    assert not cparse.parse_sarif(sarif(result("oops")))[0].moved


def test_the_quoted_line_and_the_function_come_off_the_location():
    raw = result(
        "expected ';'",
        locations=[
            {
                "physicalLocation": {
                    "region": {"startLine": 1, "startColumn": 23},
                    "contextRegion": {"snippet": {"text": "int f(void) { return 1 }\n"}},
                },
                "logicalLocations": [{"fullyQualifiedName": "f"}],
            }
        ],
    )
    one = cparse.parse_sarif(sarif(raw))[0]
    assert one.snippet == "int f(void) { return 1 }"
    assert one.function == "f"


def test_storing_a_diagnostic_and_reading_it_back_gives_the_same_thing():
    """The corpus round trip. If this drifts, a re-recording silently loses a field."""
    for one in recorded():
        for diagnostic in one.diagnostics:
            assert cparse._stored(cparse.stored(diagnostic)) == diagnostic


def test_a_stored_diagnostic_leaves_out_what_it_does_not_have():
    bare = cparse.Diagnostic(level="error", message="oops", at=cparse.Span(1, 1))
    assert cparse.stored(bare) == {"level": "error", "message": "oops", "at": [1, 1, 0]}


# ---------------------------------------------------------------------------
# The two transcribed tables.


def test_the_suffix_table_is_thirteen_branches_and_one_catch_all():
    assert len(cparse.SUFFIXES) == 13
    assert sum(1 for one in cparse.SUFFIXES if not one.types) == 1
    assert cparse.SUFFIXES[-1].text == " before %qs token"


def test_a_message_that_names_a_number_is_pinned_to_one_branch():
    one = cparse.suffix_for("expected ';' before numeric constant")
    assert one is not None
    assert one.types == ("CPP_NUMBER",)


def test_a_message_that_ends_in_one_quoted_character_is_pinned_to_neither():
    """A one letter identifier and a character constant print the same. This is not a defect."""
    found = cparse.suffixes_for("expected ';' before 'c'")
    assert len(found) == 2
    assert {one.types[0] for one in found} == {"CPP_CHAR", "CPP_NAME"}
    assert cparse.suffix_for("expected ';' before 'c'") is None


def test_a_longer_identifier_is_not_mistaken_for_a_character_constant():
    one = cparse.suffix_for("expected ';' before 'while'")
    assert one is not None
    assert one.types == ("CPP_NAME",)


def test_a_pragma_is_not_read_as_an_identifier_despite_the_quotes():
    one = cparse.suffix_for("expected ';' before '#pragma'")
    assert one is not None
    assert one.types == ("CPP_PRAGMA",)


def test_punctuation_lands_in_the_catch_all():
    one = cparse.suffix_for("expected ';' before '}' token")
    assert one is not None
    assert one.types == ()


def test_a_message_that_matches_no_branch_at_all_is_not_forced_into_one():
    assert cparse.suffixes_for("'x' undeclared (first use in this function)") == []


def test_the_insertion_table_is_seven_tokens_split_two_and_five():
    assert len(cparse.INSERTION) == 7
    assert sorted(k for k, v in cparse.INSERTION.items() if v == "before") == ["(", "["]
    after = sorted(k for k, v in cparse.INSERTION.items() if v == "after")
    assert after == [")", ",", ":", ";", "]"]


@needs_tree
def test_the_insertion_table_matches_the_switch_in_the_tree():
    """The transcription against the source, in both directions.

    `get_missing_token_insertion_kind` is a switch over seven token types and a default. If
    GCC grows an eighth, or moves one from one arm to the other, the lesson's table has to
    move with it, and this is the only thing that would notice.
    """
    spelling = {
        "CPP_OPEN_SQUARE": "[",
        "CPP_OPEN_PAREN": "(",
        "CPP_CLOSE_PAREN": ")",
        "CPP_CLOSE_SQUARE": "]",
        "CPP_SEMICOLON": ";",
        "CPP_COMMA": ",",
        "CPP_COLON": ":",
    }
    text = COMMON.read_text(encoding="utf-8")
    body = text.partition("get_missing_token_insertion_kind (enum cpp_ttype type)")[2]
    body = body.partition("\n}\n")[0]
    found = {}
    side = "before"
    for name in re.findall(r"case (CPP_\w+):|return (MTIK_\w+);", body):
        label, action = name
        if label:
            found[label] = side
        elif action == "MTIK_INSERT_BEFORE_NEXT":
            side = "after"
    assert {spelling[k]: v for k, v in found.items()} == cparse.INSERTION


@needs_tree
def test_the_suffix_table_has_a_branch_for_every_one_in_the_tree():
    """Every `catenate_messages` in `c_parse_error`, against the transcribed table.

    Compared on the appended string, which is the part a reader sees. A branch added to the
    front end that this table does not know about would leave `suffix_for` returning nothing
    for a message the lesson prints.
    """
    text = COMMON.read_text(encoding="utf-8")
    body = text.partition("c_parse_error (const char *gmsgid, enum cpp_ttype token_type,")[2]
    body = body.partition("#undef catenate_messages")[0]
    found = re.findall(r'catenate_messages \(gmsgid,\s*"([^"]*)"\)', body)
    # One branch prints a hex escape, so the C literal has a doubled backslash in it and the
    # transcription has the single backslash a reader would see.
    said = {one.replace("\\\\", "\\") for one in found}
    assert sorted(said) == sorted({one.text for one in cparse.SUFFIXES})


@needs_tree
def test_the_parser_still_has_exactly_four_token_slots():
    """The number the whole lesson is named after, read off the struct rather than believed."""
    text = PARSER.read_text(encoding="utf-8")
    found = re.search(r"c_token tokens_buf\[(\d+)\]", text)
    assert found
    assert int(found.group(1)) == recorded().lookahead.slots == 4


# ---------------------------------------------------------------------------
# The recording.


def test_the_recording_has_the_programs_the_lesson_talks_about():
    rec = recorded()
    assert len(rec) == 15
    assert set(SAME) <= set(rec.cases)
    assert rec.target
    assert rec.compiler.startswith("gcc")


def test_asking_for_a_program_that_is_not_there_says_what_is():
    with pytest.raises(cparse.CParseError, match="no case called 'nope'"):
        recorded().case("nope")


def test_a_recording_iterates_over_its_programs():
    rec = recorded()
    assert [one.name for one in rec] == list(rec.cases)
    assert rec["brace"] is rec.case("brace")


def test_asking_for_a_line_that_is_not_in_the_program_says_how_many_there_are():
    with pytest.raises(cparse.CParseError, match="and line 9 was asked for"):
        recorded()["brace"].line(9)


def test_one_missing_semicolon_gives_eight_different_sentences():
    """The spine of the lesson. Eight copies of one mistake, eight messages."""
    rec = recorded()
    said = {rec[name].errors[0].message for name in SAME}
    assert len(said) == len(SAME)


def test_every_recorded_message_matches_at_least_one_branch():
    """The tables against the output, rather than against the source they came from."""
    rec = recorded()
    for name in SAME:
        one = rec[name].errors[0]
        assert one.suffixes, one.message


def test_exactly_two_of_the_eight_do_not_say_which_branch_made_them():
    rec = recorded()
    unsure = sorted(name for name in SAME if cparse.suffix_for(rec[name].errors[0].message) is None)
    assert unsure == ["char", "name"]


def test_the_one_with_no_fix_it_is_the_one_whose_caret_did_not_move():
    """The split the boss fight asks about, checked as one fact rather than two.

    `expected ',' or ';'` names two possible tokens, so `type_is_unique` is false, so no hint
    is offered, so the caret is never swapped onto the hint. Every other program gets all
    three, and the recording has to keep showing that or the lesson is wrong.
    """
    rec = recorded()
    hinted = sorted(name for name in SAME if rec[name].errors[0].fixes)
    moved = sorted(name for name in SAME if rec[name].errors[0].moved)
    assert hinted == moved == sorted(set(SAME) - {"name"})


def test_the_caret_is_at_the_missing_semicolon_except_in_the_one_case():
    rec = recorded()
    columns = {name: rec[name].errors[0].at.column for name in SAME}
    assert {name for name, column in columns.items() if column == 23} == set(SAME) - {"name"}
    assert columns["name"] == 25


def test_the_swapped_diagnostic_keeps_the_place_the_caret_came_from():
    one = recorded()["brace"].errors[0]
    assert one.at.column == 23
    assert one.fixes[0].insert == ";"
    assert [span.column for span in one.related] == [24]
    assert one.moved


def test_the_two_readings_of_one_line_differ_only_in_a_declaration_above_it():
    rec = recorded()
    a, b = rec["meaning-typedef"], rec["meaning-variable"]
    assert a.line(3) == b.line(3) == "void f(void) { A * b; }"
    assert a.line(1) != b.line(1)
    assert not a.errors and not b.errors
    assert [one.message for one in a.warnings] == [
        "declaration of 'b' shadows a global declaration",
        "unused variable 'b'",
    ]
    assert [one.message for one in b.warnings] == ["statement with no effect"]


def test_the_scope_pair_differs_in_whether_the_last_line_compiles():
    rec = recorded()
    good, bad = rec["scope-typedef"], rec["scope-variable"]
    assert not good.errors
    assert "unused variable 'x'" in {one.message for one in good.warnings}
    assert len(bad.errors) == 1
    assert bad.errors[0].message.startswith("'x' undeclared")
    assert bad.errors[0].at.line == 7


def test_three_missing_semicolons_come_out_as_two_errors():
    one = recorded()["recovery"]
    assert one.source.count("\n  int") == 3
    assert len(one.errors) == 2
    assert one.errors[-1].message.endswith(" at end of input")
    assert one.errors[-1].at.line == 6


def test_an_unclosed_bracket_points_at_two_lines_at_once():
    one = recorded()["paren"]
    error = one.errors[0]
    assert error.message == "expected ')' before 'g'"
    assert len(error.related) == 2
    assert sorted({span.line for span in error.related}) == [4, 5]
    assert error.fixes[0].insert == ")"


def test_a_conflict_marker_is_three_errors_seven_columns_wide():
    one = recorded()["conflict"]
    assert len(one.errors) == 3
    assert {error.message for error in one.errors} == {"version control conflict marker in file"}
    assert {error.at.column for error in one.errors} == {1}
    assert {error.at.width for error in one.errors} == {7}


def test_the_caret_line_is_drawn_from_the_span():
    one = recorded()["conflict"]
    drawn = one.under(one.errors[0])
    assert drawn == "^~~~~~~"


def test_the_programs_shared_with_another_target_all_agree():
    rec = recorded()
    shared = [one for one in rec if one.elsewhere]
    assert len(shared) == 3
    assert all(one.agrees for one in shared)


def test_a_program_that_was_not_shared_agrees_vacuously():
    """`agrees` has to be true for the twelve that were never sent, or the table lies."""
    assert all(one.agrees for one in recorded() if not one.elsewhere)


def test_a_program_whose_other_target_said_something_else_does_not_agree():
    one = cparse.Case(name="x", about="", source="", text="error: a", elsewhere="error: b")
    assert not one.agrees


def test_trailing_space_is_not_a_disagreement():
    """GCC pads the caret line, and Compiler Explorer does not always send the padding."""
    one = cparse.Case(name="x", about="", source="", text="a  \n\nb", elsewhere="a\nb\n")
    assert one.agrees


# ---------------------------------------------------------------------------
# The counts taken off the tree.


def test_the_parser_is_mostly_not_about_c():
    """The number that surprises people, and the reason the file is so large."""
    rec = recorded()
    parts = rec.grammar.dialects
    assert len(rec.grammar) == 298
    assert sum(len(names) for names in parts.values()) == len(rec.grammar)
    assert len(parts["OpenMP"]) > len(parts["C"])
    assert len(parts["C"]) < len(rec.grammar) / 2


def test_asking_the_grammar_for_a_prefix_gives_back_full_names():
    found = recorded().grammar.named("declaration")
    assert found == ["c_parser_declaration_or_fndef"]


def test_the_deepest_the_parser_looks_is_the_width_of_its_buffer():
    look = recorded().lookahead
    assert look.deepest == look.slots == 4
    assert look.depths[4] == 3


def test_most_of_the_peeking_is_one_token_deep():
    look = recorded().lookahead
    assert look.peeks > 7 * look.seconds
    assert look.seconds > sum(look.depths.values())


def test_a_lookahead_that_was_never_filled_in_still_answers():
    assert cparse.Lookahead().deepest == 2


# ---------------------------------------------------------------------------
# The boss fight.


def test_the_grader_answers_its_own_three_questions():
    key = grader(LESSON).questions()
    assert key["odd"] == "name"
    assert key["unsure"] == ["char", "name"]
    assert key["deep"] == 3
    assert key["usual"] == 23


def test_the_grader_accepts_the_right_answers():
    module = grader(LESSON)
    assert module.main(["--odd", "name", "--unsure", "char, name", "--deep", "3"]) == 0


def test_the_grader_refuses_the_wrong_ones():
    module = grader(LESSON)
    assert module.main(["--odd", "brace", "--unsure", "eof", "--deep", "9"]) == 1
