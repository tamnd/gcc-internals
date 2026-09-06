"""What GCC's C parser saw, read back from the diagnostics it printed.

    from gxray import cparse

    rec = cparse.load("f03")
    one = rec.case("brace")

    one.text                       # the message a person sees, carets and all
    one.errors[0].message          # "expected ';' before '}' token"
    one.errors[0].at               # line 3, column 11, which is not where '}' is
    one.errors[0].fixes[0].insert  # ";"

A C parser is hard to look at. It has no dump flag, it produces no file, and the tree it
builds is F04's subject rather than this one's. What it does produce, on every program that
is wrong, is a diagnostic, and a GCC diagnostic is a far more detailed readout of parser
state than it looks. It carries the message, the token the parser was looking at, the place
it thinks the mistake is, a suggested repair, and sometimes a second location it wants you
to compare against. Those five things are enough to reconstruct what the parser knew.

GCC 16 will print them as SARIF, which is a machine readable format meant for static
analysis tools, and this module reads that. Only the `results` array is kept. The rest of a
SARIF log is the absolute path of the compiler, the arguments it was invoked with and two
timestamps, none of which would be the same twice and all of which would make a recording
that cannot be compared with another recording.

One wrinkle worth knowing about, because it shows up in the recorded text. SARIF message
strings use braces for placeholders, so GCC doubles any brace in a message before writing
it out. `expected ';' before '}' token` arrives as `expected ';' before '}}' token`, and
`undouble` puts it back. The plain text GCC prints alongside is not affected.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "corpora" / "diag"


class CParseError(Exception):
    """Something asked of a recording that the recording cannot answer."""


# ---------------------------------------------------------------------------
# The two tables the C front end decides messages with
# ---------------------------------------------------------------------------

#: Where a fix-it hint for a missing token goes, transcribed from
#: `get_missing_token_insertion_kind` at gcc/c-family/c-common.cc:9973. Seven token types
#: get a hint at all. An opening bracket goes before the token the parser is looking at,
#: because `if( flag)` is not what anybody meant to write. Everything else goes after the
#: token before it, which is why the caret in `expected ';' before '}' token` lands on the
#: line above the brace. Every other token type gets no hint and no caret move.
INSERTION: dict[str, str] = {
    "[": "before",
    "(": "before",
    ")": "after",
    "]": "after",
    ";": "after",
    ",": "after",
    ":": "after",
}


@dataclass(frozen=True)
class Suffix:
    """One branch of `c_parse_error`, which is the sentence factory for the whole front end.

    A parser function passes in a complaint like `expected ';'` and nothing else. The rest
    of the sentence is chosen here, by the type of the token the parser is looking at and by
    nothing else. That is why the same mistake reads eight different ways depending on what
    happens to come after it.
    """

    #: What GCC appends, with its own format directives left in, exactly as the source has it.
    text: str
    #: What that turns into once printed, as a pattern anchored to the end of the sentence.
    #: Two of these overlap, which is a fact about the messages and not a defect here.
    shows: str
    #: The token types that select it, spelled as `cpplib.h` spells them. Empty on the last
    #: branch, which is a range test rather than a list.
    types: tuple[str, ...]
    #: What a reader would call the thing, for a table in a notebook.
    about: str

    def matches(self, message: str) -> bool:
        return re.search(self.shows, message) is not None


#: Every branch of `c_parse_error`, in source order, from gcc/c-family/c-common.cc:7003.
#: Thirteen of them, and the last is the one almost every punctuation mark lands in.
SUFFIXES: tuple[Suffix, ...] = (
    Suffix(" at end of input", r" at end of input$", ("CPP_EOF",), "the file ran out"),
    Suffix(
        " before %s'%c'",
        r" before (?:L|u|U|u8)?'.'$",
        ("CPP_CHAR", "CPP_WCHAR", "CPP_CHAR16", "CPP_CHAR32", "CPP_UTF8CHAR"),
        "a character constant you could print",
    ),
    Suffix(
        " before %s'\\x%x'",
        r" before (?:L|u|U|u8)?'\\x[0-9a-f]+'$",
        ("CPP_CHAR", "CPP_WCHAR", "CPP_CHAR16", "CPP_CHAR32", "CPP_UTF8CHAR"),
        "a character constant you could not",
    ),
    Suffix(
        " before user-defined character literal",
        r" before user-defined character literal$",
        (
            "CPP_CHAR_USERDEF",
            "CPP_WCHAR_USERDEF",
            "CPP_CHAR16_USERDEF",
            "CPP_CHAR32_USERDEF",
            "CPP_UTF8CHAR_USERDEF",
        ),
        "a C++ thing the C parser can still be handed",
    ),
    Suffix(
        " before user-defined string literal",
        r" before user-defined string literal$",
        (
            "CPP_STRING_USERDEF",
            "CPP_WSTRING_USERDEF",
            "CPP_STRING16_USERDEF",
            "CPP_STRING32_USERDEF",
            "CPP_UTF8STRING_USERDEF",
        ),
        "the same, in string form",
    ),
    Suffix(
        " before string constant",
        r" before string constant$",
        ("CPP_STRING", "CPP_WSTRING", "CPP_STRING16", "CPP_STRING32", "CPP_UTF8STRING"),
        "a string, whose text is not quoted back at you",
    ),
    Suffix(" before numeric constant", r" before numeric constant$", ("CPP_NUMBER",), "a number"),
    Suffix(
        " before %qE",
        r" before '[A-Za-z_$][A-Za-z_$0-9]*'$",
        ("CPP_NAME",),
        "an identifier, which is quoted back at you",
    ),
    Suffix(" before %<#pragma%>", r" before '#pragma'$", ("CPP_PRAGMA",), "a pragma"),
    Suffix(
        " before end of line", r" before end of line$", ("CPP_PRAGMA_EOL",), "the end of a pragma"
    ),
    Suffix(
        " before %<decltype%>", r" before 'decltype'$", ("CPP_DECLTYPE",), "a token only C++ makes"
    ),
    Suffix(" before %<#embed%>", r" before '#embed'$", ("CPP_EMBED",), "a C23 directive"),
    Suffix(
        " before %qs token",
        r" before '.*' token$",
        (),
        "anything else, which is where punctuation lands",
    ),
)

#: The doubling SARIF does to braces, because `{` starts a placeholder in a SARIF message.
_DOUBLED = re.compile(r"([{}])\1")

#: A terminal colour escape. Compiler Explorer runs GCC with colour turned on, so a
#: diagnostic that arrives from there has a dozen of these per line and would compare equal
#: to nothing.
_COLOUR = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def undouble(message: str) -> str:
    """Undo SARIF's brace doubling, so a recorded message reads as GCC printed it."""
    return _DOUBLED.sub(r"\1", message)


