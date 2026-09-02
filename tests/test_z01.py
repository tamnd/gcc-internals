"""Z01 reads GCC's own source, which is the one thing in this project that nothing else checks.

Every other lesson rests on a recording of a compilation, and a recording is self describing:
if a dump changes shape the parser notices. An extract of source lines is not like that. It is
eighteen spans of plain text, and if one of them slides by four lines because somebody upstream
added a comment, the notebook prints something that is still valid C++, still nicely numbered,
and no longer the thing the prose is talking about.

Two mechanisms guard against that and they cover different halves. `refcheck` pins the hash of
each cited line, so a span that moves fails CI. These tests pin what the spans have to contain,
so a span that moves to somewhere that happens to hash differently still fails here with a
message that says which construct went missing.

The rest is the grader and the annotation, both of which are derived rather than keyed, so the
tests assert the derivation rather than the answers.
"""

from __future__ import annotations

import pytest
from conftest import grader

from gxray import glossary, source

LESSON = "z01-cpp-for-reading"
EXTRACT = "z01"

#: Every snippet the lesson reads, and the span it has to be. Written out rather than read
#: back from `record.py`, because a test that imports the thing it is checking agrees with it
#: by construction. If a GCC bump moves one of these, both files change and both changes are
#: visible in the diff.
SPANS = {
    "tree-union": ("gcc/tree-core.h", 2182, 2200),
    "tree-base": ("gcc/tree-core.h", 1138, 1160),
    "gimple-base": ("gcc/gimple.h", 220, 246),
    "gimple-subclass": ("gcc/gimple.h", 896, 905),
    "is-a-helper": ("gcc/gimple.h", 976, 982),
    "is_a": ("gcc/is-a.h", 224, 233),
    "as_a": ("gcc/is-a.h", 248, 257),
    "dyn_cast": ("gcc/is-a.h", 274, 286),
    "for-each-bb": ("gcc/basic-block.h", 208, 216),
    "vec-strategies": ("gcc/vec.h", 72, 89),
    "vec-declaration": ("gcc/vec.h", 446, 458),
    "hash-map": ("gcc/hash-map.h", 35, 45),
    "poly-int": ("gcc/poly-int.h", 374, 387),
    "includes": ("gcc/tree-ssa-ccp.cc", 121, 132),
    "ccp-read": ("gcc/tree-ssa-ccp.cc", 280, 319),
    "ccp-walk": ("gcc/tree-ssa-ccp.cc", 900, 930),
    "ccp-dump": ("gcc/tree-ssa-ccp.cc", 566, 570),
    "ccp-pass": ("gcc/tree-ssa-ccp.cc", 3042, 3060),
}

#: A line each snippet has to still contain. This is the half `refcheck` cannot do: it knows
#: the bytes at a line number, and this knows what the lesson says is there.
LANDMARKS = {
    "tree-union": 'desc ("tree_node_structure (&%h)")',
    "tree-base": "ENUM_BITFIELD(tree_code) code : 16;",
    "gimple-base": "ENUM_BITFIELD(gimple_code) code : 8;",
    "gimple-subclass": "gcond : public gimple_statement_with_ops",
    "is-a-helper": "return gs->code == GIMPLE_ASSIGN;",
    "is_a": "return is_a_helper<T>::test (p);",
    "as_a": "gcc_checking_assert (is_a <T> (p));",
    "dyn_cast": "if (is_a <T> (p))",
    "for-each-bb": "#define FOR_EACH_BB_FN(BB, FN)",
    "vec-strategies": "allocation is done using ggc_alloc/ggc_free",
    "vec-declaration": "struct GTY((user)) vec",
    "hash-map": "class GTY((user)) hash_map",
    "poly-int": "class poly_int",
    "includes": '#include "coretypes.h"',
    "ccp-read": "stmt = SSA_NAME_DEF_STMT (var);",
    "ccp-walk": "for (i = gsi_start_bb (bb); !gsi_end_p (i); gsi_next (&i))",
    "ccp-dump": "if (dump_file && (dump_flags & TDF_DETAILS))",
    "ccp-pass": '"ccp", /* name */',
}

#: The twelve the boss fight asks about, in the order it asks them, with the answer. This is
#: the one place the answers are written down, and the grader is not allowed to read it.
BOSS = [
    ("gcc/basic-block.h", 209, "loop"),
    ("gcc/is-a.h", 282, "cast"),
    ("gcc/poly-int.h", 377, "poly"),
    ("gcc/tree-core.h", 2185, "gty"),
    ("gcc/tree-ssa-ccp.cc", 121, "include"),
    ("gcc/tree-ssa-ccp.cc", 286, "treemacro"),
    ("gcc/tree-ssa-ccp.cc", 288, "gimple"),
    ("gcc/tree-ssa-ccp.cc", 304, "wide"),
    ("gcc/tree-ssa-ccp.cc", 566, "dump"),
    ("gcc/tree-ssa-ccp.cc", 905, "gsi"),
    ("gcc/tree-ssa-ccp.cc", 3042, "pass"),
    ("gcc/vec.h", 455, "vec"),
]


