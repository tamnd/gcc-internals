"""MkDocs hooks.

One job: find the island markers in a page and build the notebooks they name. The work is
in `tools/island`, which knows nothing about MkDocs, so it can be tested without one.

Building a notebook costs a few seconds because the cells actually run, so pages with no
marker in them never pay for it and `mkdocs serve` stays usable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tools import island

log = logging.getLogger("mkdocs.hooks.islands")
ROOT = Path(__file__).resolve().parent.parent


def on_page_markdown(markdown: str, page, config, files) -> str:  # noqa: ARG001
    wanted = island.islands_in(markdown)
    if not wanted:
        return markdown
    for name in wanted:
        log.info("building island %s for %s", name, page.file.src_path)
    return island.expand(markdown, root=ROOT)
