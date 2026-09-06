"""The spec language reader.

`gxray.specs` is a reader for a language with no grammar written down anywhere except a
comment and a switch statement in `gcc/gcc.cc`. Two things follow from that.

The first is that every claim about the language has to be checked against the source
rather than against what the module believes. The test that compares `FORMS` with the case
labels of `do_spec_1` is the important one in this file: it is the only thing standing
between a GCC that grew a new `%` form and a lesson that prints it as though it were text.

The second is that the tokenizer has to round trip. A reader that drops a character
somewhere is a reader that shows a notebook a spec its compiler never had, and no amount of
plausible looking output would give that away.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import grader

from gxray import specs

ROOT = Path(__file__).resolve().parent.parent
TREE = ROOT / "vendor" / "gcc"
DRIVER = TREE / "gcc" / "gcc.cc"
needs_tree = pytest.mark.skipif(not DRIVER.is_file(), reason="vendor/gcc is not checked out")

#: A dump written by hand, small enough to read and awkward in the three ways a real one is:
#: a name defined twice, a value with a newline in the middle of it, and an empty spec.
DUMP = """\
*asm:
-arch %(darwin_arch) %{march*}

*asm_debug:


*invoke_as:
%{!S: -o %|.s |
 as %(asm_options) %|.s %A }

*asm_debug:
-g

