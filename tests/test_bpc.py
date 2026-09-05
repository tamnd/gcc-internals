"""The blueprint compiler.

Most of these run against small pieces of C written into the test, because what is being
tested is the reader and not GCC. The ones that read the real pinned tree are marked
`needs_tree` and skip when the submodule is not checked out, and they are the ones that
would catch GCC changing shape under us.

The pieces of C here are copied from `gimple.h` and `gimple.def` rather than invented, with
the parts that are not being tested cut out. A parser test written against text somebody
made up to make the parser pass is worth nothing.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tools import bpc
from tools.bpc import Blueprint, BpcError, bootstrap, buildsys, gccsrc
from tools.bpc import coverage as ledger
from tools.bpc import plugin as plugin_gen
from tools.bpc.gccsrc import SourceError

HAVE_TREE = (bpc.GCC_ROOT / "gimple.def").is_file()
needs_tree = pytest.mark.skipif(not HAVE_TREE, reason="vendor/gcc is not checked out")


def dedent(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


# The .def reader


DEF_FILE = dedent(
    """
    /* This file contains the definitions of the GIMPLE IR tuples used in GCC.

       Each entry is:

         DEFGSCODE(GIMPLE_symbol, printable name, GSS_symbol)  */

    /* Error marker.  This is used in similar ways as ERROR_MARK in tree.def.  */
    DEFGSCODE(GIMPLE_ERROR_MARK, "gimple_error_mark", GSS_BASE)

    /* IMPORTANT.  Do not rearrange the codes between GIMPLE_COND and
       GIMPLE_RETURN.  The ordering is exposed by gimple_has_ops.  */

    /* GIMPLE_COND <COND, LABEL, LABEL> represents a conditional.  */
    DEFGSCODE(GIMPLE_COND, "gimple_cond",
              GSS_WITH_OPS)

    DEFGSCODE(GIMPLE_RETURN, "gimple_return", GSS_WITH_MEM_OPS)
    """
)


def test_reads_every_invocation_of_one_macro():
    entries = gccsrc.parse_def(DEF_FILE, "DEFGSCODE")
    assert [e.name for e in entries] == ["GIMPLE_ERROR_MARK", "GIMPLE_COND", "GIMPLE_RETURN"]
    assert [e.index for e in entries] == [0, 1, 2]


def test_ignores_the_format_description_in_the_file_header():
    # The header comment spells out the macro's shape, and a grep counts that as an entry.
    assert len(gccsrc.parse_def(DEF_FILE, "DEFGSCODE")) == 3


def test_takes_the_quotes_off_a_string_argument():
    cond = gccsrc.parse_def(DEF_FILE, "DEFGSCODE")[1]
    assert cond.arg(1) == "gimple_cond"
    assert cond.arg(2) == "GSS_WITH_OPS"


def test_a_multi_line_invocation_reports_the_line_it_starts_on():
    cond = gccsrc.parse_def(DEF_FILE, "DEFGSCODE")[1]
    assert DEF_FILE.splitlines()[cond.line - 1].startswith("DEFGSCODE(GIMPLE_COND")


def test_the_comment_above_an_entry_is_its_documentation():
    error, cond, ret = gccsrc.parse_def(DEF_FILE, "DEFGSCODE")
    assert error.doc.startswith("Error marker.")
    assert cond.doc.startswith("GIMPLE_COND <COND, LABEL, LABEL>")
    assert ret.doc == ""


def test_a_second_comment_above_that_is_kept_as_a_note():
    cond = gccsrc.parse_def(DEF_FILE, "DEFGSCODE")[1]
    assert len(cond.notes) == 1
    assert "Do not rearrange" in cond.notes[0]


def test_a_file_with_none_of_the_macro_is_an_error_rather_than_an_empty_list():
    with pytest.raises(SourceError, match="changed shape"):
        gccsrc.parse_def(DEF_FILE, "DEFGSSTRUCT")


def test_an_unclosed_macro_call_says_where_it_started():
    with pytest.raises(SourceError, match="line 1"):
        gccsrc.parse_def("DEFGSCODE(GIMPLE_COND,\n", "DEFGSCODE")


def test_arguments_split_on_top_level_commas_only():
    assert gccsrc.split_args('A, f (b, c), "d, e"') == ["A", "f (b, c)", '"d, e"']


def test_a_comment_keeps_its_internal_indentation():
    body = gccsrc.clean_comment(["/* One.", "", "     indented", "   back.  */"])
    assert body == "One.\n\n  indented\nback."


def test_a_missing_file_says_how_to_get_the_tree(tmp_path: Path):
    with pytest.raises(SourceError, match="git submodule update"):
        gccsrc.read(tmp_path / "gimple.def")


# The header reader


HEADER = dedent(
    """
    /* Base structure for all GIMPLE statements.  */
    struct GTY((desc ("gimple_statement_structure (&%h)")), tag ("GSS_BASE"),
               variable_size))
      gimple
    {
      /* [ WORD 1 ]
         Main identifying code for a statement.  */
      ENUM_BITFIELD(gimple_code) code : 8;

      /* Nonzero if a warning should not be emitted on this tuple.  */
      unsigned int no_warning : 1;

      /* [ WORD 2 ]
         Number of operands in this tuple.  */
      unsigned num_ops;
    };

    /* A statement with operands.  */
    struct GTY((tag ("GSS_WITH_OPS")))
      gimple_statement_with_ops : public gimple_statement_with_ops_base
    {
      /* [ WORD 1-9 ] : base class.  */

      /* [ WORD 10 ]
         Operand vector.  */
      tree GTY((length ("%h.num_ops"))) op[1];
    };

    /* A function call.  */
    struct GTY((tag ("GSS_CALL")))
      gcall : public gimple_statement_with_memory_ops_base
    {
      static const enum gimple_code code_ = GIMPLE_CALL;

      /* [ WORD 8 ]
         Either the function to be called, or a builtin code.  */
      union GTY ((desc ("%1.subcode & GF_CALL_INTERNAL"))) {
        tree GTY ((tag ("0"))) fntype;
        enum internal_fn GTY ((tag ("GF_CALL_INTERNAL"))) internal_fn;
      } u;

      /* [ WORD 9 ]
         Operand vector.  */
      tree GTY((length ("%h.num_ops"))) op[1];
    };
    """
)


@pytest.fixture
def structs() -> dict[str, gccsrc.Struct]:
    return {s.name: s for s in gccsrc.parse_structs(HEADER)}


def test_reads_the_name_the_base_and_the_gsstruct_tag(structs):
    assert set(structs) == {"gimple", "gimple_statement_with_ops", "gcall"}
    assert structs["gcall"].base == "gimple_statement_with_memory_ops_base"
    assert structs["gcall"].tag == "GSS_CALL"
    assert structs["gimple"].base == ""


def test_the_comment_above_a_struct_is_its_documentation(structs):
    assert structs["gcall"].doc == "A function call."


def test_a_field_gets_its_type_its_name_and_the_comment_above_it(structs):
    code, no_warning, num_ops = structs["gimple"].fields
    assert (code.type, code.name) == ("ENUM_BITFIELD(gimple_code) : 8", "code")
    assert code.doc == "Main identifying code for a statement."
    assert (no_warning.type, no_warning.name) == ("unsigned int : 1", "no_warning")
    assert (num_ops.type, num_ops.name) == ("unsigned", "num_ops")


def test_the_word_marker_is_pulled_off_the_front_of_the_comment(structs):
    code, no_warning, num_ops = structs["gimple"].fields
    assert code.word == "WORD 1"
    assert no_warning.word == ""
    assert num_ops.word == "WORD 2"


def test_a_gty_marker_with_nested_parentheses_does_not_leak_into_the_type(structs):
    (op,) = structs["gimple_statement_with_ops"].fields
    assert op.type == "tree[1]"
    assert op.gty == 'length ("%h.num_ops")'


def test_the_words_a_struct_gets_from_its_base_are_not_a_field(structs):
    assert structs["gimple_statement_with_ops"].inherited_words == "WORD 1-9"
    assert [f.name for f in structs["gimple_statement_with_ops"].fields] == ["op"]


def test_an_anonymous_union_is_one_field_with_its_alternatives_underneath(structs):
    u, op = structs["gcall"].fields
    assert (u.name, u.type, u.word) == ("u", "union", "WORD 8")
    assert u.doc.startswith("Either the function to be called")
    assert [m.name for m in u.members] == ["fntype", "internal_fn"]
    assert op.name == "op"


def test_the_compile_time_code_member_is_read_off_the_struct(structs):
    assert structs["gcall"].code == "GIMPLE_CALL"
    assert structs["gimple"].code == ""


HELPERS = dedent(
    """
    template <>
    template <>
    inline bool
    is_a_helper <gassign *>::test (gimple *gs)
    {
      return gs->code == GIMPLE_ASSIGN;
    }

    template <>
    template <>
    inline bool
    is_a_helper <const gassign *>::test (const gimple *gs)
    {
      return gs->code == GIMPLE_ASSIGN;
    }

    template <>
    template <>
    inline bool
    is_a_helper <gimple_statement_omp_taskreg *>::test (gimple *gs)
    {
      return gs->code == GIMPLE_OMP_PARALLEL || gs->code == GIMPLE_OMP_TASK;
    }

    template <>
    template <>
    inline bool
    is_a_helper <gimple_statement_with_ops *>::test (gimple *gs)
    {
      return gimple_has_ops (gs);
    }
    """
)


def test_reads_which_codes_each_class_accepts():
    helpers = gccsrc.parse_is_a_helpers(HELPERS)
    assert helpers["gassign"] == ["GIMPLE_ASSIGN"]
    assert helpers["gimple_statement_omp_taskreg"] == ["GIMPLE_OMP_PARALLEL", "GIMPLE_OMP_TASK"]


def test_the_const_specialisation_is_not_a_second_class():
    assert "const gassign" not in gccsrc.parse_is_a_helpers(HELPERS)


def test_a_class_narrowed_by_a_range_check_is_known_but_names_no_codes():
    assert gccsrc.parse_is_a_helpers(HELPERS)["gimple_statement_with_ops"] == []


RANGES = dedent(
    """
    static inline bool
    gimple_has_ops (const gimple *g)
    {
      return gimple_code (g) >= GIMPLE_COND && gimple_code (g) <= GIMPLE_RETURN;
    }

    static inline bool
    gimple_has_mem_ops (const gimple *g)
    {
      return gimple_code (g) >= GIMPLE_ASSIGN && gimple_code (g) <= GIMPLE_RETURN;
    }

    static inline bool
    gimple_has_substatements (const gimple *g)
    {
      switch (gimple_code (g))
        {
        case GIMPLE_BIND:
          return true;
        }
    }
    """
)


def test_reads_the_two_bounds_of_a_range_predicate():
    ranges = gccsrc.parse_code_ranges(RANGES)
    assert ranges["gimple_has_ops"] == ("GIMPLE_COND", "GIMPLE_RETURN")
    assert ranges["gimple_has_mem_ops"] == ("GIMPLE_ASSIGN", "GIMPLE_RETURN")


def test_a_predicate_that_is_not_a_range_is_left_out():
    assert "gimple_has_substatements" not in gccsrc.parse_code_ranges(RANGES)


# Blueprints and their generated blocks


SHELL = dedent(
    """
    # BP-EXAMPLE: An example

    **Status:** partial
    **Applies to:** GCC releases/gcc-16.2.0
    **Generated sections:** 2

    ## 1. Purpose and scope

    ## 2. Data structures

    <!-- bpc:begin example -->
    <!-- bpc:end example -->

    ## 3. Algorithms
    ## 4. Invariants
    ## 5. Observable behaviour
    ## 6. Edge cases and error paths
    ## 7. Interactions
    ## 8. Conformance
    ## 9. Port notes
    """
)


@pytest.fixture
def example(tmp_path: Path) -> Path:
    """A directory holding one well formed blueprint with one empty generated block."""
    (tmp_path / "BP-EXAMPLE.md").write_text(SHELL, encoding="utf-8")
    return tmp_path


@pytest.fixture
def registered():
    """A generator called `example`, taken back out again afterwards."""
    bpc._register_generators()  # so that the snapshot below has the real ones in it
    saved = dict(bpc.GENERATORS)
    bpc.GENERATORS["example"] = lambda root: f"The tree is at {root.name}."
    yield
    bpc.GENERATORS.clear()
    bpc.GENERATORS.update(saved)


def blueprint(text: str) -> Blueprint:
    return Blueprint(path=Path("BP-T.md"), text=text)


def test_reads_the_title_the_header_fields_and_the_sections():
    bp = blueprint(SHELL)
    assert bp.title == "BP-EXAMPLE: An example"
    assert bp.header("Status") == "partial"
    assert bp.header("Applies to") == "GCC releases/gcc-16.2.0"
    assert bp.header("Nothing") == ""
    assert len(bp.sections) == 9


def test_finds_a_generated_block_and_what_is_inside_it():
    text = "<!-- bpc:begin a -->\nbody\n<!-- bpc:end a -->\n"
    (block,) = blueprint(text).blocks
    assert (block.id, block.body) == ("a", "body")


def test_a_block_that_opens_inside_another_one_is_an_error():
    text = "<!-- bpc:begin a -->\n<!-- bpc:begin b -->\n"
    with pytest.raises(BpcError, match="opens inside another"):
        _ = blueprint(text).blocks


def test_a_block_that_never_closes_is_an_error():
    with pytest.raises(BpcError, match="never closed"):
        _ = blueprint("<!-- bpc:begin a -->\nbody\n").blocks


def test_an_end_marker_with_no_begin_is_an_error():
    with pytest.raises(BpcError, match="no bpc:begin"):
        _ = blueprint("<!-- bpc:end a -->\n").blocks


def test_an_end_marker_naming_the_wrong_block_is_an_error():
    text = "<!-- bpc:begin a -->\n<!-- bpc:end b -->\n"
    with pytest.raises(BpcError, match="closes"):
        _ = blueprint(text).blocks


def test_an_unknown_generator_lists_the_ones_that_exist(registered):
    """The list is sorted, so what comes before `example` depends on what exists today."""
    with pytest.raises(BpcError, match=r"Registered generators: .*\bexample\b"):
        bpc.render("nope", Path("."))


def test_building_writes_the_generated_body_and_the_do_not_edit_warning(example, registered):
    assert bpc.build(example, Path("/tmp/gcc")) == [example / "BP-EXAMPLE.md"]
    text = (example / "BP-EXAMPLE.md").read_text()
    assert "The tree is at gcc." in text
    assert "edit the generator" in text


def test_building_twice_changes_nothing_the_second_time(example, registered):
    bpc.build(example, Path("/tmp/gcc"))
    assert bpc.build(example, Path("/tmp/gcc")) == []


def test_building_leaves_everything_outside_the_markers_alone(example, registered):
    bpc.build(example, Path("/tmp/gcc"))
    text = (example / "BP-EXAMPLE.md").read_text()
    assert text.startswith("# BP-EXAMPLE: An example")
    assert text.rstrip().endswith("## 9. Port notes")


def test_a_stale_block_is_caught_and_the_first_differing_line_is_named(example, registered):
    bpc.build(example, Path("/tmp/gcc"))
    path = example / "BP-EXAMPLE.md"
    path.write_text(path.read_text().replace("The tree is at gcc.", "The tree is elsewhere."))
    (problem,) = bpc.check(example, Path("/tmp/gcc"))
    assert "the example block is stale" in problem
    assert "The tree is elsewhere." in problem


def test_a_freshly_built_blueprint_passes_the_check(example, registered):
    bpc.build(example, Path("/tmp/gcc"))
    assert bpc.check(example, Path("/tmp/gcc")) == []


def test_a_missing_section_is_reported_by_name(example, registered):
    path = example / "BP-EXAMPLE.md"
    path.write_text(SHELL.replace("## 4. Invariants\n", ""))
    problems = bpc.check(example, Path("/tmp/gcc"))
    assert any("4. Invariants" in p for p in problems)


def test_a_status_outside_the_three_allowed_ones_is_reported(example, registered):
    path = example / "BP-EXAMPLE.md"
    path.write_text(SHELL.replace("**Status:** partial", "**Status:** nearly there"))
    problems = bpc.check(example, Path("/tmp/gcc"))
    assert any("nearly there" in p for p in problems)


def test_a_blueprint_that_does_not_say_which_gcc_it_applies_to_is_reported(example, registered):
    path = example / "BP-EXAMPLE.md"
    path.write_text(SHELL.replace("releases/gcc-16.2.0", "trunk"))
    problems = bpc.check(example, Path("/tmp/gcc"))
    assert any("applies to releases/gcc-16.2.0" in p for p in problems)


# The coverage ledger


LEDGER = dedent(
    """
    [inventory.gimple-codes]
    what = "GIMPLE statement codes"
    source = "gcc/gimple.def"
    macro = "DEFGSCODE"

    [[inventory.gimple-codes.rule]]
    match = "GIMPLE_COND"
    status = "covered"

    [[inventory.gimple-codes.rule]]
    match = "GIMPLE_*"
    status = "mentioned"
    """
)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A tree with a `gimple.def` in it, standing in for the pinned one."""
    (tmp_path / "gimple.def").write_text(DEF_FILE, encoding="utf-8")
    return tmp_path