def plain(text: str) -> str:
    """A diagnostic with the colour taken out, which is what makes two of them comparable."""
    return _COLOUR.sub("", text)


def suffixes_for(message: str) -> list[Suffix]:
    """Every branch of `c_parse_error` that could have produced the tail of this message.

    Matching on the printed sentence rather than on a token type, because the printed
    sentence is what a recording has, and it is also what a reader has. Usually the answer
    is one branch. It is two when the message ends in a single quoted character, because a
    one-letter identifier and a character constant print the same and no amount of care
    here can separate them.
    """
    return [one for one in SUFFIXES if one.matches(message)]


def suffix_for(message: str) -> Suffix | None:
    """The one branch that produced this message, or nothing if the message does not say."""
    found = suffixes_for(message)
    return found[0] if len(found) == 1 else None


# ---------------------------------------------------------------------------
# One diagnostic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Span:
    """A place in a file, the way a diagnostic carries one.

    Columns are one based and `end` is one past the last character, which is SARIF's
    convention and also the one the caret line follows: a span three columns wide prints
    `^~~`.
    """

    line: int
    column: int
    end: int = 0

    @property
    def width(self) -> int:
        return max(1, self.end - self.column)

    def __str__(self) -> str:
        return f"{self.line}:{self.column}" + (f"-{self.end}" if self.end else "")


@dataclass(frozen=True)
class Fix:
    """A repair GCC is confident enough to write out.

    `insert` is the text, and the span is where it goes. A fix-it with an empty `insert` is
    a deletion, which the C parser does not produce for a missing token but other passes do.
    """

    at: Span
    insert: str

    def __str__(self) -> str:
        return f"insert {self.insert!r} at {self.at}"


@dataclass(frozen=True)
class Diagnostic:
    """One thing GCC said, with everywhere it pointed while saying it."""

    level: str
    message: str
    at: Span
    #: The line of your program the caret sits under, as GCC quoted it back.
    snippet: str = ""
    #: The enclosing function, when GCC knew one. This is the `In function 'f':` line.
    function: str = ""
    fixes: tuple[Fix, ...] = ()
    #: Other places the same diagnostic pointed at. For a missing token this is the token
    #: the parser was actually looking at, which is usually not where the caret went.
    related: tuple[Span, ...] = ()

    @property
    def error(self) -> bool:
        return self.level == "error"

    @property
    def suffix(self) -> Suffix | None:
        """Which branch of `c_parse_error` chose the tail of this sentence, if it says."""
        return suffix_for(self.message)

    @property
    def suffixes(self) -> list[Suffix]:
        """Every branch that could have. More than one means the message is not telling."""
        return suffixes_for(self.message)

    @property
    def moved(self) -> bool:
        """Whether the caret is somewhere other than the token being complained about.

        True when the diagnostic carries a related location on a different line or column
        from the caret, which is what the swap in `maybe_suggest_missing_token_insertion`
        leaves behind.
        """
        return any((one.line, one.column) != (self.at.line, self.at.column) for one in self.related)

    def __str__(self) -> str:
        return f"{self.at}: {self.level}: {self.message}"


