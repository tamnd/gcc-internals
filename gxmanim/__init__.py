"""The drawing side of the project.

Right now this holds one thing, the palette, and that is on purpose. The palette has to
exist before anything draws, because the rule it encodes is that a still from an animation
and a live widget look like the same project, and that only works if there is one file that
says what a colour means and everything imports it.

The mobjects come later. Importing this package does not import manim and never will, so
`gxwidgets` can use the palette in an environment with no rendering stack in it at all.
"""

from gxmanim import palette

__all__ = ["palette"]
