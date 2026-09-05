"""A model of GCC's test harness, small enough to read and real enough to run.

The harness itself is fourteen thousand lines of Tcl that needs `expect`, a build tree and a
compiler that has just been built. None of those exist in a notebook. What does exist is the
part that decides things: read the directives out of a test's comments, compile once, strike
each expected message off the output, and fail on whatever is left over. That part is a page
of Python, and once it exists a reader can run a real GCC test against a real GCC and watch
the harness reach the same verdict the real harness reaches.

    from gxray import dejagnu
    t = dejagnu.read_test(text, path="gcc.dg/c99-flex-array-1.c")
    t.options                      # ['-std=iso9899:1999', '-pedantic-errors']
    for one in dejagnu.check(t, stderr):
        print(one)

This is a model and the lesson says so more than once. It implements the seven directives a
reader meets first and the matching rule they all share. It does not implement selectors,
effective targets, multiline output, PCH, the cleanup procedures, or the two hundred lines of
`prune.exp`. Where it stops, it stops loudly: an unknown directive is kept and reported as
unhandled rather than ignored, because a model that quietly skips the directive that decides
the test would produce a confident wrong answer.

`BP-TESTSUITE` is the specification. Section 3.2 is `check` below, section 3.4 is
`torture_list`, and section 3.5 is `race`, which is the one worth running twice.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "corpora" / "testsuite" / "b04.json"

#: The directives that say something is expected in the output. `dg-bogus` is the odd one:
#: finding it is the failure, which is why it carries the same fields and the opposite verdict.
MESSAGE_KINDS = {
    "dg-error": "error",
    "dg-warning": "warning",
    "dg-message": "message",
    "dg-note": "note",
    "dg-bogus": "bogus",
}

#: What the model knows how to act on. Everything else is reported as unhandled.
KNOWN = set(MESSAGE_KINDS) | {
    "dg-do",
    "dg-options",
    "dg-additional-options",
    "dg-final",
    "dg-excess-errors",
    "dg-prune-output",
}

#: A GCC diagnostic under `-fdiagnostics-plain-output`, which is what every test is compiled
#: with. Without that flag this regular expression would also have to survive colour escapes,
#: the quoted source line and the caret, which is the whole reason the flag exists.
DIAGNOSTIC = re.compile(
    r"^(?P<file>[^\s:]+):(?P<line>\d+):(?:(?P<column>\d+):)?\s*"
    r"(?P<kind>error|warning|note|fatal error):\s*(?P<text>.*)$"
)

#: The subset of `prune.exp` this model implements, as a list rather than as a regexp soup.
#: The real thing has about forty of these (`gcc/testsuite/lib/prune.exp`), and the four here
#: are the ones that fire on the tests in this lesson's corpus.
PRUNED = (
    re.compile(r"^[^\n]*: In function [^\n]*$"),
    re.compile(r"^[^\n]*: At top level:[^\n]*$"),
    re.compile(r"^\s*\d+ errors?\.$"),
    re.compile(r"^Please submit a full bug report.*$"),
)

#: On every compilation the suite makes, from `TEST_ALWAYS_FLAGS` in `gcc/testsuite/lib/prune.exp`.
#: One flag, and it is the reason the regular expression above can be six fields long: it turns
#: off colour, the quoted source line, the caret, the option name in brackets and the URL.
ALWAYS = ("-fdiagnostics-plain-output",)

#: What `gcc.dg` compiles a test with when the test does not say. Set in `gcc.dg/dg.exp`, and it
#: is C90 with pedantic errors, which surprises everybody once.
DEFAULT_CFLAGS = ("-ansi", "-pedantic-errors")

#: The six sets from `gcc/testsuite/lib/gcc-dg.exp`. Copied rather than imported because a
#: notebook has no GCC tree, and pinned by a test that reads the tree when there is one.
TORTURE = (
    "-O0",
    "-O1",
    "-O2",
    "-O3 -fomit-frame-pointer -funroll-loops -fpeel-loops -ftracer -finline-functions",
    "-O3 -g",
    "-Os",
)

#: What the harness takes out when the source has no loop in it. Not a different list, the
#: same list with the loop options removed from the one set that has them.
NO_LOOPS = tuple(
    " ".join(w for w in one.split() if w not in ("-funroll-loops", "-fpeel-loops"))
    for one in TORTURE
)


class HarnessError(RuntimeError):
    """The model was asked for something it does not do, said out loud."""


@dataclass(frozen=True)
class Directive:
    """One `{ dg-something ... }` out of a comment, with the line it was written on."""

    name: str
    line: int
    args: tuple[str, ...]
    raw: str

    @property
    def handled(self) -> bool:
        return self.name in KNOWN

    def __str__(self) -> str:
        shown = " ".join(f'"{a}"' for a in self.args)
        return f"{self.line:>3}  {{ {self.name} {shown} }}".rstrip()


@dataclass(frozen=True)
class Expectation:
    """A message a directive says will appear, and where."""

    kind: str
    line: int
    pattern: str
    comment: str = ""

    @property
    def bogus(self) -> bool:
        return self.kind == "bogus"

    def matches(self, line: int, kind: str, text: str) -> bool:
        """Does one diagnostic satisfy this expectation. Three conditions and all must hold.

        The line has to be the one the directive was written on, which is why a test writes
        each expectation on the line it belongs to rather than collecting them at the top.

        The kind has to agree, except for `dg-bogus` and `dg-message`, which accept any kind.
        That is what makes `dg-message "note: [...]"` the way to check one note without
        signing up to account for all of them.

        The pattern is a regular expression, and it is searched against the message with its
        kind still on the front, so `dg-bogus "note"` matches any note at all and
        `dg-error "not at end"` matches the words in the message. It is a search and not a
        full match, which is why almost every pattern in the suite is a fragment.
        """
        if line != self.line:
            return False
        if self.kind not in ("bogus", "message") and kind != self.kind:
            return False
        return re.search(self.pattern, f"{kind}: {text}") is not None


@dataclass(frozen=True)
class Diagnostic:
    """One line of what the compiler printed, parsed."""

    line: int
    column: int
    kind: str
    text: str
    raw: str


@dataclass(frozen=True)
class Outcome:
    """One line of a `.sum` file: a state and the name of what produced it."""

    state: str
    name: str

    def __str__(self) -> str:
        return f"{self.state}: {self.name}"


@dataclass
class Test:
    """One test file, read."""

    path: str
    text: str
    directives: list[Directive] = field(default_factory=list)

    @property
    def do_what(self) -> str:
        """What `dg-do` asked for, or `compile`, which is what most directories default to."""
        for one in self.directives:
            if one.name == "dg-do" and one.args:
                return one.args[0]
        return "compile"

    @property
    def given(self) -> list[str]:
        """The flags from `dg-options`, which replace the directory's default entirely."""
        found: list[str] = []
        for one in self.directives:
            if one.name == "dg-options" and one.args:
                found += one.args[0].split()
        return found

    @property
    def extra(self) -> list[str]:
        """The flags from `dg-additional-options`, which are added rather than substituted."""
        found: list[str] = []
        for one in self.directives:
            if one.name == "dg-additional-options" and one.args:
                found += one.args[0].split()
        return found

    @property
    def options(self) -> list[str]:
        """Every flag the file asks for, in file order. Not the whole command line."""
        return self.given + self.extra

    def command(
        self, default: tuple[str, ...] = DEFAULT_CFLAGS, always: tuple[str, ...] = ALWAYS
    ) -> list[str]:
        """The flags the compiler is actually handed, which is not what the file says.

        Three sources and they combine differently. `always` goes on every compilation in the
        whole suite. `default` is the directory's, and `dg-options` replaces it rather than
        adding to it, which is why a test with `dg-options "-O2"` in `gcc.dg` is compiled
        without `-pedantic-errors` and a test with no `dg-options` at all is compiled as C90.
        `dg-additional-options` is the directive for wanting the third behaviour.
        """
        return [*always, *(self.given or default), *self.extra]

    @property
    def expectations(self) -> list[Expectation]:
        found = []
        for one in self.directives:
            if one.name not in MESSAGE_KINDS or not one.args:
                continue
            found.append(
                Expectation(
                    kind=MESSAGE_KINDS[one.name],
                    line=one.line,
                    pattern=one.args[0],
                    comment=one.args[1] if len(one.args) > 1 else "",
                )
            )
        return found

    @property
    def finals(self) -> list[str]:
        """The body of each `dg-final`, as written."""
        return [one.args[0] for one in self.directives if one.name == "dg-final" and one.args]

    @property
    def prunes(self) -> list[str]:
        """The patterns from `dg-prune-output`, which delete output before it is judged."""
        return [
            one.args[0] for one in self.directives if one.name == "dg-prune-output" and one.args
        ]

    @property
    def prune_notes(self) -> bool:
        """Whether a note nobody asked for is allowed to go unmentioned.

        It is, in every test in the suite except one that uses `dg-note`. Writing `dg-note`
        once turns the pruning off for the whole file, so a test that accounts for one note
        has to account for all of them. That switch is why `attr-assume_aligned-2.c` passes
        while printing two notes it never mentions.
        """
        return not any(one.name == "dg-note" for one in self.directives)

    @property
    def unhandled(self) -> list[Directive]:
        """Directives this model does not act on. A test with any of these is a test whose
        verdict here may differ from the real harness's, and the lesson says so."""
        return [one for one in self.directives if not one.handled]

    @property
    def name(self) -> str:
        """The name the harness puts in the `.sum`, which is the path below `testsuite/`.

        Not the path from the build tree and not the basename. Two directories hold a file
        called `pr78517.c`, so the directory has to be in the name, and the part above
        `testsuite` differs between everybody's machine, so it cannot be.
        """
        _, sep, below = self.path.partition("testsuite/")
        return below if sep else self.path


