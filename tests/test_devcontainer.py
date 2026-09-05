"""The devcontainer, which is B01's escape hatch and therefore has to work unattended.

Nobody runs a devcontainer in CI, so nothing else in this project would notice if the image
it names stopped existing. What can be checked cheaply is that the digest it pins is a
digest the build matrix actually published, which is the failure that would otherwise turn
up as a stranger's first five minutes with the repository ending in a pull error.

JSON with comments in it is what the devcontainer specification takes, and `json` will not
read that, so the comments are stripped here rather than left out of the file. Leaving them
out is the wrong trade: the file is read by people far more often than by machines.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".devcontainer" / "devcontainer.json"
LOCKFILE = ROOT / "containers" / "images.lock.json"

#: A `//` comment, anywhere except inside a string. The lookbehind is the whole trick: a
#: `https://` in a value is two slashes and is not a comment.
COMMENT = re.compile(r"(?<!:)//.*$", re.MULTILINE)


def load() -> dict:
    return json.loads(COMMENT.sub("", CONFIG.read_text(encoding="utf-8")))


def published() -> dict[str, str]:
    return json.loads(LOCKFILE.read_text(encoding="utf-8"))["images"]


def test_the_file_is_there_and_parses_once_the_comments_are_gone():
    assert CONFIG.is_file(), "B01 tells the reader to open this repository in a container"
    assert load()["name"].startswith("gcc-internals")


def test_the_image_is_pinned_by_digest_and_not_by_a_tag_somebody_could_move():
    image = load()["image"]
    assert "@sha256:" in image, f"{image} is a tag, and a tag is a name that can be moved"


def test_the_digest_is_one_the_build_matrix_published():
    """A digest nobody published is a pull error on somebody's first five minutes."""
    name, digest = load()["image"].split("@", 1)
    known = published()
    matching = [tag for tag, sha in known.items() if sha == digest]
    assert matching, f"{digest} is in no row of images.lock.json. Known: {sorted(known)}"
    assert all(tag.startswith(name + ":") for tag in matching), (
        f"{digest} belongs to {matching} and the devcontainer calls it {name}"
    )


def test_the_container_installs_the_tooling_the_lessons_import():
    """`import gxray` failing in the escape hatch defeats the point of the escape hatch."""
    assert "pip install -e" in load()["postCreateCommand"]


def test_it_asks_for_a_python_new_enough_for_this_package():
    features = load()["features"]
    python = next(v for k, v in features.items() if "python" in k)
    assert tuple(int(n) for n in str(python["version"]).split(".")) >= (3, 11)


@pytest.mark.parametrize("field", ["image", "features", "postCreateCommand"])
def test_the_fields_a_reader_depends_on_are_all_present(field):
    assert field in load()
