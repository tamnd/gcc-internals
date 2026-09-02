"""Z02 is a map of a tree that is not in the repository, which is a specific kind of fragile.

Every number the notebook prints comes out of `corpora/layout/gcc.json`, and that file is a
recording. Nothing about reading a recording can tell you the recording is still true. The
guards are in three layers and they cover different failures.

`refcheck` pins the bytes at every cited line, and `record.py` writes each citation out as a
literal string so refcheck can see it. That catches a span that slid. These tests pin what the
map has to say: the shape of the six scavenger hunt items, the spans the prose walks through,
and the landmark line inside each one. That catches a span that moved somewhere plausible.
And the recorder itself refuses to write a file it cannot fully resolve, which catches the
pass table drifting out from under the lesson.

The counts are deliberately not pinned to exact numbers here. They move with every GCC bump and
an assertion on 86075 would fail on a bump for no reason a reader cares about. What is pinned is
the shape: the ordering, the ratios the prose relies on, and the facts the claims state.
"""

from __future__ import annotations

import pytest
from conftest import grader

from gxray import glossary, layout, source

LESSON = "z02-where-things-are"
EXTRACT = "z02"

#: Every span the notebook reads, and the lines it has to be. Written out rather than imported
#: from `record.py`, because a test that reads its expectations out of the thing it is checking
#: agrees with it by construction and proves nothing.
SPANS = {
    "def": ("gcc/tree.def", 295, 298),
    "md": ("gcc/config/aarch64/aarch64.md", 2965, 2979),
    "opt": ("gcc/common.opt", 3220, 3226),
    "pd": ("gcc/match.pd", 236, 239),
    "pass-data": ("gcc/tree-pass.h", 39, 47),
    "passes": ("gcc/passes.def", 80, 88),
    "make": ("gcc/tree-ssa-ccp.cc", 3082, 3086),
    "loops": ("gcc/cfgloop.cc", 160, 166),
    "merge": ("gcc/tree-cfg.cc", 1979, 1981),
    "simulate": ("gcc/tree-ssa-propagate.cc", 484, 488),
    "block": ("gcc/tree-cfg.cc", 2191, 2196),
    "genmatch": ("gcc/genmatch.cc", 911, 915),
}

#: The line each span exists for. If GCC reorganizes and a span lands on different but equally
#: valid code, refcheck fails on the hash and this fails with the name of what went missing.
LANDMARKS = {
    "def": "DEFTREECODE (INTEGER_CST",
    "md": 'define_insn "add<mode>3_compare0"',
    "opt": "ftree-ccp",
    "pd": "(op @0 integer_zerop)",
    "pass-data": "const char *name;",
    "passes": "NEXT_PASS (pass_ccp",
    "make": "make_pass_ccp (gcc::context *ctxt)",
    "loops": ";; %d loops found",
    "merge": '"Merging blocks %d and %d\\n"',
    "simulate": '"\\nSimulating statement: "',
    "block": '"Removing basic block %d\\n"',
    "genmatch": "Applying pattern",
}

#: The six hunt items, in the order the grader asks them, with the answer and the route. The
#: two with a year are the two a checkout cannot answer.
HUNT = [
    ("loops", "grep", "gcc/cfgloop.cc", 163, ""),
    ("merge", "grep", "gcc/tree-cfg.cc", 1980, ""),
    ("simulate", "grep", "gcc/tree-ssa-propagate.cc", 486, ""),
    ("ccp", "passes", "gcc/tree-ssa-ccp.cc", 3083, ""),
    ("block", "history", "gcc/tree-cfg.cc", 2193, "2004"),
    ("pattern", "generated", "gcc/match.pd", 239, "2014"),
]

#: A right answer for each, in the order asked, in the format the grader accepts.
RIGHT = [
    "gcc/cfgloop.cc:163",
    "gcc/tree-cfg.cc:1980",
    "gcc/tree-ssa-propagate.cc:486",
    "gcc/tree-ssa-ccp.cc:3083",
    "gcc/tree-cfg.cc:2193:2004",
    "gcc/match.pd:239:2014",
]


@pytest.fixture(scope="module")
def tree():
    return layout.load()


@pytest.fixture(scope="module")
def cuts():
    return source.load_extract(EXTRACT)


@pytest.fixture(scope="module")
def grade():
    return grader(LESSON)


# The extract