def write_ledger(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "coverage.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_first_rule_that_matches_an_item_wins(tmp_path, tree):
    path = write_ledger(tmp_path, LEDGER)
    (report,) = ledger.report(tree, path)
    assert report.counts == {"covered": 1, "mentioned": 2}
    assert report.total == 3
    assert report.unclassified == []


def test_the_summary_line_names_every_status(tmp_path, tree):
    (report,) = ledger.report(tree, write_ledger(tmp_path, LEDGER))
    assert report.line() == "gimple-codes: 3 items, 1 covered, 2 mentioned, 0 out of scope"


def test_an_item_no_rule_matches_is_a_problem_that_says_what_to_do(tmp_path, tree):
    text = LEDGER.replace('match = "GIMPLE_*"', 'match = "GIMPLE_RETURN"')
    (problem,) = ledger.problems(tree, write_ledger(tmp_path, text))
    assert "GIMPLE_ERROR_MARK" in problem
    assert "out of scope with a reason" in problem


def test_the_inventory_comes_from_the_tree_not_from_the_ledger(tmp_path, tree):
    # A code added to GCC turns the build red rather than quietly going uncounted.
    (tree / "gimple.def").write_text(
        DEF_FILE + '\nDEFGSCODE(GIMPLE_NEW_IN_17, "gimple_new", GSS_BASE)\n'
    )
    text = LEDGER.replace('match = "GIMPLE_*"', 'match = "GIMPLE_ERROR_MARK"')
    problems = ledger.problems(tree, write_ledger(tmp_path, text))
    assert any("GIMPLE_NEW_IN_17" in p for p in problems)


def test_putting_something_out_of_scope_without_saying_why_is_refused(tmp_path):
    text = LEDGER.replace('status = "covered"', 'status = "out of scope"')
    with pytest.raises(BpcError, match="without saying why"):
        ledger.load(write_ledger(tmp_path, text))


def test_out_of_scope_with_a_reason_is_fine(tmp_path):
    text = LEDGER.replace(
        'status = "covered"', 'status = "out of scope"\nwhy = "It is its own book."'
    )
    (inv,) = ledger.load(write_ledger(tmp_path, text))
    assert inv.rules[0].why == "It is its own book."


def test_a_status_the_ledger_does_not_define_is_refused(tmp_path):
    text = LEDGER.replace('status = "covered"', 'status = "sort of covered"')
    with pytest.raises(BpcError, match="sort of covered"):
        ledger.load(write_ledger(tmp_path, text))


def test_a_missing_ledger_says_where_it_was_looking(tmp_path):
    with pytest.raises(BpcError, match="no coverage ledger"):
        ledger.load(tmp_path / "nope.toml")


def test_an_inventory_that_names_neither_a_macro_nor_a_provider_is_refused(tmp_path):
    """Where the list of items comes from is the whole point of an inventory, so it is not
    something the ledger is allowed to leave out."""
    text = LEDGER.replace('macro = "DEFGSCODE"\n', "")
    with pytest.raises(BpcError, match="exactly one of"):
        ledger.load(write_ledger(tmp_path, text))


def test_an_inventory_that_names_both_is_refused_too(tmp_path):
    text = LEDGER.replace('macro = "DEFGSCODE"', 'macro = "DEFGSCODE"\nprovider = "front-ends"')
    with pytest.raises(BpcError, match="exactly one of"):
        ledger.load(write_ledger(tmp_path, text))


def test_an_unknown_provider_lists_the_ones_that_exist(tmp_path):
    text = LEDGER.replace('macro = "DEFGSCODE"', 'provider = "back-ends"')
    with pytest.raises(BpcError, match="Known: build-configs, checking-categories, front-ends"):
        ledger.load(write_ledger(tmp_path, text))


@needs_tree
def test_a_provider_supplies_the_items_and_the_rules_work_the_same_way(tmp_path):
    """The two mechanisms differ in where the list comes from and nowhere else."""
    text = dedent(
        """
        [inventory.front-ends]
        what = "front ends"
        source = "gcc/*/config-lang.in"
        provider = "front-ends"

        [[inventory.front-ends.rule]]
        match = "c"
        status = "covered"

        [[inventory.front-ends.rule]]
        match = "*"
        status = "mentioned"
        """
    )
    (report,) = ledger.report(bpc.GCC_ROOT, write_ledger(tmp_path, text))
    assert report.counts == {"covered": 1, "mentioned": 13}
    assert report.unclassified == []


# The real tree


@needs_tree
def test_gimple_def_still_has_the_shape_the_generator_expects():
    entries = gccsrc.parse_def(gccsrc.read(bpc.GCC_ROOT / "gimple.def"), "DEFGSCODE")
    assert len(entries) == 47
    assert entries[0].name == "GIMPLE_ERROR_MARK"
    assert all(len(e.args) == 3 for e in entries)


@needs_tree
def test_every_layout_a_code_names_is_declared_in_gsstruct_def():
    codes = gccsrc.parse_def(gccsrc.read(bpc.GCC_ROOT / "gimple.def"), "DEFGSCODE")
    layouts = gccsrc.parse_def(gccsrc.read(bpc.GCC_ROOT / "gsstruct.def"), "DEFGSSTRUCT")
    declared = {e.name for e in layouts}
    assert len(declared) == 28
    assert {e.arg(2) for e in codes} <= declared


@needs_tree
def test_the_two_operand_predicates_are_still_ranges_over_the_enum():
    ranges = gccsrc.parse_code_ranges(gccsrc.read(bpc.GCC_ROOT / "gimple.h"))
    assert ranges["gimple_has_ops"] == ("GIMPLE_COND", "GIMPLE_RETURN")
    assert ranges["gimple_has_mem_ops"] == ("GIMPLE_ASSIGN", "GIMPLE_RETURN")


@needs_tree
def test_every_code_a_cast_accepts_is_a_code_that_exists():
    text = gccsrc.read(bpc.GCC_ROOT / "gimple.def")
    codes = {e.name for e in gccsrc.parse_def(text, "DEFGSCODE")}
    helpers = gccsrc.parse_is_a_helpers(gccsrc.read(bpc.GCC_ROOT / "gimple.h"))
    assert len(helpers) > 30
    for cls, accepted in helpers.items():
        assert set(accepted) <= codes, cls


@needs_tree
def test_the_blueprints_in_the_repository_are_built_and_well_formed():
    assert bpc.check() == []
    assert ledger.problems() == []


# The plugin event scanner


def test_a_call_on_one_line_is_found_with_its_data_expression(tmp_path: Path):
    (tmp_path / "x.cc").write_text(
        "void f () { invoke_plugin_callbacks (PLUGIN_FINISH_UNIT, NULL); }\n", encoding="utf-8"
    )
    found = plugin_gen.sites(tmp_path)
    assert found["PLUGIN_FINISH_UNIT"] == [("x.cc", 1, "NULL")]


def test_a_call_split_across_two_lines_is_still_one_call(tmp_path: Path):
    """c-opts.cc writes the only two line call in the tree, and a line based scan misses it."""
    (tmp_path / "x.cc").write_text(
        dedent(
            """
            void f ()
            {
              invoke_plugin_callbacks
                (PLUGIN_INCLUDE_FILE,
                 const_cast<char*> (NAME (m)));
            }
            """
        ),
        encoding="utf-8",
    )
    found = plugin_gen.sites(tmp_path)
    assert found["PLUGIN_INCLUDE_FILE"] == [("x.cc", 3, "const_cast<char*> (NAME (m))")]


def test_the_dispatcher_itself_is_not_a_call_site(tmp_path: Path):
    (tmp_path / "plugin.cc").write_text(
        "int g () { invoke_plugin_callbacks (PLUGIN_FINISH, NULL); }\n", encoding="utf-8"
    )
    assert plugin_gen.sites(tmp_path) == {}


def test_a_front_end_call_is_reported_under_its_directory(tmp_path: Path):
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "c-decl.cc").write_text(
        "void f () { invoke_plugin_callbacks (PLUGIN_FINISH_DECL, decl); }\n", encoding="utf-8"
    )
    found = plugin_gen.sites(tmp_path)
    assert found["PLUGIN_FINISH_DECL"] == [("c/c-decl.cc", 1, "decl")]


