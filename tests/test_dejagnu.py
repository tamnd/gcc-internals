"""The model of GCC's test harness.

Two kinds of test in here. Most run against directive text written into the test, because
what is under test is the model and not GCC. The ones marked `needs_tree` read the pinned
tree, and they are the ones that fail when GCC changes: the torture list is copied into
`gxray/dejagnu.py` and there is exactly one place that proves the copy is still right.

The last group runs against `corpora/testsuite/b04.json`, the recording B04 reads. Those are
not testing the model, they are testing that the recording still says what the notebook says
it says, and they skip when the corpus has not been recorded.
"""

from __future__ import annotations

import textwrap

import pytest

from gxray import dejagnu
from gxray.dejagnu import HarnessError
from tools.refcheck import GCC_ROOT

SUITE = GCC_ROOT / "gcc" / "testsuite"
HAVE_TREE = (SUITE / "lib" / "gcc-dg.exp").is_file()
needs_tree = pytest.mark.skipif(not HAVE_TREE, reason="vendor/gcc is not checked out")
HAVE_CORPUS = dejagnu.CORPUS.is_file()
needs_corpus = pytest.mark.skipif(not HAVE_CORPUS, reason="corpora/testsuite/b04.json is not there")


def dedent(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


# Reading directives out of a file


FLEX = dedent(
    """
    /* Test for invalid uses of flexible array members.  */
    /* { dg-do compile } */
    /* { dg-options "-std=iso9899:1999 -pedantic-errors" } */

    struct s1 { int x[]; }; /* { dg-error "no named members" "members" } */
    struct s2 { int :1; int x[]; }; /* { dg-error "no named members" "members" } */
    struct s3 { int x[]; int y; }; /* { dg-error "not at end" "not at end" } */
    struct s4 { int x; int y[]; };
    """
)


def test_a_directive_carries_the_line_it_was_written_on():
    test = dejagnu.read_test(FLEX, path="gcc/testsuite/gcc.dg/c99-flex-array-1.c")
    assert [d.name for d in test.directives] == [
        "dg-do",
        "dg-options",
        "dg-error",
        "dg-error",
        "dg-error",
    ]
    assert [d.line for d in test.directives] == [2, 3, 5, 6, 7]


def test_the_test_name_is_the_path_below_testsuite():
    test = dejagnu.read_test(FLEX, path="gcc/testsuite/gcc.dg/tree-ssa/ssa-fre-6.c")
    assert test.name == "gcc.dg/tree-ssa/ssa-fre-6.c"


def test_dg_options_replaces_the_default_and_dg_additional_options_does_not():
    test = dejagnu.read_test(FLEX)
    assert test.given == ["-std=iso9899:1999", "-pedantic-errors"]
    assert test.command(default=("-ansi",)) == [
        "-fdiagnostics-plain-output",
        "-std=iso9899:1999",
        "-pedantic-errors",
    ]
    more = dejagnu.read_test('/* { dg-additional-options "-Wall" } */\n')
    assert more.command(default=("-ansi",)) == ["-fdiagnostics-plain-output", "-ansi", "-Wall"]


def test_a_file_with_no_dg_options_gets_the_directory_default():
    test = dejagnu.read_test("/* { dg-do compile } */\nint i;\n")
    assert test.given == []
    assert test.command() == ["-fdiagnostics-plain-output", "-ansi", "-pedantic-errors"]


def test_dg_do_defaults_to_compile():
    assert dejagnu.read_test("int i;\n").do_what == "compile"
    assert dejagnu.read_test("/* { dg-do run } */\n").do_what == "run"


def test_a_dg_final_body_keeps_its_own_braces_out_of_the_way():
    test = dejagnu.read_test('/* { dg-final { scan-tree-dump-times "a {b}" 6 "fre1" } } */\n')
    assert test.finals == ['scan-tree-dump-times "a {b}" 6 "fre1"']


def test_an_unclosed_directive_is_an_error_and_not_a_shrug():
    with pytest.raises(HarnessError, match="unclosed directive"):
        dejagnu.read_test("/* { dg-do compile */\n")


def test_a_directive_the_model_does_not_act_on_is_reported_rather_than_dropped():
    test = dejagnu.read_test("/* { dg-require-effective-target lp64 } */\n")
    assert [d.name for d in test.unhandled] == ["dg-require-effective-target"]
    assert test.directives[0].args == ("lp64",)


# Matching output against expectations


STDERR = dedent(
    """
    <source>:5:17: error: flexible array member in a struct with no named members
    <source>:6:25: error: flexible array member in a struct with no named members
    <source>:7:17: error: flexible array member not at end of struct
    """
)


def test_every_expectation_that_matches_is_a_pass_and_the_run_is_clean():
    test = dejagnu.read_test(FLEX, path="gcc/testsuite/gcc.dg/c99-flex-array-1.c")
    got = dejagnu.check(test, STDERR)
    assert [o.state for o in got] == ["PASS", "PASS", "PASS", "PASS"]
    assert got[0].name == "gcc.dg/c99-flex-array-1.c (test for errors, line 5)"
    assert got[-1].name == "gcc.dg/c99-flex-array-1.c (test for excess errors)"


def test_a_diagnostic_on_the_wrong_line_does_not_match():
    test = dejagnu.read_test(FLEX)
    moved = STDERR.replace("<source>:7:", "<source>:8:")
    got = dejagnu.check(test, moved)
    assert [o.state for o in got] == ["PASS", "PASS", "FAIL", "FAIL"]


def test_one_diagnostic_cannot_satisfy_two_expectations():
    test = dejagnu.read_test('int i; /* { dg-error "boom" } */ /* { dg-error "boom" } */\n')
    got = dejagnu.check(test, "<source>:1:1: error: boom\n")
    assert [o.state for o in got] == ["PASS", "FAIL", "PASS"]


def test_an_unclaimed_diagnostic_fails_the_test_for_excess_errors():
    test = dejagnu.read_test(FLEX)
    extra = STDERR + "<source>:8:24: error: ISO C90 does not support flexible array members\n"
    assert dejagnu.check(test, extra)[-1].state == "FAIL"
    assert dejagnu.excess(test, extra) == [
        "<source>:8:24: error: ISO C90 does not support flexible array members"
    ]


def test_a_warning_does_not_satisfy_a_dg_error():
    test = dejagnu.read_test('int i; /* { dg-error "boom" } */\n')
    got = dejagnu.check(test, "<source>:1:1: warning: boom\n")
    assert [o.state for o in got] == ["FAIL", "FAIL"]


def test_dg_message_takes_a_diagnostic_of_any_kind():
    test = dejagnu.read_test('int i; /* { dg-message "boom" } */\n')
    assert dejagnu.check(test, "<source>:1:1: warning: boom\n")[0].state == "PASS"


def test_dg_bogus_passes_by_not_matching():
    test = dejagnu.read_test('void a() {} /* { dg-bogus "note" } */\n')
    assert [o.state for o in dejagnu.check(test, "")] == ["PASS", "PASS"]
    found = dejagnu.check(test, "<source>:1:1: note: nothing to see\n")
    assert [o.state for o in found] == ["FAIL", "PASS"]
    assert found[0].name.endswith("(test for bogus messages, line 1)")


def test_a_note_nobody_asked_for_is_pruned():
    test = dejagnu.read_test('int i; /* { dg-error "boom" } */\n')
    said = "<source>:1:1: error: boom\n<source>:1:1: note: because of this\n"
    assert test.prune_notes is True
    assert dejagnu.excess(test, said) == []


def test_one_dg_note_anywhere_turns_the_pruning_off_for_the_whole_file():
    test = dejagnu.read_test(
        'int i; /* { dg-error "boom" } */\nint j; /* { dg-note "here" } */\n',
    )
    assert test.prune_notes is False
    said = "<source>:1:1: error: boom\n<source>:2:1: note: here\n<source>:1:1: note: stray\n"
    assert dejagnu.excess(test, said) == ["<source>:1:1: note: stray"]


def test_dg_prune_output_deletes_what_it_names():
    test = dejagnu.read_test('/* { dg-prune-output "not at end" } */\n')
    assert dejagnu.excess(test, STDERR) == [
        "<source>:5:17: error: flexible array member in a struct with no named members",
        "<source>:6:25: error: flexible array member in a struct with no named members",
    ]


def test_output_that_is_not_a_diagnostic_is_pruned_when_it_is_context():
    kept = dejagnu.prune(["<source>: In function 'f':", "cc1: out of memory"])
    assert kept == ["cc1: out of memory"]


# dg-final


DUMP = "Replaced a\nReplaced b\nnothing\nReplaced c\n"


def test_scan_tree_dump_times_counts_and_names_itself_the_way_the_sum_does():
    test = dejagnu.read_test(
        '/* { dg-final { scan-tree-dump-times "Replaced " 3 "fre1" } } */\n',
        path="gcc/testsuite/gcc.dg/x.c",
    )
    got = dejagnu.scan(test, {"fre1": DUMP})
    assert got[0].state == "PASS"
    assert got[0].name == 'gcc.dg/x.c scan-tree-dump-times fre1 "Replaced " 3'
    wrong = dejagnu.read_test('/* { dg-final { scan-tree-dump-times "Replaced " 6 "fre1" } } */\n')
    assert dejagnu.scan(wrong, {"fre1": DUMP})[0].state == "FAIL"


def test_scan_tree_dump_and_its_not_variant_are_opposites():
    yes = dejagnu.read_test('/* { dg-final { scan-tree-dump "Replaced " "fre1" } } */\n')
    no = dejagnu.read_test('/* { dg-final { scan-tree-dump-not "Replaced " "fre1" } } */\n')
    assert dejagnu.scan(yes, {"fre1": DUMP})[0].state == "PASS"
    assert dejagnu.scan(no, {"fre1": DUMP})[0].state == "FAIL"
    assert dejagnu.scan(no, {"fre1": "nothing\n"})[0].state == "PASS"


def test_a_scan_with_no_dump_to_read_is_unresolved_and_says_which_one():
    test = dejagnu.read_test('/* { dg-final { scan-tree-dump-times "x" 1 "vect" } } */\n')
    got = dejagnu.scan(test, {"fre1": DUMP})
    assert got[0].state == "UNRESOLVED"
    assert "no vect dump here, have fre1" in got[0].name


def test_a_final_the_model_does_not_implement_says_so_rather_than_passing():
    test = dejagnu.read_test("/* { dg-final { cleanup-saved-temps } } */\n")
    assert dejagnu.scan(test, {})[0].state == "UNRESOLVED"


def test_the_dump_suffix_is_the_pass_name_with_every_modifier_taken_off():
    assert dejagnu.dump_suffix("-fdump-tree-fre1-details") == "fre1"
    assert dejagnu.dump_suffix("-fdump-tree-fre1") == "fre1"
    assert dejagnu.dump_suffix("-fdump-rtl-combine-details-blocks") == "combine"
    assert dejagnu.dump_suffix("-fdump-tree-optimized=stderr") == "optimized"
    with pytest.raises(HarnessError, match="not a dump flag"):
        dejagnu.dump_suffix("-O2")


# The torture loop


def test_a_file_with_a_loop_gets_the_longer_option_set():
    with_loop = dejagnu.torture_list("void f(){ for (;;) ; }")
    without = dejagnu.torture_list("int i;")
    assert len(with_loop) == len(without) == 6
    assert "-funroll-loops" in with_loop[3] and "-fpeel-loops" in with_loop[3]
    assert "-funroll-loops" not in without[3] and "-fpeel-loops" not in without[3]
    assert with_loop[:3] == without[:3]


def test_the_loop_test_is_a_glob_and_catches_things_that_are_not_loops():
    assert dejagnu.has_loop("__attribute__((format (printf, 1, 2)))") is True
    assert dejagnu.has_loop("while (x)") is True
    assert dejagnu.has_loop("int forward;") is False


# Running one test out of forty thousand


def test_the_runtestflags_filter_matches_the_file_name_only():
    names = ["gcc.dg/pr87309.c", "gcc.dg/torture/pr78517.c", "gcc.dg/uninit-1.c"]
    assert dejagnu.selected(names, "pr*.c") == names[:2]
    assert dejagnu.selected(names, "uninit-1.c") == names[2:]
    assert dejagnu.selected(names, "") == names


# The parallel race


NAMES = [f"t{n:02d}.c" for n in range(25)]


def test_when_every_process_enumerates_the_same_list_every_test_runs_once():
    found = dejagnu.race([NAMES, NAMES, NAMES])
    assert found.sound
    assert found.counts == {0: 10, 1: 10, 2: 5}


def test_one_process_that_enumerates_one_file_fewer_both_skips_and_duplicates():
    short = [n for n in NAMES if n != "t03.c"]
    found = dejagnu.race([NAMES, short, NAMES])
    assert not found.sound
    assert found.skipped == ["t10.c"]
    assert found.twice == ["t20.c"]


def test_who_wins_which_batch_does_not_change_the_answer_when_the_orders_agree():
    for winners in ([0, 0, 0], [2, 1, 0], [1, 1, 2]):
        assert dejagnu.race([NAMES, NAMES, NAMES], winners=winners).sound


def test_a_race_with_no_processes_is_an_error():
    with pytest.raises(HarnessError, match="no processes"):
        dejagnu.race([])


# Reading a .sum


SUM = dedent(
    """
    Running /work/gcc/testsuite/gcc.dg/dg.exp ...
    PASS: gcc.dg/c99-flex-array-1.c (test for errors, line 5)
    FAIL: gcc.dg/pr87309.c (test for bogus messages, line 4)
    UNSUPPORTED: gcc.dg/x.c
    \t\t=== gcc Summary ===
    """
)


def test_only_the_result_lines_come_out_of_a_sum():
    got = dejagnu.parse_sum(SUM)
    assert [o.state for o in got] == ["PASS", "FAIL", "UNSUPPORTED"]
    assert dejagnu.summarize(got) == {"FAIL": 1, "PASS": 1, "UNSUPPORTED": 1}


def test_a_test_that_stopped_running_is_not_a_regression_and_is_reported_separately():
    before = dejagnu.parse_sum("PASS: a\nPASS: b\nFAIL: c\n")
    after = dejagnu.parse_sum("FAIL: a\nPASS: d\nPASS: c\n")
    assert dejagnu.regressions(before, after) == {
        "worse": ["a"],
        "better": ["c"],
        "gone": ["b"],
        "new": ["d"],
    }


# Against the pinned tree


@needs_tree
def test_the_torture_list_is_still_the_one_in_gcc_dg_exp():
    text = (SUITE / "lib" / "gcc-dg.exp").read_text(encoding="utf-8")
    body = text.split("set DG_TORTURE_OPTIONS [list \\\n", 1)[1].split("]", 1)[0]
    found = [line.strip().strip("\\").strip().strip("{}").strip() for line in body.splitlines()]
    assert [one for one in found if one] == list(dejagnu.TORTURE)


@needs_tree
def test_the_directory_default_is_still_ansi_and_pedantic_errors():
    text = (SUITE / "gcc.dg" / "dg.exp").read_text(encoding="utf-8")
    assert 'set DEFAULT_CFLAGS " -ansi -pedantic-errors"' in text


@needs_tree
def test_every_flag_the_suite_always_passes_is_still_the_one_flag():
    text = (SUITE / "lib" / "prune.exp").read_text(encoding="utf-8")
    assert 'set TEST_ALWAYS_FLAGS "-fdiagnostics-plain-output $TEST_ALWAYS_FLAGS"' in text


@needs_tree
def test_notes_are_still_pruned_unless_a_dg_note_says_otherwise():
    text = (SUITE / "lib" / "gcc-dg.exp").read_text(encoding="utf-8")
    assert "proc dg-note { args } {" in text
    assert "set prune_notes 0" in text


# Against the recording


@needs_corpus
def test_the_recording_holds_twelve_compilations_of_the_pinned_release():
    corpus = dejagnu.load()
    assert len(corpus) == 12
    assert corpus.tag == "releases/gcc-16.2.0"
    assert corpus.compiler.startswith("gcc 16.2.0")


@needs_corpus
@needs_tree
def test_every_recorded_file_is_still_byte_for_byte_what_is_in_the_pinned_tree():
    for one in dejagnu.load():
        below = one.path.split("gcc/testsuite/", 1)[1]
        assert one.text == (SUITE / below).read_text(encoding="utf-8"), one.name


@needs_corpus
def test_the_recorded_tests_reach_the_verdicts_the_lesson_says_they_do():
    corpus = dejagnu.load()
    for name in ("flex", "assume", "bogus", "fre"):
        one = corpus[name]
        assert all(o.state == "PASS" for o in dejagnu.check(one.test, one.stderr)), name
    assert dejagnu.scan(corpus["fre"].test, corpus["fre"].dumps)[0].state == "PASS"


@needs_corpus
def test_the_same_test_under_the_wrong_standard_fails_on_the_line_it_left_alone():
    c90 = dejagnu.load()["flex-c90"]
    left = dejagnu.excess(c90.test, c90.stderr)
    assert len(left) == 4
    assert left[-1].startswith("<source>:8:")
    assert dejagnu.check(c90.test, c90.stderr)[-1].state == "FAIL"


@needs_corpus
def test_the_six_torture_compilations_are_the_six_option_sets_and_all_are_quiet():
    corpus = dejagnu.load()
    tortured = [corpus[f"torture-{n}"] for n in range(6)]
    assert [list(t.args[1:]) for t in tortured] == [
        one.split() for one in dejagnu.torture_list(tortured[0].text)
    ]
    assert all(t.returncode == 0 and not t.stderr for t in tortured)


@needs_corpus
def test_asking_the_corpus_for_something_it_does_not_have_lists_what_it_does():
    with pytest.raises(KeyError, match="torture-0"):
        dejagnu.load()["torture-9"]
