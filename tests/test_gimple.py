"""The GIMPLE parser.

Two things are being tested. That it reads a real dump correctly, and that it never throws
on one it does not understand, because a parser that throws takes forty lessons down with
it the day GCC adds a statement form.
"""

from __future__ import annotations

from gxray import gimple


def test_parses_the_real_l1_dump(ssa_dump):
    fn = gimple.parse(ssa_dump).only()
    assert fn.name == "f"
    assert fn.signature == "int f (int n)"
    assert sorted(fn.blocks) == [2, 3, 4, 5]
    assert len(fn.stmts) == 11


def test_nothing_in_a_real_dump_is_unparsed(ssa_dump):
    assert gimple.parse(ssa_dump).unparsed == []


def test_phi_arguments_carry_their_predecessor(ssa_dump):
    fn = gimple.parse(ssa_dump).only()
    phis = {str(p.lhs): p for p in fn.blocks[4].phis}
    assert set(phis) == {"s_1", "i_2"}
    assert phis["s_1"].args == (("s_3", 2), ("s_8", 3))
    assert phis["i_2"].args == (("i_4", 2), ("i_9", 3))


def test_ssa_web_finds_the_definition_and_every_use(ssa_dump):
    fn = gimple.parse(ssa_dump).only()
    web = fn.ssa_web("s_1")
    assert str(web["def"]) == "# s_1 = PHI <s_3(2), s_8(3)>"
    assert [u.block for u in web["uses"]] == [3, 5]


def test_a_parameter_has_no_definition_here(ssa_dump):
    """n_5(D) is the value f was called with, so nothing in f defines it."""
    web = gimple.parse(ssa_dump).only().ssa_web("n_5")
    assert web["def"] is None
    assert len(web["uses"]) == 1


def test_ssa_names_reads_versions_and_the_default_marker():
    names = gimple.ssa_names("if (i_2 < n_5(D))")
    assert [str(n) for n in names] == ["i_2", "n_5(D)"]
    assert names[1].default is True
    assert names[1].base == "n"


def test_a_temporary_has_an_empty_base():
    (name,) = gimple.ssa_names("_6 = s_1;")[:1]
    assert name.base == ""
    assert name.version == 6


def test_successors_come_off_the_gotos(ssa_dump):
    fn = gimple.parse(ssa_dump).only()
    assert fn.blocks[4].successors == (3, 5)
    assert fn.blocks[2].successors == (4,)


def test_statement_kinds(ssa_dump):
    fn = gimple.parse(ssa_dump).only()
    kinds = [s.kind for s in fn.blocks[4].stmts]
    assert kinds == ["cond", "goto", "else", "goto"]
    assert fn.blocks[5].stmts[-1].kind == "return"


def test_an_unknown_statement_is_kept_not_thrown():
    text = ";; Function g (g)\n\nint g ()\n{\n  <bb 2> :\n  @@ something from the future @@\n}\n"
    fn = gimple.parse(text).only()
    (stmt,) = fn.blocks[2].stmts
    assert stmt.is_unparsed
    assert stmt.kind == "unparsed"
    assert stmt.text == "@@ something from the future @@"
    assert fn.unparsed == [stmt]


def test_debug_statements_are_recognised():
    """A Compiler Explorer build emits these and a local build without -g does not."""
    text = ";; Function g (g)\n\nint g ()\n{\n  <bb 2> :\n  # DEBUG BEGIN_STMT\n}\n"
    (stmt,) = gimple.parse(text).only().blocks[2].stmts
    assert stmt.kind == "debug"
    assert not stmt.is_unparsed


def test_empty_input_gives_an_empty_dump():
    dump = gimple.parse("")
    assert dump.functions == {}
    assert dump.unparsed == []


def test_only_refuses_when_there_is_more_than_one_function():
    text = ";; Function a (a)\n\nint a ()\n{\n}\n\n;; Function b (b)\n\nint b ()\n{\n}\n"
    dump = gimple.parse(text)
    assert set(dump.functions) == {"a", "b"}
    try:
        dump.only()
    except ValueError as exc:
        assert "found 2" in str(exc)
    else:
        raise AssertionError("only() should refuse a two function dump")


def test_local_declarations_are_collected(ssa_dump):
    fn = gimple.parse(ssa_dump).only()
    assert ("int", "i") in fn.decls
    assert ("int", "_6") in fn.decls