def test_data_passed_by_address_is_said_to_be_by_address():
    assert plugin_gen.data_type("NULL") == "none"
    assert plugin_gen.data_type("&gate_status") == "`gate_status`, by address"
    assert plugin_gen.data_type("pass") == "`pass`"


@needs_tree
def test_every_event_is_either_fired_or_one_of_the_three_pseudo_events():
    """The check that catches a new event nobody has classified.

    A row reading "no call site found" in the generated table means either GCC added an
    event and has not wired it up, or the scanner stopped recognising a call. Both are
    worth a build failure, and neither is visible by reading the table.
    """
    names = {e.name for e in plugin_gen.events(bpc.GCC_ROOT)}
    fired = set(plugin_gen.sites(bpc.GCC_ROOT))
    assert fired <= names, fired - names
    assert names - fired == set(plugin_gen.PSEUDO)


@needs_tree
def test_the_event_numbering_is_the_order_of_the_file():
    events = plugin_gen.events(bpc.GCC_ROOT)
    assert [e.index for e in events] == list(range(len(events)))
    assert events[0].name == "PLUGIN_START_PARSE_FUNCTION"
    assert all(e.name.startswith("PLUGIN_") for e in events)


@needs_tree
def test_the_two_events_this_project_relies_on_fire_from_the_pass_manager():
    found = plugin_gen.sites(bpc.GCC_ROOT)
    assert [f for f, _, _ in found["PLUGIN_PASS_EXECUTION"]] == ["passes.cc"]
    assert [d for _, _, d in found["PLUGIN_PASS_EXECUTION"]] == ["pass"]
    assert [d for _, _, d in found["PLUGIN_OVERRIDE_GATE"]] == ["&gate_status"]


