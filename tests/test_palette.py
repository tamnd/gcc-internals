"""The palette has to hold up in greyscale, in dark mode, and for a reader who cannot tell
red from green. Those are properties, so they are checked here rather than remembered.
"""

from __future__ import annotations

import pytest

from gxmanim.palette import (
    DARK_PAGE,
    EDGES,
    LIGHT_PAGE,
    ROLES,
    contrast,
    css,
    luminance,
    rgb,
    role,
)

THEMES = {"light": LIGHT_PAGE, "dark": DARK_PAGE}


def test_the_seven_roles_are_the_ones_the_spec_names():
    assert set(ROLES) == {
        "neutral",
        "added",
        "removed",
        "changed",
        "focus",
        "constant",
        "unknown",
    }


@pytest.mark.parametrize("name", sorted(ROLES))
@pytest.mark.parametrize("theme", sorted(THEMES))
def test_ink_is_readable_on_its_own_fill_and_on_the_page(name, theme):
    s = ROLES[name].swatch(theme)
    assert contrast(s.ink, s.fill) >= 4.5
    assert contrast(s.ink, THEMES[theme]) >= 4.5


def test_no_two_roles_share_a_glyph():
    glyphs = [r.glyph for r in ROLES.values() if r.glyph]
    assert len(glyphs) == len(set(glyphs))


def test_every_role_that_is_not_the_default_has_a_glyph():
    for name, r in ROLES.items():
        assert bool(r.glyph) == (name != "neutral")


def test_a_role_is_told_apart_by_more_than_colour():
    """Glyph and border together, so the same six pairs are never both identical."""
    seen = set()
    for r in ROLES.values():
        assert (r.glyph, r.border) not in seen
        seen.add((r.glyph, r.border))


def test_every_role_says_what_it_means_in_words():
    for r in ROLES.values():
        assert r.means and not r.means.endswith(".")


def test_edges_carry_no_colour():
    """An edge is a thin line, and colour on a thin line is the worst channel available."""
    for name, e in EDGES.items():
        assert "colour" not in e and "color" not in e, name
        assert e["stroke"] in {"solid", "dashed", "dotted"}


def test_true_and_false_edges_differ_without_colour():
    assert EDGES["true"]["glyph"] != EDGES["false"]["glyph"]


def test_swatch_rejects_a_theme_that_does_not_exist():
    with pytest.raises(ValueError, match="light or dark"):
        ROLES["added"].swatch("sepia")


def test_role_lookup_names_the_alternatives():
    with pytest.raises(KeyError, match="seven"):
        role("green")


def test_rgb_and_luminance_agree_with_the_known_values():
    assert rgb("#ffffff") == (255, 255, 255)
    assert rgb("0d1117") == (13, 17, 23)
    assert luminance("#ffffff") == pytest.approx(1.0)
    assert luminance("#000000") == pytest.approx(0.0)
    assert contrast("#ffffff", "#000000") == pytest.approx(21.0)


def test_rgb_refuses_a_colour_it_cannot_read():
    with pytest.raises(ValueError, match="six digit"):
        rgb("#fff")


def test_css_defines_a_property_for_every_role_in_both_themes():
    for theme in THEMES:
        text = css(theme)
        for name in ROLES:
            assert f"--gx-{name}-ink:" in text
            assert f"--gx-{name}-fill:" in text
        assert "--gx-page:" in text


def test_the_two_themes_are_actually_different():
    assert css("light") != css("dark")