def parse_sarif(text: str) -> list[Diagnostic]:
    """Every result in a SARIF log, and nothing else from it.

    Raises if the text is not SARIF, rather than returning nothing, because a recorder that
    silently records zero diagnostics for a program that does not compile is a recorder that
    has stopped recording.
    """
    try:
        log = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CParseError(f"not a SARIF log: {exc}") from exc
    runs = log.get("runs")
    if not runs:
        raise CParseError("a SARIF log with no runs in it")
    return [_result(one) for one in runs[0].get("results", [])]


def _region(where: dict) -> Span:
    physical = where.get("physicalLocation", where)
    region = physical.get("region", {})
    return Span(
        line=region.get("startLine", 0),
        column=region.get("startColumn", 1),
        end=region.get("endColumn", 0),
    )


def _snippet(where: dict) -> str:
    physical = where.get("physicalLocation", where)
    context = physical.get("contextRegion", {})
    return context.get("snippet", {}).get("text", "").rstrip("\n")


def _result(raw: dict) -> Diagnostic:
    locations = raw.get("locations") or [{}]
    first = locations[0]
    logical = first.get("logicalLocations") or [{}]
    fixes = []
    for fix in raw.get("fixes", []):
        for change in fix.get("artifactChanges", []):
            for one in change.get("replacements", []):
                fixes.append(
                    Fix(
                        at=_region({"region": one.get("deletedRegion", {})}),
                        insert=one.get("insertedContent", {}).get("text", ""),
                    )
                )
    return Diagnostic(
        level=raw.get("level", "error"),
        message=undouble(raw.get("message", {}).get("text", "")),
        at=_region(first),
        snippet=_snippet(first),
        function=logical[0].get("fullyQualifiedName", ""),
        fixes=tuple(fixes),
        related=tuple(_region(one) for one in raw.get("relatedLocations", [])),
    )


