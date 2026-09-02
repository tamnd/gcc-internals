"""Every Tier 0 experiment, run both ways.

A Tier 0 experiment is one recorded compilation that a lesson reads. There are two ways to
get it. Offline, out of the corpus committed in this repository, which needs nothing at all
and is what a reader gets when the network is gone. Online, from Compiler Explorer, which is
a real GCC 16 answering a real request and is what the lesson is actually about.

The whole promise of Tier 0 is that those two agree. A reader who swaps `gxray.corpus` for
`gxray.ce` in the setup cell, which several lessons invite them to do, has to get the same
answer, or the recorded half of the book is a lie about the live half. This module is what
proves it on every push.

Three kinds of experiment, because three different things are provable.

`recorded` is an entry that came from Compiler Explorer in the first place. The check
re-sends the identical request, gets it out of the committed cache, and compares the dumps
byte for byte with what is in the corpus. Nothing is allowed to differ, and if something
does then either the cache or the corpus was edited by hand.

`paired` is an entry recorded against a local compiler. The same source and the same flags
go to Compiler Explorer, and what has to agree is the shape rather than the text: the
functions, the block count, the PHI count, the statement count and the multiset of
operators. Those are the facts a lesson about GIMPLE actually asserts, and they are the ones
that have no business changing between an aarch64 Darwin compiler and an x86-64 Linux one.
The text does change, in register names and in `-g` line notes, and pretending otherwise
would make the check fail for reasons nobody should care about.

`offline` is an entry with no Compiler Explorer counterpart, and every one of them carries a
written reason. There are three reasons and they are all limits of the API rather than
shortcuts taken here: it cannot split a `-all` dump, it cannot produce a graph dump at all,
and it always adds `-S`, so it can never show a driver chain that reaches the assembler.

CI never touches the live API. The online half runs against the committed cache with a
sender that raises, so a cache miss is a build failure and populating the cache is a
reviewed diff in a pull request rather than something that happens behind a green check.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from gxray import corpus_store, gimple
from gxray.driver import CE_FILTERS, CE_RAW, CEBackend
from gxray.dumps import dump_flags
from tools.cecache import DEFAULT_STORE, Cache, OfflineCache, request_key

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = Path(__file__).resolve().parent / "experiments.toml"

KINDS = ("recorded", "paired", "offline")

#: What a paired experiment can compare, and what every one of them compares unless it says
#: otherwise. `functions` is the set of function names in the dump, and the other four are
#: counted per function.
#:
#: All five hold for anything before the target-aware tree passes, and the ones that ask the
#: target are late and few. Two of them show up in this book's own corpus. `ivopts` picks an
#: induction variable by asking `targetm` which addressing modes exist, so a target with a
#: scaled index gets `MEM[base + iv * 8]` where one without it gets a pointer increment.
#: `widening_mul` builds a `WIDEN_MULT_PLUS_EXPR` only when `optab_handler` says the target
#: has a multiply-accumulate, so aarch64 gets one statement where x86-64 gets two.
#:
#: Neither changes the block structure, which is why an experiment that hits one of them
#: narrows `agree` rather than giving up. What it must not do is narrow it silently, so
#: narrowing requires a written reason.
COMPARATORS = ("functions", "blocks", "phis", "statements", "operators")


class Tier0Error(RuntimeError):
    """The registry says something that cannot be true."""


@dataclass
class Experiment:
    """One recorded compilation, and what can be proved about it."""

    id: str
    kind: str
    question: str
    lessons: list[str] = field(default_factory=list)
    corpus: str = ""
    compiler: str = ""
    dumps: list[str] = field(default_factory=list)
    agree: list[str] = field(default_factory=lambda: list(COMPARATORS))
    asm: bool = False
    raw_asm: bool = False
    chains: list[str] = field(default_factory=list)
    why: str = ""

    def check(self) -> list[str]:
        """Everything wrong with this entry, as sentences. Empty means it is usable."""
        problems = []
        if self.kind not in KINDS:
            problems.append(f"{self.kind!r} is not one of {', '.join(KINDS)}")
        if not self.question:
            problems.append("no question, so nobody can tell what this experiment is for")
        if self.kind == "offline":
            if not self.why:
                problems.append(
                    "an offline experiment has to say why it cannot be checked online, "
                    "because the default assumption is that it can be"
                )
            if self.compiler:
                problems.append("an offline experiment has no Compiler Explorer compiler")
        else:
            if not self.compiler:
                problems.append(f"a {self.kind} experiment needs a Compiler Explorer compiler id")
            if not self.dumps and not self.asm:
                problems.append(f"a {self.kind} experiment with nothing to compare proves nothing")
        if self.kind == "paired":
            unknown = [c for c in self.agree if c not in COMPARATORS]
            if unknown:
                problems.append(f"no such comparator: {', '.join(unknown)}")
            if not self.agree:
                problems.append("a paired experiment that agrees on nothing is not a check")
            if len(self.agree) < len(COMPARATORS) and not self.why:
                missing = [c for c in COMPARATORS if c not in self.agree]
                problems.append(
                    f"this experiment does not compare {', '.join(missing)} and does not say "
                    "why, and a comparison quietly turned off is worse than one never written"
                )
        if self.corpus and not corpus_store.path_for(self.corpus).exists():
            problems.append(f"no corpus entry {self.corpus!r}")
        return problems

    def record(self) -> corpus_store.Record:
        return corpus_store.load(self.corpus)

    def backend(self, cache: Cache | None = None) -> CEBackend:
        filters = CE_RAW if self.raw_asm else CE_FILTERS
        return CEBackend(self.compiler, cache=cache, filters=dict(filters))


def load(path: Path | str | None = None) -> list[Experiment]:
    """The registry, as objects. Raises if any entry is unusable."""
    p = Path(path or REGISTRY)
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    found = [Experiment(**row) for row in data.get("experiment", [])]

    seen: dict[str, str] = {}
    problems = []
    for x in found:
        problems += [f"{x.id}: {bad}" for bad in x.check()]
        if x.id in seen:
            problems.append(f"{x.id}: two experiments with the same id")
        seen[x.id] = x.corpus
    if problems:
        raise Tier0Error("\n".join(problems))
    return found


def shape(text: str) -> dict[str, dict]:
    """The facts about a GIMPLE dump that do not depend on the target.

    Block, PHI and statement counts and the operators used, per function. Not the text: an
    aarch64 dump and an x86-64 dump of the same source differ in ways that are real and
    uninteresting, and a comparison that trips over them would be turned off within a week.
    """
    dump = gimple.parse(text)
    return {
        name: {
            "blocks": len(f.blocks),
            "phis": sum(len(b.phis) for b in f.blocks.values()),
            "statements": len(f.code),
            "operators": sorted(s.operator or s.kind for s in f.code),
        }
        for name, f in dump.functions.items()
    }


def _describe(a: dict, b: dict, left: str, right: str, agree: list[str]) -> list[str]:
    """Where two shapes differ, said in a way that points at the function."""
    out = []
    if "functions" in agree:
        for name in sorted(set(a) - set(b)):
            out.append(f"{left} has a function {name!r} and {right} does not")
        for name in sorted(set(b) - set(a)):
            out.append(f"{right} has a function {name!r} and {left} does not")
    for name in sorted(set(a) & set(b)):
        for key in COMPARATORS:
            if key == "functions" or key not in agree:
                continue
            if a[name][key] != b[name][key]:
                out.append(f"{name}: {left} {key} {a[name][key]}, {right} {key} {b[name][key]}")
    return out


def offline(x: Experiment) -> list[str]:
    """Run the experiment the way a reader with no network gets it.

    An offline-only experiment is still an experiment, so it gets checked here even though
    there is nothing to compare it against. What it has to prove is that the entry a lesson
    opens is present, is not empty, and parses into functions rather than into silence.
    """
    if not x.corpus:
        return []
    try:
        record = x.record()
    except FileNotFoundError as exc:
        return [str(exc)]

    problems = []
    if not record.dump_texts:
        problems.append("the corpus entry has no dumps in it at all")
    for name in sorted(record.dump_texts):
        if not record.dump_texts[name]:
            problems.append(f"the {name} dump in the corpus entry is empty")
    for name in x.dumps:
        text = record.dump_texts.get(name)
        if not text:
            problems.append(f"the corpus entry has no {name} dump, or it is empty")
        elif name.startswith("tree-") and not shape(text):
            problems.append(f"the {name} dump parses to no functions at all")
    if x.asm and not record.asm:
        problems.append("the corpus entry has no assembly in it")
    return problems


def online(x: Experiment, cache: Cache | None = None) -> list[str]:
    """Run the experiment the way a reader in a browser gets it, from the cache.

    The cache refuses misses, so this never reaches the network. A miss means somebody added
    an experiment and did not run `just ce-refresh`, and saying that out loud is better than
    quietly fetching it in CI and making the build depend on a volunteer run service.
    """
    if x.kind == "offline":
        return []

    record = x.record()
    backend = x.backend(cache if cache is not None else OfflineCache())
    problems = []

    if x.kind == "recorded":
        # One request with every dump on it, which is what `gxray.corpus.record` did when the
        # entry was made. It matters. Asking for two dumps splits stderr into chunks and
        # asking for one takes the whole of stderr, and the two differ by a leading blank
        # line, so a byte comparison against a differently shaped request is a false alarm
        # every single time.
        result = _compile(backend, record, x.dumps)
        if isinstance(result, str):
            return [result]
        for name in x.dumps:
            if result.dump_texts.get(name, "") != record.dump_texts.get(name, ""):
                problems.append(
                    f"{name}: the cached response and the corpus entry are not the same text. "
                    "One of them was edited by hand, or the entry was recorded with different "
                    "flags than the registry says."
                )
        if x.asm and result.asm != record.asm:
            problems.append("the cached assembly and the corpus assembly are not the same text")
        return problems

    for name in x.dumps:
        result = _compile(backend, record, [name])
        if isinstance(result, str):
            problems.append(result)
            continue
        ours = record.dump_texts.get(name, "")
        theirs = result.dump_texts.get(name, "")
        bad = _describe(shape(ours), shape(theirs), "the corpus", "Compiler Explorer", x.agree)
        problems += [f"{name}: {line}" for line in bad]
    return problems


def _requests(x: Experiment) -> list[list[str]]:
    """The requests this experiment needs, as lists of dump names.

    A recorded experiment is one request, because that is how it was recorded. A paired one
    is a request per dump, because nothing about it needs the dumps to have travelled
    together and one at a time can never fail to split.
    """
    if x.kind == "offline":
        return []
    if x.kind == "recorded":
        return [list(x.dumps)]
    return [[name] for name in x.dumps]


def _compile(backend: CEBackend, record: corpus_store.Record, dumps: list[str]):
    """One request through the backend, or a sentence saying why there is not one."""
    try:
        return backend.compile(record.source, *record.args, dumps=dumps)
    except Exception as exc:  # noqa: BLE001 - reporting the message is the whole point
        return f"{', '.join(dumps) or 'the assembly'}: {exc}"


#: What `CEBackend.version` and `CEBackend.target` compile to ask the compiler who it is.
#: Both go through one `-###` request, so a compiler id and a filter set cost one cache entry
#: between them however many times they are asked.
PROBE = "int main(void){return 0;}"


def keys(x: Experiment) -> set[str]:
    """Every cache entry this experiment justifies the existence of.

    The requests it compares, plus the `-###` probe behind `version` and `target`, which
    `gxray record` sends for every entry it writes and which is therefore what makes
    re-recording a Compiler Explorer entry possible with the network off.
    """
    if x.kind == "offline":
        return set()
    record = x.record()
    filters = dict(CE_RAW if x.raw_asm else CE_FILTERS)
    out = {request_key(x.compiler, PROBE, "-###", filters)}
    for dumps in _requests(x):
        args = " ".join([*record.args, *dump_flags(dumps, to_stderr=True)])
        out.add(request_key(x.compiler, record.source, args, filters))
    for flags in x.chains:
        out.add(request_key(x.compiler, record.source, " ".join(["-###", *flags.split()]), filters))
    return out


def orphans(found: list[Experiment] | None = None, root=None) -> list[str]:
    """Cache entries nothing in the registry asks for, newest first is not the point.

    A committed response that no experiment and no recording recipe reads is 60 KB of
    somebody else's bandwidth kept forever for no reason, and nobody can tell years later
    whether deleting it breaks something. So the rule is that the registry accounts for the
    store exactly.
    """
    store = Path(root or DEFAULT_STORE)
    if not store.exists():
        return []
    wanted = set().union(*(keys(x) for x in found or load())) if (found or load()) else set()
    return sorted(p.stem for p in store.rglob("*.json") if p.stem not in wanted)


def coverage(found: list[Experiment] | None = None) -> list[str]:
    """What the registry has missed. This is what makes the word "every" mean something.

    Without it the registry is a list of experiments somebody remembered, and the first
    corpus entry added after this file was written would quietly go unchecked in both
    directions while the job stayed green.
    """
    found = found if found is not None else load()
    problems = []

    registered = {x.corpus for x in found if x.corpus}
    for entry in corpus_store.entries():
        if entry not in registered:
            problems.append(
                f"corpus entry {entry!r} is not in the registry, so nothing checks it. Add an "
                "experiment for it, or an offline one saying why it cannot be checked online."
            )

    read = {slug for x in found for slug in x.lessons}
    for d in sorted(p.name for p in (ROOT / "lessons").iterdir() if p.is_dir()):
        if d not in read:
            problems.append(f"lesson {d!r} has no experiment registered against it")

    for x in found:
        for slug in x.lessons:
            if not (ROOT / "lessons" / slug).is_dir():
                problems.append(f"{x.id}: no lesson {slug!r}")

    for key in orphans(found):
        problems.append(
            f"cache entry {key} is not asked for by anything in the registry. Either an "
            "experiment that needed it was deleted, or it was fetched while trying something "
            "out. Delete it, or add the experiment that reads it."
        )
    return problems


def refresh(x: Experiment, cache: Cache | None = None) -> list[str]:
    """Fetch whatever this experiment needs and is missing. The only thing that may send."""
    if x.kind == "offline":
        return []
    record = x.record()
    backend = x.backend(cache)
    fetched = []

    def note(label, send):
        before = backend.cache.size
        send()
        if backend.cache.size > before:
            fetched.append(label)

    for dumps in _requests(x):
        note(
            ", ".join(dumps) or "the assembly",
            lambda d=dumps: backend.compile(*[record.source, *record.args], dumps=d),
        )
    # One request answers both, and `gxray record` needs it to write an entry offline.
    note("the version and target probe", backend.version)
    for flags in x.chains:
        note(f"the chain for {flags}", lambda f=flags: backend.chain(record.source, *f.split()))
    return fetched
