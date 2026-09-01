"""A scene: shapes, where they ended up, and what the picture says.

A scene is the thing a mobject builds and a renderer draws. It holds placed shapes, the
links between them, a title and a caption, and it knows how to say in words what it shows.

That last part is not decoration. The rule is that alt text is written for a human and
describes what happens, and "diagram of a control flow graph" is rejected. A scene cannot
write the sentence that explains why the picture matters, but it can write the inventory
underneath it, so the human writing the alt text is editing something true rather than
starting from a blank line and a vague memory of the dump.

Placement is the mobject's job. A scene does not lay anything out, it records decisions and
answers questions about them, mostly "where did the thing with this id end up", which is
what an edge needs before it can be drawn.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gxmanim.primitives import Block, Box, Card, Edge, Placed, Point, Rung, Slot, Thread

# Room around the whole drawing, so a box on the edge is not against the frame.
MARGIN = 16

# Extra room on the right for the links that bow out there: back edges, self edges, and
# threads that run the other way. A renderer has to bow them somewhere and the alternative
# is drawing them on top of the shapes, so the frame makes room instead of clipping them.
BOW = 48


@dataclass
class Scene:
    """One picture. Deterministic: the same inputs place the same shapes at the same points.

    `theme` is light or dark and only affects what a renderer looks up in the palette. The
    geometry is the same either way, so a scene rendered both ways is the same drawing.
    """

    title: str
    caption: str = ""
    theme: str = "light"
    placed: list[Placed] = field(default_factory=list)
    links: list[Edge | Thread] = field(default_factory=list)

    def add(self, shape, x: float, y: float):
        """Put a shape at a point and hand it back, so a caller can keep using it."""
        self.placed.append(Placed(shape, Point(x, y)))
        return shape

    def link(self, *links: Edge | Thread) -> None:
        """Join two placed shapes. Both ends have to exist by the time anything draws."""
        self.links.extend(links)

    # Where things are

    def boxes(self) -> dict[str, Box]:
        """Every id in the scene and the box it occupies, children included.

        A card inside a block has its own id and its own box, because a def-use thread runs
        between two statements and not between two blocks. Walking in here rather than
        making every mobject flatten its own contents is what keeps the mobjects short.
        """
        out: dict[str, Box] = {}
        for p in self.placed:
            shape = p.shape
            if getattr(shape, "id", ""):
                out[shape.id] = p.box
            if isinstance(shape, Block | Rung):
                for card, box in shape.card_boxes(p.at):
                    if card.id:
                        out[card.id] = box
                    for badge, bbox in card.badge_boxes(Point(box.x, box.y)):
                        if badge.id:
                            out[badge.id] = bbox
            elif isinstance(shape, Card):
                for badge, bbox in shape.badge_boxes(p.at):
                    if badge.id:
                        out[badge.id] = bbox
            elif isinstance(shape, Slot):
                for label, _, box in shape.part_boxes(p.at):
                    out[f"{shape.id}.{label}"] = box
        return out

    def box(self, id: str) -> Box:
        found = self.boxes()
        if id not in found:
            have = ", ".join(sorted(found)) or "nothing"
            raise KeyError(f"nothing in this scene is called {id!r}. It holds: {have}")
        return found[id]

    def bounds(self) -> Box:
        """The whole drawing, with a margin. An empty scene is a small empty box."""
        if not self.placed:
            return Box(0, 0, 2 * MARGIN, 2 * MARGIN)
        right = max(p.box.right for p in self.placed)
        bottom = max(p.box.bottom for p in self.placed)
        return Box(0, 0, right + MARGIN + (BOW if self.links else 0), bottom + MARGIN)

    # What it says

    def check(self) -> list[str]:
        """Everything wrong with this scene, as sentences. Empty means it is drawable.

        Called by the renderer before it draws and by the tests, because an edge pointing
        at an id nothing has is a mistake that produces a picture rather than an error, and
        a silently missing arrow is the worst kind of wrong diagram.
        """
        known = set(self.boxes())
        problems = []
        for link in self.links:
            for end in (link.src, link.dst):
                if end not in known:
                    problems.append(f"{link.describe()} points at {end!r}, which is not here")
        if not self.title:
            problems.append("the scene has no title, and the title is the one idea it shows")
        return problems

    def describe(self) -> str:
        """The picture in words: the title, the caption, then everything in it.

        This is the starting point for alt text and not the alt text itself. A human reads
        it, keeps what matters and writes the sentence about why the picture is worth
        looking at, which is the part no inventory can produce.
        """
        lines = [self.title]
        if self.caption:
            lines.append(self.caption)
        for p in self.placed:
            lines.append(p.shape.describe())
        for link in self.links:
            lines.append(link.describe())
        return "\n".join(lines)
