"""The build banner.

Rule 2 of the notebook contract: the first cell of every notebook is this. It says which
compiler, which target and which backend produced everything below it, and it shouts if the
corpus fallback is active.

Every observation in this book is version dependent and target dependent. "GCC generates a
cmov here" is true on x86-64 and false on aarch64, and it is stated as a universal truth in
a great deal of published material. The banner is the cheapest possible defence against
this project doing the same thing.
"""

from __future__ import annotations

import platform
import textwrap
from dataclasses import dataclass

from gxray.driver import Backend, CEBackend, CorpusBackend, LocalBackend

PINNED = "16.2.0"

LABEL_WIDTH = 13


def _labelled(label: str, text: str, width: int) -> list[str]:
    """A label and its text, wrapped so a banner never runs off the side of a notebook."""
    body = textwrap.wrap(text, max(20, width - LABEL_WIDTH)) or [""]
    head = f"  {label}".ljust(LABEL_WIDTH)
    return [head + body[0]] + [" " * LABEL_WIDTH + line for line in body[1:]]


@dataclass
class Banner:
    """What the reader is looking at."""

    backend: str
    tier: str
    compiler: str
    target: str
    host: str
    warning: str = ""

    @property
    def pinned(self) -> bool:
        return PINNED in self.compiler

    def as_dict(self) -> dict[str, str]:
        return {
            "backend": self.backend,
            "tier": self.tier,
            "compiler": self.compiler,
            "target": self.target,
            "host": self.host,
            "warning": self.warning,
        }

    def as_text(self, width: int = 88) -> str:
        lines = [
            f"  compiler   {self.compiler}",
            f"  target     {self.target}",
            f"  backend    {self.backend}  ({self.tier})",
            f"  host       {self.host}",
        ]
        if not self.pinned:
            lines += _labelled(
                "NOTE", f"this is not the pinned {PINNED}, so the numbers may differ", width
            )
        if self.warning:
            lines += _labelled("WARNING", self.warning, width)
        rule = "-" * (max(len(x) for x in lines) + 2)
        return "\n".join([rule, *lines, rule])

    def as_html(self) -> str:
        rows = "".join(
            f"<tr><th style='text-align:left;padding-right:1em'>{k}</th><td>{v}</td></tr>"
            for k, v in [
                ("compiler", self.compiler),
                ("target", self.target),
                ("backend", f"{self.backend} ({self.tier})"),
            ]
        )
        note = ""
        if self.warning:
            note = (
                "<p style='margin:.4em 0 0;padding:.4em .6em;background:#fff3cd;"
                f"border-left:3px solid #d39e00'>{self.warning}</p>"
            )
        return (
            "<div style='font:13px ui-monospace,monospace;border:1px solid #ccc;"
            f"border-radius:4px;padding:.6em .8em'><table>{rows}</table>{note}</div>"
        )

    def __str__(self) -> str:
        return self.as_text()


def banner(backend: Backend | None = None) -> Banner:
    """Describe a backend. With no argument, describe a local `gcc-16`."""
    backend = backend if backend is not None else LocalBackend()
    host = f"{platform.system()} {platform.release()} {platform.machine()}"

    if isinstance(backend, LocalBackend):
        if not backend.available:
            return Banner(
                backend=backend.name,
                tier="Tier 1",
                compiler="not found",
                target="unknown",
                host=host,
                warning=f"{backend.gcc} is not on PATH, so nothing below this will run",
            )
        return Banner(backend.name, "Tier 1", backend.version(), backend.target(), host)

    if isinstance(backend, CEBackend):
        return Banner(
            backend=backend.name,
            tier="Tier 0",
            compiler=f"Compiler Explorer {backend.compiler}",
            target="x86-64 unless the flags say otherwise",
            host=host,
        )

    if isinstance(backend, CorpusBackend):
        from gxray.corpus import load

        try:
            rec = load(backend.entry, root=backend.root)
        except FileNotFoundError as exc:
            return Banner(backend.name, "Tier 0 offline", "unknown", "unknown", host, str(exc))
        return Banner(
            backend=backend.name,
            tier="Tier 0 offline",
            compiler=rec.compiler,
            target=rec.target,
            host=host,
            warning=(
                f"these are recorded dumps from {rec.recorded}, not a live compiler. "
                "Nothing here responds to a change in the source."
            ),
        )

    return Banner(str(backend), "unknown", "unknown", "unknown", host)
