"""A film: a sequence of scenes, a caption under each one, and the rules they have to obey.

The visual system says animate what is inherently temporal and draw what is structural. A
control flow graph is structural and gets a diagram. Renaming every variable in a function
one definition at a time is temporal, and a reader who sees the finished dump has no idea
which order any of it happened in. That is what a film is for.

A film is a list of `Shot`s. Each shot is an ordinary `Scene`, the same kind the diagrams
use, so a still lifted out of a film and a diagram in a lesson are the same drawing made the
same way from the same recorded dumps. Nothing here places a shape or picks a colour.

What this module does add is the rules, in `check`, because the rules in the spec are the
kind that get quietly broken:

- Sixty to ninety seconds. Longer is two films.
- One idea per shot, and the shot's scene title says what it is.
- Alt text written by a human, describing what happens, in whole sentences. `Animation of
  SSA construction` is rejected here in code, not in review.
- Deterministic, which is not checked here because it is checked where it can be: the tests
  render every film twice and compare the bytes.

There is no narration and no sound anywhere in this project, so a caption is the only way a
shot can say anything. That makes captions load bearing rather than decorative, and an empty
one is an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gxmanim.scene import Scene

#: The window from the animation rules. A film under a minute is usually a diagram somebody
#: has animated for no reason, and one over ninety seconds is two films that have not been
#: split yet.
SHORTEST = 60.0
LONGEST = 90.0

#: How long a shot may sit on screen. The floor is about how long it takes to notice that
#: anything changed, and the ceiling is where a reader starts wondering if it is broken.
BRIEFEST = 1.5
LONGEST_SHOT = 9.0

#: Openings that describe the file rather than what happens in it. Alt text starting with
#: one of these is the failure the spec calls out by name.
LAZY = ("animation of", "an animation", "a video", "video of", "diagram of", "this shows")

#: What a film may be called. Also the file name on disk and part of every CSS class in the
#: rendered film, which is the reason for the narrow spelling.
NAME = re.compile(r"[a-z][a-z0-9-]*")


@dataclass(frozen=True)
class Shot:
    """One scene on screen for a while, with the sentence that says what to look at."""

    scene: Scene
    caption: str
    seconds: float = 4.5

    @property
    def title(self) -> str:
        return self.scene.title


@dataclass(frozen=True)
class Film:
    """One film. `name` is the file name, `title` is the one idea, `alt` is for a reader.

    `still` picks the shot to render as the poster frame, and defaults to the last one,
    because the end state is what somebody scrolling past is most likely to want. A film
    whose point is the before rather than the after can say so.
    """

    name: str
    title: str
    alt: str
    shots: tuple[Shot, ...]
    still: int = -1

    def seconds(self) -> float:
        return sum(shot.seconds for shot in self.shots)

    def poster(self) -> Scene:
        return self.shots[self.still].scene

    def marks(self) -> list[tuple[float, float]]:
        """Where each shot starts and ends, as a percentage of the whole film.

        The renderer turns these into keyframes and the tests read them, which is why the
        arithmetic lives here and not in the renderer. Rounded, because a keyframe stop is
        written into a stylesheet and a float with seventeen digits in it makes a diff
        unreadable for no gain.
        """
        total = self.seconds()
        out = []
        running = 0.0
        for shot in self.shots:
            start = round(100 * running / total, 3)
            running += shot.seconds
            out.append((start, round(100 * running / total, 3)))
        return out

    def describe(self) -> str:
        """The film in words: the alt text, then every shot in order.

        The alt text comes first because it is the part a human wrote. What follows is the
        inventory, which is what the alt text was written against.
        """
        lines = [self.title, self.alt, f"{len(self.shots)} shots, {self.seconds():.0f} seconds"]
        for n, shot in enumerate(self.shots, start=1):
            lines.append(f"{n}. {shot.title}. {shot.caption}")
        return "\n".join(lines)

    def check(self) -> list[str]:
        """Everything wrong with this film, as sentences. Empty means it can be rendered."""
        problems = []
        # The name is not only a key. It goes into every class name and every keyframe name
        # in the rendered film, which is what keeps two films on one page apart, so it has
        # to be something CSS will accept.
        if not NAME.fullmatch(self.name):
            problems.append(
                f"{self.name!r} is not a usable name. It ends up in a CSS class, so it has "
                "to be lower case letters, digits and hyphens, starting with a letter."
            )
        if len(self.shots) < 2:
            problems.append("a film with one shot is a diagram")
        total = self.seconds()
        if not SHORTEST <= total <= LONGEST:
            problems.append(
                f"{total:.0f} seconds, and the rule is {SHORTEST:.0f} to {LONGEST:.0f}. "
                "Over the top means this is two films."
            )
        for n, shot in enumerate(self.shots, start=1):
            if not shot.caption.strip():
                problems.append(f"shot {n} has no caption, and a silent film has nothing else")
            if not BRIEFEST <= shot.seconds <= LONGEST_SHOT:
                problems.append(
                    f"shot {n} is {shot.seconds:g} seconds, and a shot runs "
                    f"{BRIEFEST:g} to {LONGEST_SHOT:g}"
                )
            problems += [f"shot {n}: {bad}" for bad in shot.scene.check()]
        problems += self._alt_problems()
        return problems

    def _alt_problems(self) -> list[str]:
        alt = self.alt.strip()
        if not alt:
            return ["there is no alt text, and it is the only version some readers get"]
        out = []
        if alt.lower().startswith(LAZY):
            out.append(f"the alt text opens with {alt.split()[0]!r}, which describes the file")
        sentences = [s for s in re.split(r"(?<=[.?!])\s+", alt) if s.strip()]
        if len(sentences) < 3:
            out.append(
                f"the alt text is {len(sentences)} sentence(s). It has to say what happens, "
                "which takes three or four."
            )
        return out
