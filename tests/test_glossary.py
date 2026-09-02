"""The glossary.

The committed `GLOSSARY.md` is generated, so the important test is that it still matches the
module it came from. The rest is about the links, because a glossary whose cross references
go nowhere is worse than no glossary.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gxray import glossary

ROOT = Path(__file__).resolve().parent.parent


def test_the_committed_file_matches_the_module():
    """Run `python -m gxray.glossary` from the root of the repository if this fails."""
    assert (ROOT / glossary.PATH).read_text(encoding="utf-8") == glossary.markdown()


def test_every_cross_reference_points_at_a_term_that_exists():
    for term in glossary.TERMS:
        for other in term.see:
            glossary.get(other)


def test_nothing_refers_to_itself():
    for term in glossary.TERMS:
        assert term.name not in term.see, term.name


def test_no_term_is_defined_twice():
    names = [term.name.lower() for term in glossary.TERMS]
    assert len(names) == len(set(names))


def test_no_two_terms_share_an_anchor():
    """Two headings with the same slug means one of the links goes to the wrong place."""
    anchors = [term.anchor for term in glossary.TERMS]
    assert len(anchors) == len(set(anchors))


def test_an_underscore_survives_the_anchor():
    """GitHub keeps underscores and turns spaces into hyphens, which is easy to get wrong."""
    assert glossary.anchor("SSA_NAME") == "ssa_name"
    assert glossary.anchor("phi node") == "phi-node"


def test_looking_up_a_term_ignores_case():
    assert glossary.get("SSA Name") is glossary.get("ssa name")


def test_a_term_that_does_not_exist_says_how_many_there_are():
    with pytest.raises(KeyError) as exc:
        glossary.get("monomorphisation")
    assert str(len(glossary.TERMS)) in str(exc.value)


def test_a_link_can_say_something_other_than_the_term():
    link = glossary.link("phi node", "the phi at the top of the block")
    assert link.startswith("[the phi at the top of the block](")
    assert link.endswith("#phi-node)")


def test_links_are_absolute_because_colab_has_no_idea_where_it_came_from():
    assert glossary.link("SSA").startswith(f"[SSA]({glossary.REPOSITORY}/blob/main/")


def test_every_term_says_where_a_reader_first_meets_it():
    """A term with no lesson behind it is a term the course has not earned yet."""
    for term in glossary.TERMS:
        assert term.met, term.name


def test_the_index_lists_everything():
    body = glossary.markdown()
    for name in glossary.names():
        assert f"[{name}](#{glossary.anchor(name)})" in body
