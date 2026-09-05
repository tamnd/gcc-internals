"""The recorded answer to what `./configure` decides, which B01 is built on top of.

The recorder next door needs `vendor/gcc` and takes a few seconds. This needs neither,
because the thing under test is the committed recording and the reader that loads it. What it
is really guarding is drift: the notebook prints sentences with numbers in them, the numbers
come from this file, and a recording that quietly loses half its front ends would make the
lesson wrong rather than make anything fail.

The counts below are deliberately written as bounds rather than as the exact numbers. GCC
gains a front end every few years and this should not fail when it does, but a recording with
three front ends in it is a broken recorder and should.
"""

from __future__ import annotations

import json

import pytest

from gxray import configure

BUILD = configure.load()


def test_the_package_exports_it_so_a_lesson_can_say_gxray_configure():
    import gxray

    assert gxray.configure is configure
    assert "configure" in gxray.__all__


def test_it_says_which_tree_it_was_read_from():
    """A recording that does not name its tag is a set of numbers with no provenance."""
    assert BUILD.tag.startswith("releases/gcc-")
    assert BUILD.version.startswith("16.")
    assert len(BUILD.commit) == 40


def test_asking_for_a_recording_that_is_not_there_says_what_is():
    with pytest.raises(FileNotFoundError, match="Have: "):
        configure.load("nosuchtree")


def test_every_front_end_has_a_word_and_a_directory():
    assert len(BUILD.languages) >= 10
    for one in BUILD.languages:
        assert one.name, "a front end with no --enable-languages word is unusable"
        assert one.directory
        assert "$" not in " ".join(one.libs), f"{one.name} kept an unexpanded shell variable"


def test_the_three_spellings_of_c_plus_plus_are_the_three_the_lesson_prints():
    """The whole point of the front end table, and the one everybody gets wrong."""
    cxx = BUILD.language("c++")
    assert (cxx.directory, cxx.compiler) == ("cp", "cc1plus")
    assert "libstdc++-v3" in cxx.libs


def test_the_compiler_names_have_no_makefile_syntax_left_on_them():
    """`cc1plus$(exeext)` is what the declaration says and is not a program name."""
    for one in BUILD.languages:
        assert "$" not in one.compiler and "(" not in one.compiler


def test_asking_for_a_front_end_that_does_not_exist_lists_the_ones_that_do():
    with pytest.raises(KeyError, match="There are: "):
        BUILD.language("pascal")


def test_c_and_c_plus_plus_are_on_by_default_and_most_things_are_not():
    got = BUILD.default_languages
    assert {"c", "c++"} <= set(got)
    assert len(got) < len(BUILD.languages), "if everything is default the parser found nothing"


def test_the_checking_levels_are_the_ones_the_help_text_names():
    check = BUILD.checking
    assert any("release" in level for level in check.levels)
    assert {"rtl", "tree", "gc", "assert"} <= set(check.flags)


def test_a_release_tag_defaults_to_release_checking_and_a_branch_would_not():
    """The empty DEV-PHASE, which is the fact the whole checking section turns on."""
    check = BUILD.checking
    assert check.release, "the pinned tree is a release tag"
    assert check.default == "release"
    assert check.development != check.default


def test_each_library_has_a_hard_minimum_below_the_version_it_is_happy_with():
    assert [one.library for one in BUILD.requires] == ["gmp", "mpfr", "mpc"]
    for one in BUILD.requires:
        hard = tuple(int(n) for n in one.hard.split("."))
        good = tuple(int(n) for n in one.good.split("."))
        assert hard <= good, f"{one.library} refuses above the version it recommends"


def test_the_gmp_error_message_is_looser_than_the_gmp_check():
    """The one place configure's message and its test disagree, which B01 shows on purpose."""
    gmp = BUILD.requires[0]
    assert gmp.rounded, "if these agree now, the lesson's paragraph about it is stale"
    assert not BUILD.requires[1].rounded


def test_there_are_two_configure_scripts_and_the_inner_one_is_bigger():
    top, inner = BUILD.knobs
    assert top.total == top.enable + top.with_
    assert inner.total > top.total, "gcc/configure is where most of the options are"
    assert BUILD.options == top.total + inner.total >= 100


def test_the_summary_line_a_notebook_prints_names_the_tree_and_the_counts():
    said = str(BUILD)
    assert BUILD.tag in said
    assert str(len(BUILD.languages)) in said
    assert str(BUILD.options) in said


def test_the_recording_on_disk_has_no_keys_the_reader_throws_away():
    """A recorder that writes a field nothing reads is a field that will go stale unnoticed."""
    raw = json.loads((configure.BUILDS / "gcc.json").read_text(encoding="utf-8"))
    assert set(raw) == {"tag", "commit", "version", "languages", "checking", "requires", "knobs"}
