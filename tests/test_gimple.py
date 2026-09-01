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


# Dumps made with the lineno modifier, which is what the recorded corpus now is.

LINENO = """;; Function f (f, funcdef_no=0, decl_uid=4594, cgraph_uid=1, symbol_order=0)

int f (int n)
{
  int i;
  int s;

  <bb 2> :
  [l1.c:5:3] # DEBUG BEGIN_STMT
  [l1.c:5:7] s_3 = 0;
  [l1.c:5:7] # DEBUG s => s_3
  [l1.c:6:12] i_4 = 0;

  <bb 3> :
  # s_1 = PHI <[l1.c:5:7] s_3(2), [l1.c:7:7] s_8(3)>
  [l1.c:7:7] s_8 = s_1 + i_4;

}
"""


def test_a_location_goes_on_the_statement_and_not_into_its_text():
    """So a statement reads the same whether or not the dump was made with locations, and
    a lesson can quote one without knowing how the corpus happened to be recorded."""
    fn = gimple.parse(LINENO).only()
    stmt = fn.blocks[2].stmts[1]
    assert stmt.text == "s_3 = 0;"
    assert (stmt.loc.line, stmt.loc.col) == (5, 7)


def test_a_statement_from_a_dump_without_locations_has_none(ssa_dump):
    assert all(s.loc is None for s in gimple.parse(ssa_dump).only().stmts)


def test_a_location_inside_a_phi_argument_does_not_end_up_in_the_argument():
    fn = gimple.parse(LINENO).only()
    (phi,) = fn.blocks[3].phis
    assert phi.args == (("s_3", 2), ("s_8", 3))
    assert str(phi) == "# s_1 = PHI <s_3(2), s_8(3)>"


def test_declarations_still_parse_when_the_statements_have_locations():
    """Removing a location must keep the indentation, since a declaration is recognised by
    being indented exactly two spaces and a statement is not."""
    fn = gimple.parse(LINENO).only()
    assert ("int", "i") in fn.decls
    assert ("int", "s") in fn.decls


def test_debug_statements_are_in_the_dump_but_are_not_code():
    fn = gimple.parse(LINENO).only()
    assert len(fn.stmts) == 5
    assert len(fn.code) == 3
    assert [s.text for s in fn.code] == ["s_3 = 0;", "i_4 = 0;", "s_8 = s_1 + i_4;"]


def test_a_debug_statement_is_not_a_use():
    """`# DEBUG s => s_3` mentions s_3, but it only says where a debugger can find `s`. The
    PHI below it is a real use, and it is the only one."""
    web = gimple.parse(LINENO).only().ssa_web("s_3")
    assert str(web["def"]) == "s_3 = 0;"
    assert [str(u) for u in web["uses"]] == ["# s_1 = PHI <s_3(2), s_8(3)>"]


def test_how_big_a_function_is_means_the_code_in_it():
    assert str(gimple.parse(LINENO).only()) == "f (2 blocks, 3 statements)"


# The gimplification dump, which is the only one with no banner and no basic blocks.

PRE_CFG = """int nested (int a, int b, int c)
{
  int D.4635;

  _1 = a + b;
  _2 = a - c;
  D.4635 = _1 * _2;
  return D.4635;
}


int loopy (int n)
{
  int D.4603;
  int s;

  s = 0;
  {
    int i;

    i = 0;
    goto <D.4601>;
    <D.4600>:
    s = s + i;
    i = i + 1;
    <D.4601>:
    if (i < n) goto <D.4600>; else goto <D.4598>;
    <D.4598>:
  }
  D.4603 = s;
  return D.4603;
}
"""


def test_a_headerless_dump_still_finds_its_functions():
    """The gimplification dump announces a function with nothing but its signature, so the
    parser has to be willing to start one on a line that looks like C."""
    dump = gimple.parse(PRE_CFG)
    assert list(dump.functions) == ["nested", "loopy"]
    assert dump.functions["nested"].signature == "int nested (int a, int b, int c)"


def test_a_pre_cfg_function_says_so_and_has_one_block():
    fn = gimple.parse(PRE_CFG).functions["nested"]
    assert fn.pre_cfg
    assert list(fn.blocks) == [gimple.PRE_CFG_BLOCK]
    assert str(fn) == "nested (4 statements, no blocks yet)"


def test_the_statements_come_back_in_the_order_the_front_end_wrote_them():
    fn = gimple.parse(PRE_CFG).functions["nested"]
    assert [s.text for s in fn.code] == [
        "_1 = a + b;",
        "_2 = a - c;",
        "D.4635 = _1 * _2;",
        "return D.4635;",
    ]


def test_a_return_is_not_mistaken_for_a_declaration():
    """`return D.4635;` is two words and a semicolon, which is exactly what a declaration
    looks like, and before the CFG exists there is no block header to tell them apart."""
    fn = gimple.parse(PRE_CFG).functions["nested"]
    assert fn.decls == [("int", "D.4635")]
    assert fn.code[-1].kind == "return"


def test_a_nested_scope_declares_into_the_same_function():
    """The front end keeps the braces the source had. Each one has its own declarations and
    none of them ends the function."""
    fn = gimple.parse(PRE_CFG).functions["loopy"]
    assert fn.decls == [("int", "D.4603"), ("int", "s"), ("int", "i")]
    assert len(fn.code) == 11
    assert fn.code[0].text == "s = 0;"
    assert fn.code[-1].text == "return D.4603;"


def test_nothing_in_a_headerless_dump_is_unparsed():
    assert gimple.parse(PRE_CFG).unparsed == []


def test_a_dump_with_blocks_is_not_treated_as_pre_cfg(ssa_dump):
    """The two shapes go through one parser, so the older one has to be left alone."""
    fn = gimple.parse(ssa_dump).only()
    assert not fn.pre_cfg
    assert sorted(fn.blocks) == [2, 3, 4, 5]
