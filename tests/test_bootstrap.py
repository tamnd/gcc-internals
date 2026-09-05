"""The recorded bootstrap, and the comparison rule re-implemented on top of it.

Two different things are under test here and they deserve different amounts of suspicion.

The recording is a set of numbers read out of `Makefile.def` and `configure.ac`, and the
tests on it are the same kind as `test_configure.py`: bounds rather than exact counts, so
that a GCC which grows a tenth stage does not fail this and a recorder which finds two does.

The comparison is code I wrote to match a shell loop in `Makefile.tpl`, and the lesson's
whole claim is that it is the same rule. So it gets tested against the shell's behaviour
directly: the sixteen byte skip, the `$(objext)` expansion, the silence on a file the earlier
stage does not have, and the fact that a forgiven difference is still a difference.
"""

from __future__ import annotations

import json

import pytest

from gxray import bootstrap

BOOT = bootstrap.load()


def test_the_package_exports_it_so_a_lesson_can_say_gxray_bootstrap():
    import gxray

    assert gxray.bootstrap is bootstrap
    assert "bootstrap" in gxray.__all__


def test_it_says_which_tree_it_was_read_from_and_which_compiler_built_the_objects():
    """The object files are the one part of this that is not a property of the sources."""
    assert BOOT.tag.startswith("releases/gcc-")
    assert len(BOOT.commit) == 40
    assert "16." in BOOT.compiler
    assert BOOT.host, "an object file with no host recorded cannot be reasoned about"


def test_asking_for_a_recording_that_is_not_there_says_what_is():
    with pytest.raises(FileNotFoundError, match="Have: "):
        bootstrap.load("nosuchtree")


def test_there_are_more_declared_stages_than_the_three_anybody_talks_about():
    assert len(BOOT.stages) >= 8
    assert [one.id for one in BOOT.default] == ["1", "2", "3"]


def test_only_stage_one_is_built_by_something_that_is_not_a_stage():
    started = [one for one in BOOT.stages if not one.previous]
    assert [one.id for one in started] == ["1"]
    assert BOOT.stage("1").built_by == "the compiler already there"
    assert BOOT.stage("3").built_by == "stage2"


def test_almost_none_of_the_stages_compare_anything():
    """The fact the lesson is built on. Nine stages declared, two of them check their work."""
    assert len(BOOT.compared) == 2
    assert [one.id for one in BOOT.compared] == ["3", "4"]
    assert BOOT.stage("3").compares == "2"
    assert BOOT.stage("2").compares == "", "stage two against stage one would prove nothing"


def test_asking_for_a_stage_that_does_not_exist_lists_the_ones_that_do():
    with pytest.raises(KeyError, match="There are: "):
        BOOT.stage("7")


def test_the_three_stage_targets_are_the_ones_the_lesson_tells_you_to_type():
    assert BOOT.stage("2").target == "bootstrap2"
    assert BOOT.stage("3").target == "bootstrap"
    assert BOOT.stage("1").target == "", "there is no target that stops after stage one"


def test_stage_one_is_unoptimised_and_stage_three_turns_checking_back_on():
    """Why stage one is fast to build and slow to run, and stage three the other way."""
    assert any("stage1_cflags" in flag for flag in BOOT.stage("1").cflags)
    assert any("-fno-checking" in flag for flag in BOOT.stage("2").cflags)
    assert any("-fchecking=1" in flag for flag in BOOT.stage("3").cflags)


def test_under_half_the_host_modules_are_rebuilt_every_stage():
    assert "gcc" in BOOT.inside and "libcpp" in BOOT.inside
    assert "gdb" in BOOT.outside and "dejagnu" in BOOT.outside
    assert not set(BOOT.inside) & set(BOOT.outside), "a module cannot be both"
    assert len(BOOT.inside) < len(BOOT.outside)


def test_the_target_libraries_are_a_separate_list_from_the_host_modules():
    """libgcc is compiled by the stage's own compiler, which makes it a different animal."""
    assert "libgcc" not in BOOT.inside and "libgcc" not in BOOT.outside
    assert "gcc" not in BOOT.target_inside and "gcc" not in BOOT.target_outside


def test_the_target_libraries_the_comparison_can_see_include_libgcc():
    """The only generated target code a stage comparison ever looks at."""
    assert {"libgcc", "libstdc++-v3", "libatomic"} <= set(BOOT.target_inside)
    assert "newlib" in BOOT.target_outside
    assert not set(BOOT.target_inside) & set(BOOT.target_outside)
    assert len(BOOT.target_inside) < len(BOOT.target_outside)


def test_there_is_a_build_config_for_every_way_of_making_the_bootstrap_stricter():
    assert len(BOOT.configs) >= 15
    assert {"bootstrap-O3", "bootstrap-debug", "bootstrap-lto", "bootstrap-ubsan"} <= set(
        BOOT.configs
    )


# The comparison rule, which is the part I wrote rather than the part I read.


def test_a_checksum_is_forgiven_after_the_makefile_variable_is_expanded():
    """`gcc/cc*-checksum$(objext)` is a pattern make expands before the shell sees it."""
    assert BOOT.forgives("gcc/cc1-checksum.o") == "gcc/cc*-checksum$(objext)"
    assert BOOT.forgives("gcc/cc1plus-checksum.o") == "gcc/cc*-checksum$(objext)"
    assert BOOT.forgives("gcc/cobol/parse.o") == "gcc/cobol/parse$(objext)"


