"""One API, three backends.

This is the load bearing decision in the whole project. A notebook cell does not know
whether there is a local compiler behind it, a web service, or a directory of dumps
recorded months ago:

    gcc = gxray.local("gcc-16")       # Tier 1, a compiler on this machine
    gcc = gxray.ce("cg162")           # Tier 0, works from a browser
    gcc = gxray.corpus("l1-O2")       # Tier 0 offline, nothing needed at all

    r = gcc.compile(gxray.L1, "-O2", dumps=["tree-ssa"])
    r.dump("tree-ssa").only().blocks[2].stmts

Without this, every lesson would be written twice and the browser version would rot.
With it, the same eight lines are the browser experience, the local experience and the CI
regression test.

The backends do not have identical powers and pretending otherwise would be worse than
useless, so `Backend.capabilities` says what each one can do and the parts of the API that
a backend cannot serve raise rather than return something plausible.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from gxray import cfg, gimple, passes
from gxray.dumps import DumpFile, dump_flags, find_dumps, split_spec, split_stderr_dumps
from tools.cecache import Cache, request_key

CE_URL = "https://godbolt.org/api/compiler/{compiler}/compile"
CE_FILTERS = {
    "binary": False,
    "execute": False,
    "intel": True,
    "demangle": True,
    "labels": True,
    "libraryCode": True,
    "directives": True,
    "commentOnly": True,
    "trim": False,
}


class BackendError(RuntimeError):
    """Something the backend cannot do, said out loud rather than faked."""


@dataclass
class Result:
    """One compilation, whichever backend produced it."""

    source: str
    args: tuple[str, ...]
    backend: str
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    asm: str = ""
    dump_texts: dict[str, str] = field(default_factory=dict)
    dump_files: list[DumpFile] = field(default_factory=list)
    _parsed: dict[str, gimple.GimpleDump] = field(default_factory=dict, repr=False)
    _graphs: dict[str, dict[str, cfg.CFG]] = field(default_factory=dict, repr=False)

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def dump_keys(self) -> list[str]:
        return list(self.dump_texts)

    def dump_text(self, key: str) -> str:
        if key not in self.dump_texts:
            have = ", ".join(self.dump_texts) or "none"
            raise KeyError(f"no dump {key!r} in this result. Have: {have}")
        return self.dump_texts[key]

    def dump(self, key: str) -> gimple.GimpleDump:
        """The parsed dump. Parsed once and kept, because widgets ask repeatedly."""
        if key not in self._parsed:
            self._parsed[key] = gimple.parse(self.dump_text(key), name=key)
        return self._parsed[key]

    def cfgs(self, key: str) -> dict[str, cfg.CFG]:
        """Every control flow graph in a `-graph` dump, by function name.

        Asking for `tree-optimized` works as well as asking for `tree-optimized-graph`. The
        text dump of the same pass is usually sitting right next to it, and handing the dot
        parser a text dump gets you an empty graph rather than an error, which is the worst
        possible outcome, so the graph always wins here.
        """
        if not key.endswith("-graph") and f"{key}-graph" in self.dump_texts:
            key = f"{key}-graph"
        if key not in self._graphs:
            self._graphs[key] = cfg.parse(self.dump_text(key))
        return self._graphs[key]

    def cfg(self, key: str, function: str | None = None) -> cfg.CFG:
        """One function's control flow graph. The only function, unless you name one."""
        found = self.cfgs(key)
        if function is None:
            if len(found) != 1:
                names = ", ".join(found) or "none"
                raise KeyError(f"{key!r} holds {len(found)} functions, so name one. Have: {names}")
            return next(iter(found.values()))
        if function not in found:
            raise KeyError(f"no function {function!r} in {key!r}. Have: {', '.join(found)}")
        return found[function]

    @property
    def unparsed_count(self) -> int:
        """How many statements the parser did not recognise, across every dump here.

        CI records this across the corpus and fails when it rises. That is the whole drift
        detection story for the dump parsers.

        Graph dumps are skipped. They are dot files, not GIMPLE, and running the statement
        parser over one would report a few hundred unparsed lines and drown the number this
        is for.
        """
        return sum(len(self.dump(k).unparsed) for k in self.dump_texts if not k.endswith("-graph"))

    def __str__(self) -> str:
        state = "ok" if self.ok else f"failed ({self.returncode})"
        return f"{self.backend}: {state}, {len(self.dump_texts)} dump(s)"


