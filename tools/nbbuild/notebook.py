"""Writing a `.ipynb` that a diff tool can cope with.

Notebook JSON is not hard, it is just fussy, and every fussy detail here is one that makes
a rebuild produce different bytes from the last one. That matters more than it sounds,
because the notebooks are committed and CI compares a fresh build to what is on disk. Any
instability at all and the check fails at random, and a check that fails at random gets
switched off within a week.

So: keys in alphabetical order, which is what Jupyter itself writes, so opening a lesson
and saving it does not reorder the file. Two space indent and a trailing newline, same
reason. Source stored as a list of lines with the newlines left on, because that is the
format nbformat produces and anything else looks like a conflict the moment somebody edits
a notebook in Jupyter.

Outputs are never written. The only proof a cell works is CI running it, and a stored
output is a screenshot that goes stale without telling anybody.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

NBFORMAT = (4, 5)


def as_lines(source: str) -> list[str]:
    """A cell's source in the shape nbformat stores it.

    One string per line with the newline still on the end, and no newline on the last one.
    `"".join(lines)` gives the source back exactly.
    """
    text = source.strip("\n")
    if not text:
        return []
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


@dataclass
class Cell:
    """One cell. `kind` is `markdown` or `code`."""

    kind: str
    ident: str
    source: str

    def as_json(self) -> dict:
        cell = {
            "cell_type": self.kind,
            "id": self.ident,
            "metadata": {},
            "source": as_lines(self.source),
        }
        if self.kind == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        return dict(sorted(cell.items()))


def document(cells: list[Cell], python: str = "3.12") -> str:
    """The whole notebook, as the text that goes on disk.

    The kernel and language metadata is what Colab and Jupyter read to decide they can open
    the file. `python` is the version the lesson was written against, which is a note to a
    reader rather than a requirement Colab enforces.
    """
    notebook = {
        "cells": [cell.as_json() for cell in cells],
        "metadata": {
            "colab": {"provenance": []},
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": python},
        },
        "nbformat": NBFORMAT[0],
        "nbformat_minor": NBFORMAT[1],
    }
    return json.dumps(notebook, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
