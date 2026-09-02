"""The films: the rules a film has to obey, and the SVG they turn into.

A film is six or seven ordinary scenes and a stylesheet, so most of what could go wrong is
already covered by the scene tests next door. What is not covered there, and is checked
here, is everything that only exists once a scene becomes a shot: the running time, the
alt text, the keyframes lining up end to end, and the poster frame being a real shot rather
than a stack of all of them.

Building all six is the slow part of this file, so it happens once per session and every
test reads the same six.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from gxmanim import films, svg
from gxmanim.film import BRIEFEST, LONGEST, LONGEST_SHOT, SHORTEST, Film, Shot
from gxmanim.primitives import Edge
from gxmanim.scene import Scene

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def reels():
    return films.films()


@pytest.fixture(scope="session")
def names():
    return sorted(films.BUILDERS)


#: The smallest legal film is eight shots, not two. A shot may run nine seconds and a film
#: has to reach sixty, so seven is the floor and eight is the first round number above it.
SHOTS = tuple(
    Shot(scene=Scene(title=f"scene {n}"), caption=f"the {n} one", seconds=8.0) for n in range(1, 9)
)


def tiny(**kw) -> Film:
    """A film that passes, for the tests that are about breaking one rule at a time."""
    defaults = dict(
        name="tiny",
        title="A film with nothing in it",
        alt=(
            "One empty scene follows another empty scene. Nothing is drawn in any of them. "
            "This exists so a test has something legal to break."
        ),
        shots=SHOTS,
    )
    return Film(**{**defaults, **kw})


# The rules


def test_the_smallest_legal_film_is_legal():
    assert tiny().check() == []


def test_a_name_css_cannot_spell_is_caught_before_it_is_rendered():
    assert any("usable name" in bad for bad in tiny(name="SSA The Movie").check())


def test_a_film_with_one_shot_is_a_diagram():
    one = tiny(shots=(Shot(scene=Scene(title="only"), caption="alone", seconds=70.0),))
    assert any("one shot is a diagram" in bad for bad in one.check())


def test_a_film_that_runs_too_long_is_two_films():
    long = tiny(
        shots=tuple(
            Shot(scene=Scene(title=f"s{n}"), caption="something", seconds=9.0) for n in range(11)
        )
    )
    assert any("two films" in bad for bad in long.check())


def test_a_film_that_runs_too_short_is_a_diagram_somebody_animated():
    short = tiny(
        shots=(
            Shot(scene=Scene(title="a"), caption="one", seconds=5.0),
            Shot(scene=Scene(title="b"), caption="two", seconds=5.0),
        )
    )
    assert any("the rule is" in bad for bad in short.check())


def test_a_shot_nobody_can_read_in_time_is_caught():
    quick = tiny(
        shots=(
            Shot(scene=Scene(title="a"), caption="one", seconds=BRIEFEST / 2),
            Shot(scene=Scene(title="b"), caption="two", seconds=69.0),
        )
    )
    assert any("shot 1 is" in bad for bad in quick.check())


def test_a_shot_that_outstays_its_welcome_is_caught():
    slow = tiny(
        shots=(
            Shot(scene=Scene(title="a"), caption="one", seconds=LONGEST_SHOT + 1),
            Shot(scene=Scene(title="b"), caption="two", seconds=60.0),
        )
    )
    assert any("shot 1 is" in bad for bad in slow.check())


def test_a_shot_with_no_caption_has_nothing_to_say():
    quiet = tiny(
        shots=(
            Shot(scene=Scene(title="a"), caption="   ", seconds=35.0),
            Shot(scene=Scene(title="b"), caption="two", seconds=35.0),
        )
    )
    assert any("no caption" in bad for bad in quiet.check())


@pytest.mark.parametrize(
    "opening",
    ["Animation of SSA construction.", "A video showing the passes.", "Diagram of the CFG."],
)
def test_alt_text_that_describes_the_file_rather_than_the_film_is_rejected(opening):
    lazy = tiny(alt=f"{opening} It moves. Then it stops.")
    assert any("describes the file" in bad for bad in lazy.check())


def test_alt_text_of_one_sentence_is_not_alt_text():
    thin = tiny(alt="The pass tape fills up.")
    assert any("sentence" in bad for bad in thin.check())


def test_no_alt_text_at_all_says_who_it_was_for():
    assert any("some readers get" in bad for bad in tiny(alt="").check())


def test_a_problem_in_a_shots_scene_is_a_problem_with_the_film():
    # An edge to a box that is not in the scene is the scene's own rule. The film has to
    # inherit it and say which shot it came from, rather than discovering it at render time.
    scene = Scene(title="broken")
    scene.link(Edge(src="a", dst="b"))
    broken = tiny(
        shots=(
            Shot(scene=scene, caption="one", seconds=35.0),
            Shot(scene=Scene(title="ok"), caption="two", seconds=35.0),
        )
    )
    assert any(bad.startswith("shot 1:") for bad in broken.check())


# The arithmetic


def test_the_marks_run_end_to_end_with_no_gap():
    film = tiny()
    marks = film.marks()
    assert marks[0][0] == 0
    assert marks[-1][1] == 100
    for (_, ends), (starts, _) in zip(marks, marks[1:], strict=False):
        assert ends == starts


def test_a_shot_gets_a_slice_of_the_film_the_size_of_its_seconds():
    film = tiny(
        shots=(
            Shot(scene=Scene(title="a"), caption="one", seconds=20.0),
            Shot(scene=Scene(title="b"), caption="two", seconds=60.0),
        )
    )
    assert film.marks() == [(0.0, 25.0), (25.0, 100.0)]


def test_the_poster_is_the_last_shot_unless_the_film_says_otherwise():
    film = tiny()
    assert film.poster() is film.shots[-1].scene
    assert tiny(still=0).poster() is film.shots[0].scene


def test_the_description_puts_the_alt_text_before_the_inventory():
    lines = tiny().describe().splitlines()
    assert lines[0] == "A film with nothing in it"
    assert lines[2] == "8 shots, 64 seconds"
    assert lines[3].startswith("1. scene 1.")


# The six


def test_there_are_six_films(names):
    assert len(names) == 6


def test_every_film_obeys_its_own_rules(reels):
    for name, reel in reels.items():
        assert reel.check() == [], f"{name}:\n  " + "\n  ".join(reel.check())


def test_a_film_is_named_after_the_key_it_is_filed_under(reels):
    for name, reel in reels.items():
        assert reel.name == name


def test_every_film_lands_in_the_window(reels):
    for name, reel in reels.items():
        assert SHORTEST <= reel.seconds() <= LONGEST, name


def test_asking_for_a_film_that_does_not_exist_says_what_does():
    with pytest.raises(KeyError) as exc:
        films.build("ssa-the-movie")
    assert "pass-tape" in str(exc.value)


def test_no_two_shots_in_a_film_say_the_same_thing(reels):
    """A shot that repeats the one before it is a shot that could be cut.

    Repeated captions are the usual sign of a builder that meant to vary something and
    varied it in the scene only, which a reader watching the caption line will not see.
    """
    for name, reel in reels.items():
        captions = [shot.caption for shot in reel.shots]
        assert len(captions) == len(set(captions)), name


def test_a_shot_says_something_the_title_does_not(reels):
    for name, reel in reels.items():
        for n, shot in enumerate(reel.shots, start=1):
            assert shot.caption.strip() != shot.scene.title.strip(), f"{name} shot {n}"


# The SVG


def test_a_film_renders_the_same_bytes_twice(reels):
    """The rule the whole project runs on, applied to the one output with a clock in it.

    An animated SVG has timings in it, and a timing computed from `time` rather than from
    the corpus would pass every other test in this file and fail this one.
    """
    for name, reel in reels.items():
        assert svg.film_document(reel) == svg.film_document(reel), name


def test_a_film_is_one_svg_element_and_it_parses(reels):
    for name, reel in reels.items():
        root = ET.fromstring(svg.film_document(reel))
        assert root.tag.endswith("svg"), name


def test_the_frame_is_big_enough_for_the_biggest_shot(reels):
    for name, reel in reels.items():
        drawn = svg.Film(reel)
        widest = max(shot.scene.bounds().w for shot in reel.shots)
        tallest = max(shot.scene.bounds().h for shot in reel.shots)
        assert drawn.width == widest, name
        assert drawn.height == tallest, name


def test_every_shot_gets_a_group_and_a_keyframe_block(reels):
    for name, reel in reels.items():
        out = svg.film(reel)
        for n in range(1, len(reel.shots) + 1):
            assert f"gx-{name} gx-{name}-{n}" in out, f"{name} shot {n}"
            assert f"@keyframes gx-{name}-{n}" in out, f"{name} shot {n}"


def test_two_films_on_one_page_do_not_take_each_others_timings(reels):
    """Keyframes are global to the page wherever the style that declares them sits.

    The contact sheet inlines all six, and a lesson that embeds a film sits on a page with
    other drawings on it, so every name a film declares has the film's name in it.
    """
    declared = [set(re.findall(r"@keyframes ([\w-]+)", svg.film(reel))) for reel in reels.values()]
    for n, mine in enumerate(declared):
        for theirs in declared[n + 1 :]:
            assert mine & theirs == set()


def test_the_arrowheads_are_defined_once_and_not_once_per_shot(reels):
    """Two elements with the same id in one document is invalid SVG, and the arrowheads are
    the only thing a film draws that has a fixed id on it."""
    for name, reel in reels.items():
        assert svg.film(reel).count('id="gx-arrow"') == 1, name


def test_with_no_animation_at_all_one_whole_shot_is_visible(reels):
    """Base state is the poster frame. A renderer that ignores CSS animation, and a reader
    who has asked for no motion, both get one readable picture rather than a stack."""
    for name, reel in reels.items():
        out = svg.film(reel)
        still = reel.still % len(reel.shots) + 1
        assert f".gx-{name}-{still} {{ opacity: 1 }}" in out, name


def test_a_reader_who_asked_for_no_motion_gets_none(reels):
    for name, reel in reels.items():
        out = svg.film(reel)
        assert "prefers-reduced-motion: reduce" in out, name
        assert re.search(r"reduce\)[^}]*\{[^}]*animation: none", out), name


def test_the_standalone_file_carries_the_title_and_the_alt_text(reels):
    for name, reel in reels.items():
        out = svg.film_document(reel)
        assert f"<title>{reel.title}</title>" in out, name
        assert reel.alt.split(".")[0] in out, name


def test_the_fragment_does_not_repeat_the_alt_text(reels):
    """Inline in a page the surrounding markup carries the description, and a screen reader
    that finds it twice reads it twice."""
    for name, reel in reels.items():
        assert "<desc>" not in svg.film(reel), name


def test_the_poster_frame_is_a_plain_scene_with_no_animation_in_it(reels):
    for name, reel in reels.items():
        out = svg.still(reel)
        assert "@keyframes" not in out, name
        assert f"gx-{name}" not in out, name


def test_a_film_that_breaks_its_own_rules_refuses_to_draw():
    with pytest.raises(ValueError) as exc:
        svg.film(tiny(alt=""))
    assert "cannot be drawn" in str(exc.value)


def test_the_committed_films_are_the_films_the_corpus_makes(reels):
    """`python -m gxmanim film` writes these, and CI runs it and looks for a diff.

    Reading the committed file here as well means a stale one fails the test suite rather
    than only failing the workflow, which is the difference between finding out in the
    editor and finding out in a pull request.
    """
    root = ROOT / films.DIRECTORY
    for name, reel in reels.items():
        assert (root / f"{name}.svg").read_text(encoding="utf-8") == svg.film_document(reel), name
        assert (root / f"{name}-still.svg").read_text(encoding="utf-8") == svg.still(reel), name


def test_the_films_page_says_what_the_films_say(reels):
    """The page is generated from the films, so the description on it cannot go stale.

    This is the same arrangement as `GLOSSARY.md`. A description that has drifted from the
    thing it describes is worse than no description, and prose in a markdown file has no
    other way of noticing.
    """
    page = ROOT / films.PAGE
    assert page.read_text(encoding="utf-8") == films.markdown(reels)


def test_every_film_points_at_a_lesson_that_exists(reels):
    for name in reels:
        _, slug = films.GOES_WITH[name]
        assert (ROOT / "lessons" / f"{slug}.ipynb").exists(), name


def test_every_lesson_with_a_film_points_back_at_it(reels):
    """A film nobody is sent to is a film nobody watches.

    The anchor rather than the title, because the title is allowed to change and this link
    is not supposed to break when it does.
    """
    for name in reels:
        _, slug = films.GOES_WITH[name]
        builder = (ROOT / "lessons" / slug).parent / "build.py"
        assert films.ANCHOR.format(name=name) in builder.read_text(encoding="utf-8"), name