@pytest.fixture(scope="module")
def cuts():
    return source.load_extract(EXTRACT)


@pytest.fixture(scope="module")
def grade():
    return grader(LESSON)


# The extract


def test_every_snippet_is_where_the_recorder_says(cuts):
    """The eighteen spans, exactly.

    A snippet that has quietly grown or shrunk is a snippet whose prose is now describing a
    different number of lines, and the numbered listing in the notebook would show it without
    anything failing.
    """
    got = {s.name: (s.path, s.first, s.last) for s in cuts}
    assert got == SPANS


def test_every_snippet_still_contains_the_line_it_is_about(cuts):
    """The landmark check, which is the half refcheck cannot do.

    refcheck proves the bytes at a line number have not changed. It cannot prove those bytes
    are the ones the lesson claims, because it has never read the prose. If GCC reorganizes a
    header and a span lands on a different but equally valid piece of code, refcheck fails on
    the hash and this fails with the name of the thing that went missing, which is the more
    useful message of the two.
    """
    missing = [name for name, text in LANDMARKS.items() if text not in cuts[name].text]
    assert not missing


def test_the_line_count_matches_the_spans(cuts):
    """`lines()` is printed in the notebook and in the recorder, so it is a fact now."""
    assert cuts.lines() == sum(last - first + 1 for _, first, last in SPANS.values())
    assert len(cuts) == 18
    assert len(cuts.files) == 8


def test_the_extract_is_pinned_to_the_tag_the_project_is_pinned_to(cuts):
    """One tag per site version. A snippet cut from a different tree is not evidence."""
    from tools.refcheck import PINNED_TAG

    assert cuts.tag == PINNED_TAG
    assert all(s.citation.endswith("@" + PINNED_TAG) for s in cuts)


def test_a_citation_is_the_path_and_the_first_line(cuts):
    """The citation travels with the snippet, so the notebook cannot cite the wrong span."""
    for snippet in cuts:
        assert snippet.citation.startswith(f"{snippet.path}:{snippet.first}@")


# The constructs


def test_there_are_seventeen_constructs_and_the_lesson_says_seventeen(cuts):
    """The count is in the prose four times, so it is worth one assertion."""
    assert len(source.IDIOMS) == 17
    assert len(source.KEYS) == 17
    assert len(set(source.KEYS)) == 17


def test_every_construct_appears_somewhere_in_the_extract(cuts):
    """The notebook asserts this in a cell, which means a failure is a broken lesson.

    Catching it here instead gives a message naming the construct rather than a stack trace
    out of a notebook execution, and it catches it before the notebook is built.
    """
    seen = {key for s in cuts for keys in source.annotate(s).values() for key in keys}
    assert sorted(seen) == sorted(source.KEYS)


def test_comments_are_not_searched_for_constructs():
    """The reason `code_only` exists.

    GCC's comments quote the code they are about. `gimple.h:897` is a comment saying
    `stmt->code == GIMPLE_COND`, four lines above the struct that guarantees it. Pointing at
    that line and calling it a tag test is a wrong answer that looks right, so the annotator
    blanks comments out first.
    """
    lines = [
        "/* A statement with the invariant that",
        "     stmt->code == GIMPLE_COND",
        "   i.e. a conditional jump statement.  */",
        "  return gs->code == GIMPLE_ASSIGN;",
    ]
    bare = source.code_only(lines)
    assert len(bare) == len(lines)
    assert source.idioms(bare[1]) == []
    assert "code" in source.idioms(bare[3])


def test_a_comment_that_starts_and_ends_on_one_line_is_also_stripped():
    """The single line case, which is a different branch from the block case."""
    (bare,) = source.code_only(["  int n = 0;  /* stmt->code == GIMPLE_COND */"])
    assert "GIMPLE_COND" not in bare
    assert "int n = 0;" in bare


def test_annotate_reports_line_numbers_in_the_file_not_in_the_snippet(cuts):
    """A margin note against line 3 of a snippet is useless. It has to be the file's line."""
    marks = source.annotate(cuts["ccp-read"])
    assert marks
    assert min(marks) >= cuts["ccp-read"].first
    assert max(marks) <= cuts["ccp-read"].last


