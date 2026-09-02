"""A map of the GCC source tree, recorded once so a notebook can read it without the tree.

Z01 taught the constructs a line of GCC is made of. This is the other half of being able to
read the compiler: knowing which of four and a half million lines to open. The tree is 1.3 GB
and Colab has none of it, so the same trick as `gxray.source` applies. A recorder walks the
pinned checkout, counts what is there, and writes `corpora/layout/gcc.json`. Everything in
this module reads that recording.

    from gxray import layout
    tree = layout.load()
    print(tree.place("gcc/config"))
    print(tree.find("ccp"))

The interesting part is `find`. A dump file is called something like `hunt.c.114t.ccp2`, and
the only thing in that name that points at source is `ccp`. GCC does not keep a table from
dump name to file, so the recorder builds one: it pairs every `pass_data_foo` block with the
`make_pass_foo` function that hands it to the pass manager, and the `"ccp"` string inside the
block is the dump name. That chain is the single most useful thing in this lesson.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

#: Where the recorder puts the map, and where a notebook looks for it.
MAPS = Path(__file__).resolve().parent.parent / "corpora" / "layout"

#: Files GCC writes during its own build, and what to read instead of them. A build directory
#: has hundreds of these and a reader who opens one is reading the output of a program in the
#: tree rather than anything a person wrote. The key is a bare file name because that is what
#: a dump or a backtrace gives you.
#:
#: The numbered variants are real. match.pd is compiled into `gimple-match-1.cc` through
#: `gimple-match-11.cc` so the build can run the compiles in parallel, and a dump line naming
#: `gimple-match-6.cc` is naming a file that does not exist until you build.
GENERATED: dict[str, str] = {
    "gimple-match.cc": "gcc/match.pd",
    "gimple-match-exports.cc": "gcc/match.pd",
    "generic-match.cc": "gcc/match.pd",
    "insn-recog.cc": "the .md file for the target",
    "insn-emit.cc": "the .md file for the target",
    "insn-output.cc": "the .md file for the target",
    "insn-attrtab.cc": "the .md file for the target",
    "insn-opinit.cc": "the .md file for the target",
    "insn-modes.cc": "the modes.def file for the target",
    "insn-flags.h": "the .md file for the target",
    "insn-codes.h": "the .md file for the target",
    "options.cc": "the .opt file that declares the option",
    "options.h": "the .opt file that declares the option",
    "tm.h": "the target's config headers",
    "gtype-desc.cc": "the type declaration that gengtype read",
    "gtype-desc.h": "the type declaration that gengtype read",
    "tree-check.h": "gcc/tree.def",
    "gcov-iov.h": "the version number in gcc/BASE-VER",
}

_NUMBERED = re.compile(r"^(.*?)-\d+(\.(?:cc|h))$")


def generated(filename: str) -> str | None:
    """What to read instead, if this file is written by GCC's build rather than by a person.

    Takes a bare file name or a path, and understands the numbered split files, so both
    `gimple-match-6.cc` and `gcc/gimple-match.cc` answer `gcc/match.pd`. Returns None for a
    file that is checked in, which is the common case and not an error.
    """
    name = filename.rsplit("/", 1)[-1]
    if name in GENERATED:
        return GENERATED[name]
    joined = _NUMBERED.match(name)
    if joined:
        return GENERATED.get(joined.group(1) + joined.group(2))
    return None


#: The ways to get from something a compiler printed to the line of source that printed it.
#: Each is a key you can type, a name, the command, and one sentence on when it is the right
#: one. The scavenger hunt names one of these per item, because the skill being taught is
#: picking the route, not typing the command.
ROUTES: tuple[tuple[str, str, str, str], ...] = (
    (
        "grep",
        "grep for the literal",
        'git grep -n "Removing basic block"',
        "Most dump text is a plain string in an fprintf. Cut the numbers out and search it.",
    ),
    (
        "passes",
        "follow the pass name",
        "grep pass_ccp gcc/passes.def, then grep make_pass_ccp",
        "The dump file name ends in the pass name. passes.def says where it runs, and the "
        "make_pass function is in the file that implements it.",
    ),
    (
        "generated",
        "the file does not exist",
        "ls gcc/gimple-match-6.cc, then read gcc/match.pd",
        "If the name is in the build directory and not in the tree, a program in the tree "
        "wrote it. Find that program and read its input.",
    ),
    (
        "history",
        "search the history",
        'git log -S"Removing basic block" -- gcc/tree-cfg.cc',
        "Which commit added or removed this exact text. The one route that answers why.",
    ),
    (
        "blame",
        "blame the line",
        "git blame -L 2190,2196 gcc/tree-cfg.cc",
        "Which commit last touched this line. Faster than -S when you already have the line.",
    ),
    (
        "maintainers",
        "look up the owner",
        "grep 'aarch64 port' MAINTAINERS",
        "Who to ask, and who has to approve a patch to this part of the tree.",
    ),
    (
        "bugzilla",
        "read the bug",
        "gcc.gnu.org/bugzilla, or search the PR number from a commit message",
        "Commit subjects carry PR numbers. The bug is usually a better explanation than the "
        "commit message is.",
    ),
)

#: Every route key, in the order the lesson lists them.
ROUTE_KEYS = tuple(key for key, _, _, _ in ROUTES)


def route(key: str) -> tuple[str, str, str]:
    """The name, the command and the sentence for one route."""
    for known, name, command, about in ROUTES:
        if known == key:
            return (name, command, about)
    raise KeyError(f"no route called {key!r}. Have: {', '.join(ROUTE_KEYS)}")


@dataclass(frozen=True)
class Place:
    """One directory in the tree, with how much source is under it and what it holds."""

    path: str
    files: int
    lines: int
    about: str

    def __str__(self) -> str:
        return f"{self.path}  {self.files} files, {self.lines} lines. {self.about}"


@dataclass(frozen=True)
class Kind:
    """One file extension GCC gives meaning to, and an example of it."""

    suffix: str
    count: int
    name: str
    about: str
    example: str

    def __str__(self) -> str:
        return f"{self.suffix}  {self.count} files, {self.name}. {self.about}"


@dataclass(frozen=True)
class Generator:
    """One program in the tree that writes source during the build."""

    program: str
    writes: str
    reads: str

    def __str__(self) -> str:
        return f"{self.program} reads {self.reads} and writes {self.writes}"


@dataclass(frozen=True)
class Pass:
    """One entry in passes.def, resolved to the file and line that defines it."""

    name: str
    dump: str
    path: str
    line: int

    @property
    def citation(self) -> str:
        return f"{self.path}:{self.line}"

    def __str__(self) -> str:
        return f"{self.name}  dumps as {self.dump!r}, defined at {self.path}:{self.line}"


@dataclass(frozen=True)
class Big:
    """One of the largest files, with the reason it is large."""

    path: str
    lines: int
    about: str

    def __str__(self) -> str:
        return f"{self.path}  {self.lines} lines. {self.about}"


@dataclass(frozen=True)
class Clue:
    """One item in the scavenger hunt: what a compiler printed, and where it came from."""

    key: str
    dump: str
    route: str
    path: str
    line: int
    text: str
    about: str
    commit: str = ""
    date: str = ""
    author: str = ""
    subject: str = ""

    @property
    def answer(self) -> str:
        return f"{self.path}:{self.line}"

    @property
    def historic(self) -> bool:
        """Whether this one needs the history and not just the checkout."""
        return bool(self.commit)

    def __str__(self) -> str:
        return f"{self.key}  {self.dump!r} -> {self.answer} by {self.route}"


@dataclass(frozen=True)
class Layout:
    """The whole recorded map of one GCC checkout."""

    tag: str
    commit: str
    places: tuple[Place, ...]
    kinds: tuple[Kind, ...]
    ports: tuple[str, ...]
    portless: tuple[str, ...]
    generators: tuple[Generator, ...]
    passes: tuple[Pass, ...]
    biggest: tuple[Big, ...]
    notable: tuple[Big, ...]
    hunt: tuple[Clue, ...]

    def place(self, path: str) -> Place:
        for got in self.places:
            if got.path == path:
                return got
        raise KeyError(f"no place {path!r}. Have: {', '.join(p.path for p in self.places)}")

    def kind(self, suffix: str) -> Kind:
        for got in self.kinds:
            if got.suffix == suffix:
                return got
        raise KeyError(f"no kind {suffix!r}. Have: {', '.join(k.suffix for k in self.kinds)}")

    def find(self, dump: str) -> Pass:
        """The pass a dump file name points at, so `ccp2` and `ccp` both find pass_ccp.

        Dump files are numbered per run of a pass, because most passes run more than once.
        The trailing digits are the run and not part of the name, so they come off before
        the lookup, and a pass whose name really ends in a digit still matches first.
        """
        by_dump = {p.dump: p for p in self.passes}
        if dump in by_dump:
            return by_dump[dump]
        bare = dump.rstrip("0123456789")
        if bare in by_dump:
            return by_dump[bare]
        raise KeyError(f"no pass dumps as {dump!r}. {len(self.passes)} passes are recorded.")

    def clue(self, key: str) -> Clue:
        for got in self.hunt:
            if got.key == key:
                return got
        raise KeyError(f"no clue {key!r}. Have: {', '.join(c.key for c in self.hunt)}")

    @property
    def lines(self) -> int:
        """Lines of source in the whole tree, from the top level places."""
        return sum(p.lines for p in self.places if "/" not in p.path)

    @property
    def files(self) -> int:
        return sum(p.files for p in self.places if "/" not in p.path)

    def __len__(self) -> int:
        return len(self.places)

    def __str__(self) -> str:
        return (
            f"{self.tag}: {self.files} source files, {self.lines} lines, {len(self.passes)} passes"
        )


def load(name: str = "gcc", root: Path | str | None = None) -> Layout:
    """Read the committed map. This is the call a notebook makes."""
    path = Path(root or MAPS) / f"{name}.json"
    if not path.exists():
        have = ", ".join(sorted(p.stem for p in path.parent.glob("*.json"))) or "none"
        raise FileNotFoundError(f"no layout called {name!r}. Have: {have}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Layout(
        tag=data["tag"],
        commit=data["commit"],
        places=tuple(Place(**row) for row in data["places"]),
        kinds=tuple(Kind(**row) for row in data["kinds"]),
        ports=tuple(data["ports"]),
        portless=tuple(data["portless"]),
        generators=tuple(Generator(**row) for row in data["generators"]),
        passes=tuple(Pass(**row) for row in data["passes"]),
        biggest=tuple(Big(**row) for row in data["biggest"]),
        notable=tuple(Big(**row) for row in data["notable"]),
        hunt=tuple(Clue(**row) for row in data["hunt"]),
    )