def find_directives(text: str) -> list[tuple[int, str]]:
    """Every `{ dg-... }` in the text, with its line number and its inside.

    Brace counting rather than a regular expression, because a `dg-final` body contains
    braces of its own and the outer one has to be matched with the right partner.
    """
    found = []
    at = 0
    while True:
        start = text.find("{ dg-", at)
        if start == -1:
            return found
        depth = 0
        stop = start
        while stop < len(text):
            if text[stop] == "{":
                depth += 1
            elif text[stop] == "}":
                depth -= 1
                if depth == 0:
                    break
            stop += 1
        if depth != 0:
            raise HarnessError(
                f"unclosed directive at offset {start} of {text[start : start + 40]!r}"
            )
        found.append((text.count("\n", 0, start) + 1, text[start + 1 : stop].strip()))
        at = stop + 1


def split_args(body: str) -> tuple[str, tuple[str, ...]]:
    """A directive body into its name and its arguments.

    Tcl quoting, cut down to the two forms a test file uses: a double quoted string, and a
    braced group that keeps its braces because the thing inside is another command.
    """
    name, _, rest = body.partition(" ")
    args: list[str] = []
    at = 0
    rest = rest.strip()
    while at < len(rest):
        if rest[at].isspace():
            at += 1
        elif rest[at] == '"':
            stop = rest.find('"', at + 1)
            if stop == -1:
                raise HarnessError(f"unclosed quote in {body!r}")
            args.append(rest[at + 1 : stop])
            at = stop + 1
        elif rest[at] == "{":
            depth, stop = 0, at
            while stop < len(rest):
                if rest[stop] == "{":
                    depth += 1
                elif rest[stop] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                stop += 1
            args.append(rest[at + 1 : stop].strip())
            at = stop + 1
        else:
            stop = at
            while stop < len(rest) and not rest[stop].isspace():
                stop += 1
            args.append(rest[at:stop])
            at = stop
    return name, tuple(args)