def test_every_construct_has_a_name_and_a_sentence():
    """Both are printed in the notebook and in the grader's feedback."""
    for key in source.KEYS:
        assert source.named(key)
        assert source.explain(key).endswith(".")


# Rendering


def test_numbered_uses_the_files_own_line_numbers(cuts):
    """The whole point of the listing. A reader has to be able to open the file and look."""
    snippet = cuts["ccp-pass"]
    first, *_, last = snippet.numbered().splitlines()
    assert first.strip().startswith(str(snippet.first))
    assert last.strip().startswith(str(snippet.last))


def test_numbered_expands_tabs_and_the_stored_lines_do_not(cuts):
    """GCC indents with real tabs at eight columns.

    The stored lines keep them, because refcheck hashes the file's bytes and a snippet that
    had been detabbed would not match. The rendering expands them, because a notebook that
    printed them raw shows the reader something with its indentation shredded.
    """
    tabbed = [s for s in cuts if any("\t" in line for line in s.lines)]
    assert tabbed, "no snippet has a tab in it, so this test is no longer testing anything"
    assert all("\t" not in s.numbered() for s in tabbed)


def test_a_margin_note_lands_on_the_line_it_is_for(cuts):
    """The marks are how the T0 exercise works, so they have to be on the right rows."""
    snippet = cuts["tree-base"]
    shown = snippet.numbered({1139: "the tag"})
    (row,) = [line for line in shown.splitlines() if line.strip().startswith("1139")]
    assert row.endswith("<-- the tag")
    assert "ENUM_BITFIELD" in row


# The glossary


def test_z01_terms_are_in_the_glossary():
    """The notebook links to six terms, and a link into the glossary has to resolve."""
    wanted = {
        "gengtype",
        "garbage collector",
        "checking build",
        "current function",
        "poly_int",
        "wide_int",
    }
    assert wanted <= set(glossary.names())
    assert all(glossary.get(name).met == "Z01" for name in wanted)


def test_reading_the_source_comes_first_in_the_glossary():
    """Z01 is the first lesson in the book, so its group is the first group on the page."""
    assert glossary.GROUPS[0].title == "Reading the source"


# The boss fight


def test_the_boss_fight_asks_about_twelve_lines(grade):
    """Twelve, because the spec says twelve, and the prose in three places says twelve."""
    cuts = source.load_extract(EXTRACT)
    rows = grade.questions(cuts)
    assert len(rows) == 12
    assert [(path, line, key) for path, line, _, key in rows] == BOSS


def test_no_question_has_two_right_answers(grade):
    """A line with two constructs on it is a bad question, so the grader does not use one."""
    cuts = source.load_extract(EXTRACT)
    for path, line, _, key in grade.questions(cuts):
        snippet = next(s for s in cuts if s.path == path and s.first <= line <= s.last)
        assert source.annotate(snippet)[line] == [key]


def test_the_questions_are_not_in_the_order_of_the_table(grade):
    """Otherwise the answer is the first twelve rows of a table printed earlier in the lesson."""
    cuts = source.load_extract(EXTRACT)
    asked = [key for *_, key in grade.questions(cuts)]
    assert asked != [key for key in source.KEYS if key in asked]


def test_the_grader_says_which_constructs_it_did_not_ask_about(grade):
    """Five are left out and the report says so, rather than letting the reader assume."""
    cuts = source.load_extract(EXTRACT)
    assert grade.skipped(cuts) == ["hash", "assert", "code", "template", "bitfield"]


def test_a_perfect_answer_passes(grade):
    assert grade.main(["--says", ",".join(key for *_, key in BOSS)]) == 0


def test_the_key_order_is_not_the_answer(grade):
    """The order of the table would be an easy wrong guess, so it has to actually be wrong."""
    table = sorted({key for *_, key in BOSS}, key=source.KEYS.index)
    assert grade.main(["--says", ",".join(table)]) == 1


def test_one_wrong_answer_fails(grade):
    said = [key for *_, key in BOSS]
    said[0] = "gsi"
    assert grade.main(["--says", ",".join(said)]) == 1


def test_answers_may_be_typed_with_spaces_or_commas(grade):
    """Nobody should fail the exam on punctuation."""
    keys = [key for *_, key in BOSS]
    assert grade.main(["--says", " ".join(keys)]) == 0
    assert grade.main(["--says", ", ".join(k.upper() for k in keys)]) == 0


def test_saying_nothing_fails_rather_than_crashing(grade):
    """The grader runs under CI with no tty, so an unanswered question has to score zero."""
    assert grade.main([]) == 1
