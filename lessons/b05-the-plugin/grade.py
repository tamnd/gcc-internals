"""The B05 boss fight: eight questions about loading, events, passes and gates.

    python lessons/b05-the-plugin/grade.py
    python lessons/b05-the-plugin/grade.py --says 'int plugin_is_GPL_compatible; 5; ...'

Answers are separated by semicolons, matching B01 through B04.

Three of the eight are computed rather than typed in: the number of fields the default
version check compares is counted out of the excerpt of `plugin.cc` the notebook printed,
and the two numbers at the end come out of the same recorded gxplug stream. So an answer
here cannot drift away from the compiler the lesson was written against.

The three worth thinking about are the failures. Two of them are mistakes GCC tells you
about at once, in a way that names the cause, and one of them is a mistake GCC cannot tell
you about at all, which is why it is the one that costs an afternoon.

Marking is lenient about spelling and strict about the answer. Whitespace, case, a trailing
period or semicolon, a leading `a `, `the ` or `-` and the order of a comma separated list
are all ignored.
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gxray import plug, source  # noqa: E402

#: Where the answer and the explanation sit, under the number the question was asked with.
INDENT = " " * 7


def tidy(said: str) -> str:
    """One answer, with everything that is not the answer taken off it."""
    out = re.sub(r"\s+", " ", said.strip().lower()).strip(" .!;")
    for prefix in ("a ", "an ", "the ", "-", "it is ", "it ", "gcc "):
        out = out.removeprefix(prefix)
    return out.strip()


def listed(said: str) -> str:
    """A comma separated answer, sorted, so the order it was typed in does not matter."""
    return ",".join(sorted(part for part in re.split(r"[,\s]+", tidy(said)) if part))


def paragraph(text: str, indent: str = INDENT, first: str | None = None) -> str:
    """One long line of prose, wrapped to fit a terminal and indented under its question."""
    return textwrap.fill(
        " ".join(text.split()),
        width=88,
        initial_indent=indent if first is None else first,
        subsequent_indent=indent,
    )


@dataclass(frozen=True)
class Question:
    #: The question, as one unwrapped paragraph. Wrapping happens when it is printed.
    ask: str

    #: The right answer, computed from the recording where it can be.
    answer: str

    #: What the reader should take away when they got it wrong, unwrapped.
    about: str

    #: How to compare. `list` ignores the order of a comma separated answer, `near` allows a
    #: factor of two on a number, and the default is exact once both sides have been tidied.
    compare: str = "exact"

    #: A nudge, printed only with --hints.
    hint: str = ""

    #: Other wordings that are the same answer.
    accepts: tuple[str, ...] = field(default_factory=tuple)

    def marks(self, said: str) -> bool:
        if self.compare == "list":
            return listed(said) == listed(self.answer)
        got = tidy(said)
        return got == tidy(self.answer) or got in tuple(tidy(a) for a in self.accepts)

    def first(self) -> str:
        """The opening clause, for the one line summary at the end."""
        words = self.ask.split()
        short = " ".join(words[:11])
        return short + (" ..." if len(words) > 11 else "")


def questions() -> list[Question]:
    cuts = source.load_extract("b05")
    fields = sum(1 for line in cuts["version"].lines if "strcmp (" in line)

    session = plug.load_session()
    runs = session.stream.runs
    marked = sum(1 for one in runs if one.changed)

    return [
        Question(
            ask=(
                "GCC looks one symbol up by name before it calls anything in your plugin, never"
                " reads it, and refuses to compile at all without it. Name the symbol."
            ),
            answer="plugin_is_GPL_compatible",
            accepts=(
                "int plugin_is_gpl_compatible",
                "int plugin_is_gpl_compatible;",
                "plugin_is_gpl_compatible;",
            ),
            about=(
                "`int plugin_is_GPL_compatible;`, at file scope. The check is a `dlsym` for that"
                " name and nothing more, so the type does not matter and the value is never"
                " looked at. What does matter is that it fails with `fatal_error` rather than a"
                " warning, before your `plugin_init` runs, which is why a plugin missing it"
                " prints nothing of its own before the compilation stops."
            ),
            hint="it is a definition, not a function, and its value is never used",
        ),
        Question(
            ask=(
                "How many fields does plugin_default_version_check compare before it agrees that"
                " a plugin was built for this compiler? A number."
            ),
            answer=str(fields),
            accepts=(f"{fields} fields", "five"),
            about=(
                f"{fields}. The version, the datestamp, the development phase, the revision, and"
                " the entire configure command line. People expect the first and are surprised"
                " by the last, which is the one that actually bites: it means a plugin is tied"
                " to a build and not to a release."
            ),
            hint="more than one, and the last one is a whole command line",
        ),
        Question(
            ask=(
                "Two machines have GCC 16.2.0 from the same tarball. One was configured with"
                " --enable-checking=release and the other without. A plugin built on the first"
                " is refused by the second. Name the field that refused it."
            ),
            answer="configuration_arguments",
            accepts=(
                "configuration arguments",
                "configure arguments",
                "configure line",
                "configuration_arguments",
                "the configure command line",
                "configure command line",
            ),
            about=(
                "`configuration_arguments`, compared as a string. It is there because"
                " `--enable-checking` changes struct layouts and `--enable-languages` changes"
                " which trees exist, so two builds of one release genuinely have different"
                " plugin ABIs. The string comparison is crude and it is the only thing between"
                " you and a crash with no diagnostic. It is also why no plugin can be shipped as"
                " a binary."
            ),
            hint="it is the fifth of the five, and it is not a version number",
        ),
        Question(
            ask=(
                "You register your pass with register_callback (name,"
                " PLUGIN_PASS_MANAGER_SETUP, my_setup_func, &pass_info), copying the shape of"
                " every other registration you have written. What does GCC do?"
            ),
            answer="asserts",
            accepts=(
                "assert",
                "asserts",
                "aborts",
                "crashes",
                "internal compiler error",
                "ice",
                "gcc_assert",
                "gcc_assert fires",
                "assertion failure",
                "trips an assertion",
            ),
            about=(
                "It trips `gcc_assert (!callback)` and dies. PLUGIN_PASS_MANAGER_SETUP is a"
                " pseudo-event: it is handled inside `register_callback` and never fired, so"
                " there is nothing for a callback to be called from. The fourth argument is not"
                " user data being kept for later, it is a `register_pass_info *` read on the"
                " spot. Three of the twenty six names in plugin.def work this way, and none of"
                " them looks any different from the ones that do not."
            ),
            hint="the third argument has nowhere to be called from",
        ),
        Question(
            ask=(
                "You want to switch off the pass whose dump you get with -fdump-tree-cddce1."
                " What name do you compare current_pass->name against?"
            ),
            answer="cddce",
            accepts=("cddce", '"cddce"'),
            about=(
                "`cddce`. The trailing digit in a dump name is the instance number the pass"
                " manager assigned, not part of the pass name, because the same pass is in the"
                " pipeline more than once. Comparing against `cddce1` matches nothing, and"
                " nothing is exactly what it reports: no error, no warning, and a compilation"
                " that looks like a successful experiment. This is the same distinction that"
                " `ref_pass_instance_number` exists for, seen from the other side."
            ),
            hint="the pass is in the pipeline more than once",
        ),
        Question(
            ask=(
                "In a register_pass_info you set reference_pass_name to ssa and"
                " ref_pass_instance_number to 0. What does the 0 mean? A few words."
            ),
            answer="every instance",
            accepts=(
                "every instance",
                "all instances",
                "every run of that pass",
                "all of them",
                "every occurrence",
                "each instance",
            ),
            about=(
                "Every instance of the reference pass, so your pass is inserted once for each"
                " time `ssa` appears in the pipeline. 1 does not mean the first one it finds: it"
                " means the instance marked `TODO_mark_first_instance`, which is a different"
                " thing from `static_pass_number == 1`. Getting this wrong gives you a pass that"
                " runs more often than you meant, which usually shows up as duplicated output"
                " rather than as an error."
            ),
            hint="it is not a count and it is not an index",
        ),
        Question(
            ask=(
                "Your GIMPLE pass deletes a statement, returns 0 from execute, and works. Two"
                " passes later the compilation dies inside code you did not write. What did you"
                " leave out of the pass? Name the thing, not the value."
            ),
            answer="todo flags",
            accepts=(
                "todo flags",
                "todo",
                "todo_flags_finish",
                "todo mask",
                "return todo flags",
                "a todo mask",
                "the todo return value",
            ),
            about=(
                "The TODO mask. What `execute` returns tells the pass manager what needs putting"
                " back together: the CFG cleaned up, SSA renamed, the function verified."
                " Returning 0 says nothing needs doing, so the pass manager believes the IR is"
                " consistent when it is not, and the failure lands in whichever later pass first"
                " trips over it. It is the most expensive mistake a first plugin can make"
                " because the backtrace points at innocent code. A pass that only reads can"
                " honestly return 0, which is why the one in this lesson does."
            ),
            hint="the pass manager is waiting to be told something, and 0 tells it nothing",
        ),
        Question(
            ask=(
                f"gxplug watched {len(runs)} pass runs on a nine line program. Roughly how many"
                " of them changed the statement count, the insn count, the block count or the"
                " property bits? A number."
            ),
            answer=str(marked),
            compare="near",
            about=(
                f"{marked} of {len(runs)}, about {100 * marked // len(runs)}%. Read it carefully"
                " in both directions. It is not that the other passes did nothing: a pass that"
                " rewrites an expression in place changes none of those four counts and did real"
                " work. What the number is good for is the honest version of the sentence people"
                " say about GCC having hundreds of passes. On a program this small most of them"
                " look at the function and leave, and the ones that move the counts are"
                " concentrated around lowering, SSA construction and expand."
            ),
            hint="most people guess most of them",
        ),
    ]


def marks(question: Question, said: str) -> bool:
    """One answer, marked. `near` is the numeric one, where a factor of two either way is fine."""
    if question.compare != "near":
        return question.marks(said)
    found = re.search(r"-?\d[\d,]*", said.replace(" ", ""))
    if not found:
        return False
    got = int(found.group(0).replace(",", ""))
    want = int(question.answer)
    return want // 2 <= got <= want * 2


def put(n: int, question: Question, hints: bool) -> str:
    """Ask one question, and read the answer if there is somebody there to give one."""
    print()
    print(paragraph(question.ask, indent="   ", first=f"{n}. "))
    if hints and question.hint:
        print(f"   ({question.hint})")
    if not sys.stdin.isatty():
        return ""
    return input("   > ").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--says", help="the answers, semicolon separated, in the order asked")
    parser.add_argument("--hints", action="store_true", help="print a nudge with each question")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    asked = questions()
    typed = [part.strip() for part in args.says.split(";")] if args.says else []

    session = plug.load_session()
    print(f"{len(session.invocations)} recorded compilations by {session.compiler}.")
    print(f"{len(asked)} questions about writing the plugins that did it. Semicolons between.")

    answers = []
    for n, question in enumerate(asked, start=1):
        if typed:
            answers.append(typed[n - 1] if n <= len(typed) else "")
        else:
            answers.append(put(n, question, args.hints))

    print()
    scored = 0
    for question, said in zip(asked, answers, strict=True):
        right = marks(question, said)
        scored += right
        print(f"{'right' if right else 'wrong':<7}{question.first()}")
        print(f"{INDENT}{question.answer}")
        if not right:
            print(f"{INDENT}you said: {said or '(nothing)'}")
            print(paragraph(question.about))

    print(f"\n{scored} of {len(asked)}.")
    if scored == len(asked):
        print("You can write a plugin, say why one was refused, put a pass of your own in the")
        print("pipeline at a place you chose, switch one of GCC's off, and explain why none of")
        print("it will survive the next release without being rebuilt.")
        print("That is M2. M3 next: the front end, starting before the parser.")
        return 0
    print("\nEverything except the reasoning questions is in the notebook. To reread:")
    print("    from gxray import plug, source")
    print("    session = plug.load_session()")
    print("    print(plug.body('countpass'))")
    print("    print(source.load_extract('b05')['version'].numbered())")
    print("    print(source.load_extract('b05')['pseudo'].numbered())")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
