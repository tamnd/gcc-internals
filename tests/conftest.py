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
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
HAVE_GCC = shutil.which("gcc-16") is not None
HAVE_MARIMO = importlib.util.find_spec("marimo") is not None
HAVE_NBCLIENT = importlib.util.find_spec("nbclient") is not None


def _gcc_with_plugin_headers() -> str | None:
    """A GCC that can build a plugin, or None.

    Two conditions, and they are separate. A GCC 16 without its plugin development package
    has no `gcc-plugin.h` to compile against, and that is the ordinary case on a machine
    that installed a compiler and nothing else. A GCC of any other version has the headers
    but the wrong ABI, and `plugin_default_version_check` would refuse the result at load
    time, so building against it proves nothing.
    """
    for name in ("gcc-16", "gcc"):
        found = shutil.which(name)
        if not found:
            continue
        version = subprocess.run(
            [found, "-dumpfullversion"], capture_output=True, text=True, check=False
        )
        if not version.stdout.startswith("16."):
            continue
        where = subprocess.run(
            [found, "-print-file-name=plugin"], capture_output=True, text=True, check=False
        )
        if (Path(where.stdout.strip()) / "include" / "gcc-plugin.h").exists():
            return found
    return None


GCC_PLUGIN = _gcc_with_plugin_headers()


LESSONS = Path(__file__).resolve().parent.parent / "lessons"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def grader(lesson: str):
    """The `grade.py` of one lesson, loaded from its path.

    Every lesson has a module called `grade`, so a plain import would hand the second test
    that asks for one whatever the first test imported. Loading by path under the lesson's
    own name keeps them apart.
    """
    path = LESSONS / lesson / "grade.py"
    spec = importlib.util.spec_from_file_location(f"grade_{lesson.replace('-', '_')}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


@pytest.fixture(scope="session")
def gcc_plugin() -> str:
    """The compiler the plugin tests build against.

    Only reached by a test marked `needs_gcc_plugin`, which has already been skipped when
    there is no such compiler, so the assert is a statement about the marker and not a
    thing that can fire in a normal run.
    """
    assert GCC_PLUGIN is not None
    return GCC_PLUGIN


def pytest_collection_modifyitems(config, items):
    no_gcc = pytest.mark.skip(reason="no gcc-16 on PATH")
    no_plugin = pytest.mark.skip(reason="no gcc-16 with plugin headers, try gcc-16-plugin-dev")
    no_marimo = pytest.mark.skip(reason="marimo is not installed, try pip install -e '.[site]'")
    no_kernel = pytest.mark.skip(reason="nbclient is missing, try pip install -e '.[lessons]'")
    for item in items:
        if "needs_gcc" in item.keywords and not HAVE_GCC:
            item.add_marker(no_gcc)
        if "needs_gcc_plugin" in item.keywords and GCC_PLUGIN is None:
            item.add_marker(no_plugin)
        if "needs_marimo" in item.keywords and not HAVE_MARIMO:
            item.add_marker(no_marimo)
        if "needs_nbclient" in item.keywords and not HAVE_NBCLIENT:
            item.add_marker(no_kernel)
