"""Dump file names, ordering, and splitting a stderr stream back into dumps."""

from __future__ import annotations

from pathlib import Path

from gxray import dumps


def test_reads_a_dump_filename():
    d = dumps.parse_dump_filename("l1.c.024t.ssa")
    assert (d.index, d.phase, d.name) == (24, "tree", "ssa")
    assert d.key == "tree-ssa"


def test_all_three_phase_letters():
    assert dumps.parse_dump_filename("l1.c.216r.expand").phase == "rtl"
    assert dumps.parse_dump_filename("l1.c.000i.cgraph").phase == "ipa"
    assert dumps.parse_dump_filename("l1.c.273t.optimized").phase == "tree"


def test_a_name_with_dots_in_it_survives():
    d = dumps.parse_dump_filename("l1.c.024t.ssa.dot")
    assert d.name == "ssa.dot"


def test_not_a_dump_file():
    assert dumps.parse_dump_filename("l1.c") is None
    assert dumps.parse_dump_filename("l1.c.o") is None
    assert dumps.parse_dump_filename("l1.c.24t.ssa") is None


def test_find_dumps_sorts_by_pass_order(tmp_path: Path):
    for name in ["l1.c.273t.optimized", "l1.c.024t.ssa", "l1.c.216r.expand", "notes.txt"]:
        (tmp_path / name).write_text("x")
    found = dumps.find_dumps(tmp_path)
    assert [d.key for d in found] == ["tree-ssa", "rtl-expand", "tree-optimized"]


def test_find_dumps_can_filter_by_base(tmp_path: Path):
    (tmp_path / "l1.c.024t.ssa").write_text("a")
    (tmp_path / "other.c.024t.ssa").write_text("b")
    found = dumps.find_dumps(tmp_path, base="l1.c")
    assert len(found) == 1
    assert found[0].text == "a"


def test_dump_flags():
    assert dumps.dump_flags(["tree-ssa"]) == ["-fdump-tree-ssa"]
    assert dumps.dump_flags(["tree-ssa"], to_stderr=True) == ["-fdump-tree-ssa=stderr"]
    assert dumps.dump_flags([]) == []


def test_split_stderr_on_function_headers():
    stream = (
        ";; Function f (f, funcdef_no=0)\n"
        "\n"
        "int f ()\n"
        "{\n"
        "}\n"
        ";; Function f (f, funcdef_no=0)\n"
        "\n"
        "int f ()\n"
        "{\n"
        "  return 0;\n"
        "}\n"
    )
    chunks = dumps.split_stderr_dumps(stream)
    assert len(chunks) == 2
    assert chunks[0].startswith(";; Function f")
    assert "return 0;" in chunks[1]
    assert "return 0;" not in chunks[0]


def test_split_ignores_anything_before_the_first_header():
    stream = "some warning nobody asked for\n;; Function f (f)\nint f ()\n"
    chunks = dumps.split_stderr_dumps(stream)
    assert len(chunks) == 1
    assert "nobody asked for" not in chunks[0]


def test_split_of_nothing_is_nothing():
    assert dumps.split_stderr_dumps("") == []
    assert dumps.split_stderr_dumps("no dumps here at all\n") == []
