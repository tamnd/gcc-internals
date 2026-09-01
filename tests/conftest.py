"""Shared fixtures.

The parser tests run against text a real `gcc-16` produced, kept in `tests/fixtures`, not
against text somebody wrote to make a parser pass. Regenerate them with:

    python -m gxray dumps --dump tree-ssa -O2

Tests that drive a compiler are marked `needs_gcc` and skip when there is not one, so the
suite is green on a laptop with no GCC and thorough on one that has it.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
HAVE_GCC = shutil.which("gcc-16") is not None
HAVE_MARIMO = importlib.util.find_spec("marimo") is not None


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def ssa_dump() -> str:
    """The tree-ssa dump of L1 at -O2."""
    return fixture("l1-O2-tree-ssa.txt")


@pytest.fixture
def passes_text() -> str:
    """The -fdump-passes output for L1 at -O2. 395 lines."""
    return fixture("l1-O2-passes.txt")


@pytest.fixture
def loops_graph() -> str:
    """A graph dump of a switch and two nested loops, at -O1.

    Written by `gcc-16 -O1 -c -fdump-tree-optimized-graph`. It is here because `l1.c` has
    one loop and no nesting, and the cluster nesting in a graph dump is the only place the
    loop tree shows up.
    """
    return fixture("loops-O1-optimized-graph.dot")


@pytest.fixture
def setjmp_graph() -> str:
    """A graph dump of a function that calls setjmp, at -O1.

    This is where the abnormal edges are. It also has the awkward case the parser has to get
    right: an edge back to the setjmp receiver that is abnormal and a back edge at once.
    """
    return fixture("setjmp-O1-optimized-graph.dot")


def pytest_collection_modifyitems(config, items):
    no_gcc = pytest.mark.skip(reason="no gcc-16 on PATH")
    no_marimo = pytest.mark.skip(reason="marimo is not installed, try pip install -e '.[site]'")
    for item in items:
        if "needs_gcc" in item.keywords and not HAVE_GCC:
            item.add_marker(no_gcc)
        if "needs_marimo" in item.keywords and not HAVE_MARIMO:
            item.add_marker(no_marimo)
