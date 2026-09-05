"""The reader facing view of the build matrix.

`tools.matrix` is checked next door and is about whether the file is well formed and whether
the workflow agrees with it. This is about the other question, the one B01 asks: given the
same file, does a reader get commands that would work if they typed them.

Nothing here needs Docker, a registry, or the pinned GCC tree.
"""

from __future__ import annotations

import pytest

from gxray import toolchain
from tools import matrix

EVERY = toolchain.names()


def test_the_package_exports_it_so_a_lesson_can_say_gxray_toolchain():
    import gxray

    assert gxray.toolchain is toolchain
    assert "toolchain" in gxray.__all__


def test_every_configuration_in_the_file_has_a_plan():
    """A configuration somebody adds and nothing here can describe is a configuration the
    lesson silently stops mentioning."""
    assert EVERY == [c.id for c in matrix.load().configs]
    for name in EVERY:
        arch = matrix.load()[name].arches[0]
        assert toolchain.plan(name, arch).id == name


def test_asking_for_an_architecture_a_configuration_is_not_built_for_says_which_it_is():
    every = matrix.load()
    name = every.configs[0].id
    with pytest.raises(toolchain.ToolchainError, match="only for"):
        toolchain.plan(name, "sparc")


def test_asking_for_a_configuration_that_does_not_exist_lists_the_ones_that_do():
    with pytest.raises(matrix.MatrixError, match="There is"):
        toolchain.plan("nope")


def test_the_configure_line_carries_the_shared_flags_and_the_ones_that_differ():
    """The point of the shared block is that a reader comparing two configurations sees the
    two flags that differ, and the point of `flags` is that they still get the whole line."""
    line = toolchain.plan("rel").configure()
    assert "--prefix=/opt/gcc" in line
    assert "--disable-bootstrap" in line
    assert "--enable-languages=c,c++" in line


def test_the_optimization_setting_goes_on_the_configure_line_and_not_the_make_line():
    """`make CFLAGS=...` after configuring is the mistake, because it rebuilds some of the
    tree with one setting and leaves the rest with another."""
    plan = toolchain.plan("rel")
    assert 'CFLAGS="-O2"' in plan.configure()
    assert "CFLAGS" not in plan.shell().split("../gcc/configure")[1].split("make")[1]


def test_the_bootstrap_configuration_asks_for_a_bootstrap_and_the_others_refuse_one():
    assert "--enable-bootstrap" in toolchain.plan("boot").configure()
    assert "make bootstrap" in toolchain.plan("boot").shell()
    for name in EVERY:
        config = matrix.load()[name]
        if name == "boot" or not config.from_source:
            continue
        assert "--disable-bootstrap" in toolchain.plan(name, config.arches[0]).configure()


def test_the_configuration_that_builds_nothing_has_no_configure_line_to_give():
    """`plug` wraps a distribution compiler. Asking it how it configured GCC is a question
    with no answer, and returning an empty string would look like one."""
    with pytest.raises(toolchain.ToolchainError, match="wraps one"):
        toolchain.plan("plug").configure()
    assert toolchain.plan("plug").shell().startswith("docker pull")


def test_an_image_is_pulled_by_digest_when_one_has_been_published():
    """A tag is a name somebody can move. Ten of the twelve images are recorded today, so
    this asserts the mechanism on whichever ones are, rather than on a fixed count."""
    locked = toolchain.digests()
    pulled = [toolchain.plan(c.id, a) for c in matrix.load().configs for a in c.arches]
    by_digest = [p for p in pulled if p.digest]
    assert by_digest, "no image has a recorded digest, so nothing here proves anything"
    for p in by_digest:
        assert p.pull() == f"docker pull {p.image.rsplit(':', 1)[0]}@{p.digest}"
        assert locked[p.image] == p.digest
    for p in pulled:
        if not p.digest:
            assert p.pull() == f"docker pull {p.image}"


def test_a_missing_lockfile_is_not_an_error_because_a_pip_install_has_no_containers_dir(
    tmp_path,
):
    assert toolchain.digests(tmp_path / "nothing.json") == {}


def test_the_cheapest_route_is_the_one_the_lesson_recommends_first():
    """Five minutes and a distribution compiler beats twenty two minutes and a build, and
    the recommendation has to keep saying so after somebody edits the numbers."""
    cheapest = toolchain.cheapest()
    assert cheapest.minutes == min(p.minutes for p in toolchain.plans())
    assert cheapest.id == "plug"


def test_a_reader_with_an_hour_is_shown_what_fits_and_not_what_does_not():
    fits = toolchain.route(60)
    assert [p.id for p in fits] == sorted(
        (p.id for p in fits),
        key=lambda i: (toolchain.plan(i).minutes, toolchain.plan(i).gigabytes, i),
    )
    assert all(p.minutes <= 60 for p in fits)
    assert "boot" not in [p.id for p in fits], "four hours does not fit in one"


def test_a_reader_with_no_time_at_all_is_shown_nothing_rather_than_the_shortest_thing():
    assert toolchain.route(1) == []


def test_the_table_has_one_row_per_configuration_and_no_stray_pipe():
    text = toolchain.table()
    rows = text.splitlines()
    assert len(rows) == len(toolchain.plans()) + 2
    widths = {len(row.split("|")) for row in rows}
    assert len(widths) == 1, "a pipe inside a purpose would make one row wider"


def test_every_from_source_plan_ends_with_something_that_checks_it_worked():
    for name in EVERY:
        config = matrix.load()[name]
        if not config.from_source:
            continue
        assert toolchain.plan(name, config.arches[0]).smoke()


def test_the_clone_names_the_tag_the_whole_project_is_pinned_to():
    """A lesson that tells a reader to clone the default branch is a lesson whose line
    numbers are wrong the week after it ships."""
    text = toolchain.plan("rel").shell()
    assert matrix.load().tag in text
    assert "--depth 1" in text


def test_the_prerequisites_are_pairs_of_a_thing_and_a_reason():
    assert toolchain.PREREQUISITES
    for item, why in toolchain.PREREQUISITES:
        assert item and why
        assert not why.endswith("."), "these are printed inside a sentence"
