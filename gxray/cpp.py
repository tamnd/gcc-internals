"""What the preprocessor prints, read back as the tokens it actually was.

`gcc -E` looks like text going in and text coming out, and that reading survives right up
until the first time it does not. This module reads the four things the preprocessor will
tell you about itself:

    from gxray import cpp
    rec = cpp.load("f02")

    rec.macros("local")                  # 443 macros nobody wrote
    rec.macros("local").only_in(rec.macros("elsewhere"))   # the ones that are this target
    cpp.markers(rec.expansion("markers").output)           # every `# 1 "file"` line
    cpp.parse_trace(rec.headers("local").text).files       # 38 files for one #include

Like `gxray.specs`, this is a reader and not a second implementation. It never expands a
macro. Expanding one needs the include path, the target's macros, the date, the file being
compiled and a hash table with the state of every other macro in it, and a lesson that faked
those would be teaching a fiction.

The one table here that is a claim about GCC rather than about its output is `PASTES`, which
is the pairs of adjacent tokens `cpp_avoid_paste` puts a space between at
`libcpp/lex.cc:4728@releases/gcc-16.2.0`. Every row names the `case` label it comes from, and
a test compares the set of labels against the switch in the pinned tree, so a GCC that learns
a new pair fails the build rather than quietly making a sentence wrong. That space is the
whole lesson: it is a character in the output that is in no input file, and it is there
because two tokens would otherwise lex as one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Where a recording of one compiler's preprocessor lives.
CORPUS = Path(__file__).resolve().parent.parent / "corpora" / "cpp"


class CppError(Exception):
    """Something asked of a preprocessor recording that it cannot answer."""


# ---------------------------------------------------------------------------
# Line markers
# ---------------------------------------------------------------------------

#: What the digits after a line marker mean. GCC writes them in `print_line_1` at
#: `gcc/c-family/c-ppoutput.cc:592@releases/gcc-16.2.0`, and a reader who does not know them
#: reads `# 1 "/usr/include/stdio.h" 1 3 4` as noise rather than as the four facts it is.
MARKER_FLAGS: dict[int, str] = {
    1: "entering a file",
    2: "returning to a file",
    3: "a system header, where warnings are suppressed",
    4: 'to be wrapped in extern "C"',
}

#: `# 61 "stdio.h" 2 3 4`. The quotes are always there and the flags never are.
MARKER = re.compile(r'^#\s+(?P<line>\d+)\s+"(?P<file>(?:[^"\\]|\\.)*)"(?P<flags>[\s\d]*)$')


@dataclass(frozen=True)
class Marker:
    """One `# line "file" flags` line of preprocessed output.

    Not a comment and not a directive: it is how the preprocessor hands the parser back the
    line numbers it just destroyed. Everything after it came from `file` starting at `line`,
    and that is what makes an error message in a header point at the header.
    """

    line: int
    file: str
    flags: tuple[int, ...]

    @property
    def entering(self) -> bool:
        return 1 in self.flags

    @property
    def returning(self) -> bool:
        return 2 in self.flags

    @property
    def system(self) -> bool:
        return 3 in self.flags

    @property
    def meanings(self) -> list[str]:
        return [MARKER_FLAGS[flag] for flag in self.flags if flag in MARKER_FLAGS]

    def __str__(self) -> str:
        said = ", ".join(self.meanings) or "no flags, so the line number moved and nothing else"
        return f"{self.file}:{self.line}  ({said})"


def markers(text: str) -> list[Marker]:
    """Every line marker in a chunk of `-E` output, in the order they were printed."""
    found = []
    for line in text.split("\n"):
        got = MARKER.match(line)
        if got:
            flags = tuple(int(n) for n in got["flags"].split())
            found.append(Marker(line=int(got["line"]), file=got["file"], flags=flags))
    return found


def body(text: str) -> list[str]:
    """The output with its line markers and its blank lines taken out.

    Which is usually a much shorter file than the reader expected, and is the point of
    printing the length of both.
    """
    return [line for line in text.split("\n") if line.strip() and not MARKER.match(line)]


# ---------------------------------------------------------------------------
# Macro tables
# ---------------------------------------------------------------------------

#: One line of `-dM -E` output. The name runs to a space or an open bracket, and a bracket
#: touching the name is what makes a macro function-like: `#define f (x) x` defines `f` as
#: `(x) x`, and getting that wrong is a rite of passage rather than a corner case.
DEFINE = re.compile(
    r"^#define\s+(?P<name>[A-Za-z_$][\w$]*)(?P<params>\([^)]*\))?(?: (?P<body>.*))?$"
)


@dataclass(frozen=True)
class Macro:
    """One macro, as `-dM` prints it."""

    name: str
    params: str | None
    body: str

    @property
    def function_like(self) -> bool:
        return self.params is not None

    @property
    def empty(self) -> bool:
        """Defined and expanding to nothing, which is not the same as not defined."""
        return self.body == ""

    def __str__(self) -> str:
        head = f"{self.name}{self.params or ''}"
        return f"{head} {self.body}".rstrip()


@dataclass
class Macros:
    """Every macro a compiler defines before it has read a line of your program.

    A mapping, but the interesting operations are the set ones. One of these tables on its
    own is a wall of names. Two of them, from two targets, sort themselves into what C
    guarantees, what GCC adds, and what the machine underneath is admitting to.
    """

    text: str
    entries: dict[str, Macro]
    flags: str = ""
    compiler: str = ""
    target: str = ""
    about: str = ""

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, name: object) -> bool:
        return name in self.entries

    def __iter__(self):
        return iter(self.entries.values())

    def __getitem__(self, name: str) -> Macro:
        if name not in self.entries:
            raise CppError(f"{name} is not defined on {self.target or 'this target'}")
        return self.entries[name]

    @property
    def names(self) -> list[str]:
        return sorted(self.entries)

    @property
    def function_like(self) -> list[str]:
        return sorted(one.name for one in self if one.function_like)

    @property
    def empty(self) -> list[str]:
        return sorted(one.name for one in self if one.empty)

    def starting(self, *prefixes: str) -> list[str]:
        return sorted(n for n in self.entries if n.startswith(prefixes))

    def only_in(self, other: Macros) -> list[str]:
        """Names this table has and the other does not."""
        return sorted(set(self.entries) - set(other.entries))

    def shared(self, other: Macros) -> list[str]:
        return sorted(set(self.entries) & set(other.entries))

    def differing(self, other: Macros) -> list[str]:
        """Names both tables define, to different things, which is the awkward set.

        A macro missing on the other target is a thing `#ifdef` can see. A macro defined on
        both with a different value is a thing only arithmetic can see, and it is where the
        portability bugs live.
        """
        return sorted(
            name
            for name in set(self.entries) & set(other.entries)
            if self.entries[name].body != other.entries[name].body
        )

    def __str__(self) -> str:
        where = self.target or "somewhere"
        return f"{len(self)} macros on {where}{' with ' + self.flags if self.flags else ''}"


def parse_macros(text: str, **about) -> Macros:
    """Read `gcc -dM -E` output. Anything that is not a `#define` line is an error.

    Strict on purpose. The whole value of this table is that it is exhaustive, so a line
    this cannot read is a line the count is wrong about.
    """
    entries: dict[str, Macro] = {}
    for line in text.split("\n"):
        if not line.strip():
            continue
        got = DEFINE.match(line)
        if not got:
            raise CppError(f"-dM printed a line that is not a definition: {line!r}")
        entries[got["name"]] = Macro(name=got["name"], params=got["params"], body=got["body"] or "")
    return Macros(text=text, entries=entries, **about)


# ---------------------------------------------------------------------------
# Include traces
# ---------------------------------------------------------------------------

#: A `-H` line: one dot per level of nesting, a space, and the path. The dots are written by
#: `trace_include` at `libcpp/line-map.cc:1592@releases/gcc-16.2.0`, which prints when a file
#: is stacked, so a file that is skipped without being opened leaves no line at all.
TRACED = re.compile(r"^(?P<dots>\.+) (?P<path>.+)$")

#: The trailer `-H` prints after everything else, and the only advice GCC gives unasked.
GUARDS_WANTED = "Multiple include guards may be useful for:"


@dataclass(frozen=True)
class Include:
    depth: int
    path: str

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]


@dataclass
class Trace:
    """The include tree, as `-H` reports it.

    Every line is one file being opened. A file included twice appears twice, unless the
    preprocessor worked out that reading it again could not change anything, in which case
    the second `#include` costs nothing and shows nothing.
    """

    text: str
    includes: tuple[Include, ...]
    guards_wanted: tuple[str, ...] = ()
    about: str = ""

    def __len__(self) -> int:
        return len(self.includes)

    def __iter__(self):
        return iter(self.includes)

    @property
    def files(self) -> list[str]:
        """Distinct paths, in the order first seen."""
        seen: list[str] = []
        for one in self.includes:
            if one.path not in seen:
                seen.append(one.path)
        return seen

    @property
    def names(self) -> list[str]:
        return [one.name for one in self.includes]

    @property
    def depth(self) -> int:
        return max((one.depth for one in self.includes), default=0)

    @property
    def opened_twice(self) -> list[str]:
        """Paths that were stacked more than once, which is the whole header guard story."""
        counts: dict[str, int] = {}
        for one in self.includes:
            counts[one.path] = counts.get(one.path, 0) + 1
        return sorted(path for path, n in counts.items() if n > 1)

    def under(self, path: str) -> list[Include]:
        """Everything included because of `path`, to any depth."""
        found: list[Include] = []
        collecting = False
        outer = 0
        for one in self.includes:
            if collecting and one.depth <= outer:
                collecting = False
            if one.path == path and not collecting:
                collecting, outer = True, one.depth
                continue
            if collecting:
                found.append(one)
        return found

    def tree(self, limit: int = 0) -> str:
        shown = self.includes[:limit] if limit else self.includes
        return "\n".join(f"{'  ' * (one.depth - 1)}{one.name}" for one in shown)


def parse_trace(text: str, about: str = "") -> Trace:
    """Read `gcc -H` output, which arrives on stderr and is not sorted by anything."""
    includes: list[Include] = []
    wanted: list[str] = []
    trailer = False
    for line in text.split("\n"):
        if line.startswith(GUARDS_WANTED):
            trailer = True
            continue
        if trailer:
            if line.strip():
                wanted.append(line.strip())
            continue
        got = TRACED.match(line)
        if got:
            includes.append(Include(depth=len(got["dots"]), path=got["path"]))
    return Trace(text=text, includes=tuple(includes), guards_wanted=tuple(wanted), about=about)


# ---------------------------------------------------------------------------
# The pairs that cannot be printed next to each other
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pair:
    """Two tokens that would lex as one if they were printed with nothing between them.

    `case` is the label in `cpp_avoid_paste` this row stands for, which is what lets a test
    check the table against the switch rather than against somebody's memory of it.
    """

    left: str
    right: str
    case: str
    about: str

    @property
    def glued(self) -> str:
        """What the two would spell with no space, which is the token nobody asked for."""
        return f"{self.left}{self.right}"


#: Every pair `cpp_avoid_paste` separates, one row per reason. Not every pair the switch
#: covers, which would be hundreds: one witness per `case` label, chosen so that the glued
#: spelling is a real token a reader recognises. The labels are the checkable part.
PASTES: tuple[Pair, ...] = (
    Pair(">", ">", "CPP_GREATER", "or it would be a right shift"),
    Pair("<", "<", "CPP_LESS", "or it would be a left shift"),
    Pair("<", ":", "CPP_LESS", "or it would be the digraph for an open bracket"),
    Pair("+", "+", "CPP_PLUS", "or it would be an increment"),
    Pair("-", "-", "CPP_MINUS", "or it would be a decrement"),
    Pair("-", ">", "CPP_MINUS", "or it would be a member access"),
    Pair("/", "/", "CPP_DIV", "or it would be a comment, and eat the rest of the line"),
    Pair("/", "*", "CPP_DIV", "or it would open a comment that nobody closes"),
    Pair("%", ">", "CPP_MOD", "or it would be the digraph for a close brace"),
    Pair("&", "&", "CPP_AND", "or it would be a logical and"),
    Pair("|", "|", "CPP_OR", "or it would be a logical or"),
    Pair(":", ">", "CPP_COLON", "or it would be the digraph for a close bracket"),
    Pair("->", "*", "CPP_DEREF", "or it would be a pointer to member, which C++ has"),
    Pair(".", ".", "CPP_DOT", "two of three characters of an ellipsis"),
    Pair(".", "5", "CPP_DOT", "or it would be the number .5"),
    Pair("<=", ">", "CPP_LESS_EQ", "or it would be the spaceship operator"),
    Pair("+", "=", "CPP_LAST_EQ", "or it would be a compound assignment"),
    Pair("!", "=", "CPP_LAST_EQ", "or it would be a comparison, which is the opposite"),
    Pair("x", "y", "CPP_NAME", "or it would be one identifier called xy"),
    Pair("x", "5", "CPP_NAME", "or it would be one identifier called x5"),
    Pair("L", "'c'", "CPP_NAME", "or it would be a wide character literal"),
    Pair("L", '"s"', "CPP_NAME", "or it would be a wide string literal"),
    Pair("1", "2", "CPP_NUMBER", "or it would be twelve"),
    Pair("1", "x", "CPP_NUMBER", "or it would be a number with a suffix on it"),
    Pair("1", ".", "CPP_NUMBER", "or it would be a floating point number"),
    Pair("1", "+", "CPP_NUMBER", "or it would be an exponent, in a number like 1e+5"),
    Pair("\\", "x", "CPP_OTHER", "or it would be a universal character name"),
    Pair("#", "#", "CPP_HASH", "or it would be a paste operator"),
    Pair("#", "%", "CPP_HASH", "or it would be the digraph for a paste operator"),
)

#: Pairs that get nothing, which is half of the demonstration. A rule that fires on every
#: pair is not a rule about tokens, it is a rule about spacing.
KEPT_TOGETHER: tuple[tuple[str, str], ...] = (
    ("+", "-"),
    ("x", "+"),
    ("*", "&"),
    ("]", "["),
    (";", ";"),
    ("&", "|"),
    ("!", "!"),
    ("~", "x"),
    ("1", "]"),
)


@dataclass(frozen=True)
class Probe:
    """One pair put next to each other on purpose, and what came out."""

    left: str
    right: str
    output: str
    case: str = ""
    about: str = ""

    @property
    def spaced(self) -> bool:
        return " " in self.output.strip()

    @property
    def glued(self) -> str:
        return f"{self.left}{self.right}"


# ---------------------------------------------------------------------------
# Expansions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Expansion:
    """One small file put through `-E`, here and somewhere else.

    `elsewhere` is the same source through an x86-64 Linux GCC of the same release. The
    macro tables of two targets have almost nothing in common; the expansion rules have
    everything in common, and showing both is cheaper than asserting it.
    """

    name: str
    about: str
    source: str
    output: str
    elsewhere: str = ""

    @property
    def agrees(self) -> bool:
        """Whether the two targets produced the same expansion, ignoring trailing space."""
        if not self.elsewhere:
            return True
        return _flat(self.output) == _flat(self.elsewhere)

    def pairs(self) -> list[tuple[str, str]]:
        """Each line of the program against the line it turned into.

        Directives are dropped, because a `#define` produces no output line to pair with and
        pairing around one would put every later line against somebody else's answer. What is
        left is one output line per source line, which is what `-P` on these files gives.
        """
        was = [line for line in self.source.split("\n") if line.strip() and line[0] != "#"]
        now = [line for line in self.output.split("\n") if line.strip()]
        if len(was) != len(now):
            raise CppError(
                f"{self.name} has {len(was)} lines of program and {len(now)} of output,"
                " so no line can be paired with what it became"
            )
        return list(zip(was, now, strict=True))


def _flat(text: str) -> list[str]:
    return [line.rstrip() for line in text.split("\n") if line.strip()]


def inserted_spaces(source: str, output: str) -> int:
    """How many space characters the output has that the source did not.

    A count and not a diff, because the interesting number is that it is not zero. The two
    strings are compared with every space removed, so a line that only gained spaces has a
    difference of exactly the spaces it gained.
    """
    bare = source.replace(" ", "").replace("\t", "")
    if output.replace(" ", "").replace("\t", "") != bare:
        raise CppError("the output is not the source plus spaces, so counting them says nothing")
    return output.count(" ") - source.count(" ")


# ---------------------------------------------------------------------------
# The recording
# ---------------------------------------------------------------------------


@dataclass
class Builtin:
    """What the pinned tree says about macros nobody defined, counted rather than recalled."""

    array: tuple[str, ...] = ()
    fixed: tuple[str, ...] = ()

    def missing_from(self, table: Macros) -> list[str]:
        """Builtins that a dump of every macro does not print, which is nearly all of them."""
        return sorted(name for name in self.array if name not in table)


@dataclass
class Recording:
    """One run of the F02 recorder."""

    recorded: str
    compiler: str
    target: str
    tables: dict[str, Macros]
    expansions: dict[str, Expansion]
    probes: tuple[Probe, ...]
    traces: dict[str, Trace]
    builtin: Builtin

    #: The four headers the guard experiment was run on, by name. Kept next to the traces
    #: rather than written into a lesson, because the whole point of the experiment is that
    #: they differ by one line and a reader has to be able to see which line.
    headers_source: dict[str, str] = field(default_factory=dict)

    def macros(self, label: str = "local") -> Macros:
        if label not in self.tables:
            have = ", ".join(sorted(self.tables))
            raise CppError(f"no macro table called {label!r}. There is: {have}")
        return self.tables[label]

    def expansion(self, name: str) -> Expansion:
        if name not in self.expansions:
            have = ", ".join(sorted(self.expansions))
            raise CppError(f"no expansion called {name!r}. There is: {have}")
        return self.expansions[name]

    def headers(self, label: str = "local") -> Trace:
        if label not in self.traces:
            have = ", ".join(sorted(self.traces))
            raise CppError(f"no include trace called {label!r}. There is: {have}")
        return self.traces[label]

    def probe(self, left: str, right: str) -> Probe:
        for one in self.probes:
            if one.left == left and one.right == right:
                return one
        raise CppError(f"nothing probed {left!r} next to {right!r}")

    @property
    def spaced(self) -> list[Probe]:
        return [one for one in self.probes if one.spaced]

    @property
    def unspaced(self) -> list[Probe]:
        return [one for one in self.probes if not one.spaced]

    def __getitem__(self, name: str) -> Expansion:
        return self.expansion(name)


def load(name: str = "f02", root: Path | str | None = None) -> Recording:
    target = Path(root or CORPUS) / f"{name}.json"
    if not target.is_file():
        raise CppError(f"{target} is not there. Run lessons/f02-tokens-not-text/record.py.")
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Recording(
        recorded=raw["recorded"],
        compiler=raw["compiler"],
        target=raw["target"],
        tables={
            label: parse_macros(
                one["text"],
                flags=one.get("flags", ""),
                compiler=one["compiler"],
                target=one["target"],
                about=one["about"],
            )
            for label, one in raw["macros"].items()
        },
        expansions={
            key: Expansion(
                name=key,
                about=one["about"],
                source=one["source"],
                output=one["output"],
                elsewhere=one.get("elsewhere", ""),
            )
            for key, one in raw["expansions"].items()
        },
        probes=tuple(
            Probe(
                left=one["left"],
                right=one["right"],
                output=one["output"],
                case=one.get("case", ""),
                about=one.get("about", ""),
            )
            for one in raw["probes"]
        ),
        traces={
            label: parse_trace(one["text"], about=one["about"])
            for label, one in raw["headers"].items()
        },
        builtin=Builtin(
            array=tuple(raw["builtin"]["array"]),
            fixed=tuple(raw["builtin"]["fixed"]),
        ),
        headers_source=dict(raw.get("headers_source", {})),
    )


__all__ = [
    "CORPUS",
    "GUARDS_WANTED",
    "KEPT_TOGETHER",
    "MARKER_FLAGS",
    "PASTES",
    "Builtin",
    "CppError",
    "Expansion",
    "Include",
    "Macro",
    "Macros",
    "Marker",
    "Pair",
    "Probe",
    "Recording",
    "Trace",
    "body",
    "inserted_spaces",
    "load",
    "markers",
    "parse_macros",
    "parse_trace",
]
