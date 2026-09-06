"""gxplug, and the reader for what it emits.

Two kinds of test here. Most run anywhere and work on a recorded stream. A few build the
plugin against a real GCC 16 and run it, and those skip when there is no such compiler,
because a contributor on a laptop with GCC 13 should still get a green suite.

The one that matters most is `test_the_plugin_does_not_change_the_generated_code`. Every
lesson that uses gxplug rests on the plugin being a passive observer, and an assertion in
a design document is not a guarantee.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from gxray import plug

REPO = Path(__file__).resolve().parent.parent
GXPLUG = REPO / "gxplug"
TREE_PASS_H = REPO / "vendor" / "gcc" / "gcc" / "tree-pass.h"


# A stream is easier to reason about as a literal than as a fixture built by a compiler,
# and these are real lines, trimmed out of a run of `gcc-16 -O2 -S` on the loop in
# `make check`.
STREAM = "\n".join(
    json.dumps(record)
    for record in [
        {
            "seq": 0,
            "event": "pass-start",
            "pass": "cfg",
            "pass_number": 20,
            "function": "f",
            "properties": 16385,
            "statements": None,
            "insns": None,
            "blocks": None,
            "seconds": None,
        },
        {
            "seq": 1,
            "event": "pass-end",
            "pass": "cfg",
            "pass_number": 20,
            "function": "f",
            "properties": 84239,
            "statements": 8,
            "insns": None,
            "blocks": 6,
            "seconds": 0.000065,
        },
        {
            "seq": 2,
            "event": "pass-start",
            "pass": "*warn_function_return",
            "pass_number": -1,
            "function": "f",
            "properties": 84239,
            "statements": 8,
            "insns": None,
            "blocks": 6,
            "seconds": None,
        },
        {
            "seq": 3,
            "event": "pass-end",
            "pass": "*warn_function_return",
            "pass_number": -1,
            "function": "f",
            "properties": 84239,
            "statements": 8,
            "insns": None,
            "blocks": 6,
            "seconds": 0.000001,
        },
        {
            "seq": 4,
            "event": "pass-start",
            "pass": "expand",
            "pass_number": 180,
            "function": "f",
            "properties": 84239,
            "statements": 8,
            "insns": None,
            "blocks": 6,
            "seconds": None,
        },
        {
            "seq": 5,
            "event": "pass-end",
            "pass": "expand",
            "pass_number": 180,
            "function": "f",
            "properties": 3538136,
            "statements": None,
            "insns": 26,
            "blocks": 8,
            "seconds": 0.000211,
        },
    ]
)


def test_a_stream_parses_into_events():
    stream = plug.parse(STREAM)
    assert len(stream.events) == 6
    assert stream.events[0].pass_name == "cfg"
    assert stream.events[1].statements == 8


def test_blank_lines_are_not_events():
    assert len(plug.parse(f"\n\n{STREAM}\n\n").events) == 6


def test_a_line_that_is_not_json_says_which_line():
    with pytest.raises(ValueError, match="line 2"):
        plug.parse(
            '{"seq":0,"event":"pass-start","pass":null,"pass_number":0,'
            '"function":null,"properties":null,"statements":null,"insns":null,'
            '"blocks":null,"seconds":null}\nnot json\n'
        )


def test_a_record_missing_a_field_says_which_field():
    with pytest.raises(ValueError, match="missing blocks"):
        plug.parse(
            '{"seq":0,"event":"pass-start","pass":null,"pass_number":0,'
            '"function":null,"properties":null,"statements":null,"insns":null,'
            '"seconds":null}'
        )


def test_an_unknown_field_is_ignored_rather_than_rejected():
    """A newer plugin must not break an older reader."""
    record = json.loads(STREAM.splitlines()[0])
    record["something_new"] = 42
    assert plug.parse(json.dumps(record)).events[0].pass_name == "cfg"


def test_starts_and_ends_pair_into_runs():
    runs = plug.parse(STREAM).runs
    assert [r.name for r in runs] == ["cfg", "*warn_function_return", "expand"]
    assert runs[0].seconds == 0.000065


def test_a_pass_with_no_end_is_kept_because_it_means_the_compiler_died_there():
    """Dropping it would hide the one thing the stream is best placed to tell you."""
    truncated = "\n".join(STREAM.splitlines()[:5])
    runs = plug.parse(truncated).runs
    assert runs[-1].name == "expand"
    assert runs[-1].end is None
    assert runs[-1].seconds is None


def test_a_pass_that_changed_nothing_says_so():
    runs = {r.name: r for r in plug.parse(STREAM).runs}
    assert runs["*warn_function_return"].changed is False
    assert runs["cfg"].changed is True
    assert runs["expand"].changed is True


def test_size_follows_the_ir_across_expand():
    """Statements before expand, insns after, and never both at once."""
    events = plug.parse(STREAM).events
    assert events[1].size == 8
    assert events[5].size == 26
    for event in events:
        assert event.statements is None or event.insns is None


def test_properties_decode_to_names():
    stream = plug.parse(STREAM)
    after_cfg = stream.events[1].property_names
    assert "cfg" in after_cfg
    assert "rtl" not in after_cfg
    assert "rtl" in stream.events[5].property_names


def test_an_unknown_property_bit_is_shown_rather_than_dropped():
    """A GCC that adds a property should produce a visible question, not silence."""
    assert plug.property_names(1 << 30) == ["bit30"]


def test_no_properties_at_all_is_an_empty_list():
    assert plug.property_names(None) == []


def test_functions_come_out_in_the_order_they_appear():
    assert plug.parse(STREAM).functions == ["f"]


def test_the_property_table_matches_the_pinned_gcc_header():
    """The one duplication in `plug.py`, held honest here.

    `PROPERTIES` restates bit values from `gcc/tree-pass.h`. That is exactly the kind of
    copy that rots, so it is compared against the header in the pinned tree, in both
    directions: a bit we invented and a bit GCC added both fail.
    """
    if not TREE_PASS_H.exists():
        pytest.skip("vendor/gcc is not checked out, try just gcc-src")

    pattern = re.compile(r"^#define\s+PROP_(\w+)\s+\(1 << (\d+)\)", re.MULTILINE)
    from_gcc = {
        name: 1 << int(shift)
        for name, shift in pattern.findall(TREE_PASS_H.read_text(encoding="utf-8"))
    }
    assert from_gcc, "no PROP_ bits found, has tree-pass.h changed shape?"
    assert plug.PROPERTIES == from_gcc


def test_the_makefile_asks_for_the_homebrew_prefix_rather_than_naming_one():
    """Intel Homebrew installs under /usr/local and Apple silicon under /opt/homebrew.

    GitHub retired its Intel macOS runners, so the plugin workflow can only build the
    arm64 half. The only thing that actually differs between the two is the prefix, and
    the way to be right on a machine CI cannot reach is to ask rather than to guess. This
    is the cheap standing check that nobody replaces the question with an answer.
    """
    makefile = (GXPLUG / "Makefile").read_text(encoding="utf-8")
    assert "brew --prefix" in makefile
    assert "/opt/homebrew" not in makefile
    assert "/usr/local" not in makefile


# --- the tests that need a compiler ---------------------------------------------------

needs_plugin_gcc = pytest.mark.needs_gcc_plugin


@pytest.fixture(scope="module")
def built_plugin(gcc_plugin) -> Path:
    """Build the plugin once for every test that needs it."""
    # The developer's environment is left intact on purpose. An inherited CPPFLAGS
    # pointing at another toolchain's headers is a real failure mode, and one the Makefile
    # is written to survive, so building under it is the more honest test.
    #
    # The output is captured so a passing run stays quiet, and printed in full when the
    # build fails. `check=True` on its own reports an exit status and throws away the
    # compiler error that explains it, which turns a one line diagnosis into a round trip
    # through CI.
    built = subprocess.run(
        ["make", "-C", str(GXPLUG), f"GCC={gcc_plugin}"], capture_output=True, text=True
    )
    if built.returncode != 0:
        pytest.fail(f"building gxplug failed\n{built.stdout}\n{built.stderr}")
    return GXPLUG / "gxplug.so"


@needs_plugin_gcc
def test_the_plugin_builds(built_plugin):
    assert built_plugin.exists()


@needs_plugin_gcc
def test_the_plugin_does_not_change_the_generated_code(built_plugin, gcc_plugin, tmp_path):
    """The guarantee the whole design rests on.

    `gxplug never changes what GCC compiles`, from 03-architecture.md. Compile the same
    program twice, with and without, and require the assembly to match byte for byte.
    """
    gcc = gcc_plugin
    source = tmp_path / "t.c"
    source.write_text(
        "int f(int n){int s=0;for(int i=0;i<n;i++)s+=i*i;return s;}\n"
        "double g(double *p,int n){double t=0;for(int i=0;i<n;i++)t+=p[i]*p[i];return t;}\n"
    )
    without = tmp_path / "without.s"
    with_plugin = tmp_path / "with.s"
    events = tmp_path / "events.ndjson"

    subprocess.run([gcc, "-O2", "-S", str(source), "-o", str(without)], check=True)
    subprocess.run(
        [
            gcc,
            "-O2",
            "-S",
            f"-fplugin={built_plugin}",
            f"-fplugin-arg-gxplug-out={events}",
            str(source),
            "-o",
            str(with_plugin),
        ],
        check=True,
    )

    assert without.read_bytes() == with_plugin.read_bytes()
    assert events.stat().st_size > 0


@needs_plugin_gcc
def test_a_real_stream_parses_and_covers_both_irs(built_plugin, gcc_plugin, tmp_path):
    """Not just valid JSON: the run has to reach RTL and report both kinds of size."""
    gcc = gcc_plugin
    source = tmp_path / "t.c"
    source.write_text("int f(int n){int s=0;for(int i=0;i<n;i++)s+=i*i;return s;}\n")
    events = tmp_path / "events.ndjson"
    subprocess.run(
        [
            gcc,
            "-O2",
            "-S",
            f"-fplugin={built_plugin}",
            f"-fplugin-arg-gxplug-out={events}",
            str(source),
            "-o",
            str(tmp_path / "t.s"),
        ],
        check=True,
    )

    stream = plug.load(events)
    assert len(stream.events) > 100
    assert stream.functions == ["f"]

    names = [r.name for r in stream.runs]
    assert "expand" in names, "the run never reached RTL"

    assert any(e.statements is not None for e in stream.events), "no GIMPLE was measured"
    assert any(e.insns is not None for e in stream.events), "no RTL was measured"

    # The honest ratio T04 is about: many passes run, few leave a visible mark.
    runs = stream.runs
    changed = [r for r in runs if r.changed]
    assert 0 < len(changed) < len(runs)


@needs_plugin_gcc
def test_every_start_is_closed(built_plugin, gcc_plugin, tmp_path):
    """A dangling start would mean the plugin lost track, or the compiler died."""
    gcc = gcc_plugin
    source = tmp_path / "t.c"
    source.write_text("int f(int n){return n*n;}\nint g(void){return f(7);}\n")
    events = tmp_path / "events.ndjson"
    subprocess.run(
        [
            gcc,
            "-O2",
            "-S",
            f"-fplugin={built_plugin}",
            f"-fplugin-arg-gxplug-out={events}",
            str(source),
            "-o",
            str(tmp_path / "t.s"),
        ],
        check=True,
    )
    stream = plug.load(events)
    assert all(run.end is not None for run in stream.runs)
    starts = [e for e in stream.events if e.event == "pass-start"]
    ends = [e for e in stream.events if e.event == "pass-end"]
    assert len(starts) == len(ends)


@needs_plugin_gcc
def test_an_unknown_argument_is_an_error_and_not_a_shrug(built_plugin, gcc_plugin, tmp_path):
    """A typo in -fplugin-arg- should fail loudly rather than silently do nothing."""
    gcc = gcc_plugin
    source = tmp_path / "t.c"
    source.write_text("int main(void){return 0;}\n")
    result = subprocess.run(
        [
            gcc,
            "-O2",
            "-S",
            f"-fplugin={built_plugin}",
            "-fplugin-arg-gxplug-outt=/dev/null",
            str(source),
            "-o",
            str(tmp_path / "t.s"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "unknown argument" in result.stderr


@needs_plugin_gcc
def test_the_makefile_check_target_passes(built_plugin, gcc_plugin):
    """The same guarantee, from the entry point a reader would actually type."""
    gcc = gcc_plugin
    result = subprocess.run(
        ["make", "-C", str(GXPLUG), "check", f"GCC={gcc}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "assembly identical" in result.stdout


# --- the examples, and the recording of them ------------------------------------------

EXAMPLES = GXPLUG / "examples"
SESSION = plug.load_session()


def test_the_five_examples_are_all_there():
    """B05 names five plugins and the Makefile builds whatever is in this directory.

    A source file added here without a section in the lesson is a plugin nobody reads, and
    one removed is a lesson that talks about a file that is gone.
    """
    found = sorted(path.stem for path in EXAMPLES.glob("*.cc"))
    assert found == ["countpass", "gate", "hello", "nolicence", "wrongver"]


@pytest.mark.parametrize("name", ["hello", "countpass", "gate", "wrongver"])
def test_every_example_that_is_meant_to_load_says_it_is_GPL_compatible(name):
    """Four of the five carry the symbol. The fifth is the lesson about the symbol."""
    text = (EXAMPLES / f"{name}.cc").read_text(encoding="utf-8")
    assert "int plugin_is_GPL_compatible;" in text


def test_the_refused_example_really_is_missing_the_symbol():
    text = (EXAMPLES / "nolicence.cc").read_text(encoding="utf-8")
    # The symbol appears once, inside the comment that says it is the missing line.
    assert text.count("int plugin_is_GPL_compatible;") == 1
    assert "int plugin_is_GPL_compatible;  */" in text


def test_the_recorded_session_is_the_one_the_lesson_describes():
    assert SESSION.compiler.startswith("gcc-16")
    assert "16.2.0" in SESSION.compiler
    assert len(SESSION.invocations) == 11
    assert SESSION.stream.runs


def test_a_recording_that_is_not_there_says_which_ones_are():
    with pytest.raises(plug.PlugError, match="no recording called 'nope'"):
        SESSION["nope"]


def test_a_missing_corpus_names_the_recorder(tmp_path):
    with pytest.raises(plug.PlugError, match="record.py"):
        plug.load_session(root=tmp_path)


def test_the_passive_examples_left_the_assembly_alone():
    """The same promise gxplug makes, checked for the two examples that also make it."""
    plain = SESSION["plain"].asm
    assert plain
    for name in ("hello", "countpass"):
        assert SESSION[name].asm == plain, name


def test_the_gate_example_did_not():
    """And the one that is not passive, because a demonstration that changes nothing is not one."""
    assert SESSION["gated"].asm != SESSION["plain"].asm
    assert len(SESSION.diff("plain", "gated")) > 10


def test_diffing_a_recording_with_no_assembly_says_so():
    with pytest.raises(plug.PlugError, match="did not keep its assembly"):
        SESSION.diff("plain", "badarg")


@pytest.mark.parametrize("name", ["nolicence", "wrongver", "missing", "badarg"])
def test_every_refusal_is_a_failed_compilation_and_not_a_warning(name):
    """A plugin that cannot load stops the build. Nothing here is skipped with a warning."""
    one = SESSION[name]
    assert one.refused
    assert one.said


def test_the_recorded_corpus_carries_nobody_s_home_directory():
    """Scrubbing, checked. A corpus is read by strangers in a notebook."""
    text = (REPO / "corpora" / "plug" / "b05.json").read_text(encoding="utf-8")
    assert "/Users/" not in text
    assert "/home/" not in text
    assert "/opt/homebrew" not in text


@needs_plugin_gcc
def test_the_examples_do_what_the_lesson_says_they_do(gcc_plugin):
    """The Makefile target, from the entry point a reader would type.

    Five plugins built and loaded: two that change nothing, one that changes the assembly
    on purpose, and two that are refused. If this fails, B05 is describing plugins that no
    longer work on this compiler.
    """
    result = subprocess.run(
        ["make", "-C", str(GXPLUG), "examples-check", f"GCC={gcc_plugin}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "gate switched a pass off and the assembly moved" in result.stdout


# ---------------------------------------------------------------------------
# The boss fight.
#
# Three of B05's eight answers are computed out of the corpus rather than written down, so
# they cannot drift away from the compiler the lesson was recorded against. What can drift
# is the marking: an `accepts` list that no longer covers the phrasing the notebook uses is
# a question nobody can get right, and there is no other check for that.

GRADE = REPO / "lessons" / "b05-the-plugin" / "grade.py"


def _grader():
    """B05's grade.py, loaded by path.

    Every lesson has a module called `grade`, so importing by name would hand back whichever
    one got there first.
    """
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("grade_b05", GRADE)
    module = importlib.util.module_from_spec(spec)
    # Registered before it is executed, not after. @dataclass looks its own class up in
    # sys.modules while the module body is still running, and on 3.14 a module that is not
    # there yet fails with an AttributeError about NoneType that names no cause.
    sys.modules["grade_b05"] = module
    spec.loader.exec_module(module)
    return module


def test_the_grader_computes_its_numbers_out_of_the_corpus():
    """Not written down. Five version fields and the changed-run count, both derived."""
    asked = _grader().questions()
    assert len(asked) == 8
    assert asked[1].answer == "5"

    runs = SESSION.stream.runs
    assert asked[7].answer == str(sum(1 for one in runs if one.changed))


def test_the_grader_marks_the_answers_the_lesson_leads_you_to():
    module = _grader()
    said = [
        "plugin_is_GPL_compatible",
        "5",
        "configuration_arguments",
        "gcc_assert",
        "cddce",
        "every instance",
        "todo flags",
        module.questions()[7].answer,
    ]
    for question, answer in zip(module.questions(), said, strict=True):
        assert module.marks(question, answer), question.ask


def test_the_grader_is_lenient_about_wording_and_strict_about_the_answer():
    module = _grader()
    asked = module.questions()
    assert module.marks(asked[0], "  The plugin_is_GPL_compatible;  ")
    assert module.marks(asked[2], "the configure command line")
    assert module.marks(asked[4], '"cddce"')
    assert not module.marks(asked[4], "cddce1")
    assert not module.marks(asked[5], "the first instance")
    assert not module.marks(asked[7], "247")