def test_every_span_is_where_the_recorder_says(cuts):
    got = {s.name: (s.path, s.first, s.last) for s in cuts}
    assert got == SPANS


def test_every_span_still_contains_the_line_it_is_about(cuts):
    missing = [name for name, text in LANDMARKS.items() if text not in cuts[name].text]
    assert not missing


def test_the_extract_is_pinned_to_the_tag_the_project_is_pinned_to(cuts, tree):
    """One tag for the spans and the map, or the notebook is quoting two different trees."""
    from tools.refcheck import PINNED_TAG

    assert cuts.tag == PINNED_TAG
    assert tree.tag == PINNED_TAG
    assert all(s.citation.endswith("@" + PINNED_TAG) for s in cuts)


def test_the_map_records_which_commit_it_was_cut_from(tree):
    """A tag can be moved. The commit under it is what makes the recording reproducible."""
    assert len(tree.commit) == 40
    assert all(c in "0123456789abcdef" for c in tree.commit)


# The places


def test_the_top_level_adds_up_to_the_whole_tree(tree):
    """`Layout.lines` sums the top level rows, so a place with a slash must not be in that sum.

    The `gcc/*` row is inside `gcc`, and the `gcc/cp` row is inside `gcc` as well. Counting
    either into the total would double count, and the notebook prints the total.
    """
    top = [p for p in tree.places if "/" not in p.path]
    assert tree.lines == sum(p.lines for p in top)
    assert tree.files == sum(p.files for p in top)
    assert tree.lines > sum(p.lines for p in tree.places if p.path.startswith("gcc/"))


def test_there_is_a_row_for_everything_at_the_top_level(tree):
    """The lesson says the total is the real total, so nothing may be quietly left out."""
    assert tree.place("the rest").lines > 0
    assert tree.place("the rest").files > 0


def test_gcc_is_most_of_the_tree_and_the_compiler_is_less_than_half(tree):
    """Two claims in the notebook, both of which are ratios rather than round numbers."""
    whole = tree.place("gcc")
    tests = tree.place("gcc/testsuite")
    assert 70 <= 100 * whole.lines // tree.lines <= 80
    assert 4_000_000 < whole.lines - tests.lines < 5_500_000


def test_the_tests_are_smaller_than_the_compiler_and_far_more_numerous(tree):
    """The claim that replaced a wrong one. Tests are short files, and there are a lot of them."""
    whole = tree.place("gcc")
    tests = tree.place("gcc/testsuite")
    theirs = whole.files - tests.files
    assert tests.lines < whole.lines - tests.lines
    assert tests.files // theirs >= 10
    assert tests.files > tree.files - tests.files


def test_the_middle_end_has_no_directory_of_its_own(tree):
    """The claim in the second section, and the reason `gcc/*` is a row at all."""
    loose = tree.place("gcc/*")
    assert loose.files > 500
    assert loose.lines > 1_000_000
    assert not any(p.path in ("gcc/middle-end", "gcc/optimize") for p in tree.places)


def test_every_place_has_a_sentence_ending_in_a_full_stop(tree):
    for place in tree.places:
        assert place.about
        assert place.about.endswith(".")


def test_a_place_that_is_not_there_says_what_is(tree):
    with pytest.raises(KeyError, match="gcc/testsuite"):
        tree.place("gcc/middle-end")


# The extensions


def test_there_is_exactly_one_pd_file_and_it_is_match_pd(tree):
    """The claim, and the one extension in the list that is a single file."""
    assert tree.kind(".pd").count == 1
    assert tree.kind(".pd").example.startswith("gcc/match.pd:")


def test_md_is_not_markdown_and_there_are_hundreds(tree):
    """The trap the section exists for."""
    assert tree.kind(".md").count > 100
    assert "markdown" in tree.kind(".md").about.lower()
    assert tree.kind(".md").example.startswith("gcc/config/")


def test_every_extension_has_an_example_with_a_line_number(tree):
    for kind in tree.kinds:
        path, _, line = kind.example.rpartition(":")
        assert path
        assert line.isdigit()


# The ports


def test_three_directories_under_config_are_not_ports(tree):
    """The claim. The count everybody quotes counts directories, and it is the wrong count."""
    assert sorted(tree.portless) == ["mingw", "vms", "vxworks"]
    assert len(tree.ports) + len(tree.portless) == 52
    assert "aarch64" in tree.ports
    assert "mingw" not in tree.ports