def read_test(text: str, path: str = "test.c") -> Test:
    """Parse one test file. Nothing is compiled and nothing is checked."""
    directives = []
    for line, body in find_directives(text):
        name, args = split_args(body)
        directives.append(Directive(name=name, line=line, args=args, raw=body))
    return Test(path=path, text=text, directives=directives)


def diagnostics(stderr: str) -> tuple[list[Diagnostic], list[str]]:
    """The compiler's output, split into diagnostics and everything else."""
    found, rest = [], []
    for raw in stderr.splitlines():
        if not raw.strip():
            continue
        m = DIAGNOSTIC.match(raw)
        if m is None:
            rest.append(raw)
            continue
        found.append(
            Diagnostic(
                line=int(m.group("line")),
                column=int(m.group("column") or 0),
                kind=m.group("kind").replace("fatal error", "error"),
                text=m.group("text"),
                raw=raw,
            )
        )
    return found, rest


def prune(lines: list[str]) -> list[str]:
    """Throw away the output that is context rather than a diagnostic.

    The real `prune_gcc_output` is about forty of these. This is four, and the difference is
    the reason a model is a model.
    """
    return [one for one in lines if not any(p.match(one) for p in PRUNED)]


#: How a result line names the thing it tested. `bogus` is not a kind of diagnostic, so it
#: gets a phrase of its own rather than an `s` on the end.
PHRASE = {
    "error": "errors",
    "warning": "warnings",
    "message": "messages",
    "note": "notes",
    "bogus": "bogus messages",
}


