"""Drive GCC and parse everything it emits.

    import gxray

    gcc = gxray.local("gcc-16")
    r = gcc.compile(gxray.L1, "-O2", dumps=["tree-ssa"])
    f = r.dump("tree-ssa").only()

    f.blocks[2].stmts          # the statements in <bb 2>
    f.ssa_web("s_1")           # where s_1 comes from and everywhere it goes

Swap `gxray.local` for `gxray.ce` and the same code runs in a browser against Compiler
Explorer. Swap it for `gxray.corpus` and it runs with no network at all.

Note that `gxray.corpus` is the factory that makes a backend. The module that reads and
writes recorded dumps is `gxray.corpus_store`, and it is spelled differently on purpose,
because a notebook wants the short name for the thing it actually calls.
"""

from gxray import (
    asm,
    bootstrap,
    build,
    chain,
    configure,
    dumps,
    gimple,
    layout,
    locs,
    mdesc,
    options,
    passes,
    plug,
    regalloc,
    replay,
    rtl,
    source,
    toolchain,
)
from gxray import corpus as corpus_store
from gxray.build import banner
from gxray.driver import (
    Backend,
    BackendError,
    CEBackend,
    CorpusBackend,
    LocalBackend,
    Result,
    ce,
    corpus,
    local,
)
from gxray.programs import L0, L1, L2

__version__ = "0.1.0"

__all__ = [
    "L0",
    "L1",
    "L2",
    "Backend",
    "BackendError",
    "CEBackend",
    "CorpusBackend",
    "LocalBackend",
    "Result",
    "asm",
    "banner",
    "bootstrap",
    "build",
    "chain",
    "ce",
    "configure",
    "corpus",
    "corpus_store",
    "dumps",
    "gimple",
    "layout",
    "local",
    "locs",
    "mdesc",
    "options",
    "passes",
    "plug",
    "regalloc",
    "replay",
    "rtl",
    "source",
    "toolchain",
]
