"""The lesson builder.

Most of this is about the two properties that make the pipeline worth having: a rebuild
produces the same bytes, and a claim without a runnable cell under it fails the build. The
rest is the small stuff that is easy to get wrong once and then never look at again, like
what happens to a cell that is accidentally empty.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.nbbuild import Lesson, Malformed
from tools.nbbuild.claims import UNOBSERVABLE_CAP, Claim, TooMany, Unproved, headings, resolve
from tools.nbbuild.notebook import Cell, as_lines, document

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def lesson(tmp_path: Path) -> Lesson:
    """A lesson that writes into a temp directory rather than into the repository."""
    (tmp_path / "lessons").mkdir()
    (tmp_path / "pyproject.toml").write_text("")
    return Lesson("t99-a-test", "t99", root=tmp_path)


def test_a_line_keeps_its_newline_except_the_last_one():
    assert as_lines("a\nb\nc") == ["a\n", "b\n", "c"]
    assert "".join(as_lines("a\nb")) == "a\nb"


def test_an_empty_source_is_no_lines_rather_than_one_blank_one():
    assert as_lines("\n\n") == []


def test_a_code_cell_has_no_outputs_and_no_execution_count():
    cell = Cell("code", "t99-01", "print(1)").as_json()
    assert cell["outputs"] == []
    assert cell["execution_count"] is None


def test_a_markdown_cell_has_neither():
    cell = Cell("markdown", "t99-01", "hello").as_json()
    assert "outputs" not in cell
    assert "execution_count" not in cell


def test_keys_come_out_in_the_order_jupyter_writes_them():
    """So that opening a lesson and saving it does not reorder the whole file."""
    cell = Cell("code", "t99-01", "print(1)").as_json()
    assert list(cell) == sorted(cell)


def test_the_notebook_is_json_colab_will_open():
    book = json.loads(document([Cell("markdown", "t99-01", "hi")]))
    assert book["nbformat"] == 4
    assert book["metadata"]["kernelspec"]["name"] == "python3"
    assert "colab" in book["metadata"]


def test_cell_ids_are_counted_rather_than_typed(lesson):
    lesson.md("one")
    lesson.code("two")
    lesson.md("three")
    assert [c.ident for c in lesson.cells] == ["t99-01", "t99-02", "t99-03"]


def test_an_empty_cell_is_refused(lesson):
    with pytest.raises(Malformed):
        lesson.md("   \n\n  ")


def test_an_em_dash_is_refused(lesson):
    with pytest.raises(Malformed) as exc:
        lesson.md("a sentence — with punctuation this project does not use")
    assert "em dash" in str(exc.value)


def test_the_colab_badge_points_at_this_lesson(lesson):
    assert "lessons/t99-a-test/t99.ipynb" in lesson.badge
    assert lesson.badge.startswith("[![Open In Colab]")


def test_a_citation_becomes_a_link_labelled_with_itself(lesson):
    link = lesson.cite("gcc/passes.cc:854@releases/gcc-16.2.0")
    assert link.startswith("[`gcc/passes.cc:854@releases/gcc-16.2.0`]")
    assert "gcc-mirror/gcc/blob/releases/gcc-16.2.0/gcc/passes.cc#L854" in link


def test_a_malformed_citation_fails_while_the_lesson_is_being_built(lesson):
    with pytest.raises(Exception, match="is not a citation"):
        lesson.cite("passes.cc, somewhere near the top")


def test_a_glossary_term_becomes_a_link(lesson):
    assert lesson.term("phi node") == (
        "[phi node](https://github.com/tamnd/gcc-internals/blob/main/GLOSSARY.md#phi-node)"
    )


def test_a_term_that_does_not_exist_fails_the_build(lesson):
    with pytest.raises(KeyError):
        lesson.term("monomorphic inline cache")


def test_a_version_note_shows_up_under_the_cell(lesson):
    lesson.code("print(1)", differs="older GCC prints this differently")
    assert len(lesson.cells) == 2
    assert lesson.cells[1].kind == "markdown"
    assert "Version note" in lesson.cells[1].source


def test_a_quiet_version_note_does_not(lesson):
    lesson.code("print(1)", differs="said once at the top of the lesson", quiet=True)
    assert len(lesson.cells) == 1


def test_a_cell_cannot_be_both_kinds_of_note(lesson):
    with pytest.raises(Malformed):
        lesson.code("print(1)", differs="one", varies="the other")


def test_building_twice_gives_the_same_bytes(lesson):
    """The property the whole committed notebook arrangement rests on."""

    def build() -> str:
        one = Lesson("t99-a-test", "t99", root=lesson.root)
        one.md("# T99. A test")
        one.setup()
        one.code("print(1)")
        return one.document()

    assert build() == build()


def test_save_writes_the_notebook_and_check_agrees_with_it(lesson, capsys):
    lesson.md("# T99. A test")
    lesson.code("print(1)")
    assert lesson.save([]) == 0
    assert lesson.path.exists()
    assert lesson.save(["--check"]) == 0


def test_check_fails_when_the_committed_notebook_has_drifted(lesson):
    lesson.md("# T99. A test")
    lesson.code("print(1)")
    lesson.save([])
    lesson.path.write_text(lesson.path.read_text().replace("print(1)", "print(2)"))
    assert lesson.save(["--check"]) == 1


def test_check_fails_when_the_notebook_was_never_built(lesson):
    lesson.md("# T99. A test")
    lesson.code("print(1)")
    assert lesson.save(["--check"]) == 1


# The claim ledger.


def test_a_heading_inside_a_fence_is_not_a_heading():
    """A lesson quoting a dump or a shell session is full of lines starting with a hash."""
    fence = "```text\n# not a heading\n```\n"
    assert headings(fence + "# a heading\n") == [len(fence)]


def test_a_claim_reads_the_same_as_the_sentence_would_have(lesson):
    text = "the loop is gone by the time tree-optimized runs"
    assert lesson.claim(text) == text


def test_a_claim_is_proved_by_the_next_code_cell(lesson):
    lesson.md(f"## A section\n\n{lesson.claim('five blocks go in')}, which is the point.")
    lesson.code("print(1)")
    (found,) = resolve(lesson.claims, lesson.cells)
    assert found.evidence == "t99-02"


def test_a_claim_with_no_cell_at_all_fails(lesson):
    lesson.md(f"## A section\n\n{lesson.claim('five blocks go in')}.")
    lesson.md("## The next section")
    with pytest.raises(Unproved) as exc:
        resolve(lesson.claims, lesson.cells)
    assert "five blocks go in" in str(exc.value)


def test_a_claim_proved_after_the_next_heading_does_not_count(lesson):
    """Because nobody reading the paragraph is going to find that cell."""
    lesson.md(f"## A section\n\n{lesson.claim('five blocks go in')}.")
    lesson.md("## Something else")
    lesson.code("print(1)")
    with pytest.raises(Unproved):
        resolve(lesson.claims, lesson.cells)


def test_a_heading_at_the_end_of_the_claims_own_cell_still_counts(lesson):
    """Prose cells routinely end on the heading that opens the next section."""
    lesson.md(f"{lesson.claim('five blocks go in')}.\n\n## Something else")
    lesson.code("print(1)")
    with pytest.raises(Unproved):
        resolve(lesson.claims, lesson.cells)


def test_an_unobservable_claim_needs_no_cell(lesson):
    lesson.md(lesson.claim("the gimplifier is one switch", unobservable="you need a debugger"))
    (found,) = resolve(lesson.claims, lesson.cells)
    assert found.evidence == ""


def test_there_is_a_cap_on_unobservable_claims(lesson):
    claims = [Claim(f"claim {n}", 0, "because") for n in range(UNOBSERVABLE_CAP + 1)]
    with pytest.raises(TooMany):
        resolve(claims, lesson.cells)


def test_every_missing_claim_is_reported_at_once(lesson):
    lesson.md(f"## One\n\n{lesson.claim('first')}.")
    lesson.md(f"## Two\n\n{lesson.claim('second')}.")
    lesson.md("## Three")
    with pytest.raises(Unproved) as exc:
        resolve(lesson.claims, lesson.cells)
    assert "first" in str(exc.value)
    assert "second" in str(exc.value)


# The lessons that are actually in the repository.


def test_every_committed_notebook_matches_its_builder():
    """What CI runs, run here too, so the failure shows up before the push."""
    from tools.nbbuild.cli import builders, run

    found = builders(ROOT)
    assert found, "no lesson builders found"
    for builder in found:
        done = run(builder, "--check")
        assert done.returncode == 0, f"{builder.parent.name}:\n{done.stdout}{done.stderr}"


def test_the_claim_ledger_is_current():
    from tools.nbbuild.cli import claims

    assert claims(check=True) == 0


@pytest.mark.needs_nbclient
@pytest.mark.parametrize(
    "path",
    sorted((ROOT / "lessons").glob("*/*.ipynb")),
    ids=lambda p: p.parent.name,
)
def test_every_lesson_runs_top_to_bottom(path):
    """The only evidence a lesson still works, since outputs are never committed.

    It is not evidence that a lesson is right. A cell can print an empty list where the
    prose promised four names and nothing raises, which is why `python -m tools.nbbuild run
    --show` exists and why reading it is part of changing a lesson.
    """
    from tools.nbbuild.execute import run

    assert run(path) > 0, f"{path.name} has no code cells"


# Executing a lesson, and reading what it printed.


def notebook_of(*sources: str) -> str:
    from tools.nbbuild import Cell, document

    return document([Cell("code", f"c{i}", src) for i, src in enumerate(sources)])


@pytest.mark.needs_nbclient
def test_a_cell_that_raises_fails_the_run(tmp_path):
    from tools.nbbuild.execute import Failed, run

    lesson = tmp_path / "lessons" / "x" / "x.ipynb"
    lesson.parent.mkdir(parents=True)
    lesson.write_text(notebook_of("print('fine')", "raise ValueError('boom')"))
    with pytest.raises(Failed) as exc:
        run(lesson)
    assert "boom" in str(exc.value)
    assert "x.ipynb" in str(exc.value)


@pytest.mark.needs_nbclient
def test_a_transcript_shows_what_a_cell_printed(tmp_path):
    from tools.nbbuild.execute import execute, transcript

    lesson = tmp_path / "lessons" / "x" / "x.ipynb"
    lesson.parent.mkdir(parents=True)
    lesson.write_text(notebook_of("print('the answer is 42')", "1 + 1"))
    text = transcript(execute(lesson))
    assert "the answer is 42" in text
    assert "2" in text


@pytest.mark.needs_nbclient
def test_a_cell_that_prints_nothing_is_still_in_the_transcript(tmp_path):
    """The failure this is here to catch is a silent one, so silence has to be visible."""
    from tools.nbbuild.execute import execute, transcript

    lesson = tmp_path / "lessons" / "x" / "x.ipynb"
    lesson.parent.mkdir(parents=True)
    lesson.write_text(notebook_of("x = 1"))
    assert "(no output)" in transcript(execute(lesson))


def test_a_long_output_is_clipped_with_a_count():
    from tools.nbbuild.execute import clip

    text = "\n".join(str(i) for i in range(100))
    clipped = clip(text, lines=10)
    assert clipped.endswith("... 90 more lines")
    assert clipped.startswith("0\n1\n")


def test_a_short_output_is_not_clipped():
    from tools.nbbuild.execute import clip

    assert clip("one\ntwo", lines=10) == "one\ntwo"


ENTRY = {
    "id": "T05",
    "title": "5. SSA in one lesson",
    "notebook": "lessons/t05-ssa-in-one-lesson/t05.ipynb",
    "summary": "what a phi is",
    "milestone": "M0",
    "badge": "[![Open In Colab](x)](y)",
}


def test_the_index_row_drops_the_number_off_the_title():
    """The heading says "5. SSA in one lesson" and the first column already says T05."""
    from tools.nbbuild.cli import table

    row = table([ENTRY]).splitlines()[2]
    assert "[SSA in one lesson](" in row
    assert "5. SSA" not in row


def test_the_index_says_how_far_along_the_course_is():
    from tools.nbbuild.cli import table

    assert "1 of 96 written." in table([ENTRY])


def test_splice_replaces_the_block_and_leaves_the_prose_alone():
    from tools.nbbuild.cli import BEGIN, END, splice

    before = f"intro\n\n{BEGIN}\nstale\n{END}\n\nafter\n"
    after = splice(before, "fresh\n")
    assert after == f"intro\n\n{BEGIN}\nfresh\n{END}\n\nafter\n"


def test_splice_is_idempotent():
    """Two builds in a row have to produce the same README, or `check` fails on a clean tree."""
    from tools.nbbuild.cli import BEGIN, END, splice

    once = splice(f"{BEGIN}\n{END}\n", "fresh\n")
    assert splice(once, "fresh\n") == once


def test_splice_complains_when_the_markers_are_gone():
    from tools.nbbuild.cli import splice

    with pytest.raises(RuntimeError, match="nbbuild:begin index"):
        splice("a README with no markers in it\n", "fresh\n")


def test_the_readme_has_somewhere_to_put_the_index():
    """Deleting the markers by accident should fail here rather than at the next build."""
    from tools.nbbuild.cli import BEGIN, END

    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert text.count(BEGIN) == 1
    assert text.count(END) == 1
    assert text.find(BEGIN) < text.find(END)