def claim(test: Test, stderr: str) -> tuple[list[tuple[Expectation, Diagnostic | None]], list[str]]:
    """Hand each expectation the diagnostic it claims, and return what nobody claimed.

    Subtractive, and that is the shape worth noticing. Each expectation takes one diagnostic
    out of the pile, first match wins, and what is still in the pile at the end is output the
    test never mentioned.
    """
    found, other = diagnostics(stderr)
    left = list(found)
    claimed: list[tuple[Expectation, Diagnostic | None]] = []
    for want in test.expectations:
        hit = next((d for d in left if want.matches(d.line, d.kind, d.text)), None)
        if hit is not None:
            left.remove(hit)
        claimed.append((want, hit))

    if test.prune_notes:
        left = [d for d in left if d.kind != "note"]
    over = [d.raw for d in left] + prune(other)
    for pattern in test.prunes:
        over = [line for line in over if re.search(pattern, line) is None]
    return claimed, over


def excess(test: Test, stderr: str) -> list[str]:
    """The output no directive claimed, which is what fails a test for excess errors."""
    return claim(test, stderr)[1]


def check(test: Test, stderr: str) -> list[Outcome]:
    """Compare what the compiler printed against what the test said it would print.

    This is the harness in one function. A test that checks nine things correctly and emits a
    tenth diagnostic nobody mentioned still fails, on the last line, and that last line is
    there whether or not anything went wrong: a run of a clean test says so twice.
    """
    claimed, left = claim(test, stderr)
    results = []
    for want, hit in claimed:
        good = (hit is None) if want.bogus else (hit is not None)
        where = f"(test for {PHRASE[want.kind]}, line {want.line})"
        results.append(Outcome("PASS" if good else "FAIL", f"{test.name} {where}"))
    if test.expectations or test.do_what == "compile":
        state = "FAIL" if left else "PASS"
        results.append(Outcome(state, f"{test.name} (test for excess errors)"))
    return results


#: The three `dg-final` commands this model runs. `scan-tree-dump-times` is the one that
#: matters, because a dump that says a thing once when it should say it six times is the
#: failure mode a `scan-tree-dump` cannot see.
SCANS = ("scan-tree-dump", "scan-rtl-dump", "scan-ipa-dump")


def run_final(test: Test, body: str, dumps: dict[str, str]) -> Outcome:
    """One `dg-final` command against the dumps the compilation produced.

    `dumps` is keyed by the suffix the directive names, `fre1` and not `tree-fre1`, because
    that is what the test writes. The pattern is a Tcl regular expression, which for these
    three commands is close enough to a Python one that the difference has never mattered on
    a pattern anybody actually wrote.
    """
    name, args = split_args(body)
    kind = next((s for s in SCANS if name.startswith(s)), "")
    variant = name[len(kind) :] if kind else ""
    if not kind or variant not in ("", "-times", "-not") or len(args) < 2:
        return Outcome("UNRESOLVED", f"{test.name} {body} (not implemented by this model)")

    pattern = args[0]
    times = int(args[1]) if variant == "-times" else 0
    suffix = args[2] if variant == "-times" else args[1]
    if suffix not in dumps:
        have = ", ".join(sorted(dumps)) or "none"
        return Outcome("UNRESOLVED", f"{test.name} {body} (no {suffix} dump here, have {have})")

    found = len(re.findall(pattern, dumps[suffix]))
    printable = pattern.replace("\n", "\\n")
    if variant == "-times":
        shown = f'{name} {suffix} "{printable}" {times}'
        return Outcome("PASS" if found == times else "FAIL", f"{test.name} {shown}")
    shown = f'{name} {suffix} "{printable}"'
    good = (found == 0) if variant == "-not" else (found > 0)
    return Outcome("PASS" if good else "FAIL", f"{test.name} {shown}")


#: What can be stuck on the end of a dump flag without changing which file it writes.
#: `-fdump-tree-fre1-details` and `-fdump-tree-fre1` both write `x.c.035t.fre1`, which is why
#: a `dg-final` names `fre1` and never names the modifier the `dg-options` line asked for.
MODIFIERS = (
    "-details",
    "-stats",
    "-blocks",
    "-graph",
    "-vops",
    "-lineno",
    "-uid",
    "-verbose",
    "-eh",
    "-scev",
    "-gimple",
    "-folding",
    "-alias",
    "-nouid",
    "-raw",
    "-slim",
    "-all",
    "-optimized",
    "-missed",
    "-note",
    "-optall",
    "-internals",
)