# The generated files


def test_a_numbered_split_file_resolves_to_what_it_was_generated_from():
    """`gimple-match-6.cc` is the name in a real dump line and is not in the tree."""
    assert layout.generated("gimple-match-6.cc") == "gcc/match.pd"
    assert layout.generated("gcc/gimple-match.cc") == "gcc/match.pd"
    assert layout.generated("generic-match-3.cc") == "gcc/match.pd"


def test_a_checked_in_file_is_not_reported_as_generated():
    """The common answer, and it has to be None rather than an empty string."""
    assert layout.generated("tree-cfg.cc") is None
    assert layout.generated("gcc/tree-ssa-ccp.cc") is None


def test_every_generator_says_what_it_reads_and_what_it_writes(tree):
    assert len(tree.generators) >= 10
    for gen in tree.generators:
        assert gen.program.startswith("gcc/gen")
        assert gen.reads
        assert gen.writes


def test_the_generated_table_covers_what_the_generators_write(tree):
    """A reader who is sent to `insn-recog.cc` has to get an answer, not a shrug."""
    for name in ("insn-recog.cc", "insn-emit.cc", "insn-modes.cc", "options.cc", "tm.h"):
        assert layout.generated(name)


# The pass table


def test_every_pass_in_passes_def_resolves_to_a_file_and_a_dump_name(tree):
    """The claim. It was 267 of 297 before the recorder learned to follow constructors."""
    assert len(tree.passes) > 250
    unresolved = [p.name for p in tree.passes if not p.path or not p.line or not p.dump]
    assert not unresolved


def test_the_pass_a_dump_file_name_points_at(tree):
    """The chain the whole lesson is built around, on the example the prose uses."""
    found = tree.find("ccp2")
    assert found.name == "pass_ccp"
    assert found.path == "gcc/tree-ssa-ccp.cc"
    assert found.citation == "gcc/tree-ssa-ccp.cc:3083"


def test_the_run_number_comes_off_before_the_lookup(tree):
    """Dump files are numbered per run, and the number is not part of the name."""
    assert tree.find("ccp") is tree.find("ccp2") or tree.find("ccp").name == "pass_ccp"
    for name in ("fre3", "dom2", "cddce1", "vrp2"):
        assert tree.find(name).name.startswith("pass_")


def test_a_pass_whose_dump_name_really_ends_in_a_digit_still_resolves(tree):
    """`switchlower1` is a real dump name and stripping the 1 has to not lose it."""
    assert tree.find("switchlower1").name == "pass_lower_switch"


def test_a_dump_name_nothing_produces_says_so(tree):
    with pytest.raises(KeyError, match="passes are recorded"):
        tree.find("no_such_pass")


def test_two_passes_may_share_a_dump_name(tree):
    """The whole program and the per function version of a pass write into the same dump."""
    sharing = [p for p in tree.passes if p.dump == "sra"]
    assert len(sharing) == 2
    assert {p.name for p in sharing} == {"pass_sra", "pass_ipa_sra"}


# The largest files


def test_the_largest_file_is_a_hand_written_parser(tree):
    """The claim at the end. The intuition is that the biggest file must be generated."""
    biggest = tree.biggest[0]
    assert biggest.path == "gcc/cp/parser.cc"
    assert layout.generated(biggest.path) is None
    assert biggest.lines > 40_000


def test_the_biggest_files_are_in_order_and_each_has_a_reason(tree):
    sizes = [big.lines for big in tree.biggest]
    assert sizes == sorted(sizes, reverse=True)
    for big in tree.biggest:
        assert big.about.endswith(".")


def test_the_short_files_worth_starting_on_are_actually_short(tree):
    """Two of them are not short and are listed as a warning, so this checks the first four."""
    assert tree.notable[0].path == "gcc/passes.def"
    assert all(one.lines < 4000 for one in tree.notable[:4])


# The scavenger hunt


def test_the_hunt_asks_six_things_in_a_fixed_order(tree):
    got = [(c.key, c.route, c.path, c.line, c.date[:4] if c.commit else "") for c in tree.hunt]
    assert got == HUNT


def test_exactly_two_of_them_need_the_history(tree):
    """The spec asks for two that a checkout cannot answer, which is the point of the exercise."""
    historic = [c for c in tree.hunt if c.historic]
    assert len(historic) == 2
    for clue in historic:
        assert len(clue.commit) >= 12
        assert clue.author
        assert clue.subject


