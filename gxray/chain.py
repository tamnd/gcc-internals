"""What the driver would run, read out of `-###`.

`gcc` is not a compiler. It is a program that reads your command line, decides which other
programs have to run and in what order, builds a command line for each of them, and runs
them. The compiler proper is `cc1`, it is not on your PATH, and most people who have used
GCC for years have never seen its name.

`-###` is the driver saying what it would do without doing any of it. That output is a
fixed shape and this parses it:

    chain = gxray.local("gcc-16").chain(gxray.L1, "-O2", "-c")

    len(chain)                 # 2, because -c stops before the link
    [step.name for step in chain]   # ['cc1', 'as']
    chain.named("cc1").argv    # everything the driver decided cc1 should be told

There is a related flag, `-v`, which prints the same thing and then actually runs it. `-###`
is the one to teach with, because it is safe to run on anything and it quotes its arguments,
so what it prints can be parsed rather than guessed at.

The chain is a property of how this GCC was configured and what it targets, not of GCC. The
same source and the same flags produce a two step chain on one machine and a three step
chain on another, with different programs in it. That is why `Chain` carries the target and
the configure line, and why a lesson showing one always says which.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

#: What each program in a chain is for, by the name the driver invokes it under. The driver
#: does not label these, and a reader looking at four absolute paths under `libexec` has no
#: way to tell which one is the compiler, so the lesson needs the labels from somewhere and
#: this is the somewhere.
ROLES = {
    "cc1": "the C compiler, the thing people mean when they say GCC",
    "cc1plus": "the C++ compiler",
    "cc1obj": "the Objective C compiler",
    "f951": "the Fortran compiler",
    "d21": "the D compiler",
    "go1": "the Go compiler",
    "gnat1": "the Ada compiler",
    "lto1": "the compiler again, on the IR saved in the object files",
    "cpp": "the preprocessor, run on its own",
    "as": "the assembler, which is binutils and not GCC",
    "gas": "the assembler, which is binutils and not GCC",
    "collect2": "a wrapper around the linker that also arranges for static constructors",
    "ld": "the linker, which is binutils and not GCC",
    "ld.gold": "the linker",
    "ld.lld": "the linker",
    "lto-wrapper": "the driver again, in charge of the link time optimization step",
}


@dataclass(frozen=True)
class Step:
    """One program the driver would run, and everything it would be told."""

    program: str
    argv: tuple[str, ...] = ()

    #: The `COLLECT_GCC_OPTIONS` line in force when the driver printed this step. It is the
    #: driver's own view of your command line after it has finished adding to it, which is
    #: not the same list as `argv` and is interesting precisely because of the difference.
    options: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        """The program's own name, without the path it was found at.

        Worth separating, because the path is thirty characters of build prefix that differ
        on every machine and the name is the part that means something.
        """
        return self.program.rsplit("/", 1)[-1]

    @property
    def role(self) -> str:
        """What this program is for, in a sentence, or an empty string if we do not know."""
        return ROLES.get(self.name, "")

    def __str__(self) -> str:
        return f"{self.name} ({len(self.argv)} arguments)"


@dataclass(frozen=True)
class Chain:
    """Everything `-###` said, parsed.

    The header fields are kept rather than dropped because a chain without them is not a
    fact about anything. Two GCCs of the same version, configured differently, run different
    programs, and a reader comparing what they see against what a lesson shows needs to be
    able to tell which difference they are looking at.
    """

    steps: tuple[Step, ...] = ()
    target: str = ""
    version: str = ""
    configured: str = ""
    thread_model: str = ""

    #: The raw output, so a lesson can show the thing itself rather than only our reading
    #: of it. Every parser in this project keeps its input for the same reason.
    text: str = field(default="", repr=False)

    def __len__(self) -> int:
        return len(self.steps)

    def __iter__(self):
        return iter(self.steps)

    def __getitem__(self, i: int) -> Step:
        return self.steps[i]

    @property
    def names(self) -> list[str]:
        return [step.name for step in self.steps]

    def named(self, name: str) -> Step:
        """The step run under this name. Raises rather than returning nothing.

        A chain that does not contain `cc1` is a real answer to some questions, so asking
        for a step that is not there has to be loud. `-E` alone runs one program and it is
        not the assembler, and a lesson that quietly got `None` back would print something
        confident and wrong.
        """
        for step in self.steps:
            if name in (step.name, step.program):
                return step
            # `-###` prints the program the way the driver found it, which for cc1 is an
            # absolute path under libexec and for as is often the bare word. Matching on
            # either end means a caller can ask for "cc1" without knowing which it will be.
            if step.program.endswith(f"/{name}"):
                return step
        have = ", ".join(self.names) or "nothing"
        raise KeyError(f"no step named {name!r} in this chain. It runs: {have}")

    def __str__(self) -> str:
        where = self.target or "an unknown target"
        steps = "step" if len(self) == 1 else "steps"
        return f"{len(self)} {steps} on {where}: {', '.join(self.names) or 'nothing'}"


#: Header lines, in the order the driver prints them, and the field each one fills. The
#: driver prints these whether or not `-###` was asked for, which is why they are recognised
#: rather than skipped: the first four lines of any `-v` transcript are here.
HEADERS = {
    "Target: ": "target",
    "gcc version ": "version",
    "Configured with: ": "configured",
    "Thread model: ": "thread_model",
}


def parse(text: str) -> Chain:
    """Read `-###` output, or the same lines out of a `-v` transcript.

    A command is a line that begins with exactly one space. Everything the driver prints
    about itself begins at column zero, so that single space is the whole grammar, and it
    holds for `-v` output too, which means a transcript somebody pasted from a bug report
    parses the same way.

    Arguments come back through `shlex` rather than `split`, because `-###` quotes any
    argument it thinks needs it. Splitting on whitespace turns `"-mcpu=apple-m1"` into an
    argument with quotation marks welded to it, which then does not compare equal to
    anything a reader would type.
    """
    steps: list[Step] = []
    fields: dict[str, str] = {}
    options: tuple[str, ...] = ()

    for line in text.splitlines():
        if line.startswith(" ") and line.strip():
            argv = shlex.split(line)
            steps.append(Step(program=argv[0], argv=tuple(argv[1:]), options=options))
            continue
        if line.startswith("COLLECT_GCC_OPTIONS="):
            options = tuple(shlex.split(line.split("=", 1)[1]))
            continue
        for prefix, name in HEADERS.items():
            if line.startswith(prefix) and name not in fields:
                fields[name] = line[len(prefix) :].strip()
                break

    return Chain(steps=tuple(steps), text=text, **fields)