def dump_suffix(flag: str) -> str:
    """Which dump a `-fdump-...` flag writes, named the way a `dg-final` names it.

    Two things come off: the `-fdump-tree-` or `-fdump-rtl-` head, and any modifiers on the
    tail. What is left is the pass name, and the pass name is the whole of the suffix.
    """
    body = flag.split("=")[0]
    for head in ("-fdump-tree-", "-fdump-rtl-", "-fdump-ipa-"):
        if body.startswith(head):
            body = body[len(head) :]
            break
    else:
        raise HarnessError(f"{flag!r} is not a dump flag this model knows how to name")
    changed = True
    while changed:
        changed = False
        for one in MODIFIERS:
            if body.endswith(one) and body != one.lstrip("-"):
                body, changed = body[: -len(one)], True
    return body


def scan(test: Test, dumps: dict[str, str]) -> list[Outcome]:
    """Every `dg-final` in the test, in the order they were written."""
    return [run_final(test, body, dumps) for body in test.finals]


def has_loop(text: str) -> bool:
    """What the harness greps for before choosing a torture list.

    A glob and not a regular expression, so `for*(` matches `for (`, `for(` and `format(`.
    The false positive costs one extra option and nothing else, which is why nobody has ever
    tightened it.
    """
    return re.search(r"for.*\(", text) is not None or re.search(r"while.*\(", text) is not None


def torture_list(text: str) -> tuple[str, ...]:
    """The option sets one file will be compiled with under `gcc-dg-runtest`."""
    return TORTURE if has_loop(text) else NO_LOOPS


def selected(names: list[str], pattern: str) -> list[str]:
    """Which tests a `RUNTESTFLAGS` filter keeps.

    The filter is `dg.exp=glob`, and the glob applies to the file name only. This is the
    function a reader is really asking about when they ask how to run one test.
    """
    if not pattern:
        return list(names)
    out = []
    for name in names:
        tail = name.split("/")[-1]
        if _glob(tail, pattern):
            out.append(name)
    return out


def _glob(text: str, pattern: str) -> bool:
    return (
        re.fullmatch(re.escape(pattern).replace(r"\*", ".*").replace(r"\?", "."), text) is not None
    )


@dataclass
class Race:
    """What N runtest processes did to one list of tests.

    `taken` is which process ran each test. `skipped` is the tests no process ran and `twice`
    is the ones more than one did, and both of those are empty when every process enumerated
    the same list. They are the two failure modes of invariant I4 in `BP-TESTSUITE`, and
    nothing in the real harness notices either of them.
    """

    taken: dict[str, list[int]] = field(default_factory=dict)
    batch: int = 10

    @property
    def skipped(self) -> list[str]:
        return sorted(k for k, v in self.taken.items() if not v)

    @property
    def twice(self) -> list[str]:
        return sorted(k for k, v in self.taken.items() if len(v) > 1)

    @property
    def counts(self) -> dict[int, int]:
        found: dict[int, int] = {}
        for who in self.taken.values():
            for one in who:
                found[one] = found.get(one, 0) + 1
        return dict(sorted(found.items()))

    @property
    def sound(self) -> bool:
        return not self.skipped and not self.twice