def test_every_route_the_hunt_names_is_a_route_that_exists(tree):
    for clue in tree.hunt:
        assert clue.route in layout.ROUTE_KEYS
        name, command, about = layout.route(clue.route)
        assert name and command and about


def test_the_routes_between_them_cover_four_different_kinds_of_answer(tree):
    """A hunt where every item is a grep teaches one route, which is not the lesson."""
    assert len({c.route for c in tree.hunt}) == 4


def test_an_unknown_route_says_which_ones_there_are():
    with pytest.raises(KeyError, match="grep"):
        layout.route("google")


def test_the_text_a_clue_points_at_is_the_line_the_span_shows(tree, cuts):
    """The clue's `text` is the line at `path:line`, so the two records cannot disagree."""
    named = {s.name for s in cuts}
    for clue in tree.hunt:
        if clue.key not in named:
            continue
        snippet = cuts[clue.key]
        assert snippet.path == clue.path
        assert snippet.first <= clue.line <= snippet.last
        assert clue.text.strip() in snippet.text


# The grader


def test_a_perfect_answer_passes(grade):
    assert grade.main(["--says", ",".join(RIGHT)]) == 0


def test_the_right_line_without_the_year_fails_on_the_two_historic_ones(grade):
    """Those two are the exercise. Getting the line from a grep is not the answer."""
    said = list(RIGHT)
    said[4] = "gcc/tree-cfg.cc:2193"
    assert grade.main(["--says", ",".join(said)]) == 1


def test_the_wrong_year_fails(grade):
    said = list(RIGHT)
    said[4] = "gcc/tree-cfg.cc:2193:2014"
    assert grade.main(["--says", ",".join(said)]) == 1


def test_a_line_a_few_off_still_counts(grade):
    """Pointing at the `if (dump_file)` above the `fprintf` is finding it."""
    said = list(RIGHT)
    said[1] = "gcc/tree-cfg.cc:1979"
    assert grade.main(["--says", ",".join(said)]) == 0


def test_a_line_well_off_does_not(grade):
    said = list(RIGHT)
    said[1] = "gcc/tree-cfg.cc:1950"
    assert grade.main(["--says", ",".join(said)]) == 1


def test_the_right_line_in_the_wrong_file_fails(grade):
    """`Simulating statement` in `tree-ssa-ccp.cc` is the wrong answer this item is built on."""
    said = list(RIGHT)
    said[2] = "gcc/tree-ssa-ccp.cc:486"
    assert grade.main(["--says", ",".join(said)]) == 1


def test_a_leading_dot_slash_is_forgiven(grade):
    """Nobody should fail on how their shell completed the path."""
    said = ["./" + one for one in RIGHT]
    assert grade.main(["--says", ",".join(said)]) == 0


def test_answers_may_be_separated_by_spaces(grade):
    assert grade.main(["--says", " ".join(RIGHT)]) == 0


def test_something_that_is_not_a_path_and_a_line_fails_rather_than_crashing(grade):
    said = list(RIGHT)
    said[0] = "somewhere in cfgloop"
    assert grade.main(["--says", ",".join(said)]) == 1


def test_saying_nothing_fails_rather_than_crashing(grade):
    """The grader runs under CI with no tty, so an unanswered question has to score zero."""
    assert grade.main([]) == 1


# The glossary


def test_z02_adds_three_terms_and_links_four_it_did_not():
    """The three the lesson earns, and the ones it borrows from lessons further on.

    Borrowing forward is fine and the link resolves either way. What is not fine is a lesson
    claiming to introduce a word that another lesson already introduced, so the `met` field is
    checked in both directions.
    """
    mine = {name for name in glossary.names() if glossary.get(name).met == "Z02"}
    assert mine == {"generated file", "port", "target hook"}

    borrowed = {"machine description", "dump file", "pass manager", "pass"}
    assert borrowed <= set(glossary.names())
    assert not any(glossary.get(name).met == "Z02" for name in borrowed)


def test_finding_things_comes_second_in_the_glossary():
    """Z01 then Z02, the same order the course is in."""
    assert [group.title for group in glossary.GROUPS[:2]] == [
        "Reading the source",
        "Finding things in the tree",
    ]
