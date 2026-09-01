"""Shared fixtures.

The parser tests run against text a real `gcc-16` produced, kept in `tests/fixtures`, not
against text somebody wrote to make a parser pass. Regenerate them with:

    python -m gxray dumps --dump tree-ssa -O2

Tests that drive a compiler are marked `needs_gcc` and skip when there is not one, so the
suite is green on a laptop with no GCC and thorough on one that has it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
HAVE_GCC = shutil.which("gcc-16") is not None


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


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="no gcc-16 on PATH")
    for item in items:
        if "needs_gcc" in item.keywords and not HAVE_GCC:
            item.add_marker(skip)