def race(orders: list[list[str]], winners: list[int] | None = None, batch: int = 10) -> Race:
    """Run the marker file race, given what each process would enumerate.

    `orders[i]` is the list of tests process `i` walks, in its order. `winners[b]` is which
    process gets to the marker for batch `b` first, defaulting to round robin, which is the
    tidiest possible outcome and not one any real run produces.

    When every order is the same list, every test is run exactly once whichever way the race
    goes, and that is the point. When two orders differ, the marker for batch 3 is claimed by
    one process for one set of ten tests and honoured by another for a different set of ten,
    and tests fall through the gap.
    """
    if not orders:
        raise HarnessError("a race with no processes in it")
    batches = max((len(one) + batch - 1) // batch for one in orders)
    if winners is None:
        winners = [n % len(orders) for n in range(batches)]
    if len(winners) < batches:
        raise HarnessError(f"{batches} batches and only {len(winners)} winners named")

    taken: dict[str, list[int]] = {name: [] for one in orders for name in one}
    for who, order in enumerate(orders):
        for n, name in enumerate(order):
            if winners[n // batch] == who:
                taken[name].append(who)
    return Race(taken=taken, batch=batch)


SUM_LINE = re.compile(
    r"^(?P<state>PASS|XPASS|FAIL|XFAIL|UNRESOLVED|WARNING|ERROR|UNSUPPORTED"
    r"|UNTESTED|KFAIL|KPASS|PATH|DUPLICATE):\s*(?P<name>.+)$"
)

#: The states that make a run red. The other eight are information.
BAD = ("FAIL", "XPASS", "KPASS", "UNRESOLVED", "ERROR")


def parse_sum(text: str) -> list[Outcome]:
    """Every result line in a `.sum` file, in order. Everything else is dropped."""
    found = []
    for line in text.splitlines():
        m = SUM_LINE.match(line.strip())
        if m:
            found.append(Outcome(m.group("state"), m.group("name").strip()))
    return found


def summarize(results: list[Outcome]) -> dict[str, int]:
    """The summary block at the bottom of a `.sum`, recounted from the lines above it."""
    found: dict[str, int] = {}
    for one in results:
        found[one.state] = found.get(one.state, 0) + 1
    return dict(sorted(found.items()))


def regressions(before: list[Outcome], after: list[Outcome]) -> dict[str, list[str]]:
    """What changed between two runs, which is the only question anybody asks of a `.sum`.

    Three answers and they are not the same answer. A test that went from `PASS` to `FAIL` is
    a regression. A test that is in one run and not the other is not a regression, it is a
    test that stopped being run, and those are the ones a summary block hides because the
    total goes down by one and nothing turns red.
    """
    was = {one.name: one.state for one in before}
    now = {one.name: one.state for one in after}
    return {
        "worse": sorted(n for n in was.keys() & now.keys() if was[n] != now[n] and now[n] in BAD),
        "better": sorted(n for n in was.keys() & now.keys() if was[n] != now[n] and was[n] in BAD),
        "gone": sorted(was.keys() - now.keys()),
        "new": sorted(now.keys() - was.keys()),
    }


@dataclass(frozen=True)
class Recording:
    """One recorded compilation of one real GCC test file."""

    name: str
    path: str
    text: str
    args: tuple[str, ...]
    returncode: int
    stderr: str
    dump: str = ""

    @property
    def test(self) -> Test:
        return read_test(self.text, path=self.path)

    @property
    def dumps(self) -> dict[str, str]:
        """The dump this compilation wrote, keyed the way a `dg-final` would name it."""
        if not self.dump:
            return {}
        flags = [a for a in self.args if a.startswith("-fdump-")]
        if len(flags) != 1:
            raise HarnessError(f"{self.name} asked for {len(flags)} dumps, so one text is wrong")
        return {dump_suffix(flags[0]): self.dump}


@dataclass(frozen=True)
class Corpus:
    """What `lessons/b04-the-test-suite/record.py` wrote."""

    compiler: str
    target: str
    recorded: str
    tag: str
    entries: dict[str, Recording]
    #: Counts taken off the pinned tree at record time, because a reader has no tree to count.
    survey: dict = field(default_factory=dict)

    def __getitem__(self, name: str) -> Recording:
        if name not in self.entries:
            have = ", ".join(sorted(self.entries))
            raise KeyError(f"no recording called {name!r}. Have: {have}")
        return self.entries[name]

    def __iter__(self):
        return iter(self.entries.values())

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def banner(self) -> str:
        return (
            f"{len(self.entries)} tests, compiled by {self.compiler} "
            f"for {self.target}, recorded {self.recorded}"
        )


def load(path: Path | str | None = None) -> Corpus:
    """The recorded compilations, so none of this needs a compiler or a network."""
    target = Path(path or CORPUS)
    if not target.is_file():
        raise HarnessError(f"{target} is not there. Run lessons/b04-the-test-suite/record.py.")
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Corpus(
        compiler=raw["compiler"],
        target=raw["target"],
        recorded=raw["recorded"],
        tag=raw["tag"],
        survey=raw.get("survey", {}),
        entries={
            name: Recording(
                name=name,
                path=one["path"],
                text=one["text"],
                args=tuple(one["args"]),
                returncode=one["returncode"],
                stderr=one["stderr"],
                dump=one.get("dump", ""),
            )
            for name, one in raw["tests"].items()
        },
    )