# The build system reader


def test_a_backslash_continuation_makes_one_logical_line():
    """A makefile rule is written over four lines and is one rule, and a reader that goes
    line by line sees four things none of which parse."""
    text = "A = one \\\n    two \\\n    three\nB = four\n"
    assert buildsys.logical_lines(text) == ["A = one     two     three", "B = four", ""]


def test_a_substitution_reference_expands_word_by_word():
    names = {"files": "insn-attr.h insn-codes.h"}
    assert buildsys.expand("$(files:insn-%.h=s-%)", names) == "s-attr s-codes"


def test_a_suffix_substitution_is_the_other_form_and_both_are_needed():
    assert buildsys.substitute("foo.cc", ".cc", ".o") == "foo.o"
    assert buildsys.substitute("foo.cc", "%.cc", "s-%") == "s-foo"


def test_an_unknown_variable_expands_to_nothing_because_that_is_what_make_does():
    assert buildsys.expand("a $(nope) b", {}) == "a  b"


def test_a_variable_defined_in_terms_of_itself_is_reported_rather_than_hung_on():
    with pytest.raises(SourceError, match="after 20 rounds"):
        buildsys.expand("$(a)", {"a": "$(a)"})


def test_a_variable_assignment_is_not_a_rule_head():
    assert buildsys.split_head("CFLAGS = -O2 -g") is None
    assert buildsys.split_head("CFLAGS := -O2") is None
    assert buildsys.split_head("\tcommand: here") is None


