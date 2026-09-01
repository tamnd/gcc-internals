"""The palette, fixed once, imported by everything that draws.

A still from an animation and a live widget have to look like the same project, so there is
one file that says what a colour means and both sides import it. This one has no manim in
it and no other imports either, so a widget can use it without pulling in a rendering stack.

The rule that shapes the whole thing: **semantics are never carried by colour alone**. Every
role also has a glyph and a border style, so the same distinction survives a greyscale print,
a screenshot pasted into a terminal, and a reader who cannot tell red from green. That is an
accessibility rule and it is also a legibility rule, and it is enforced by a test rather than
by remembering.

    >>> from gxmanim.palette import ROLES
    >>> ROLES["added"].glyph
    '+'
    >>> ROLES["added"].light.ink
    '#0a5f2c'

Contrast is computed here rather than eyeballed. `contrast()` is the WCAG 2 ratio, and the
tests hold every role's ink to 4.5 to 1 against both its own fill and the page, in both
themes. The fills are deliberately faint and are not asked to carry a ratio, because a fill
is a hint and the glyph and the border are what actually distinguish one role from another.
"""

from __future__ import annotations

from dataclasses import dataclass

LIGHT_PAGE = "#ffffff"
DARK_PAGE = "#0d1117"


@dataclass(frozen=True)
class Swatch:
    """The two colours a role needs in one theme: what to write with, what to sit on."""

    ink: str
    fill: str


@dataclass(frozen=True)
class Role:
    """One meaning, encoded four ways so that no single channel is load bearing."""

    name: str
    means: str
    glyph: str
    border: str
    light: Swatch
    dark: Swatch

    def swatch(self, theme: str = "light") -> Swatch:
        if theme not in ("light", "dark"):
            raise ValueError(f"theme is light or dark, not {theme!r}")
        return self.light if theme == "light" else self.dark


ROLES: dict[str, Role] = {
    "neutral": Role(
        name="neutral",
        means="unchanged content",
        glyph="",
        border="solid",
        light=Swatch(ink="#1f2328", fill="#f6f8fa"),
        dark=Swatch(ink="#e6edf3", fill="#161b22"),
    ),
    "added": Role(
        name="added",
        means="created by this pass",
        glyph="+",
        border="solid",
        light=Swatch(ink="#0a5f2c", fill="#e6f6ec"),
        dark=Swatch(ink="#68d97a", fill="#0f2618"),
    ),
    "removed": Role(
        name="removed",
        means="deleted by this pass, shown struck through",
        glyph="-",
        border="dashed",
        light=Swatch(ink="#8b1a1a", fill="#fdeceb"),
        dark=Swatch(ink="#ff8b82", fill="#2d1517"),
    ),
    "changed": Role(
        name="changed",
        means="modified in place",
        glyph="~",
        border="double",
        light=Swatch(ink="#6b4200", fill="#fff4e0"),
        dark=Swatch(ink="#e3b341", fill="#2a2010"),
    ),
    "focus": Role(
        name="focus",
        means="what the current paragraph is about",
        glyph=">",
        border="solid",
        light=Swatch(ink="#0b4f9e", fill="#e7f0fb"),
        dark=Swatch(ink="#79c0ff", fill="#0f2440"),
    ),
    "constant": Role(
        name="constant",
        means="a value the compiler knows",
        glyph="=",
        border="solid",
        light=Swatch(ink="#5a3ba8", fill="#f1eafd"),
        dark=Swatch(ink="#d2a8ff", fill="#221733"),
    ),
    "unknown": Role(
        name="unknown",
        means="VARYING, the top of the lattice",
        glyph="?",
        border="dotted",
        light=Swatch(ink="#454d54", fill="#eceff1"),
        dark=Swatch(ink="#9aa4ae", fill="#1b2026"),
    ),
}

# Control flow edges. Colour is not in this table at all, because an edge is thin and colour
# on a one pixel line is the least readable channel there is.
EDGES: dict[str, dict[str, str]] = {
    "fallthrough": {"stroke": "solid", "width": "thin", "glyph": "", "arrow": "single"},
    "true": {"stroke": "solid", "width": "thick", "glyph": "T", "arrow": "single"},
    "false": {"stroke": "solid", "width": "thick", "glyph": "F", "arrow": "single"},
    "back": {"stroke": "solid", "width": "thin", "glyph": "", "arrow": "double"},
    "eh": {"stroke": "dashed", "width": "thin", "glyph": "!", "arrow": "single"},
    "abnormal": {"stroke": "dotted", "width": "thin", "glyph": "", "arrow": "single"},
    "complex": {"stroke": "solid", "width": "thin", "glyph": "<>", "arrow": "single"},
}


def role(name: str) -> Role:
    if name not in ROLES:
        raise KeyError(f"{name!r} is not a role. The seven are: {', '.join(ROLES)}")
    return ROLES[name]


def rgb(colour: str) -> tuple[int, int, int]:
    """`#rrggbb` as three integers."""
    text = colour.lstrip("#")
    if len(text) != 6:
        raise ValueError(f"{colour!r} is not a six digit hex colour")
    return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(colour: str) -> float:
    """Relative luminance, as WCAG 2 defines it."""
    channels = []
    for value in rgb(colour):
        c = value / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """The WCAG 2 contrast ratio between two colours, between 1 and 21."""
    la, lb = luminance(a), luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def css(theme: str = "light") -> str:
    """The palette as custom properties, so a stylesheet never hard codes a colour."""
    page = LIGHT_PAGE if theme == "light" else DARK_PAGE
    lines = [f"  --gx-page: {page};"]
    for name, r in ROLES.items():
        s = r.swatch(theme)
        lines.append(f"  --gx-{name}-ink: {s.ink};")
        lines.append(f"  --gx-{name}-fill: {s.fill};")
    return "\n".join(lines)
