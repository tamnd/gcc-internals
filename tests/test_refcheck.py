"""Citation checking.

Most of these run against a fake tree in a temp directory, because the thing being tested
is the checking, not GCC. The few that read the real pinned tree are marked `needs_gcc_src`
and skip when the submodule is not checked out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import refcheck
from tools.refcheck import Citation, RefError

HAVE_TREE = refcheck.pinned_commit() is not None
needs_tree = pytest.mark.skipif(not HAVE_TREE, reason="vendor/gcc is not checked out")

FILE = "\n".join(f"line {n}" for n in range(1, 21)) + "\n"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "gcc").mkdir()
    (tmp_path / "gcc" / "passes.cc").write_text(FILE)
    return tmp_path


def cite(line: int, path: str = "gcc/passes.cc", tag: str = refcheck.PINNED_TAG) -> Citation:
    return Citation(path=path, line=line, tag=tag, source=Path("lesson.md"), source_line=1)


def test_finds_a_citation_in_prose():
    text = "The pass name may carry a prefix, see `gcc/passes.cc:855@releases/gcc-16.2.0`.\n"
    (found,) = refcheck.find_citations(text, source=Path("t.md"))
    assert found.path == "gcc/passes.cc"
    assert found.line == 855
    assert found.tag == "releases/gcc-16.2.0"
    assert found.source_line == 1


def test_finds_several_on_one_line():
    text = "both gcc/a.cc:1@releases/gcc-16.2.0 and gcc/b.cc:2@releases/gcc-16.2.0 say so"
    assert len(refcheck.find_citations(text)) == 2


def test_ordinary_prose_is_not_a_citation():
    for text in ["see line 12 of passes.cc", "at 10:30@home", "gcc/passes.cc line 855"]:
        assert refcheck.find_citations(text) == []


def test_resolves_to_the_right_line(tree):
    r = refcheck.resolve(cite(10), root=tree)
    assert r.text == "line 10"
    assert r.window == [f"line {n}" for n in range(8, 13)]


def test_the_window_is_clipped_at_the_start_of_the_file(tree):
    r = refcheck.resolve(cite(1), root=tree)
    assert r.window == ["line 1", "line 2", "line 3"]


def test_the_window_is_clipped_at_the_end_of_the_file(tree):
    r = refcheck.resolve(cite(20), root=tree)
    assert r.window == ["line 18", "line 19", "line 20"]


def test_a_line_past_the_end_says_how_long_the_file_is(tree):
    with pytest.raises(RefError) as exc:
        refcheck.resolve(cite(99), root=tree)
    assert "has 20 lines" in str(exc.value)


def test_a_missing_file_says_where_it_looked(tree):
    with pytest.raises(RefError) as exc:
        refcheck.resolve(cite(1, path="gcc/nope.cc"), root=tree)
    assert "not in the tree" in str(exc.value)


def test_the_wrong_tag_is_refused(tree):
    with pytest.raises(RefError) as exc:
        refcheck.resolve(cite(1, tag="releases/gcc-15.1.0"), root=tree)
    assert "pinned at releases/gcc-16.2.0" in str(exc.value)


def test_a_generated_file_is_refused_with_the_file_to_cite_instead(tree):
    with pytest.raises(RefError) as exc:
        refcheck.resolve(cite(1, path="gcc/gimple-match.cc"), root=tree)
    message = str(exc.value)
    assert "does not exist until GCC is built" in message
    assert "gcc/match.pd" in message


def test_insn_recog_points_you_at_the_machine_description(tree):
    with pytest.raises(RefError) as exc:
        refcheck.resolve(cite(1, path="gcc/insn-recog.cc"), root=tree)
    assert ".md file" in str(exc.value)


def test_trailing_whitespace_does_not_change_the_hash():
    assert refcheck.digest_of(["a", "b"]) == refcheck.digest_of(["a   ", "b\t"])


def test_a_different_line_changes_the_hash():
    assert refcheck.digest_of(["a", "b"]) != refcheck.digest_of(["a", "c"])


def test_check_is_quiet_when_everything_matches(tree, tmp_path):
    prose = tmp_path / "lesson.md"
    prose.write_text(f"see `gcc/passes.cc:10@{refcheck.PINNED_TAG}`\n")
    lock = tmp_path / "lock.json"

    refcheck.update([prose], root=tree, lock=lock)
    assert refcheck.check([prose], root=tree, lock=lock) == []


def test_check_notices_when_the_cited_code_moves(tree, tmp_path):
    """The whole reason this tool exists."""
    prose = tmp_path / "lesson.md"
    prose.write_text(f"see `gcc/passes.cc:10@{refcheck.PINNED_TAG}`\n")
    lock = tmp_path / "lock.json"
    refcheck.update([prose], root=tree, lock=lock)

    moved = FILE.replace("line 10", "something else entirely")
    (tree / "gcc" / "passes.cc").write_text(moved)

    (problem,) = refcheck.check([prose], root=tree, lock=lock)
    assert "no longer matches" in problem
    assert "something else entirely" in problem


def test_check_notices_an_edit_two_lines_away(tree, tmp_path):
    """An off by one citation is the common error, so the window is wider than one line."""
    prose = tmp_path / "lesson.md"
    prose.write_text(f"see `gcc/passes.cc:10@{refcheck.PINNED_TAG}`\n")
    lock = tmp_path / "lock.json"
    refcheck.update([prose], root=tree, lock=lock)

    (tree / "gcc" / "passes.cc").write_text(FILE.replace("line 12", "line 12 changed"))
    assert refcheck.check([prose], root=tree, lock=lock) != []


def test_an_edit_outside_the_window_is_left_alone(tree, tmp_path):
    prose = tmp_path / "lesson.md"
    prose.write_text(f"see `gcc/passes.cc:10@{refcheck.PINNED_TAG}`\n")
    lock = tmp_path / "lock.json"
    refcheck.update([prose], root=tree, lock=lock)

    (tree / "gcc" / "passes.cc").write_text(FILE.replace("line 20", "line 20 changed"))
    assert refcheck.check([prose], root=tree, lock=lock) == []


def test_a_new_citation_has_to_be_locked_before_it_passes(tree, tmp_path):
    """A citation entering the book shows up in a diff, like the Compiler Explorer cache."""
    prose = tmp_path / "lesson.md"
    prose.write_text(f"see `gcc/passes.cc:10@{refcheck.PINNED_TAG}`\n")
    lock = tmp_path / "lock.json"

    (problem,) = refcheck.check([prose], root=tree, lock=lock)
    assert "not in the lockfile" in problem
    assert "refcheck update" in problem


def test_a_citation_that_was_deleted_is_reported_too(tree, tmp_path):
    prose = tmp_path / "lesson.md"
    prose.write_text(f"see `gcc/passes.cc:10@{refcheck.PINNED_TAG}`\n")
    lock = tmp_path / "lock.json"
    refcheck.update([prose], root=tree, lock=lock)

    prose.write_text("no citations here any more\n")
    (problem,) = refcheck.check([prose], root=tree, lock=lock)
    assert "no longer cited" in problem


def test_the_lockfile_is_sorted_and_readable(tree, tmp_path):
    prose = tmp_path / "lesson.md"
    prose.write_text(
        f"`gcc/passes.cc:12@{refcheck.PINNED_TAG}` and `gcc/passes.cc:3@{refcheck.PINNED_TAG}`\n"
    )
    lock = tmp_path / "lock.json"
    refcheck.update([prose], root=tree, lock=lock)

    body = lock.read_text()
    assert body.index("passes.cc:12") < body.index("passes.cc:3")
    assert body.count("\n") > 5, "one line of JSON is not a reviewable diff"


@needs_tree
def test_the_submodule_is_pinned_where_it_says_it_is():
    assert (refcheck.GCC_ROOT / "gcc" / "BASE-VER").read_text().strip() == "16.2.0"


@needs_tree
def test_every_citation_in_this_repository_resolves():
    """The real check, run over the real tree, on the same paths CI passes it.

    The list comes from the command line tool rather than being typed again here, because a
    second copy of it goes stale and then the suite stops checking a directory that CI does.
    """
    from tools.refcheck.__main__ import DEFAULT_PATHS

    paths = [Path(p) for p in DEFAULT_PATHS if Path(p).exists()]
    assert refcheck.check(paths) == []


@needs_tree
def test_the_citation_behind_the_pass_name_fix_still_says_what_it_said():
    """gxray splits pass names on a space because of this comment. If it goes, so does that."""
    r = refcheck.resolve(Citation("gcc/passes.cc", 855, refcheck.PINNED_TAG))
    assert "disambiguating prefix" in r.text