def test_a_static_pattern_rule_comes_back_as_three_fields():
    """`targets: pattern: prerequisites` is how seven generator rules are written once, and
    the middle field is what says what `$*` will stand for."""
    head = buildsys.split_head("$(gen:insn-%.h=s-%): s-%: build/gen%")
    assert head is not None
    assert [f.strip() for f in head] == ["$(gen:insn-%.h=s-%)", "s-%", "build/gen%"]


def test_a_target_list_with_an_equals_inside_it_is_still_a_rule():
    """The `=` of a substitution reference is not the `=` of an assignment."""
    assert buildsys.split_head("$(a:x=y): dep") is not None


def test_a_comment_inside_a_recipe_does_not_end_the_recipe():
    """s-gtype writes two commands with an explanation between them at column zero."""
    lines = buildsys.logical_lines(
        "s-gtype: build/gengtype\n\tfirst\n# why the second one exists\n\tsecond\n"
    )
    found = buildsys.rules(lines, {})
    assert len(found) == 1
    assert [line.strip() for line in found[0].recipe] == ["first", "second"]


def test_the_stem_is_what_the_percent_matched():
    assert buildsys.stem_of("s-attr-common", "s-%") == "attr-common"
    assert buildsys.stem_of("insn-codes.h", "insn-%.h") == "codes"


