"""The build banner and the CLI.

The banner is rule 2 of the notebook contract, and the thing it has to get right is the
warning. A reader looking at recorded dumps must be told they are recorded.
"""

from __future__ import annotations

import pytest

from gxray import corpus_store, programs
from gxray.__main__ import main
from gxray.build import PINNED, Banner, banner
from gxray.driver import CEBackend, CorpusBackend, LocalBackend


def test_the_banner_names_the_compiler_and_the_backend():
    b = Banner("local:gcc-16", "Tier 1", f"gcc-16 {PINNED}", "aarch64-apple-darwin24", "host")
    text = b.as_text()
    assert "local:gcc-16" in text
    assert "aarch64-apple-darwin24" in text
    assert b.pinned


def test_an_unpinned_compiler_is_called_out():
    b = Banner("local:gcc-14", "Tier 1", "gcc-14 14.2.0", "x86_64-linux-gnu", "host")
    assert not b.pinned
    assert "may differ" in b.as_text()


def test_a_missing_compiler_does_not_throw():
    b = banner(LocalBackend("gcc-does-not-exist"))
    assert b.compiler == "not found"
    assert "not on PATH" in b.warning


def test_the_ce_banner_says_tier_zero():
    b = banner(CEBackend("cg162"))
    assert b.tier == "Tier 0"
    assert "cg162" in b.compiler


def test_the_corpus_banner_warns_that_nothing_is_live(tmp_path):
    rec = corpus_store.Record("demo", "", [], "gcc-16 16.2.0", "aarch64", "2026-09-01", {})
    corpus_store.save(rec, root=tmp_path)
    b = banner(CorpusBackend("demo", root=tmp_path))
    assert "recorded dumps" in b.warning
    assert "2026-09-01" in b.warning
    assert "warning" in b.as_html().lower() or "background" in b.as_html()


def test_a_long_warning_is_wrapped_not_left_to_run_off_the_screen():
    b = Banner("b", "Tier 0 offline", "gcc-16 16.2.0", "aarch64", "host", "x " * 80)
    lines = b.as_text(width=88).splitlines()
    assert max(len(x) for x in lines) <= 90
    assert len(lines) > 6, "a long warning should take more than one line"


def test_the_shipped_corpus_entry_still_loads():
    """The committed entry is what a reader with no compiler and no network sees."""
    rec = corpus_store.load("l1-O2")
    assert PINNED in rec.compiler
    assert "tree-ssa" in rec.dump_texts


def test_the_html_banner_is_self_contained():
    html = Banner("b", "Tier 1", "gcc-16", "aarch64", "host").as_html()
    assert html.startswith("<div")
    assert "<table>" in html


@pytest.mark.needs_gcc
def test_cli_banner(capsys):
    assert main(["banner"]) == 0
    assert "Tier 1" in capsys.readouterr().out


@pytest.mark.needs_gcc
def test_cli_pass_counts(capsys):
    assert main(["passes", "--counts", "-O2"]) == 0
    out = capsys.readouterr().out
    assert "total" in out and "enabled" in out


@pytest.mark.needs_gcc
def test_cli_grep_narrows_the_pipeline(capsys):
    assert main(["passes", "--grep", "vrp", "-O2"]) == 0
    lines = [x for x in capsys.readouterr().out.splitlines() if x.strip()]
    assert all("vrp" in x for x in lines[:-1])


@pytest.mark.needs_gcc
def test_cli_web(capsys):
    assert main(["web", "--name", "s_1", "-O2"]) == 0
    out = capsys.readouterr().out
    assert "PHI" in out
    assert "used by 2" in out


def test_cli_passes_refuses_a_backend_that_cannot_do_it(capsys):
    assert main(["passes", "--backend", "ce"]) == 2
    assert "needs a local compiler" in capsys.readouterr().out


def test_the_cli_knows_the_corpus_programs():
    assert programs.L1.strip().endswith("}")
    assert "for (int i = 0" in programs.L1
