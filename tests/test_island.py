"""Tests for the marimo island builder.

Most of this runs without marimo installed, because the parts that can go wrong quietly are
the marker, the id rewriting and the static fallback, and all three are string work. The two
tests that build a real notebook are marked `needs_marimo` and run in the site job.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tools import island

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "site" / "notebooks" / "ce-probe.py"

# Marimo builds a notebook by starting a kernel in another process, and the sockets it opens
# to talk to it get closed by the garbage collector rather than by marimo. That is marimo's
# business, and this suite turns warnings into errors, so the two have to be kept apart.
leaky = pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")


@dataclass
class FakeOutput:
    mimetype: str
    data: str


@dataclass
class FakeStub:
    output: FakeOutput | None


def test_a_page_says_which_notebooks_it_wants_without_building_them():
    page = "before\n\n<!-- island: site/notebooks/ce-probe.py -->\n\nafter\n"
    assert island.islands_in(page) == ["site/notebooks/ce-probe.py"]


def test_a_marker_has_to_be_on_a_line_of_its_own():
    """Otherwise a sentence about the syntax turns into an island the moment it is written."""
    assert island.islands_in("text <!-- island: a.py --> more text") == []
    assert island.islands_in("  <!-- island: a.py -->  ") == ["a.py"]


def test_a_page_with_no_marker_comes_back_exactly_as_it_went_in():
    page = "# A page\n\nNo islands here.\n"
    assert island.expand(page) == page


def test_the_same_markup_builds_the_same_ids_every_time():
    markup = (
        "<marimo-cell-output><marimo-ui-element object-id='cell-1' "
        "random-id='6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d'>x</marimo-ui-element>"
        "</marimo-cell-output>"
    )
    other = markup.replace(
        "6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d", "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )
    assert island.stable_ids(markup) == island.stable_ids(other)


def test_two_elements_on_a_page_do_not_end_up_with_the_same_id():
    markup = (
        "<a object-id='cell-1' random-id='6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d'></a>"
        "<a object-id='cell-2' random-id='6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d'></a>"
    )
    ids = island.RANDOM_ID.findall(island.stable_ids(markup))
    assert len(set(ids)) == 2


def test_an_id_still_looks_like_a_uuid_afterwards():
    markup = "<a object-id='cell-1' random-id='6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d'></a>"
    (fixed,) = island.RANDOM_ID.findall(island.stable_ids(markup))
    assert [len(part) for part in fixed.split("-")] == [8, 4, 4, 4, 12]


def test_prose_output_is_written_into_the_page_as_well():
    stub = FakeStub(FakeOutput("text/markdown", "<p>It worked.</p>"))
    assert island.static_copy(stub) == '<div class="island-static"><p>It worked.</p></div>'


def test_an_input_control_gets_no_static_copy():
    """A button that cannot be pressed is worse than no button at all."""
    assert island.static_copy(FakeStub(FakeOutput("text/html", "<marimo-button />"))) == ""
    assert island.static_copy(FakeStub(FakeOutput("text/markdown", ""))) == ""
    assert island.static_copy(FakeStub(None)) == ""


def test_the_runtime_is_parked_in_a_template_so_nothing_downloads_on_page_load():
    markup = island.Island("probe", "<script src='marimo.js'></script>", "<p>cells</p>").embed()
    head = markup.index("<template")
    assert head < markup.index("<script src='marimo.js'>") < markup.index("</template>")
    assert "data-island-start" in markup
    assert "<noscript>" in markup


def test_the_button_says_what_it_is_about_to_do():
    markup = island.Island("probe", "", "").embed(label="Run the probe")
    assert ">Run the probe</button>" in markup
    assert "Starts Python in your browser" in markup


@pytest.mark.needs_marimo
@leaky
def test_the_probe_notebook_builds_into_something_a_page_can_hold():
    built = island.render(PROBE)
    assert built.name == "ce-probe"
    assert "marimo-island" in built.body
    # The banner cell renders at build time, and this is the branch it has to take there.
    assert "not started yet" in built.body
    assert "island-static" in built.body


@pytest.mark.needs_marimo
@leaky
def test_building_the_same_notebook_twice_gives_the_same_bytes():
    """Otherwise every rebuild is a diff nobody can read and nobody reviews."""
    assert island.render(PROBE).body == island.render(PROBE).body