def test_a_foreach_leaves_its_own_punctuation_on_the_last_output():
    """The split outputs are written inside a $(foreach ...) and the count is an autoconf
    substitution, so neither the semicolon nor the number is part of a filename."""
    assert buildsys.tidy("insn-emit-$(id).cc;)") == "insn-emit-N.cc"


@needs_tree
def test_every_generator_program_the_makefile_names_is_classified():
    found = buildsys.programs(bpc.GCC_ROOT)
    assert len(found) > 25
    assert all(what for _, what in found)
    assert ("recog", "the RTL reader") in found
    assert ("match", "nothing extra") in found
    # The names are stems, so `gengenrtl` is `genrtl` and that is not a typo.
    assert ("genrtl", "error reporting") in found


@needs_tree
def test_the_generator_that_writes_another_generator_is_not_confused_with_it():
    """genconditions writes build/gencondmd.cc and gencondmd writes insn-conditions.md.
    Attributing an output by the program name that appears next to it gets both wrong."""
    writes = buildsys.outputs(bpc.GCC_ROOT)
    assert writes["conditions"] == ["build/gencondmd.cc"]
    assert writes["condmd"] == ["insn-conditions.md"]


@needs_tree
def test_the_seven_generators_written_as_one_pattern_rule_are_all_found():
    """These are the ones a line by line reader misses entirely, because their rule names
    none of them."""
    writes = buildsys.outputs(bpc.GCC_ROOT)
    for stem, out in [
        ("attr", "insn-attr.h"),
        ("attr-common", "insn-attr-common.h"),
        ("codes", "insn-codes.h"),
        ("config", "insn-config.h"),
        ("flags", "insn-flags.h"),
        ("target-def", "insn-target-def.h"),
        ("constants", "insn-constants.h"),
        ("enums", "insn-enums.cc"),
    ]:
        assert writes[stem] == [out], stem


