"""The blueprint pages of the published book.

None of this needs the pinned GCC tree, which is the point of keeping the generator out of
`bpc check`. It reads the blueprints and the MkDocs navigation and nothing else, so it can
run in the job that builds the site.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tools.bpc import BLUEPRINTS, REPO_ROOT, Blueprint, load, pages

FOUND = load(BLUEPRINTS)


def test_the_committed_pages_are_the_ones_the_generator_writes():
    assert pages.check() == []


def test_there_is_a_page_for_every_blueprint_and_nothing_else():
    on_disk = {p.name for p in pages.PAGES.glob("*.md")}
    assert on_disk == {f"{bp.id}.md" for bp in FOUND} | {f"{n}.md" for n in pages.COMPANIONS}


def test_a_page_is_an_include_and_not_a_copy():
    """One copy of every blueprint. Two is one too many the first day they differ."""
    for path in pages.PAGES.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert f'--8<-- "blueprints/{path.stem}.md"' in text
        assert len(text.splitlines()) < 6


def test_the_index_lists_every_blueprint_with_its_status():
    text = pages.index_page(FOUND)
    for bp in FOUND:
        assert f"[{bp.id}](blueprints/{bp.id}.md)" in text
        assert bp.header("Status")
    assert "9 of 58 written: 1 complete, 1 partial, 7 stub." in text


def test_the_index_says_what_each_blueprint_is_for_in_its_own_words():
    """The paragraph comes out of the document, so a rewritten document rewrites the page."""
    text = pages.index_page(FOUND)
    for bp in FOUND:
        assert pages.summary(bp) in text
        assert pages.summary(bp)


def test_the_summary_is_the_first_real_paragraph_and_not_the_header():
    bp = next(b for b in FOUND if b.id == "BP-PIPELINE")
    said = pages.summary(bp)
    assert said.startswith("This document specifies the control flow of one compilation")
    assert "Applies to" not in said
    assert "\n" not in said


def test_a_blueprint_missing_from_the_navigation_is_a_failure(tmp_path):
    """MkDocs builds an unlinked page happily, and `--strict` does not mind either."""
    config = tmp_path / "mkdocs.yml"
    config.write_text("nav:\n  - Start here: index.md\n", encoding="utf-8")
    problems = pages.nav_problems(FOUND, config)
    assert len(problems) == len(FOUND) + len(pages.COMPANIONS)
    assert all("no entry in mkdocs.yml" in line for line in problems)


def test_the_real_navigation_lists_all_of_them():
    assert pages.nav_problems(FOUND) == []


def test_the_navigation_check_wants_the_path_and_not_just_the_name(tmp_path):
    """A nav line has to point at the page. Naming the blueprint in a title is not enough."""
    config = tmp_path / "mkdocs.yml"
    config.write_text("nav:\n  - BP-CFG, blocks and edges: nope.md\n", encoding="utf-8")
    assert any("BP-CFG" in line for line in pages.nav_problems(FOUND, config))


def test_writing_the_pages_twice_changes_nothing_the_second_time():
    assert pages.build() == []


def test_a_blueprint_with_no_prose_under_its_header_still_gets_a_row(tmp_path):
    path = tmp_path / "BP-NOTHING.md"
    path.write_text(
        textwrap.dedent("""
            # BP-NOTHING, a document with nothing in it

            **Status:** stub
            **Generated sections:** none
            **Target-dependent:** no
            **Last verified:** never
        """).lstrip(),
        encoding="utf-8",
    )
    bp = Blueprint(path=path, text=path.read_text(encoding="utf-8"))
    assert pages.summary(bp) == ""
    assert "BP-NOTHING" in pages.row(bp)


@pytest.mark.parametrize("bp", FOUND, ids=lambda bp: bp.id)
def test_every_blueprint_page_is_reachable_from_the_index(bp: Blueprint):
    index = (REPO_ROOT / "docs" / "blueprints.md").read_text(encoding="utf-8")
    assert f"blueprints/{bp.id}.md" in index


def test_the_notation_page_exists_because_every_algorithm_needs_it():
    """A reader who meets an algorithm before the dialect reads it as broken C."""
    assert Path(pages.PAGES / "NOTATION.md").exists()
    assert "blueprints/NOTATION.md" in (REPO_ROOT / "docs" / "blueprints.md").read_text(
        encoding="utf-8"
    )
