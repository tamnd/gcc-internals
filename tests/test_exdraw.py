"""The Excalidraw writer, and the committed scenes that come out of it.

The interesting tests here are the boring ones. A scene has to be byte for byte the same on
every run, or the diagrams are unreviewable, and every scene in `lessons/` has to still match
the script that generates it, or a reader opens a picture that disagrees with the lesson.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import exdraw

ROOT = Path(__file__).resolve().parent.parent


def small() -> exdraw.Scene:
    scene = exdraw.Scene("small")
    a = scene.box(0, 0, 100, 40, "bb 2", fill=exdraw.BLUE)
    b = scene.box(0, 100, 100, 40, "bb 3", fill=exdraw.YELLOW)
    scene.arrow(a, b, "falls through")
    return scene


def test_a_scene_is_a_scene_excalidraw_will_open():
    scene = json.loads(small().document())
    assert scene["type"] == "excalidraw"
    assert scene["version"] == 2
    assert scene["files"] == {}
    assert scene["appState"]["viewBackgroundColor"] == "#ffffff"


def test_every_element_has_the_keys_the_format_requires():
    """Excalidraw is forgiving about extra keys and silent about missing ones."""
    required = {
        "id",
        "type",
        "x",
        "y",
        "width",
        "height",
        "angle",
        "strokeColor",
        "backgroundColor",
        "seed",
        "version",
        "versionNonce",
        "isDeleted",
        "groupIds",
        "boundElements",
        "updated",
        "locked",
    }
    for element in json.loads(small().document())["elements"]:
        assert required <= set(element), f"{element['type']} is missing {required - set(element)}"


def test_the_same_scene_twice_is_the_same_bytes():
    """The whole reason for generating these. Excalidraw seeds elements randomly."""
    assert small().document() == small().document()


def test_ids_do_not_collide_across_kinds():
    ids = [element["id"] for element in json.loads(small().document())["elements"]]
    assert len(ids) == len(set(ids))


def test_a_label_is_bound_to_its_box_rather_than_floating_on_top():
    """So that dragging the box in the app takes the text with it."""
    elements = {e["id"]: e for e in json.loads(small().document())["elements"]}
    box = next(e for e in elements.values() if e["type"] == "rectangle")
    bound = [b for b in box["boundElements"] if b["type"] == "text"]
    assert len(bound) == 1
    assert elements[bound[0]["id"]]["containerId"] == box["id"]


def test_an_arrow_is_bound_at_both_ends():
    elements = json.loads(small().document())["elements"]
    arrow = next(e for e in elements if e["type"] == "arrow")
    assert arrow["startBinding"] is not None
    assert arrow["endBinding"] is not None
    boxes = [e for e in elements if e["type"] == "rectangle"]
    for box in boxes:
        assert any(b["type"] == "arrow" for b in box["boundElements"])


def test_a_bend_puts_a_point_in_the_middle():
    scene = exdraw.Scene("bent")
    a = scene.box(0, 0, 100, 40)
    b = scene.box(0, 200, 100, 40)
    scene.arrow(a, b, bend=80)
    arrow = next(e for e in scene.elements if e["type"] == "arrow")
    assert len(arrow["points"]) == 3
    assert arrow["points"][1][0] == pytest.approx(80)


def test_measure_grows_with_the_longest_line_not_the_total():
    wide, tall = exdraw.measure("a\nbbbbbbbbbb", 16)
    assert wide == pytest.approx(10 * 16 * exdraw.WIDTH)
    assert tall == pytest.approx(2 * 16 * exdraw.LINE)


def test_a_box_with_no_label_has_nothing_bound_to_it():
    scene = exdraw.Scene("bare")
    scene.box(0, 0, 10, 10)
    assert [e["type"] for e in scene.elements] == ["rectangle"]


def scripts() -> list[Path]:
    return sorted((ROOT / "lessons").glob("*/diagram.py"))


def test_there_is_at_least_one_lesson_diagram():
    assert scripts(), "no lessons/*/diagram.py found"


@pytest.mark.parametrize("script", scripts(), ids=lambda p: p.parent.name)
def test_the_committed_scene_matches_the_script_that_draws_it(script, tmp_path):
    """A diagram that has drifted from its script is worse than no diagram."""
    before = {p: p.read_bytes() for p in (script.parent / "diagrams").glob("*.excalidraw")}
    assert before, f"{script.parent.name} has a diagram.py and no scenes"
    done = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, cwd=ROOT, check=False
    )
    assert done.returncode == 0, done.stderr
    for path, content in before.items():
        assert path.read_bytes() == content, f"{path.name} is stale, run `just lesson-diagrams`"