@needs_tree
def test_ada_is_read_through_the_file_it_sources():
    """The outer config-lang.in sets a language and sources the rest. A reader that stops
    at the outer file says Ada has no compiler, which is wrong."""
    ada = next(d for d in buildsys.declarations(bpc.GCC_ROOT) if d.directory == "ada")
    assert ada.get("compilers") == "gnat1$(exeext)"
    assert ada.get("build_by_default") == "no"


@needs_tree
def test_a_requirement_set_inside_a_shell_if_is_recorded_as_conditional():
    """Ada requires C and C++ only when it is not being cross built."""
    ada = next(d for d in buildsys.declarations(bpc.GCC_ROOT) if d.directory == "ada")
    assert ada.get("lang_requires") == "c c++"
    assert "lang_requires" in ada.conditional
    cpp = next(d for d in buildsys.declarations(bpc.GCC_ROOT) if d.directory == "cp")
    assert cpp.conditional == set()


@needs_tree
def test_release_checking_is_applied_before_anything_the_user_asked_for():
    """`--enable-checking=rtl` is release plus rtl, and a reader who thinks otherwise
    benchmarks the wrong compiler."""
    turns_on, macros, _ = buildsys.checking(bpc.GCC_ROOT)
    assert turns_on["release"] == {"assert_checking", "runtime_checking"}
    assert turns_on["rtl"] == {"rtl_checking"}
    assert turns_on["release"] & turns_on["rtl"] == set()
    assert macros["rtl_checking"] == "ENABLE_RTL_CHECKING"


@needs_tree
def test_the_only_two_words_that_turn_everything_off_are_no_and_none():
    turns_on, _, _ = buildsys.checking(bpc.GCC_ROOT)
    assert turns_on["no|none"] == set()
    assert all(turns_on[level] for level in buildsys.LEVELS if level != "no|none")


@needs_tree
def test_the_valgrind_macro_is_found_even_though_it_is_not_the_next_line():
    """It looks for the binary first, so a scan that only reads the following line reports
    the one category with no macro, which would be a lie about what it does."""
    _, macros, _ = buildsys.checking(bpc.GCC_ROOT)
    assert macros["valgrind_checking"] == "ENABLE_VALGRIND_CHECKING"


@needs_tree
def test_a_pipe_never_reaches_a_table_cell():
    """`no|none` is one case arm and two words, and a pipe inside a Markdown cell ends it."""
    assert buildsys.label("no|none") == "`no` or `none`"
    text = buildsys.build_checking(bpc.GCC_ROOT)
    assert "no|none" not in text
    for block in text.split("\n\n"):
        rows = block.splitlines()
        if not all(row[:1] == "|" for row in rows):
            continue
        widths = {len(row.split("|")) for row in rows}
        assert widths == {len(rows[0].split("|"))}, "a stray pipe makes one row wider"


