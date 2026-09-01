"""The pass pipeline parser.

The number that matters is 395. It is quoted in the prose, it comes out of this parser, and
if the parser and the compiler ever disagree the prose is wrong. So the count is asserted
against the raw line count rather than against a constant.
"""

from __future__ import annotations

from gxray import passes


def test_counts_match_the_raw_line_count(passes_text):
    """Every line the compiler printed is a pass, so the two counts have to agree."""
    lines = [x for x in passes_text.splitlines() if x.strip()]
    pipeline = passes.parse(passes_text)
    assert len(pipeline.all) == len(lines) == 395


def test_the_awkward_lines_all_parse():
    """Four of the 395 lines are not shaped like the others. They used to be dropped."""
    text = "\n".join(
        [
            "   (null)                                              :  OFF",
            "      rtl-rtl pre                                      :  ON",
            "      rtl-no-opt dfinit                                :  OFF",
            "      (null)                                           :  OFF",
        ]
    )
    names = [p.name for p in passes.parse(text).all]
    assert names == ["(null)", "rtl-rtl pre", "rtl-no-opt dfinit", "(null)"]


def test_unnamed_passes_are_kept_and_flagged(passes_text):
    pipeline = passes.parse(passes_text)
    unnamed = [p for p in pipeline.all if not p.named]
    assert len(unnamed) == 2
    assert all(p.name == "(null)" for p in unnamed)


def test_star_means_no_dump_of_its_own():
    pipeline = passes.parse("   *nonnullcmp    :  OFF\n   tree-ssa       :  ON\n")
    star, ssa = pipeline.all
    assert star.has_dump is False
    assert star.dump_key is None
    assert ssa.has_dump is True
    assert ssa.dump_key == "tree-ssa"


def test_phase_comes_from_the_prefix():
    pipeline = passes.parse(
        "   tree-ssa      :  ON\n   rtl-expand    :  ON\n   ipa-inline    :  ON\n"
        "   warn_unused   :  ON\n"
    )
    assert [p.phase for p in pipeline.all] == ["tree", "rtl", "ipa", None]
    assert [p.short_name for p in pipeline.all] == ["ssa", "expand", "inline", "warn_unused"]


def test_indentation_is_nesting(passes_text):
    pipeline = passes.parse(passes_text)
    parents = [p for p in pipeline.all if p.children]
    assert parents, "a real pipeline has nested passes"
    for parent in parents:
        for child in parent.children:
            assert child.depth == parent.depth + 1


def test_walk_is_pipeline_order():
    pipeline = passes.parse("a : ON\n   b : ON\n      c : ON\n   d : ON\ne : ON\n")
    assert [str(p) for p in pipeline.all] == ["a", "b", "c", "d", "e"]


def test_find_by_full_name_and_by_short_name(passes_text):
    pipeline = passes.parse(passes_text)
    assert pipeline.find("tree-ssa").name == "tree-ssa"
    assert pipeline.find("ssa").name == "tree-ssa"
    assert pipeline.find("no-such-pass") is None


def test_non_pass_lines_are_ignored():
    text = "some heading\n\n   tree-ssa   :  ON\ntrailing chatter\n"
    assert [p.name for p in passes.parse(text).all] == ["tree-ssa"]


def test_enabled_is_a_subset(passes_text):
    pipeline = passes.parse(passes_text)
    counts = pipeline.counts()
    assert 0 < counts["enabled"] < counts["total"]
    assert counts["tree"] + counts["rtl"] + counts["ipa"] <= counts["total"]