"""


def table() -> specs.Table:
    return specs.parse(DUMP, compiler="gcc-16", target="aarch64-apple-darwin24")


def recorded() -> specs.Recording:
    return specs.load("f01")


# ---------------------------------------------------------------------------
# The file format.


def test_parse_reads_the_one_printf_that_writes_the_format():
    one = table()
    assert one.names == ["asm", "asm_debug", "invoke_as", "asm_debug"]
    assert one.target == "aarch64-apple-darwin24"
    assert str(one) == "4 specs for aarch64-apple-darwin24"


def test_a_value_keeps_the_newline_that_separates_two_commands():
    """The newline in `invoke_as` is what puts `as` in a command of its own."""
    assert "\n" in table()["invoke_as"].value


def test_an_empty_spec_is_a_hook_the_target_did_not_need():
    one = specs.parse("*asm_debug:\n\n\n")
    assert one.empties == ["asm_debug"]
    assert one["asm_debug"].empty


def test_lookup_takes_the_last_definition_because_set_spec_overwrites():
    """A specs file works by being read after the built in table, so later wins."""
    one = table()
    assert one.duplicates == ["asm_debug"]
    assert one["asm_debug"].value == "-g"


def test_a_missing_name_says_what_the_table_has_instead_of_raising_keyerror():
    with pytest.raises(specs.SpecError, match="no spec called 'nope'"):
        table()["nope"]


# ---------------------------------------------------------------------------
# The tokenizer.


def test_tokenizing_loses_nothing():
    """Every spec in both recorded tables, put back together character for character."""
    rec = recorded()
    for label in ("local", "elsewhere"):
        for spec in rec.table(label):
            joined = "".join(token.text for token in specs.tokenize(spec.value))
            assert joined == spec.value, f"{label} *{spec.name}"


def test_a_temporary_files_suffix_is_part_of_the_form():
    """`%|.s` is one token. Reading it as `%|` plus the text `.s` puts `.s` on the command
    line, which is the kind of wrong that looks right."""
    got = specs.tokenize("%|.s")
    assert len(got) == 1
    assert got[0].kind == "text"
    assert got[0].letter == "|"


def test_whitespace_is_an_instruction_and_not_punctuation():
    got = specs.tokenize("%{v} %{w}")
    assert [t.kind for t in got] == ["brace", "literal", "brace"]
    assert got[1].about == "whitespace, which ends an argument"


def test_a_form_this_reader_does_not_know_is_reported_and_not_guessed():
    got = specs.tokenize("%q")
    assert got[0].kind == "unknown"
    assert got[0].about == "not a form this reader knows"


def test_a_brace_splits_at_the_colon_that_separates_it_and_not_the_first_one():
    """The predicate of `%{%:debug-level-gt(0):-dD}` is a function call with a colon in it."""
    got = specs.tokenize("%{%:debug-level-gt(0):-dD}")[0]
    assert got.head == "%:debug-level-gt(0)"
    assert got.body == "-dD"


def test_a_colon_inside_a_switch_name_is_escaped_and_does_not_split_it():
    got = specs.tokenize(r"%{std=iso9899\:1999:X}")[0]
    assert got.head == r"std=iso9899\:1999"
    assert got.body == "X"


def test_an_n_way_brace_comes_back_as_clauses_with_a_default_last():
    got = specs.tokenize("%{S:X;T:Y;:D}")[0]
    assert got.clauses == (("S", "X"), ("T", "Y"), ("", "D"))
    assert specs.predicate(got.clauses[-1][0]) == "otherwise"


def test_a_brace_with_no_body_passes_the_switch_on_rather_than_substituting():
    passed = specs.tokenize("%{v}")[0]
    substituted = specs.tokenize("%{v:-verbose}")[0]
    assert passed.about == "pass -v on, if it was given"
    assert substituted.about == "if -v was given, substitute"


def test_nested_braces_do_not_split_the_one_around_them():
    got = specs.tokenize("%{!E:%{!M:%{!MM:cc1}}}")[0]
    assert got.head == "!E"
    assert got.body == "%{!M:%{!MM:cc1}}"


def test_walk_goes_inside_the_braces_where_most_of_a_spec_lives():
    value = "%{!E:%{!M:cc1 %(cc1_options)}}"
    assert len(specs.tokenize(value)) == 1
    assert [t.kind for t in specs.walk(value)] == [
        "brace",
        "literal",
        "brace",
        "literal",
        "literal",
        "spec",
    ]


# ---------------------------------------------------------------------------
# Conditions in words.


@pytest.mark.parametrize(
    ("head", "said"),
    [
        ("S", "if -S was given"),
        ("!S", "unless -S was given"),
        ("E|M|MM", "if any of -E, -M, -MM was given"),
        (".c", "if the input file's suffix is .c"),
        (",c++", "if the spec being used is c++"),
        ("%:sanitize(address)", "if %:sanitize(address) returns anything"),
        ("", "otherwise"),
    ],
)
def test_a_predicate_reads_as_a_sentence(head: str, said: str):
    assert specs.predicate(head) == said


def test_a_star_in_a_predicate_means_every_matching_switch():
    assert specs.passed_on("march*") == "pass on every switch matching march*"


# ---------------------------------------------------------------------------
# The call graph.


def test_the_two_spellings_of_a_call_are_one_edge():
    """`%(lib)` and `%L` run the same spec, and a graph that showed two would be wrong."""
    assert specs.Spec("x", "%(lib) %L").calls == ["lib"]


def test_a_call_to_a_c_function_is_not_a_call_to_a_spec():
    one = specs.Spec("x", "%:if-exists(crt0.o%s) %(lib)")
    assert one.functions == ["if-exists"]
    assert one.calls == ["lib"]


def test_reach_is_breadth_first_so_the_order_says_something_true():
    one = specs.parse("*a:\n%(b) %(c)\n\n*b:\n%(d)\n\n*c:\n\n*d:\n\n")
    assert one.reach("a") == ["a", "b", "c", "d"]


def test_dangling_names_are_not_an_error_and_link_command_is_the_reason():
    one = specs.parse("*a:\n%(link_command)\n\n")
    assert one.dangling("a") == ["link_command"]


def test_callers_finds_the_specs_that_run_one_directly():
    one = specs.parse("*a:\n%(c)\n\n*b:\n%L\n\n*c:\n\n*lib:\n\n")
    assert one.callers("c") == ["a"]
    assert one.callers("lib") == ["b"]


def test_counts_ignore_whitespace_because_it_is_not_a_thing_in_the_output():
    got = specs.Spec("x", "cc1   %(cc1_options)").counts()
    assert got == {"literal": 1, "spec": 1}


# ---------------------------------------------------------------------------
# The C string literal in the compiler table.


def test_a_spec_written_across_lines_of_c_comes_back_as_one_string():
    got = specs.from_c_literal(
        '/* a comment */\n  "%{E:%(cpp_options)}\\\n   %{!E:cc1}", 0, 0, 1},\n'
    )
    assert got == "%{E:%(cpp_options)}   %{!E:cc1}"


def test_a_backslash_n_in_the_source_becomes_a_real_newline():
    """It has to. That newline is what ends `cc1` and starts the next command."""
    got = specs.from_c_literal(r'"cc1 %g.i \n cc1 -fpreprocessed"')
    assert got == "cc1 %g.i \n cc1 -fpreprocessed"


def test_adjacent_literals_are_concatenated_the_way_c_concatenates_them():
    assert specs.from_c_literal('"cc1 " "%(cc1_options)"') == "cc1 %(cc1_options)"


def test_the_recorded_c_spec_is_a_spec_the_reader_understands():
    from gxray import source

    at_c = specs.from_c_literal(source.load_extract("f01")["c-spec"].text)
    assert at_c.startswith("%{E|M|MM:")
    assert "\n" in at_c
    assert specs.Spec("@c", at_c).calls == [
        "trad_capable_cpp",
        "cpp_options",
        "cpp_debug_options",
        "cc1_options",
        "cpp_unique_options",
        "invoke_as",
    ]


# ---------------------------------------------------------------------------
# Explaining.


def test_explain_puts_one_token_on_each_line_with_what_it_does_beside_it():
    got = specs.explain("cc1 %{!S:-o %|.s}", depth=1).splitlines()
    assert got[0].startswith("cc1")
    assert got[1].endswith("unless -S was given, substitute")


def test_explain_stops_at_the_depth_it_was_given_and_says_how_much_it_left():
    got = specs.explain("%{!E:%{!M:%{!MM:cc1 %(cc1_options)}}}", depth=2)
    assert "more characters" in got


def test_explain_survives_every_spec_in_both_recorded_tables():
    """Not a check that the output is right, a check that nothing in a real table crashes
    the explainer or comes back blank when the spec was not."""
    rec = recorded()
    for label in ("local", "elsewhere"):
        for spec in rec.table(label):
            got = specs.explain(spec.value)
            assert spec.empty or got.strip(), f"{label} *{spec.name}"


# ---------------------------------------------------------------------------
# The recording.


def test_the_recording_has_two_targets_of_one_release():
    rec = recorded()
    assert "16.2.0" in rec.compiler
    assert rec.source.startswith("/* L1:")
    assert rec.table("local").target != rec.table("elsewhere").target
    assert len(rec.table("local")) > 40
    assert len(rec.table("elsewhere")) > 40


def test_no_form_in_either_recorded_table_is_unrecognised():
    """The one that fails when GCC grows a `%` form nobody told this module about."""
    rec = recorded()
    assert rec.table("local").unknown() == []
    assert rec.table("elsewhere").unknown() == []


def test_the_built_in_specs_are_in_both_tables_and_the_target_ones_are_not():
    rec = recorded()
    built = rec.builtin
    assert len(built.static_specs) == 45
    for label in ("local", "elsewhere"):
        assert built.missing_from(rec.table(label)) == []
    added = {label: built.added_by(rec.table(label)) for label in ("local", "elsewhere")}
    assert added["local"] and added["elsewhere"]
    assert added["local"] != added["elsewhere"]


def test_link_command_is_printed_by_dumpspecs_and_is_not_in_the_spec_list():
    rec = recorded()
    assert "link_command" in rec.table("local")
    assert "link_command" not in rec.builtin.static_specs


def test_a_target_can_add_spec_functions_of_its_own():
    """`EXTRA_SPEC_FUNCTIONS`. Twenty one is a floor, not a total."""
    rec = recorded()
    built = rec.builtin
    assert len(built.functions) == 21
    for label in ("local", "elsewhere"):
        called = {name for spec in rec.table(label) for name in spec.functions}
        assert called - set(built.functions), label


def test_every_specs_file_in_the_recording_changed_something():
    rec = recorded()
    assert sorted(rec.overrides) == ["argument", "assembler", "guard", "suffix"]
    for name, one in rec.overrides.items():
        assert one.moved, name
        assert one.argv[1] == "-###", name


def test_three_of_the_four_specs_files_moved_the_chain_and_one_moved_an_argument():
    rec = recorded()
    moved = {name for name, one in rec.overrides.items() if one.programs()[0] != one.programs()[1]}
    assert moved == {"assembler", "guard", "suffix"}
    argument = rec["argument"]
    before = set(argument.chain_before.named("cc1").argv)
    after = set(argument.chain_after.named("cc1").argv)
    assert after - before == {"-fverbose-asm"}


def test_the_guard_file_makes_gcc_dash_s_run_the_assembler():
    """The whole lesson in one assertion. `-S` is a string, not a feature."""
    one = recorded()["guard"]
    assert "-S" in one.argv
    assert one.programs() == (["cc1"], ["cc1", "as"])


# ---------------------------------------------------------------------------
# Against the source.


@needs_tree
def test_forms_is_exactly_what_do_spec_1_handles():
    """The check that keeps this module honest.

    `do_spec_1` is one switch over the character after the `%`. Every case in it is a form
    of the language, and `FORMS` claims to be all of them apart from the four structural
    ones and the three compound ones the tokenizer handles itself. If GCC adds a case, this
    fails, and it fails before a lesson can print the new form as though it were text.
    """
    whole = DRIVER.read_text(encoding="utf-8").split("\n")
    first = 6163
    last = next(n for n in range(first, len(whole) + 1) if whole[n - 1] == "}")
    body = "\n".join(whole[first - 1 : last])
    assert body.startswith("do_spec_1 ") or "do_spec_1" in whole[first - 2]

    escapes = {"\\n": "\n", "\\t": "\t", "\\\\": "\\"}
    labels = {escapes.get(one, one) for one in re.findall(r"case '(\\?.)':", body)}

    #: Whitespace, which ends an argument or a command rather than substituting anything,
    #: and the three compound forms: `%{` is `handle_braces`, `%:` is
    #: `handle_spec_function`, and `%(` is a named spec, all read by the tokenizer itself.
    structural = {"\n", "\t", " ", "\\", "{", ":", "("}

    assert labels - structural == set(specs.FORMS)


@needs_tree
def test_every_letter_spec_names_a_spec_the_driver_really_has():
    """`%L` is `lib` because `do_spec_1` says so, not because it looks like it."""
    body = DRIVER.read_text(encoding="utf-8")
    for letter, name in specs.LETTER_SPECS.items():
        assert f"case '{letter}':" in body, letter
        assert f"*{name}" in body or f'"{name}"' in body, name


def test_every_form_belongs_to_a_family_that_has_words_for_it():
    for letter, form in specs.FORMS.items():
        assert form.family in specs.FAMILIES, letter
        assert form.operand in specs.OPERANDS, letter
        assert form.about and form.about[0].islower(), letter


# ---------------------------------------------------------------------------
# The boss fight.


def test_the_grader_works_its_answers_out_of_the_recording():
    """None of the three are written down, so re-recording cannot leave the grader marking
    against an answer the notebook no longer shows."""
    key = grader("f01-the-spec-language").questions()
    rec = recorded()
    assert key["calls"] == rec.table("local")["cpp_options"].calls
    assert key["changed"] == ["assembler", "guard", "suffix"]
    assert key["odd"] == "link_command"


def test_the_odd_name_is_derived_from_two_targets_and_not_from_a_list():
    """The evidence is that two targets which share nothing else both show the name."""
    key = grader("f01-the-spec-language").questions()
    assert key["both"] == [key["odd"]]
    assert set(key["added"]) & set(key["elsewhere"]) == {key["odd"]}


def test_the_grader_marks_a_right_answer_right_however_it_is_punctuated():
    module = grader("f01-the-spec-language")
    assert module.words("cpp_unique_options, cc1") == ["cc1", "cpp_unique_options"]
    assert module.words("  guard   suffix,assembler ") == ["assembler", "guard", "suffix"]


def test_the_grader_scores_the_answers_the_lesson_leads_you_to():
    module = grader("f01-the-spec-language")
    assert (
        module.main(
            [
                "--calls",
                "cpp_unique_options,cc1",
                "--changed",
                "assembler,guard,suffix",
                "--odd",
                "link_command",
            ]
        )
        == 0
    )
    assert module.main(["--calls", "cc1", "--changed", "argument", "--odd", "asm"]) == 1
