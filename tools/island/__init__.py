"""Turn a marimo notebook into a piece of a page.

A marimo island is a notebook cell that ships as ordinary HTML with its output already in
it, and wakes up into a live reactive cell once the runtime loads. That is the whole reason
this project uses them: the page is readable and correct before anything starts, and the
reader who wants to change a number gets a real Python kernel in the same place.

Two things this module adds on top of what marimo gives you.

The runtime does not start on page load. Marimo's head fragment pulls in the islands
bundle, which pulls in Pyodide, which is tens of megabytes, and a compiler course whose
front page costs thirty megabytes before you have read a sentence is a bad joke. So the
head fragment goes into a `<template>` in the body instead, and `island.js` moves it into
the head when the reader presses start. Nothing downloads until then.

There is a real static fallback. A marimo island keeps its build time output in a data
attribute for the runtime to pick up, which means a reader with no JavaScript sees an empty
box, so every cell that produced prose gets that prose written into the page as ordinary
HTML as well. The runtime hides those copies as it takes over. Cells whose output is an
input control get no copy, because a button that cannot be pressed is worse than nothing.

The ids are made deterministic. Marimo gives every UI element a fresh uuid on every build,
so two builds of an unchanged notebook produce different bytes, and every rebuild becomes a
diff nobody can read. The uuid only has to be unique on the page, so we derive it from the
element's object id instead.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import re
from dataclasses import dataclass
from pathlib import Path

# `<!-- island: site/notebooks/ce-probe.py -->` on a line of its own, in a markdown page.
MARKER = re.compile(r"^[ \t]*<!--[ \t]*island:[ \t]*(?P<path>[^\s>]+)[ \t]*-->[ \t]*$", re.M)
RANDOM_ID = re.compile(r"random-id='(?P<uuid>[0-9a-f-]{36})'")
OBJECT_ID = re.compile(r"object-id='(?P<id>[^']*)'")


@dataclass(frozen=True)
class Island:
    """One notebook, rendered. `head` is what the runtime needs, `body` is what the reader
    sees before it starts."""

    name: str
    head: str
    body: str

    def embed(self, label: str = "Run this yourself") -> str:
        """The body, plus the button that starts the runtime, plus the head it will need."""
        return (
            f'<div class="island" data-island="{html.escape(self.name)}">\n'
            f'<template class="island-head">\n{self.head}\n</template>\n'
            f'<p class="island-start"><button type="button" data-island-start>{label}</button>'
            '<span class="island-note">Starts Python in your browser. Nothing is installed'
            " and nothing leaves the page except the requests you make.</span></p>\n"
            '<noscript><p class="island-note">JavaScript is off, so what follows is the'
            " output recorded when this page was built. Everything it says is still true,"
            " you just cannot change it.</p></noscript>\n"
            f'<div class="island-cells">\n{self.body}\n</div>\n'
            "</div>"
        )


def stable_ids(markup: str) -> str:
    """Swap marimo's per build uuids for ones derived from the element they belong to.

    They have to be unique within a page and nothing else, so a hash of the object id does
    the job, and the same notebook then builds byte for byte the same every time.
    """

    def fixed(match: re.Match[str]) -> str:
        before = markup[: match.start()]
        owner = OBJECT_ID.findall(before)
        seed = owner[-1] if owner else str(match.start())
        digest = hashlib.sha256(seed.encode()).hexdigest()
        shaped = f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
        return f"random-id='{shaped}'"

    return RANDOM_ID.sub(fixed, markup)


def static_copy(stub) -> str:
    """The cell's output as plain HTML, for a reader whose runtime is not running.

    Only prose. Marimo hands back `text/markdown` already rendered to HTML, which is exactly
    what belongs in a static page, and hands back `text/html` for its own input controls,
    which are custom elements that do nothing until the runtime is there.
    """
    output = getattr(stub, "output", None)
    if output is None or output.mimetype != "text/markdown" or not output.data:
        return ""
    return f'<div class="island-static">{output.data}</div>'


def render(notebook: Path | str) -> Island:
    """Build one notebook and hand back its markup.

    The cells run here, in ordinary CPython, which is what puts real output in the static
    page. A notebook that needs the network has to notice it is not in a browser and say so,
    because this runs in CI and CI is never allowed to call a live API.
    """
    from marimo import MarimoIslandGenerator

    path = Path(notebook)

    async def build() -> Island:
        generator = MarimoIslandGenerator.from_file(str(path), display_code=False)
        await generator.build()
        body = "\n".join(static_copy(s) + "\n" + s.render() for s in generator.stubs)
        return Island(name=path.stem, head=generator.render_head(), body=stable_ids(body))

    return asyncio.run(build())


def expand(markdown: str, root: Path | str = ".") -> str:
    """Replace every island marker in a page with the island it names."""
    base = Path(root)

    def swap(match: re.Match[str]) -> str:
        return render(base / match.group("path")).embed()

    return MARKER.sub(swap, markdown)


def islands_in(markdown: str) -> list[str]:
    """Which notebooks a page asks for, without building any of them."""
    return MARKER.findall(markdown)


__all__ = ["Island", "expand", "islands_in", "render", "stable_ids", "static_copy"]
