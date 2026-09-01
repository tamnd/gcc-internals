"""The widgets, checked against the three properties the package promises.

A widget consumes a `gxray` model, renders itself in Python, and works with no runtime and
no colour vision. The first is checked by construction, the other two are checked here on
the markup, because the static fallback is the same renderer and there is nothing else to
compare it against.

The inputs are real: the tree-ssa dump and the pass list a local `gcc-16` produced, plus the
recorded corpus entry for the two ends of the pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gxray import gimple, locs, passes
from gxwidgets import (
    GateError,
    IRLadder,
    Option,
    PassTape,
    PredictGate,
    SSAWeb,
    Widget,
    html,
    script,
    state,
)
from gxwidgets.ssaweb import INLINE_LIMIT

CORPUS = Path(__file__).resolve().parent.parent / "corpora" / "dumps" / "l1-O2.json"


@pytest.fixture
def ssa(ssa_dump):
    return gimple.parse(ssa_dump).only()


@pytest.fixture
def pipeline(passes_text):
    return passes.parse(passes_text)


@pytest.fixture
def both_ends():
    """The recorded dumps at the two ends of the pipeline, keyed by dump name."""
    data = json.loads(CORPUS.read_text(encoding="utf-8"))["dumps"]
    return {k: gimple.parse(data[k]).only() for k in ("tree-ssa", "tree-optimized")}


@pytest.fixture
def recorded():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


@pytest.fixture
def ladder(recorded):
    """The real ladder, out of the recorded corpus, at all four levels."""
    return locs.ladder(
        recorded["source"],
        generic=recorded["dumps"]["tree-original"],
        gimple=recorded["dumps"]["tree-optimized"],
        rtl=recorded["dumps"]["rtl-expand"],
        asm=recorded["asm"],
        function="f",
    )


@pytest.fixture
def rungs(ladder):
    return IRLadder(ladder)


@pytest.fixture
def tape(pipeline, both_ends):
    return PassTape(pipeline, dumps=both_ends, function="f")


@pytest.fixture
def gate():
    return PredictGate(
        "Does -O2 unroll this three iteration loop?",
        [
            ("Yes, all three iterations", ""),
            ("No, the loop survives", "cunrolli unrolls a loop whose trip count is known."),
        ],
        answer="cunrolli peels all three iterations before anything else looks at the loop.",
    )


# The markup helpers


def test_esc_closes_the_four_holes():
    assert html.esc('<bb 2> & "x"') == "&lt;bb 2&gt; &amp; &quot;x&quot;"


def test_attrs_skips_none_and_false_and_writes_true_bare():
    assert html.attrs({"hidden": True}) == " hidden"
    assert html.attrs({"hidden": False, "aria_current": None}) == ""
    assert html.attrs({"tabindex": 0}) == ' tabindex="0"'


def test_attrs_turns_python_names_into_html_names():
    assert html.attrs({"class_": "a", "data_cell": "b", "for_": "c"}) == (
        ' class="a" data-cell="b" for="c"'
    )


def test_attribute_values_are_escaped():
    assert '"' not in html.attrs({"aria_label": 'a "quoted" label'}).split("=", 1)[1][1:-1]


def test_join_drops_the_empty_pieces():
    assert html.join(["a", "", "b"], " ") == "a b"


def test_the_legend_shows_a_glyph_and_a_meaning_for_every_role():
    text = html.role_legend(["added", "removed"])
    assert "+" in text and "-" in text
    assert "created by this pass" in text
    assert 'aria-label="What the markers mean"' in text


def test_the_stylesheet_hard_codes_no_colour():
    """Colours come from the palette as custom properties, so there is one source."""
    body = html.STYLESHEET.split("@media")[1]
    assert "#" not in body.split(".gx-root")[1]


def test_the_frame_carries_an_id_a_kind_and_an_accessible_name():
    out = html.frame("passtape", "The pass pipeline", "<p>hi</p>", state="at:x", id="tape2")
    assert 'data-gx="passtape"' in out
    assert 'data-id="tape2"' in out
    assert 'data-state="at:x"' in out
    assert 'aria-labelledby="tape2-title"' in out
    assert 'id="tape2-title"' in out


# The URL


def test_a_view_round_trips_through_a_fragment():
    view = {"at": "forwprop2", "sel": "s_1"}
    assert state.decode(state.encode(view)) == view


def test_the_fragment_is_meant_to_be_read_by_a_person():
    assert state.encode({"at": "forwprop2", "sel": "s_1"}) == "at:forwprop2,sel:s_1"


def test_reserved_characters_survive_the_trip():
    view = {"at": "a,b;c:d#e%f"}
    assert state.decode(state.encode(view)) == view


def test_empty_values_are_left_out_rather_than_written():
    assert state.encode({"at": "", "only": "changed"}) == "only:changed"
    assert state.fragment("tape", {}) == ""


def test_a_malformed_fragment_gives_defaults_rather_than_an_exception():
    assert state.decode("nonsense,,:x,at:ok") == {"at": "ok"}
    assert state.read("no equals sign here") == {}


def test_two_widgets_share_one_fragment():
    got = state.read("#passtape=at:ccp1;ssaweb=name:s_1")
    assert got == {"passtape": {"at": "ccp1"}, "ssaweb": {"name": "s_1"}}


# The base class


def test_a_view_key_the_widget_does_not_have_is_a_mistake(tape):
    with pytest.raises(KeyError, match="only, phase"):
        tape.update(zoom="2")


def test_a_view_key_from_a_url_is_dropped_quietly(tape):
    tape.from_fragment("#passtape=at:ccp1,zoom:2")
    assert tape.view["at"] == "ccp1"
    assert "zoom" not in tape.view


def test_a_fragment_for_another_widget_is_ignored(tape):
    before = dict(tape.view)
    tape.from_fragment("#ssaweb=name:s_1")
    assert tape.view == before


def test_the_state_attribute_has_no_widget_id_in_it(tape):
    assert tape.state == state.encode(tape.view, keep_empty=True)
    assert tape.fragment == f"passtape={tape.state}"


def test_the_state_attribute_names_every_key_even_the_empty_ones(gate):
    """It is how the browser learns which keys a link is allowed to set on this widget."""
    assert gate.state == "pick:,shown:"
    assert gate.fragment == ""


def test_a_widget_with_no_body_says_so():
    with pytest.raises(NotImplementedError):
        Widget().render()


def test_two_widgets_of_one_kind_keep_separate_state(pipeline, both_ends):
    a = PassTape(pipeline, dumps=both_ends, id="tape-a")
    b = PassTape(pipeline, dumps=both_ends, id="tape-b", at="ccp1")
    assert 'data-id="tape-a"' in a.render()
    assert b.fragment.startswith("tape-b=")
    assert a.view["at"] != b.view["at"]


# The pass tape


def test_the_tape_has_one_cell_per_pass_that_is_on(tape, pipeline):
    assert len(tape.cells) == pipeline.counts()["enabled"] == 281


def test_a_pass_with_no_dump_says_so_rather_than_guessing(tape):
    quiet = [c for c in tape.cells if c.stats is None]
    assert len(quiet) == len(tape.cells) - 2
    assert all(c.changed is None for c in quiet)
    assert "nothing recorded to compare" in quiet[0].label


def test_the_first_recorded_dump_has_nothing_to_compare_with(tape):
    first, second = tape.marked
    assert first.changed is None
    assert second.changed is True


def test_a_cell_carries_every_fact_a_filter_needs(tape):
    out = tape.render()
    assert 'data-changed="?"' in out
    assert 'data-changed="1"' in out
    assert 'data-phase="tree"' in out


def test_filtering_by_phase_keeps_only_that_phase(tape):
    tape.update(phase="rtl")
    assert tape.shown and all(c.phase == "rtl" for c in tape.shown)


def test_filtering_to_changed_keeps_only_what_moved(tape):
    tape.update(only="changed")
    assert [c.name for c in tape.shown] == ["tree-optimized"]


def test_a_filter_that_matches_nothing_says_so_instead_of_rendering_an_empty_strip(tape):
    tape.update(phase="ipa", only="changed")
    assert tape.shown == []
    assert "No pass matches this filter" in tape.render()


def test_the_tape_opens_at_the_first_pass_with_something_to_show(tape):
    assert tape.view["at"] == "tree-ssa"
    assert tape.selected.name == "tree-ssa"


def test_every_cell_has_a_label_a_screen_reader_can_use(tape):
    for c in tape.cells:
        assert c.label.startswith(f"{c.index + 1}. {c.name}")


def test_there_is_a_panel_for_each_dump_and_one_for_the_rest(tape):
    out = tape.render()
    for key in ("tree-ssa", "tree-optimized", "nodump"):
        assert f'data-panel="{key}"' in out
    assert out.count('role="tabpanel"') == 3


def test_the_ir_listing_is_escaped(tape):
    out = tape.render()
    assert "&lt;bb 2&gt;" in out
    assert "<bb 2>" not in out


def test_the_whole_pipeline_is_readable_with_no_javascript(tape):
    out = tape.render()
    assert "<noscript>" in out
    for c in tape.cells[:5]:
        assert html.esc(c.label) in out


def test_the_trend_line_is_also_written_out_as_numbers(tape):
    out = tape.render()
    assert "Statement count across the recorded boundaries" in out
    assert "11 statements" in out


def test_a_tape_with_one_dump_does_not_draw_a_trend(pipeline, ssa):
    lonely = PassTape(pipeline, dumps={"tree-ssa": ssa})
    assert "Two recorded dumps are needed" in lonely.render()


# The SSA web


def test_the_names_are_the_ones_defined_in_this_function(ssa):
    web = SSAWeb(ssa)
    assert web.names
    assert all(ssa.ssa_web(n)["def"] is not None for n in web.names)


def test_the_first_name_is_selected_when_none_is_asked_for(ssa):
    assert SSAWeb(ssa).view["name"] == SSAWeb(ssa).names[0]


def test_the_rows_mark_the_definition_once_and_every_use(ssa):
    web = SSAWeb(ssa, "s_1")
    rows = web.rows("s_1")
    assert len([r for r in rows if r.kind == "def"]) == 1
    assert len([r for r in rows if r.kind == "use"]) == len(ssa.ssa_web("s_1")["uses"])


def test_the_drawing_has_a_thread_from_the_definition_to_each_use(ssa):
    drawing = SSAWeb(ssa, "s_1")._svg("s_1")
    uses = len(ssa.ssa_web("s_1")["uses"])
    assert drawing.count('class="thread"') == uses
    assert drawing.count('class="def"') == 1
    assert drawing.count('class="use"') == uses


def test_the_definition_and_the_uses_are_marked_without_colour(ssa):
    out = SSAWeb(ssa, "s_1").render()
    assert ">D</text>" in out
    assert ">u</text>" in out


def test_every_mention_of_the_name_is_marked_in_the_text(ssa):
    out = SSAWeb(ssa, "s_1").render()
    assert '<tspan class="hit">s_1</tspan>' in out


def test_a_drawing_says_in_words_what_it_shows(ssa):
    said = SSAWeb(ssa, "s_1")._description("s_1")
    assert said.startswith("The SSA web of s_1.")
    assert ";;" not in said
    assert said.endswith(".")


def test_the_drawing_carries_that_description_as_its_label(ssa):
    web = SSAWeb(ssa, "s_1")
    assert html.esc(web._description("s_1")) in web.render()


def test_a_parameter_can_be_followed_even_though_it_has_no_definition(ssa):
    web = SSAWeb(ssa, "n_5")
    assert "n_5" in web.names
    assert "arrived as a parameter" in web._description("n_5")
    assert 'data-panel="n_5"' in web.render()


def test_the_prose_counts_in_english(ssa):
    assert "1 use." in SSAWeb(ssa, "n_5")._summary("n_5")
    assert "2 uses." in SSAWeb(ssa, "s_1")._summary("s_1")


def test_a_small_function_draws_every_name_up_front(ssa):
    web = SSAWeb(ssa)
    assert len(web.names) <= INLINE_LIMIT
    assert web.drawn == web.names
    assert web.render().count('role="tabpanel"') == len(web.names)


def test_only_the_selected_panel_is_showing(ssa):
    """Counted on the panels, not on the whole document, since the stylesheet says
    `overflow: hidden` and a substring search over everything would find that too."""
    out = SSAWeb(ssa, "s_1").render()
    assert out.count('data-panel="s_1" hidden') == 0
    assert out.count('role="tabpanel" data-panel="') == len(SSAWeb(ssa).names)
    assert out.count('role="tabpanel" data-panel="') - out.count('" hidden') == 1


def test_a_big_function_draws_one_name_and_says_why(ssa, monkeypatch):
    web = SSAWeb(ssa, "s_1")
    monkeypatch.setattr(web, "names", web.names * 3)
    assert web.drawn == ["s_1"]
    assert f"more than the {INLINE_LIMIT}" in web.render()


def test_there_is_a_text_version_of_the_web(ssa):
    out = SSAWeb(ssa, "s_1").render()
    assert "The same thing as text" in out
    assert "def: " in out and "use: " in out


# The IR ladder


def test_the_ladder_starts_on_the_first_line_that_has_anything_on_it(rungs, ladder):
    assert rungs.view["line"] == str(ladder.rungs[0].line)


def test_a_line_nobody_asked_about_falls_back_rather_than_rendering_nothing(ladder):
    """A link can name a line that is a comment, or a line from a different file."""
    assert IRLadder(ladder, line=999).view["line"] == str(ladder.rungs[0].line)


def test_every_rung_gets_a_panel_and_only_one_is_open(rungs, ladder):
    out = rungs.render()
    assert out.count('role="tabpanel"') == len(ladder.rungs)
    assert out.count('role="tabpanel" data-panel="') - out.count('" hidden') == 1


def test_a_rung_says_in_words_what_its_bars_draw(rungs):
    """The bars are the only thing on a rung that is a picture, so the sentence behind
    them has to say the same thing or a reader with a screen reader gets less."""
    label = rungs._rung_label(rungs.ladder.rung(7))
    assert "Line 7" in label
    assert "s += i;" in label
    assert "1 GENERIC, 1 GIMPLE, 1 RTL, 1 assembly" in label


def test_the_loop_header_has_the_most_on_it(rungs):
    counts = {r.line: sum(r.counts().values()) for r in rungs.ladder.rungs}
    assert max(counts, key=counts.get) == 6


def test_a_level_with_nothing_on_it_says_so_rather_than_being_left_out(rungs):
    """`return s;` has nothing at the bottom two levels, and that is the interesting part,
    so the panel has to show the gap rather than quietly close it up."""
    out = rungs.render()
    assert "Nothing here." in out
    assert rungs.ladder.rung(8).empty_levels == ["rtl", "asm"]


def test_the_ladder_names_the_file_and_counts_every_level(rungs):
    out = rungs.render()
    assert "l1.c" in out
    for name in ("GENERIC", "GIMPLE", "RTL", "assembly"):
        assert name in out


def test_the_ladder_selection_writes_to_its_own_view_key(rungs):
    assert 'data-select="line"' in rungs.render()
    assert rungs.fragment.startswith("irladder=line:")


def test_a_ladder_with_nothing_in_it_says_so():
    empty = IRLadder(locs.ladder("int main(void) { return 0; }"))
    assert "No level in this build carried a location" in empty.render()


# The prediction gate


def test_the_gate_knows_which_option_is_right(gate):
    assert gate.correct == 0
    assert gate.data()["correct"] == 0


def test_a_gate_with_one_option_is_a_statement():
    with pytest.raises(GateError, match="not a question"):
        PredictGate("q", [("only one", "")], answer="a")


def test_a_gate_needs_exactly_one_right_answer():
    with pytest.raises(GateError, match="exactly one correct"):
        PredictGate("q", [("a", ""), ("b", "")], answer="a")
    with pytest.raises(GateError, match="exactly one correct"):
        PredictGate("q", [("a", "no"), ("b", "no")], answer="a")


def test_a_wrong_option_has_to_say_why_it_is_wrong():
    with pytest.raises(GateError, match="teaches nothing"):
        PredictGate(
            "q",
            [Option("a", correct=True), Option("b")],
            answer="a",
        )


def test_a_gate_needs_an_explanation():
    with pytest.raises(GateError, match="explanation"):
        PredictGate("q", [("a", ""), ("b", "why")], answer="")


def test_the_answer_is_shut_until_the_reader_opens_it(gate):
    out = gate.render()
    assert '<details class="gx-answer">' in out
    assert "open" not in out.split("gx-answer")[1][:40]


def test_the_answer_opens_when_the_url_says_it_was_opened(gate):
    gate.update(shown="1")
    assert 'class="gx-answer" open' in gate.render()


def test_the_reader_can_answer_with_the_keyboard(gate):
    out = gate.render()
    assert out.count('type="radio"') == 2
    assert "<label" in out and "<legend>" in out


def test_the_pick_from_the_url_comes_back_checked(gate):
    gate.update(pick="1")
    assert 'value="1" data-option="1" checked' in gate.render()


def test_each_wrong_option_carries_its_own_explanation(gate):
    out = gate.render()
    assert 'data-why="1"' in out
    assert "cunrolli unrolls a loop whose trip count is known." in out


def test_the_right_option_has_nothing_to_explain(gate):
    assert 'data-why="0"' not in gate.render()


def test_the_observation_is_shown_as_written():
    g = PredictGate(
        "q",
        [("a", ""), ("b", "because")],
        answer="a",
        observe="  <bb 2>\n  s_1 = 0;",
    )
    assert "&lt;bb 2&gt;" in g.render()


def test_the_question_is_escaped():
    g = PredictGate("Is a_1 < b_2?", [("a", ""), ("b", "no")], answer="a")
    assert "<legend>Is a_1 &lt; b_2?</legend>" in g.render()


# What every widget has to do


@pytest.fixture
def every(tape, ssa, gate, rungs):
    return [tape, rungs, SSAWeb(ssa, "s_1"), gate]


def test_every_widget_renders_standalone(every):
    for w in every:
        out = w.render()
        assert out.startswith('<div class="gx-root')
        assert "<style" in out
        assert f'data-gx="{w.kind}"' in out


def test_every_widget_has_an_accessible_name(every):
    for w in every:
        assert f'aria-labelledby="{w.id}-title"' in w.render()
        assert w.title in w.render()


def test_every_widget_puts_its_view_where_the_browser_can_read_it(every):
    for w in every:
        assert f'data-state="{w.state}"' in w.render()


def test_every_widget_renders_in_a_notebook_without_being_asked(every):
    for w in every:
        assert w._repr_html_() == w.render()


def test_every_widget_survives_a_fragment_from_a_stranger(every):
    for w in every:
        w.from_fragment("#" + w.id + "=at:%%%,junk;other=x:1")
        assert w.render()


def test_there_is_exactly_one_behaviour_module():
    text = script()
    assert "export function attach" in text
    assert "export default" in text
    assert "innerHTML" in text.split("export default")[1]


def test_the_demo_page_builds_from_the_recorded_corpus():
    """`just widgets` is how a widget gets looked at, so it has to keep working."""
    from gxwidgets.__main__ import build

    page = build()
    assert page.startswith("<!doctype html>")
    for kind in ("passtape", "ssaweb", "predictgate"):
        assert f'data-gx="{kind}"' in page
    assert "attach();" in page


def test_the_demo_page_does_not_let_the_script_close_itself():
    from gxwidgets.__main__ import build

    body = build().split('<script type="module">')[1]
    assert "</script>" not in body.rsplit("\n</script>", 1)[0]


def test_the_behaviour_module_builds_no_markup():
    """If this file starts writing labels then the static page and the live page differ."""
    text = script()
    for banned in ("createElement", "insertAdjacentHTML", "textContent ="):
        assert banned not in text
