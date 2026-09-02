"""The widgets.

    import gxray
    from gxwidgets import PassTape, SSAWeb, PredictGate

    gcc = gxray.corpus("l1-O2")
    r = gcc.compile(gxray.L1, "-O2", dumps=["tree-ssa"])
    f = r.dump("tree-ssa").only()

    SSAWeb(f, name="s_1")          # renders itself in a notebook
    SSAWeb(f, name="s_1").render() # the same thing as standalone HTML

Three properties hold for all of them, and the tests check all three.

**A widget consumes a `gxray` model.** No widget in this package parses a dump. A widget
that reaches for a regular expression is a sign the parser is missing something, and the
parser is where that belongs.

**A widget renders itself in Python.** The browser side attaches behaviour to markup it did
not build, so the static fallback is the same renderer with nothing plugged into it. A
lesson is readable before any runtime starts and stays readable if none ever does.

**A widget works without a mouse and without colour vision.** Every role shows a glyph and a
border as well as a colour, selection uses real buttons with `aria-current`, drawings carry
a written description of what they show, and there is a text version of everything.

The palette lives in `gxmanim.palette` and both the widgets and the animations import it,
so a still from a video and a live widget look like the same project.
"""

from gxwidgets.base import Widget, live
from gxwidgets.flagdiff import FlagDiff
from gxwidgets.html import STYLESHEET
from gxwidgets.irladder import IRLadder
from gxwidgets.passtape import PassTape
from gxwidgets.predictgate import GateError, Option, PredictGate
from gxwidgets.ssaweb import SSAWeb

__all__ = [
    "STYLESHEET",
    "FlagDiff",
    "GateError",
    "IRLadder",
    "Option",
    "PassTape",
    "PredictGate",
    "SSAWeb",
    "Widget",
    "live",
    "script",
]

__version__ = "0.1.0"


def script() -> str:
    """The one behaviour module, for a site build that wants to inline or copy it."""
    from pathlib import Path

    return (Path(__file__).parent / "static" / "widget.js").read_text(encoding="utf-8")
