"""The drawing side of the project.

Four layers, and the order matters because each one only knows about the one under it:

    palette      what a colour means, and the glyph and border that carry the same meaning
    primitives   the nine shapes, their content and the size they want
    scene        shapes, where they ended up, and what the picture says in words
    svg          a scene as a file you can put in a lesson

A mobject in `gxmanim.mobjects` takes something `gxray` parsed and returns a scene. It never
draws. That split is the point: the meaning lives in the scene, so the SVG renderer here and
the manim renderer that comes later cannot disagree about what a drawing shows, and a still
from a video and a live widget look like the same project because they are.

Importing this package does not import manim and never will, so `gxwidgets` can use the
palette in an environment with no rendering stack in it at all. When the manim renderer
lands it goes in its own module and imports manim inside the function that needs it.
"""

from gxmanim import mobjects, palette, primitives, scene, svg
from gxmanim.scene import Scene

__all__ = ["Scene", "mobjects", "palette", "primitives", "scene", "svg"]