# ---------------------------------------------------------------------------
# One program put through the parser
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    """A small program, what GCC said about it, and what GCC said in machine form.

    `text` and `diagnostics` are two renderings of one compilation, not two compilations.
    The first is what a person reads and the second is what this module can assert against,
    and having both is the only way a notebook can show the message and check it.
    """

    name: str
    about: str
    source: str
    text: str
    diagnostics: tuple[Diagnostic, ...] = ()
    #: The same program through an x86-64 Linux GCC of the same release, when the recorder
    #: asked for one. A parser is target independent and this is how that gets checked
    #: rather than asserted.
    elsewhere: str = ""

    @property
    def errors(self) -> list[Diagnostic]:
        return [one for one in self.diagnostics if one.level == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [one for one in self.diagnostics if one.level == "warning"]

    @property
    def clean(self) -> bool:
        return not self.diagnostics

    @property
    def agrees(self) -> bool:
        """Whether the other target said the same thing, ignoring trailing space."""
        if not self.elsewhere:
            return True
        return _flat(self.text) == _flat(self.elsewhere)

    def line(self, number: int) -> str:
        """One line of the program, numbered the way a diagnostic numbers it."""
        lines = self.source.split("\n")
        if not 1 <= number <= len(lines):
            raise CParseError(
                f"{self.name} has {len(lines)} lines, and line {number} was asked for"
            )
        return lines[number - 1]

    def under(self, one: Diagnostic) -> str:
        """The caret line, rebuilt from the span, the way GCC would draw it.

        Rebuilt rather than cut out of `text`, so that a notebook can point at a span GCC
        chose not to draw, which is how a related location gets shown next to the caret it
        was not printed with.
        """
        return " " * (one.at.column - 1) + "^" + "~" * (one.at.width - 1)

    def __str__(self) -> str:
        return f"{self.name}: {len(self.errors)} errors, {len(self.warnings)} warnings"


def _flat(text: str) -> list[str]:
    return [line.rstrip() for line in text.split("\n") if line.strip()]


# ---------------------------------------------------------------------------
# What the pinned tree says about itself
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Grammar:
    """The size of the C parser, counted rather than described.

    `functions` is every `c_parser_*` defined in `gcc/c/c-parser.cc`. The rest split that
    list by what the function is for, which is the number worth knowing: the file is mostly
    not about C.
    """

    functions: tuple[str, ...] = ()

    def named(self, *prefixes: str) -> list[str]:
        wanted = tuple(f"c_parser_{p}" for p in prefixes)
        return sorted(one for one in self.functions if one.startswith(wanted))

    @property
    def dialects(self) -> dict[str, list[str]]:
        """The parser functions grouped by which language they are for."""
        groups = {
            "OpenMP": self.named("omp"),
            "OpenACC": self.named("oacc"),
            "Objective-C": self.named("objc"),
            "transactional memory": self.named("transaction"),
        }
        spoken = {name for names in groups.values() for name in names}
        return {"C": sorted(set(self.functions) - spoken), **groups}

    def __len__(self) -> int:
        return len(self.functions)


@dataclass(frozen=True)
class Lookahead:
    """Every place the parser looks past the token in front of it.

    `depths` counts calls to `c_parser_peek_nth_token` by the constant they pass, which is
    the only way the parser can reach past the second token. `peeks` and `seconds` are the
    two cheap helpers, counted for scale rather than for detail.
    """

    peeks: int = 0
    seconds: int = 0
    depths: dict[int, int] = field(default_factory=dict)
    #: The buffer in `struct c_parser`, which is the hard limit while parsing C.
    slots: int = 0

    @property
    def deepest(self) -> int:
        return max(self.depths) if self.depths else 2


@dataclass
class Recording:
    """One run of the F03 recorder."""

    recorded: str
    compiler: str
    target: str
    cases: dict[str, Case]
    grammar: Grammar
    lookahead: Lookahead

    def case(self, name: str) -> Case:
        if name not in self.cases:
            have = ", ".join(sorted(self.cases))
            raise CParseError(f"no case called {name!r}. There is: {have}")
        return self.cases[name]

    def __getitem__(self, name: str) -> Case:
        return self.case(name)

    def __iter__(self):
        return iter(self.cases.values())

    def __len__(self) -> int:
        return len(self.cases)


def load(name: str = "f03", root: Path | str | None = None) -> Recording:
    target = Path(root or CORPUS) / f"{name}.json"
    if not target.is_file():
        raise CParseError(f"{target} is not there. Run lessons/f03-four-tokens/record.py.")
    raw = json.loads(target.read_text(encoding="utf-8"))
    return Recording(
        recorded=raw["recorded"],
        compiler=raw["compiler"],
        target=raw["target"],
        cases={
            key: Case(
                name=key,
                about=one["about"],
                source=one["source"],
                text=one["text"],
                diagnostics=tuple(_stored(x) for x in one.get("diagnostics", [])),
                elsewhere=one.get("elsewhere", ""),
            )
            for key, one in raw["cases"].items()
        },
        grammar=Grammar(functions=tuple(raw["grammar"]["functions"])),
        lookahead=Lookahead(
            peeks=raw["lookahead"]["peeks"],
            seconds=raw["lookahead"]["seconds"],
            depths={int(k): v for k, v in raw["lookahead"]["depths"].items()},
            slots=raw["lookahead"]["slots"],
        ),
    )


def _stored(raw: dict) -> Diagnostic:
    return Diagnostic(
        level=raw["level"],
        message=raw["message"],
        at=Span(*raw["at"]),
        snippet=raw.get("snippet", ""),
        function=raw.get("function", ""),
        fixes=tuple(Fix(at=Span(*one["at"]), insert=one["insert"]) for one in raw.get("fixes", [])),
        related=tuple(Span(*one) for one in raw.get("related", [])),
    )


def stored(one: Diagnostic) -> dict:
    """A diagnostic as the corpus keeps it, which is the inverse of `_stored`."""
    out: dict = {
        "level": one.level,
        "message": one.message,
        "at": [one.at.line, one.at.column, one.at.end],
    }
    if one.snippet:
        out["snippet"] = one.snippet
    if one.function:
        out["function"] = one.function
    if one.fixes:
        out["fixes"] = [
            {"at": [f.at.line, f.at.column, f.at.end], "insert": f.insert} for f in one.fixes
        ]
    if one.related:
        out["related"] = [[s.line, s.column, s.end] for s in one.related]
    return out


__all__ = [
    "CORPUS",
    "INSERTION",
    "SUFFIXES",
    "CParseError",
    "Case",
    "Diagnostic",
    "Fix",
    "Grammar",
    "Lookahead",
    "Recording",
    "Span",
    "Suffix",
    "load",
    "parse_sarif",
    "plain",
    "stored",
    "suffix_for",
    "suffixes_for",
    "undouble",
]
