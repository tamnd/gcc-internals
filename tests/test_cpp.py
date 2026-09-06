"""The preprocessor reader.

`gxray.cpp` reads four kinds of `gcc -E` output back into things with names on them. Almost
all of it is parsing, and the tests for parsing are the ordinary kind: a small input written
by hand, an awkward case next to it.

Two are not ordinary. `test_pastes_covers_every_case_label_cpp_avoid_paste_has` compares the
table in this module with the switch in `libcpp/lex.cc`, because the table is the only claim
here about GCC rather than about GCC's output, and a GCC that grew a new pair would otherwise
leave a lesson saying something false with every test passing.
`test_every_pair_in_the_table_was_actually_separated` compares it with a recording, which is
the other direction: the switch could keep the label and stop firing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import grader

from gxray import cpp

ROOT = Path(__file__).resolve().parent.parent
TREE = ROOT / "vendor" / "gcc"
LEX = TREE / "libcpp" / "lex.cc"
FILES = TREE / "libcpp" / "files.cc"
needs_tree = pytest.mark.skipif(not LEX.is_file(), reason="vendor/gcc is not checked out")


def recorded() -> cpp.Recording:
    return cpp.load("f02")


# ---------------------------------------------------------------------------
# Line markers.


def test_a_marker_with_no_flags_is_a_line_number_and_nothing_else():
    one = cpp.markers('# 1 "hello.c"')[0]
    assert (one.line, one.file, one.flags) == (1, "hello.c", ())
    assert not one.entering and not one.returning and not one.system
    assert "no flags" in str(one)


def test_the_flags_after_a_marker_are_four_separate_facts():
    one = cpp.markers('# 61 "/usr/include/stdio.h" 1 3 4')[0]
    assert one.flags == (1, 3, 4)
    assert one.entering and one.system and not one.returning
    assert one.meanings == [
        "entering a file",
        "a system header, where warnings are suppressed",
        'to be wrapped in extern "C"',
    ]


def test_a_hash_that_is_not_a_marker_is_not_read_as_one():
    """`#pragma` survives preprocessing and starts with the same character."""
    assert cpp.markers('#pragma once\n# 1 "a.c"\n#define X 1') == [
        cpp.Marker(line=1, file="a.c", flags=())
    ]


def test_a_path_with_a_quote_in_it_does_not_end_the_filename_early():
    one = cpp.markers('# 3 "od\\"d.h" 1')[0]
    assert one.file == 'od\\"d.h'
    assert one.entering


def test_the_body_is_the_output_with_the_bookkeeping_taken_out():
    text = '# 1 "a.c"\n\n\nint x;\n# 2 "b.h" 1\nint y;\n'
    assert cpp.body(text) == ["int x;", "int y;"]


# ---------------------------------------------------------------------------
# Macro tables.


def test_a_bracket_touching_the_name_is_what_makes_a_macro_function_like():
    """`#define f (x) x` is not a function-like macro, and the space is the whole reason."""
    table = cpp.parse_macros("#define f(x) x\n#define g (x) x\n")
    assert table["f"].function_like and table["f"].params == "(x)"
    assert not table["g"].function_like and table["g"].body == "(x) x"


def test_a_macro_defined_to_nothing_is_defined():
    table = cpp.parse_macros("#define __STDC__ 1\n#define GUARD\n")
    assert table.empty == ["GUARD"]
    assert "GUARD" in table
    assert table["GUARD"].body == ""


def test_a_dollar_is_a_legal_character_in_a_macro_name_and_a_target_uses_it():
    assert cpp.parse_macros("#define __APPLE_CC__ 6000\n#define $x 1\n").names == [
        "$x",
        "__APPLE_CC__",
    ]


def test_a_line_that_is_not_a_define_is_an_error_and_not_a_shrug():
    """The value of this table is that it is exhaustive, so a line it skipped would make
    every count in the lesson quietly wrong."""
    with pytest.raises(cpp.CppError, match="not a definition"):
        cpp.parse_macros("#define A 1\n<File example.c has no content>\n")


def test_a_missing_macro_says_which_target_does_not_have_it():
    table = cpp.parse_macros("#define A 1\n", target="aarch64-apple-darwin24")
    with pytest.raises(cpp.CppError, match="aarch64-apple-darwin24"):
        table["__x86_64__"]


def test_the_set_operations_are_what_two_targets_are_for():
    here = cpp.parse_macros("#define A 1\n#define SIZE 8\n#define ARM 1\n")
    there = cpp.parse_macros("#define A 1\n#define SIZE 16\n#define X86 1\n")
    assert here.only_in(there) == ["ARM"]
    assert there.only_in(here) == ["X86"]
    assert here.shared(there) == ["A", "SIZE"]
    assert here.differing(there) == ["SIZE"]


# ---------------------------------------------------------------------------
# Include traces.


TRACE = """\
. /usr/include/stdio.h
.. /usr/include/features.h
... /usr/include/wordsize.h
.. /usr/include/types.h
. mine.h
Multiple include guards may be useful for:
/usr/include/wordsize.h
"""


def test_the_dots_are_the_depth_and_the_rest_of_the_line_is_the_path():
    got = cpp.parse_trace(TRACE)
    assert len(got) == 5
    assert got.depth == 3
    assert got.includes[2] == cpp.Include(depth=3, path="/usr/include/wordsize.h")
    assert got.names[-1] == "mine.h"


def test_what_a_header_dragged_in_is_everything_under_it_until_the_depth_drops():
    got = cpp.parse_trace(TRACE)
    under = got.under("/usr/include/stdio.h")
    assert [one.name for one in under] == ["features.h", "wordsize.h", "types.h"]
    assert got.under("mine.h") == []


def test_the_trailer_is_advice_and_is_not_another_file_being_opened():
    got = cpp.parse_trace(TRACE)
    assert got.guards_wanted == ("/usr/include/wordsize.h",)
    assert "/usr/include/wordsize.h" in got.files
    assert len(got) == 5


def test_a_file_opened_twice_is_two_lines_and_that_is_the_whole_guard_story():
    got = cpp.parse_trace(". a.h\n. a.h\n. b.h\n")
    assert got.opened_twice == ["a.h"]
    assert len(got) == 3 and len(got.files) == 2


# ---------------------------------------------------------------------------
# Expansions.


def test_pairing_drops_the_directives_because_they_produce_no_output_line():
    one = cpp.Expansion("t", "", "#define E\na+E+b\n", "a+ +b\n")
    assert one.pairs() == [("a+E+b", "a+ +b")]


def test_pairing_refuses_rather_than_lining_a_line_up_with_somebody_elses_answer():
    one = cpp.Expansion("t", "", "a\nb\n", "a\n")
    with pytest.raises(cpp.CppError, match="no line can be paired"):
        one.pairs()


def test_two_targets_agreeing_ignores_the_whitespace_at_the_end_of_a_line():
    assert cpp.Expansion("t", "", "x\n", "a + b\n", "a + b  \n").agrees
    assert not cpp.Expansion("t", "", "x\n", "a + b\n", "a+b\n").agrees


def test_counting_inserted_spaces_refuses_when_something_other_than_space_moved():
    assert cpp.inserted_spaces("++", "+ +") == 1
    with pytest.raises(cpp.CppError, match="not the source plus spaces"):
        cpp.inserted_spaces("a+b", "a+c")


# ---------------------------------------------------------------------------
# The recording.


def test_the_recording_has_five_tables_of_one_release_on_two_targets():
    rec = recorded()
    assert "16.2.0" in rec.compiler
    assert sorted(rec.tables) == ["c23", "elsewhere", "fast", "local", "optimized"]
    assert rec.macros("local").target != rec.macros("elsewhere").target
    for label in rec.tables:
        assert len(rec.macros(label)) > 300, label


def test_asking_for_a_table_that_is_not_there_says_what_is():
    with pytest.raises(cpp.CppError, match="local"):
        recorded().macros("windows")


def test_two_targets_of_one_release_disagree_about_how_wide_a_long_double_is():
    """The comparison the lesson is built on. Same compiler, same language, same flags."""
    here, there = recorded().macros("local"), recorded().macros("elsewhere")
    assert here["__SIZEOF_LONG_DOUBLE__"].body != there["__SIZEOF_LONG_DOUBLE__"].body
    assert here["__STDC_VERSION__"].body == there["__STDC_VERSION__"].body
    assert len(here.differing(there)) > 20


def test_the_flag_that_names_a_standard_does_not_change_the_standard():
    rec = recorded()
    local, c23 = rec.macros("local"), rec.macros("c23")
    assert c23.only_in(local) == ["__STRICT_ANSI__"]
    assert c23.differing(local) == []


def test_optimizing_adds_one_macro_and_removes_one_so_the_count_says_nothing():
    rec = recorded()
    local, fast = rec.macros("local"), rec.macros("optimized")
    assert fast.only_in(local) == ["__OPTIMIZE__"]
    assert local.only_in(fast) == ["__NO_INLINE__"]
    assert len(fast) == len(local)


def test_almost_every_built_in_macro_is_missing_from_a_dump_of_every_macro():
    """`-dM` prints the hash table, and nineteen of the twenty are C functions that are not
    in it. `__STDC__` is the one that is, because it is also defined the ordinary way."""
    rec = recorded()
    missing = rec.builtin.missing_from(rec.macros("local"))
    assert len(rec.builtin.array) == 20
    assert len(missing) == 19
    assert "__FILE__" in missing and "__STDC__" not in missing
    assert "__STDC__" in rec.builtin.fixed


def test_every_pair_in_the_table_was_actually_separated():
    """The other half of the bargain with `cpp_avoid_paste`: the label can survive while the
    behaviour goes away, and then only a recording notices."""
    rec = recorded()
    assert len(rec.probes) == len(cpp.PASTES) + len(cpp.KEPT_TOGETHER)
    for one in rec.probes:
        assert one.spaced == bool(one.case), f"{one.left!r} {one.right!r} -> {one.output!r}"
    assert len(rec.spaced) == len(cpp.PASTES)
    assert len(rec.unspaced) == len(cpp.KEPT_TOGETHER)


def test_a_separated_pair_is_the_same_two_tokens_with_exactly_one_space_added():
    for one in recorded().spaced:
        assert cpp.inserted_spaces(one.glued, one.output.strip()) == 1


def test_looking_up_a_pair_nobody_probed_says_so():
    with pytest.raises(cpp.CppError, match="nothing probed"):
        recorded().probe("@", "@")


def test_a_guarded_header_is_read_once_and_an_unguarded_one_is_read_every_time():
    guards = recorded().headers("guards")
    assert guards.opened_twice == ["bare.h", "stray.h"]
    assert [one.path for one in guards].count("clean.h") == 1


def test_a_comment_after_the_endif_does_not_cost_the_guard_optimization():
    """`untidy.h` has one, and is still read once. `stray.h` has a declaration there and is
    read twice, which is the difference between a token and a character."""
    guards = recorded().headers("guards")
    assert "untidy.h" not in guards.opened_twice
    assert "stray.h" in guards.opened_twice


def test_the_advice_arrives_for_the_file_you_have_not_had_trouble_with():
    """`-H` names a file as wanting a guard only if it read it exactly once, so the file
    being read twice right now is the one it says nothing about."""
    rec = recorded()
    assert rec.headers("guards").guards_wanted == ()
    named = sorted(one.rsplit("/", 1)[-1] for one in rec.headers("once").guards_wanted)
    assert named == ["bare.h", "stray.h"]
    assert rec.headers("once").opened_twice == []


def test_one_include_of_stdio_opens_a_great_many_files_on_both_targets():
    rec = recorded()
    here, there = rec.headers("local"), rec.headers("elsewhere")
    assert len(here.files) > 20 and len(there.files) > 20
    assert here.depth > 3 and there.depth > 3
    assert set(here.files) & set(there.files) == set()


def test_the_marker_demo_enters_and_returns_from_every_header_it_names():
    found = cpp.markers(recorded().expansion("markers").output)
    entered = [one.file for one in found if one.entering]
    assert entered == ["clean.h", "stray.h"]
    assert [one.file for one in found if one.returning] == ["markers.c", "markers.c"]


def test_the_expansion_rules_are_the_same_on_two_targets_the_macros_are_not():
    rec = recorded()
    for name in ("spacing", "prescan", "paste", "paint", "invocation"):
        assert rec.expansion(name).agrees, name


def test_stringifying_a_macro_takes_two_macros_and_the_recording_shows_why():
    rec = recorded()
    assert [now.strip() for _, now in rec["prescan"].pairs()] == ['"PLUS"', '"+"']


def test_a_macro_that_names_itself_stops_and_a_pair_that_name_each_other_stop_too():
    rec = recorded()
    assert [now.strip() for _, now in rec["paint"].pairs()] == ["foo + 1", "A"]


def test_a_function_like_macro_without_a_bracket_after_it_is_just_a_word():
    rec = recorded()
    assert [now.strip() for _, now in rec["invocation"].pairs()] == ["[1]", "f", "[2]"]


def test_the_output_gains_a_space_that_is_in_no_input_file():
    """One line, and the reason the lesson exists."""
    was, now = recorded()["spacing"].pairs()[0]
    assert " " not in was
    assert now == "a+ +b"


# ---------------------------------------------------------------------------
# Against the source.


@needs_tree
def test_pastes_covers_every_case_label_cpp_avoid_paste_has():
    """The check that keeps the table honest.

    Every `case` in `cpp_avoid_paste` is a reason two tokens cannot be printed together.
    `PASTES` claims one witness for each of them, apart from the six about string literals
    and pragmas that a `-E` of a C file cannot produce. If GCC adds a case, this fails.
    """
    whole = LEX.read_text(encoding="utf-8").split("\n")
    first = next(n for n, line in enumerate(whole, 1) if line.startswith("cpp_avoid_paste "))
    last = next(n for n in range(first, len(whole) + 1) if whole[n - 1] == "}")
    body = "\n".join(whole[first - 1 : last])
    labels = set(re.findall(r"case (CPP_\w+):", body))

    #: A user-defined literal suffix on a string is a C++ thing, and `CPP_PRAGMA` is a token
    #: the preprocessor makes for `_Pragma` rather than one a file can contain. Neither can
    #: be probed by putting two tokens next to each other in a C file.
    unprobeable = {
        "CPP_PRAGMA",
        "CPP_STRING",
        "CPP_WSTRING",
        "CPP_UTF8STRING",
        "CPP_STRING16",
        "CPP_STRING32",
    }
    #: Not a `case`. Everything up to `CPP_LAST_EQ` in the token list pastes with `=`, which
    #: the function handles with a comparison before the switch starts.
    early = {"CPP_LAST_EQ"}

    assert {one.case for one in cpp.PASTES} == (labels - unprobeable) | early
    assert "(int) a <= (int) CPP_LAST_EQ" in body


@needs_tree
def test_the_advice_condition_is_the_one_the_recording_demonstrates():
    """`stack_count == 1`, which is why including a header twice silences the suggestion."""
    body = FILES.read_text(encoding="utf-8")
    assert "file->stack_count == 1" in body
    assert cpp.GUARDS_WANTED in body


@needs_tree
def test_every_marker_flag_this_module_explains_is_one_gcc_documents():
    doc = (TREE / "gcc" / "doc" / "cpp.texi").read_text(encoding="utf-8")
    where = doc.index("Source file name and line number information")
    said = doc[where : where + 4000]
    for flag in cpp.MARKER_FLAGS:
        assert f"@samp{{{flag}}}" in said, flag


# ---------------------------------------------------------------------------
# The boss fight.


def test_the_grader_works_its_answers_out_of_the_recording():
    key = grader("f02-tokens-not-text").questions()
    rec = recorded()
    assert key["spaces"] == len(rec.spaced)
    assert key["twice"] == ["bare.h", "stray.h"]
    assert key["odd"] == "__STDC__"


def test_the_grader_marks_a_right_answer_right_however_it_is_punctuated():
    module = grader("f02-tokens-not-text")
    assert module.words("bare.h, stray.h") == ["bare.h", "stray.h"]
    assert module.words("  stray.h   bare.h ") == ["bare.h", "stray.h"]


def test_the_grader_scores_the_answers_the_lesson_leads_you_to():
    module = grader("f02-tokens-not-text")
    rec = recorded()
    assert (
        module.main(
            ["--spaces", str(len(rec.spaced)), "--twice", "bare.h,stray.h", "--odd", "__STDC__"]
        )
        == 0
    )
    assert module.main(["--spaces", "0", "--twice", "clean.h", "--odd", "__FILE__"]) == 1