class Backend:
    """What every backend has to be able to answer."""

    name = "backend"
    capabilities: frozenset[str] = frozenset()

    def compile(
        self, source: str, *args: str, dumps: list[str] | None = None, filename: str = "input.c"
    ) -> Result:
        """`filename` is the name the compiler sees, and only a backend with files can
        honour it. It matters because with `-lineno` that name is printed in front of every
        statement in the dump, and `input.c` is a poor thing for a lesson to quote."""
        raise NotImplementedError

    def can(self, capability: str) -> bool:
        return capability in self.capabilities

    def require(self, capability: str) -> None:
        if not self.can(capability):
            raise BackendError(
                f"the {self.name} backend cannot do {capability!r}. "
                f"It can do: {', '.join(sorted(self.capabilities)) or 'nothing'}."
            )

    def __str__(self) -> str:
        return self.name


class LocalBackend(Backend):
    """A `gcc-16` on this machine. Everything works and it is fast."""

    capabilities = frozenset(
        {"dumps", "all-dumps", "asm", "passes", "plugins", "named-dumps", "graph-dumps"}
    )

    def __init__(self, gcc: str = "gcc-16"):
        self.gcc = gcc
        self.name = f"local:{gcc}"

    @property
    def available(self) -> bool:
        return shutil.which(self.gcc) is not None

    def version(self) -> str:
        out = subprocess.run([self.gcc, "--version"], capture_output=True, text=True, check=False)
        return out.stdout.splitlines()[0] if out.stdout else "unknown"

    def target(self) -> str:
        out = subprocess.run(
            [self.gcc, "-dumpmachine"], capture_output=True, text=True, check=False
        )
        return out.stdout.strip() or "unknown"

    def compile(
        self, source: str, *args: str, dumps: list[str] | None = None, filename: str = "input.c"
    ) -> Result:
        with tempfile.TemporaryDirectory(prefix="gxray-") as tmp:
            tmpdir = Path(tmp)
            src = tmpdir / filename
            src.write_text(source, encoding="utf-8")
            asm_path = src.with_suffix(".s")

            # -o has to name the assembly file, because the dump base name follows -o.
            # Writing to /dev/null puts the dumps next to the input instead, which is a
            # trap that cost an afternoon once and is worth a comment.
            #
            # Both paths are relative and the run happens in the temporary directory, so
            # what GCC prints as the file name is `l1.c` rather than a path under /var that
            # is different on every run and belongs to nobody.
            cmd = [self.gcc, "-S", *args, *dump_flags(dumps or []), src.name, "-o", asm_path.name]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=tmpdir)

            found = find_dumps(tmpdir, base=filename)
            return Result(
                source=source,
                args=tuple(args),
                backend=self.name,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                asm=asm_path.read_text(encoding="utf-8") if asm_path.exists() else "",
                dump_texts={d.key: d.text for d in found},
                dump_files=found,
            )

    def pipeline(self, source: str, *args: str) -> passes.Pipeline:
        """The pass pipeline for these options, straight out of `-fdump-passes`."""
        r = self.compile(source, *args, "-fdump-passes")
        return passes.parse(r.stderr)