# The bootstrap reader


def test_a_definition_ends_at_its_own_brace_and_not_a_nested_one():
    """`Makefile.def` has no nesting today, so a reader that stops at the first `}` looks
    correct until somebody adds one and every declaration after it is silently dropped."""
    found = bootstrap.definitions("a = { x=1 ; y={ z=2 ; } ; };\nb = { q=3 ; };\n")
    assert [d.name for d in found] == ["a", "b"]
    assert found[1].one("q") == "3"


def test_a_semicolon_inside_a_string_does_not_end_a_field():
    found = bootstrap.definitions('a = { doc="one ; two" ; id=3 ; };\n')
    assert found[0].one("doc") == "one ; two"
    assert found[0].one("id") == "3"


def test_a_comment_is_dropped_and_a_slash_in_a_string_is_not():
    """`//` starts a comment in autogen and also appears inside quoted flag values."""
    text = 'a = { flags="-I// -g" ; }; // why this exists\nb = { id=1 ; };\n'
    found = bootstrap.definitions(text)
    assert found[0].one("flags") == "-I// -g"
    assert [d.name for d in found] == ["a", "b"]


def test_a_field_that_appears_twice_keeps_both():
    """A module can be declared with several `extra_make_flags`, and taking the last would
    quietly halve what the table says the build does."""
    found = bootstrap.definitions("a = { f=1 ; f=2 ; };\n")
    assert found[0].fields["f"] == ["1", "2"]
    assert found[0].has("f")
    assert not found[0].has("g")


def test_a_stage_name_with_letters_in_it_is_read_whole():
    """`STAGEtrain_GENERATOR_CFLAGS` splits into `train` and `GENERATOR_CFLAGS`, and a
    pattern that is not greedy enough invents a stage called `train_GENERATOR`."""
    m = bootstrap.FLAG.match("STAGEtrain_GENERATOR_CFLAGS = -O0")
    assert m is not None
    assert m.group("stage") == "train"
    assert m.group("what") == "GENERATOR_CFLAGS"


def test_a_commented_out_assignment_is_not_something_a_fragment_does():
    """`bootstrap-debug-ckovw.mk` carries two of them, and counting them would say the
    fragment sets `BOOT_CFLAGS` when it does not."""
    found = bootstrap.ASSIGNS.findall("# BOOT_CFLAGS += -x\nTFLAGS := -y\noverride Z = 1\n")
    assert found == ["TFLAGS", "Z"]


def test_a_fragment_with_no_comment_says_so_rather_than_inventing_one():
    assert bootstrap.sentence("") == "the fragment carries no comment"
    assert bootstrap.sentence("One thing. And another.") == "One thing"
    assert bootstrap.sentence("Trailing period.") == "Trailing period"


@needs_tree
def test_every_stage_after_the_first_is_built_by_another_one():
    found = bootstrap.stages(bpc.GCC_ROOT)
    assert len(found) == 9
    assert found[0].one("id") == "1"
    assert not found[0].has("prev")
    assert all(s.has("prev") for s in found[1:])


@needs_tree
def test_only_the_two_stages_that_can_compare_anything_do():
    """A comparison needs two stages built from one source by one set of rules, which first
    exists at stage three. Stage two has nothing legitimate to be compared against."""
    comparing = [s.one("id") for s in bootstrap.stages(bpc.GCC_ROOT) if s.has("compare_target")]
    assert comparing == ["3", "4"]


@needs_tree
def test_less_than_half_the_host_modules_are_inside_the_stage_loop():
    inside, outside = bootstrap.modules(bpc.GCC_ROOT)
    assert len(inside) == 25
    assert len(inside) + len(outside) == 54
    assert "gcc" in inside and "libiberty" in inside
    assert "gdb" in outside


@needs_tree
def test_the_exclusions_are_the_ones_that_apply_everywhere():
    """The AIX line is inside a case on the target, so a reader that took every assignment
    would tell everyone that libgomp is forgiven on their machine too."""
    found = bootstrap.exclusions(bpc.GCC_ROOT)
    assert len(found) == 6
    assert found[0] == "gcc/cc*-checksum$(objext)"
    assert not any("libgomp" in p for p in found)


@needs_tree
def test_the_fragment_that_replaces_the_comparison_says_that_is_what_it_changes():
    by_name = {c.name: c for c in bootstrap.build_configs(bpc.GCC_ROOT)}
    assert "the comparison itself" in by_name["bootstrap-debug"].changes()
    assert by_name["bootstrap-O3"].changes() == "`BOOT_CFLAGS`, so every stage"


@needs_tree
def test_a_build_config_is_named_the_way_configure_takes_it():
    """The ledger classifies these, and a name a reader cannot paste into a configure line
    is a name they have to translate before it is any use."""
    names = bootstrap.config_names(bpc.GCC_ROOT)
    assert len(names) == 19
    assert all(n.startswith("bootstrap-") for n in names)
    assert "bootstrap-lto" in names
