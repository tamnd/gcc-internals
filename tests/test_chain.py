"""Reading `-###`, which is the driver telling you what it would run.

The parser is small and the interesting part is what it refuses to guess at. A quoted
argument has to come back without its quotes, a `COLLECT_GCC_OPTIONS` line has to attach to
the step below it and not the step above it, and asking for a program the chain does not
run has to raise rather than hand back nothing.
"""

from __future__ import annotations

import shutil

import pytest

import gxray
from gxray.chain import Chain, Step, parse
from gxray.driver import BackendError

#: A real `-###` transcript, trimmed to the lines that matter. Two steps, so it exercises
#: the case where the options line changes between them.
TRANSCRIPT = """Using built-in specs.
COLLECT_GCC=gcc-16
Target: aarch64-apple-darwin24
Configured with: ../configure --prefix=/opt/homebrew/opt/gcc --disable-nls
Thread model: posix
Supported LTO compression algorithms: zlib zstd
gcc version 16.2.0 (Homebrew GCC 16.2.0)
COLLECT_GCC_OPTIONS='-O2' '-c' '-mcpu=apple-m1'
 /opt/homebrew/libexec/gcc/aarch64-apple-darwin24/16/cc1 l1.c "-mcpu=apple-m1" -O2 -o /tmp/cc1.s
COLLECT_GCC_OPTIONS='-O2' '-c'
 as -arch arm64 "-mmacosx-version-min=15.0" -o l1.o /tmp/cc1.s
COMPILER_PATH=/opt/homebrew/libexec/gcc/aarch64-apple-darwin24/16/
LIBRARY_PATH=/opt/homebrew/lib/gcc/current/
"""


def test_the_header_says_which_gcc_this_is():
    found = parse(TRANSCRIPT)
    assert found.target == "aarch64-apple-darwin24"
    assert found.version == "16.2.0 (Homebrew GCC 16.2.0)"
    assert found.thread_model == "posix"
    assert "--disable-nls" in found.configured


def test_the_steps_are_the_lines_that_start_with_one_space():
    """Which is the whole grammar. Everything the driver says about itself starts at zero."""
    assert parse(TRANSCRIPT).names == ["cc1", "as"]


def test_a_quoted_argument_comes_back_without_its_quotes():
    """`"-mcpu=apple-m1"` and `-mcpu=apple-m1` are the same flag, and a reader types the
    second one, so the parser has to produce the second one."""
    argv = parse(TRANSCRIPT).named("cc1").argv
    assert "-mcpu=apple-m1" in argv
    assert '"-mcpu=apple-m1"' not in argv


def test_the_options_line_belongs_to_the_step_below_it():
    """The driver prints its own view of the command line and then the program it built
    from it, in that order, and getting this backwards attributes `-c` to nothing."""
    found = parse(TRANSCRIPT)
    assert "-mcpu=apple-m1" in found.named("cc1").options
    assert "-mcpu=apple-m1" not in found.named("as").options


def test_a_step_knows_its_own_name_without_the_path():
    step = parse(TRANSCRIPT)[0]
    assert step.program.endswith("/cc1")
    assert step.name == "cc1"


def test_a_step_says_what_it_is_for():
    assert "C compiler" in parse(TRANSCRIPT).named("cc1").role
    assert "binutils" in parse(TRANSCRIPT).named("as").role


def test_a_program_nobody_has_a_label_for_says_nothing_rather_than_guessing():
    assert Step("/usr/bin/something-new").role == ""


def test_asking_for_a_step_that_is_not_there_raises_and_says_what_is():
    """A chain with no linker in it is a real answer, so this cannot return None and let a
    lesson print something confident about a program that never ran."""
    with pytest.raises(KeyError, match="cc1, as"):
        parse(TRANSCRIPT).named("collect2")


def test_a_chain_can_be_asked_for_a_step_by_its_full_path():
    found = parse(TRANSCRIPT)
    assert found.named("/opt/homebrew/libexec/gcc/aarch64-apple-darwin24/16/cc1").name == "cc1"


def test_a_chain_is_a_sequence():
    found = parse(TRANSCRIPT)
    assert len(found) == 2
    assert [step.name for step in found] == ["cc1", "as"]
    assert found[1].name == "as"


def test_the_raw_output_is_kept():
    """Every parser here keeps its input, so a lesson can show the thing and then the
    reading of it rather than asking anyone to take the reading on trust."""
    assert parse(TRANSCRIPT).text == TRANSCRIPT


def test_a_transcript_with_nothing_in_it_parses_to_an_empty_chain():
    found = parse("")
    assert len(found) == 0
    assert "nothing" in str(found)


def test_one_step_is_not_described_as_one_steps():
    assert str(Chain(steps=(Step("cc1"),), target="x")).startswith("1 step on")


# The recorded entry, which is what the lesson runs against and what CI can check with no
# compiler anywhere. The shape of these is the lesson's whole argument.

CORPUS = "t01-driver"


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ("-O2 -E", ["cc1"]),
        ("-O2 -S", ["cc1"]),
        ("-O2 -c", ["cc1", "as"]),
        ("-O2", ["cc1", "as", "collect2"]),
    ],
)
def test_the_recorded_chain_grows_a_step_at_a_time(flags, expected):
    """Stopping earlier runs fewer programs, and that is the entire point of T01."""
    assert gxray.corpus(CORPUS).chain("", *flags.split()).names == expected


def test_the_optimization_level_is_one_argument_to_cc1_and_reaches_nothing_else():
    """The claim the lesson makes about where `-O2` ends up, checked here as well because a
    notebook cell proving it is not a regression test."""
    backend = gxray.corpus(CORPUS)
    at_two = backend.chain("", "-O2", "-c")
    at_zero = backend.chain("", "-O0", "-c")

    assert "-O2" in at_two.named("cc1").argv
    assert "-O0" in at_zero.named("cc1").argv
    assert not [a for a in at_two.named("as").argv if a.startswith("-O")]


def test_asking_the_corpus_for_a_chain_nobody_recorded_says_which_ones_exist():
    with pytest.raises(BackendError, match="-O2 -c"):
        gxray.corpus(CORPUS).chain("", "-O3", "-c")


@pytest.mark.needs_gcc
def test_a_local_gcc_agrees_with_the_recording_about_how_many_programs_run():
    """Not that it agrees about the arguments. Those are full of paths into whichever build
    of GCC is on this machine, and a test that compared them would only ever pass here."""
    if shutil.which("gcc-16") is None:
        pytest.skip("no gcc-16")
    live = gxray.local("gcc-16").chain(gxray.L1, "-O2", "-c", filename="l1.c")
    assert live.names[0] == "cc1"
    assert len(live) >= 2