class CEBackend(Backend):
    """Compiler Explorer's public API. The whole reason Tier 0 needs nothing installed.

    The API is CORS open, so this works from a browser as well as from a terminal, which is
    what makes a compiler course runnable on a phone.

    It cannot write dump files, so dumps come back through `-fdump-...=stderr`. That has one
    consequence worth knowing: asking for a single named dump is exact, and asking for
    `tree-all` returns every dump concatenated with nothing between them. See
    `gxray.dumps.split_stderr_dumps` for what can and cannot be recovered from that.
    """

    capabilities = frozenset({"dumps", "asm", "named-dumps", "execute"})

    def __init__(self, compiler: str = "cg162", cache: Cache | None = None, lang: str = "c"):
        self.compiler = compiler
        self.lang = lang
        self.cache = cache if cache is not None else Cache()
        self.name = f"ce:{compiler}"

    def _send(self, source: str, arg_string: str) -> dict:
        body = json.dumps(
            {
                "source": source,
                "options": {"userArguments": arg_string, "filters": CE_FILTERS},
                "lang": self.lang,
                "allowStoreCodeDebug": True,
            }
        ).encode()
        req = urllib.request.Request(
            CE_URL.format(compiler=self.compiler),
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as fh:
                return json.loads(fh.read().decode())
        except urllib.error.URLError as exc:
            raise BackendError(f"Compiler Explorer request failed: {exc}") from exc

    def compile(
        self, source: str, *args: str, dumps: list[str] | None = None, filename: str = "input.c"
    ) -> Result:
        dumps = list(dumps or [])
        keys = [split_spec(spec)[0] for spec in dumps]
        for spec in keys:
            if spec.endswith("-all"):
                raise BackendError(
                    f"{spec!r} is not usable through this backend. Dumps arrive on stderr with "
                    "nothing separating them, so a name cannot be attached to a chunk. Ask for "
                    "the passes you want by name, or use the corpus backend."
                )
            if spec.endswith("-graph"):
                # `open_graph_file` in gcc/graph.cc calls fopen, always. There is no
                # `=stderr` form of a graph dump, so this is not a limit of the API.
                raise BackendError(
                    f"{spec!r} is not usable through this backend. GCC writes graph dumps to a "
                    ".dot file and never to stderr, and this backend has no files. Use the "
                    "corpus backend, which ships the graph dumps that were recorded."
                )

        arg_string = " ".join([*args, *dump_flags(dumps, to_stderr=True)])
        key = request_key(self.compiler, source, arg_string, CE_FILTERS)
        response = self.cache.fetch(key, lambda: self._send(source, arg_string))

        stderr = "\n".join(line.get("text", "") for line in response.get("stderr", []))
        asm = "\n".join(line.get("text", "") for line in response.get("asm", []))

        # One named dump means the whole of stderr is that dump, minus any real diagnostics.
        dump_texts = {keys[0]: stderr} if len(keys) == 1 else {}
        if len(keys) > 1:
            chunks = split_stderr_dumps(stderr)
            if len(chunks) == len(keys):
                dump_texts = dict(zip(keys, chunks, strict=True))
            else:
                raise BackendError(
                    f"asked for {len(keys)} dumps and stderr split into {len(chunks)} chunks, "
                    "so they cannot be paired safely. Ask for one dump at a time."
                )

        return Result(
            source=source,
            args=tuple(args),
            backend=self.name,
            returncode=response.get("code", 0),
            stdout="\n".join(line.get("text", "") for line in response.get("stdout", [])),
            stderr=stderr,
            asm=asm,
            dump_texts=dump_texts,
        )


class CorpusBackend(Backend):
    """Recorded dumps, shipped with the book. Needs nothing, not even a network.

    This is what Tier 0 falls back to when Compiler Explorer is unreachable, slow or rate
    limited, and it is what CI uses to prove every notebook still works offline. It only
    knows the answers somebody recorded, which is the whole point: it is deterministic.
    """

    capabilities = frozenset({"dumps", "all-dumps", "named-dumps", "asm", "graph-dumps"})

    def __init__(self, entry: str, root: Path | str | None = None):
        from gxray.corpus import CORPUS_ROOT

        self.entry = entry
        self.root = Path(root) if root else CORPUS_ROOT
        self.name = f"corpus:{entry}"

    def compile(
        self, source: str, *args: str, dumps: list[str] | None = None, filename: str = "input.c"
    ) -> Result:
        from gxray.corpus import load

        record = load(self.entry, root=self.root)
        wanted = [split_spec(spec)[0] for spec in dumps] if dumps else list(record.dump_texts)
        missing = [d for d in wanted if d not in record.dump_texts and not d.endswith("-all")]
        if missing:
            raise BackendError(
                f"the corpus entry {self.entry!r} has no dump named {missing[0]!r}. "
                f"It has: {', '.join(sorted(record.dump_texts)) or 'none'}. "
                "Recorded dumps are whatever somebody recorded."
            )

        selected = (
            record.dump_texts
            if any(d.endswith("-all") for d in wanted)
            else {k: v for k, v in record.dump_texts.items() if k in wanted}
        )
        return Result(
            source=record.source,
            args=tuple(record.args),
            backend=self.name,
            returncode=0,
            asm=record.asm,
            dump_texts=selected,
        )


def local(gcc: str = "gcc-16") -> LocalBackend:
    """Tier 1: a compiler on this machine."""
    return LocalBackend(gcc)


def ce(compiler: str = "cg162", cache: Cache | None = None) -> CEBackend:
    """Tier 0: Compiler Explorer. Works from a browser, needs nothing installed."""
    return CEBackend(compiler, cache=cache)


def corpus(entry: str, root: Path | str | None = None) -> CorpusBackend:
    """Tier 0 offline: dumps recorded earlier and shipped with the book."""
    return CorpusBackend(entry, root=root)
