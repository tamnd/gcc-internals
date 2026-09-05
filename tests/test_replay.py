"""The recorded debugger session, and the bisection that runs over recorded compilations.

These two artefacts are checked with different amounts of suspicion, because they are
different kinds of thing.

The session is a transcript. Nothing can regenerate it, so nothing here can prove it is
current, and pretending otherwise with a strict test would be theatre. What the tests do
instead is prove it is well formed and internally consistent: every step has output or a good
reason not to, the two `pcfun` calls really do bracket a transformation, the breakpoint
numbers gdb handed out are the ones the later steps refer to, and no step is quietly an error
message. A recording that has rotted usually rots into an error message.

The bisection is not a transcript. `Bisect.narrow` is a binary search that runs now, and its
answer has to equal the answer a full sweep gives, so it is tested the way any search is: on
the recorded data, on the edges, and against a hand built sweep with a known answer.
"""

from __future__ import annotations

import json
import re

import pytest

from gxray import replay

CC1 = replay.load("cc1")
BISECT = replay.load_bisect("counters")


def test_the_package_exports_it_so_a_lesson_can_say_gxray_replay():
    import gxray

    assert gxray.replay is replay
    assert "replay" in gxray.__all__


def test_asking_for_a_recording_that_is_not_there_says_what_is():
    with pytest.raises(FileNotFoundError, match="Have: "):
        replay.load("nosuchsession")


def test_it_records_the_machine_and_the_build_because_a_transcript_is_not_portable():
    """Everything a reader needs to know why their own session looks different."""
    assert CC1.tag.startswith("releases/gcc-")
    assert len(CC1.commit) == 40
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", CC1.recorded)
    assert "gdb" in CC1.gdb.lower()
    assert "-O0" in CC1.configure and "-g3" in CC1.configure
    assert "enable-checking" in CC1.configure
    assert CC1.megabytes > 100, "a stripped or optimised cc1 would not be this size"


def test_every_step_is_grouped_and_explained():
    assert len(CC1.steps) >= 20
    assert 4 <= len(CC1.groups) <= 8
    for step in CC1.steps:
        assert step.command.strip() == step.command
        assert step.why.endswith("."), f"step {step.n} has no sentence saying why it is there"
        assert len(step.why) < 100


def test_the_steps_are_numbered_from_one_and_the_groups_do_not_interleave():
    assert [one.n for one in CC1.steps] == list(range(1, len(CC1.steps) + 1))
    seen: list[str] = []
    for step in CC1.steps:
        if not seen or seen[-1] != step.group:
            assert step.group not in seen, f"{step.group!r} is split in two"
            seen.append(step.group)
    assert tuple(seen) == CC1.groups


def test_nothing_in_the_session_is_an_undefined_command():
    """How a recording rots. A renamed shorthand does not vanish, it becomes an error."""
    for step in CC1.steps:
        assert "Undefined command" not in step.output, f"step {step.n}: {step.command}"
        assert "No symbol" not in step.output, f"step {step.n}: {step.command}"


def test_the_only_silent_steps_are_the_ones_that_should_be():
    """gdb prints nothing for `delete` and for `ignore`, and something for everything else."""
    quiet = {one.command.split()[0] for one in CC1.steps if one.quiet}
    assert quiet <= {"delete", "ignore"}


def test_gdbinit_ran_and_set_the_four_breakpoints_before_anything_was_typed():
    assert "Successfully loaded GDB hooks for GCC" in CC1.startup
    first = CC1.step(1)
    assert first.command == "info breakpoints"
    for name in ("fancy_abort", "internal_error", "exit", "abort"):
        assert name in first.output


def test_the_refusal_is_recorded_separately_and_is_the_real_message():
    """The most common way a first session goes wrong, kept verbatim so it is recognisable."""
    assert "auto-loading has been declined" in CC1.declined
    assert "add-auto-load-safe-path" in CC1.declined
    assert "Successfully loaded GDB hooks" not in CC1.declined


def test_the_compiler_was_run_on_the_program_the_session_says_it_was():
    """The argv came from the driver, so it has to name the file whose text is recorded."""
    assert "int f (int n)" in CC1.source
    assert any(arg.endswith(".c") for arg in CC1.argv)
    assert "-O2" in CC1.argv
    assert CC1.find("run ").command.split()[1:] == list(CC1.argv)


def test_a_pass_runs_hundreds_of_times_for_nine_lines_of_c():
    """The number the lesson is built on, taken out of gdb's own hit count."""
    counted = [one for one in CC1.steps if one.command == "info breakpoints"][-1]
    hits = re.search(r"breakpoint already hit (\d+) times", counted.output)
    assert hits, "the counting breakpoint reported no hits"
    assert int(hits.group(1)) > 100


def test_the_two_pcfun_calls_bracket_a_transformation():
    """Before and after ccp, which is the one thing in the session that has to be a change."""
    before, after = (one for one in CC1.steps if one.command == "pcfun")
    assert before.n < after.n
    assert "int f (int n)" in before.output and "int f (int n)" in after.output
    assert before.output != after.output
    assert "s_3 = 0;" in before.output
    assert "s_3 = 0;" not in after.output


def test_the_pretty_printers_are_the_reason_the_output_is_readable():
    """A printed tree, a printed pass and a printed edge, none of which is a raw pointer."""
    assert "<function_decl" in CC1.find("print cfun->decl").output
    assert '"ccp"' in CC1.find("print pass").output
    assert "<edge" in CC1.find("print ((*cfun").output


