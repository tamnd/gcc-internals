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
SCRIPT = ROOT / "docs" / "assets" / "island.js"

# What the head fragment looks like, in miniature. The real one is thirty lines of marimo's
# stylesheets and font preconnects with the bundle at the top.
HEAD = (
    '<script type="module" src="https://cdn.example/islands@1.2.3/dist/main.js"></script>\n'
    '<link href="https://cdn.example/islands@1.2.3/dist/style.css" rel="stylesheet" />\n'
    '<link rel="preconnect" href="https://fonts.example" />\n'
    '<link href="https://fonts.example/css2?family=Lora" rel="stylesheet" />\n'
)

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


def test_every_host_the_runtime_will_use_gets_a_connection_opened_early():
    """A handshake carries no payload, so this is free, and it is a second off the timeout."""
    assert island.origins(HEAD) == ["https://cdn.example", "https://fonts.example"]


def test_a_host_named_twice_is_only_connected_to_once():
    twice = HEAD + '<link href="https://cdn.example/katex/katex.min.css" rel="stylesheet" />'
    assert island.origins(twice) == ["https://cdn.example", "https://fonts.example"]


def test_a_head_that_fetches_nothing_from_anywhere_else_needs_no_warming():
    assert island.origins("<marimo-filename hidden></marimo-filename>") == []
    assert island.Island("probe", "<marimo-filename hidden></marimo-filename>", "").bundle == ""


def test_the_preconnects_are_outside_the_template_or_they_do_nothing():
    """Everything in the template is inert. That is the point of the template, and it is
    exactly the wrong thing for a hint whose whole job is to happen before the button."""
    markup = island.Island("probe", HEAD, "<p>cells</p>").embed()
    assert markup.index('rel="preconnect" href="https://cdn.example"') < markup.index("<template")


def test_the_button_carries_the_bundle_so_it_can_be_warmed_before_it_is_pressed():
    built = island.Island("probe", HEAD, "")
    assert built.bundle == "https://cdn.example/islands@1.2.3/dist/main.js"
    assert f'data-island-bundle="{built.bundle}"' in built.embed()


def test_the_bundle_is_the_script_and_not_the_first_stylesheet_next_to_it():
    """Both are on the same CDN and only one of them is tens of megabytes of dependencies."""
    assert island.Island("probe", HEAD, "").bundle.endswith("main.js")


def test_the_script_and_the_builder_agree_on_the_attribute_they_share():
    """Two files, one contract. Rename it in one of them and warming silently stops."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "data-island-bundle" in text
    assert "data-island-bundle" in island.Island("probe", HEAD, "").embed()


def test_the_reader_is_told_when_it_has_given_up_rather_than_left_on_a_spinner():
    """Issue #41. Marimo's RPC times out on a cold browser and nothing on the page says so."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "is-stuck" in text
    assert "island-reload" in text
    assert "location.reload()" in text


def test_the_status_line_does_not_promise_a_few_seconds():
    """It was most of a minute on a cold browser, measured. Saying otherwise loses readers
    who would have waited if they had been told what they were waiting for."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "takes up to a minute" in text
    assert "a few seconds" not in text


def test_the_stuck_state_has_somewhere_to_be_styled():
    css = (ROOT / "docs" / "assets" / "gxray.css").read_text(encoding="utf-8")
    assert ".island.is-stuck" in css
    assert ".island-reload" in css


@pytest.mark.needs_marimo
@leaky
def test_the_real_head_names_a_bundle_and_the_hosts_it_comes_from():
    built = island.render(PROBE)
    assert built.bundle.endswith(".js")
    assert built.bundle.startswith("https://")
    assert built.bundle in built.embed()
    assert len(island.origins(built.head)) >= 2


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