def test_the_wildcard_in_an_exclusion_crosses_directory_separators():
    """`fnmatch` does that and `glob` does not, and the shell's `case` does too."""
    assert BOOT.forgives("gcc/ada/gnattools/gnatmake.o") == "gcc/ada/*tools/*"


def test_an_ordinary_object_file_is_forgiven_nothing():
    for name in ("gcc/expr.o", "gcc/tree.o", "libcpp/lex.o", "gcc/checksum.o"):
        assert BOOT.forgives(name) == "", f"{name} should not match any exclusion"


def test_every_recorded_pair_says_what_was_done_to_it():
    assert len(BOOT.objects) >= 5
    for pair in BOOT.objects:
        assert pair.about and pair.about[0].isupper()
        assert len(pair.right) > 100, f"{pair.name} is too small to be an object file"


def test_asking_for_a_pair_that_was_not_recorded_lists_the_ones_that_were():
    with pytest.raises(KeyError, match="There are: "):
        BOOT.pair("gcc/nowhere.o")


def test_the_two_files_the_recorder_changed_nothing_about_are_the_same():
    assert BOOT.pair("gcc/tree-ssa-ccp.o").differs_at() == -1


def test_building_in_a_differently_named_directory_is_enough_to_break_it():
    """Invariant I3, and the entire reason every stage builds in a directory called gcc."""
    at = BOOT.pair("gcc/gimplify.o").differs_at()
    assert at > 0, "if this passes as identical the recorder stopped inducing anything"
    assert at > 1000, "a directory name lives in the debug info, well past the code"


def test_a_real_code_difference_shows_up_much_earlier_than_a_path_difference():
    """Not decoration. The offset is the first thing that tells you which kind you have."""
    code = BOOT.pair("gcc/fold-const.o").differs_at()
    path = BOOT.pair("gcc/gimplify.o").differs_at()
    assert 0 < code < path


def test_the_skip_is_sixteen_bytes_and_it_is_not_decorative():
    """`cmp --ignore-initial=16`, which some object formats need and Mach-O does not."""
    assert bootstrap.SKIP == 16
    pair = BOOT.pair("gcc/fold-const.o")
    assert pair.differs_at(skip=0) <= pair.differs_at()


def test_a_difference_inside_the_skipped_prefix_is_invisible():
    pair = BOOT.pair("gcc/tree-ssa-ccp.o")
    poisoned = bootstrap.Objects(
        name=pair.name, about=pair.about, left=b"\xff" * 16 + pair.right[16:], right=pair.right
    )
    assert poisoned.differs_at() == -1
    assert poisoned.differs_at(skip=0) == 0


def test_a_file_the_earlier_stage_does_not_have_is_skipped_in_silence():
    """`if test ! -f $$f1; then continue; fi`, which is invariant I4 and a real hole."""
    result = BOOT.compare()
    assert BOOT.pair("gcc/rust/rust-lang.o").missing
    assert "gcc/rust/rust-lang.o" in result.skipped
    assert "gcc/rust/rust-lang.o" not in result.report()


def test_the_recorded_comparison_fails_and_names_only_the_unforgiven_files():
    result = BOOT.compare()
    assert result.failed
    assert result.checked == len(result.same) + len(result.differences)
    assert result.checked + len(result.skipped) == len(BOOT.objects)
    assert [d.name for d in result.bad] == ["gcc/gimplify.o", "gcc/fold-const.o"]


def test_a_forgiven_difference_is_still_a_difference():
    """It is counted, it is warned about, and it is not in `.bad_compare`. All three."""
    result = BOOT.compare()
    forgiven = [d for d in result.differences if d.forgiven]
    assert len(forgiven) == 2
    for one in forgiven:
        assert one.at > 0
        assert one.name not in result.bad_compare()
        assert f"warning: {one.name} differs" in result.report()


def test_the_report_reads_like_the_shell_it_was_copied_from():
    result = BOOT.compare()
    lines = result.report().splitlines()
    assert lines[0] == "Comparing stages 2 and 3"
    assert "Bootstrap comparison failure!" in lines
    assert "Comparison successful." not in lines
    assert lines.index("Bootstrap comparison failure!") > 1, "warnings are printed first"


def test_the_bad_compare_file_is_the_list_alone_one_name_per_line():
    result = BOOT.compare()
    body = result.bad_compare()
    assert body.endswith("\n")
    assert body.splitlines() == [d.name for d in result.bad]


def test_forgiving_everything_turns_the_failure_into_a_success():
    """The rule and the exclusion list are separable, which is what makes the holes holes."""
    everything = bootstrap.Bootstrap(**{**BOOT.__dict__, "exclusions": ("*",)})
    result = everything.compare()
    assert not result.failed
    assert result.bad_compare() == ""
    assert result.report().endswith("Comparison successful.")


def test_the_recording_on_disk_has_no_keys_the_reader_throws_away():
    raw = json.loads((bootstrap.BOOTS / "gcc.json").read_text(encoding="utf-8"))
    assert set(raw) == {
        "tag",
        "commit",
        "host",
        "compiler",
        "stages",
        "inside",
        "outside",
        "target_inside",
        "target_outside",
        "exclusions",
        "configs",
        "objects",
    }