def test_break_on_pass_takes_a_class_name_and_says_nothing_useful_when_it_does_not():
    """The trap, recorded. A pass name produces a pending breakpoint that never fires."""
    wrong = CC1.find("break-on-pass ccp")
    right = CC1.find("break-on-pass pass_ccp")
    assert "not defined" in wrong.output and "pending" in wrong.output
    assert "pending" not in right.output
    assert "tree-ssa-ccp.cc" in right.output, "the class name resolves to a real address"


def test_asking_for_a_command_that_was_not_typed_refuses_rather_than_inventing_one():
    with pytest.raises(KeyError, match="This is a recording"):
        CC1.find("print never_typed_this")


def test_a_group_can_be_played_back_on_its_own_and_looks_like_a_terminal():
    text = CC1.transcript(CC1.groups[0])
    assert text.startswith(replay.PROMPT)
    assert text.count(replay.PROMPT) == len(CC1.group(CC1.groups[0]))
    with pytest.raises(KeyError, match="Have: "):
        CC1.group("no such group")


def test_the_whole_transcript_has_one_prompt_per_step():
    assert CC1.transcript().count(replay.PROMPT) == len(CC1.steps)


def test_asking_for_a_step_out_of_range_says_how_many_there_are():
    with pytest.raises(KeyError, match="It has"):
        CC1.step(len(CC1.steps) + 1)


def test_the_sweep_covers_every_call_of_the_counter_and_zero():
    assert BISECT.total > 1
    assert [one.limit for one in BISECT.trials] == list(range(BISECT.total + 1))
    assert BISECT.counter in {row.split()[0] for row in BISECT.listing.splitlines() if row.strip()}


def test_fifty_compilations_produced_two_answers_which_is_why_bisecting_works():
    assert len(BISECT.variants) == 2
    assert BISECT.variants[0] != BISECT.variants[1]
    assert BISECT.good(BISECT.total), "the unlimited number of folds has to match no limit"
    assert not BISECT.good(0)


def test_the_answer_is_a_step_and_the_search_finds_the_edge_of_it():
    assert BISECT.monotone
    assert not BISECT.good(BISECT.first_good - 1)
    assert BISECT.good(BISECT.first_good)


def test_the_binary_search_agrees_with_the_exhaustive_sweep():
    narrowed = BISECT.narrow()
    assert narrowed.answer == BISECT.first_good
    assert len(narrowed.probes) < BISECT.total, "a bisection that probes everything is a sweep"
    assert narrowed.probes[-1].low == narrowed.probes[-1].high == narrowed.answer
    assert BISECT.counter in narrowed.report()
    assert str(narrowed.answer) in narrowed.report()


def test_each_probe_halves_the_range_it_was_given():
    probes = BISECT.narrow().probes
    widths = [one.high - one.low for one in probes]
    assert widths == sorted(widths, reverse=True)
    assert widths[-1] == 0


def test_the_search_is_the_same_search_on_a_sweep_with_a_known_answer():
    """Built rather than recorded, so the arithmetic is tested away from the real data."""
    for answer in (0, 1, 7, 40):
        made = replay.Bisect(
            name="made up",
            recorded="2026-01-01",
            tag="releases/gcc-16.2.0",
            commit="0" * 40,
            host="nowhere",
            compiler="none",
            counter="pretend",
            flags=(),
            program="none.c",
            source="",
            total=40,
            variants=("good", "bad"),
            trials=tuple(
                replay.Trial(limit=n, variant=0 if n >= answer else 1, stderr="") for n in range(41)
            ),
            listing="",
            culprit=("#0  nothing",),
        )
        assert made.first_good == answer
        assert made.narrow().answer == answer


def test_a_sweep_that_never_recovers_says_so_rather_than_returning_a_number():
    never = replay.Bisect(
        name="made up",
        recorded="2026-01-01",
        tag="releases/gcc-16.2.0",
        commit="0" * 40,
        host="nowhere",
        compiler="none",
        counter="pretend",
        flags=(),
        program="none.c",
        source="",
        total=3,
        variants=("good", "bad"),
        trials=tuple(replay.Trial(limit=n, variant=1, stderr="") for n in range(4)),
        listing="",
        culprit=("#0  nothing",),
    )
    with pytest.raises(ValueError, match="no limit reproduced"):
        assert never.first_good


def test_asking_for_a_limit_outside_the_sweep_says_what_was_recorded():
    with pytest.raises(KeyError, match="The recording covers"):
        BISECT.trial(BISECT.total + 1)


def test_the_counter_announced_its_limits_on_stderr():
    """How GCC tells you a limit was reached, which is the only feedback the flag gives."""
    said = BISECT.messages
    assert any("lower limit" in one for one in said)
    assert any("upper limit" in one for one in said)
    assert all(one.startswith("***dbgcnt:") for one in said)


def test_the_debugger_named_the_transformation_the_bisection_found():
    """The point of the whole exercise: a number, and then a place in the source."""
    assert BISECT.culprit[0].startswith("#0  dbg_cnt")
    assert len(BISECT.culprit) >= 4
    assert any(".cc:" in frame for frame in BISECT.culprit[1:])


def test_both_recordings_come_from_the_same_tree_and_the_same_machine():
    assert BISECT.tag == CC1.tag
    assert BISECT.commit == CC1.commit
    assert BISECT.host == CC1.host
    assert BISECT.program == CC1.program
    assert BISECT.source == CC1.source


def test_the_recordings_are_json_a_person_could_review():
    for name in ("cc1", "counters"):
        text = (replay.REPLAYS / f"{name}.json").read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert json.loads(text)
        assert "\\u" not in text, "escaped unicode in a transcript nobody can read in a diff"
