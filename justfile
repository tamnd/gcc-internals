# Everything this project does, in one place. Run `just` for the list.
#
# Nothing here needs a GCC built from source. The commands that do say so.

gcc := env_var_or_default("GXRAY_GCC", "gcc-16")
py  := "python3"

default:
    @just --list --unsorted

# Set up a virtualenv with the toolkit and the dev tools in it.
setup:
    {{py}} -m venv .venv
    .venv/bin/pip install -qe ".[dev]"
    @echo "activate with: source .venv/bin/activate"

# Everything CI runs on a push, in the order CI runs it.
check: lint prose lessons claims test
    @echo "all green"

lint:
    ruff check .
    ruff format --check .

prose:
    {{py}} -m tools.prosecheck README.md CONTRIBUTING.md LICENSE.md docs lessons blueprints corpora/programs

test:
    {{py}} -m pytest -q

# Which GCC are we actually looking at.
banner:
    {{py}} -m gxray banner --gcc {{gcc}}

# Every dump one file produces, in the order the passes ran.
dumps FILE="corpora/programs/l1.c" OPT="-O2":
    {{py}} -m gxray dumps --file {{FILE}} --gcc {{gcc}} {{OPT}}

# The pass list that actually ran, which is not the pass list in passes.def.
passes FILE="corpora/programs/l1.c" OPT="-O2":
    {{py}} -m gxray passes --file {{FILE}} --gcc {{gcc}} {{OPT}}

# Which programs the driver would run for these flags, without running any of them.
chain FILE="corpora/programs/l1.c" OPT="-O2":
    {{py}} -m gxray chain --file {{FILE}} --gcc {{gcc}} {{OPT}}

# Where an SSA name comes from and everywhere it goes.
web NAME="s_1" FILE="corpora/programs/l1.c" OPT="-O2":
    {{py}} -m gxray web --name {{NAME}} --file {{FILE}} --gcc {{gcc}} {{OPT}}

# A page with every widget on it, built from the recorded dumps. No compiler, no network.
widgets:
    {{py}} -m gxwidgets demo --open

# Every diagram, redrawn from the recorded dumps, plus a contact sheet to look at them on.
diagrams:
    {{py}} -m gxmanim draw --index --open

# The hand composed Excalidraw scenes, the ones that explain an idea rather than show a dump.
lesson-diagrams:
    #!/usr/bin/env bash
    set -euo pipefail
    for f in lessons/*/diagram.py; do {{py}} "$f"; done

# Regenerate the recorded dumps that Tier 0 falls back on when the network is gone.
# -g and the lineno modifier are what put a source location on every statement, which is
# the only thing joining GENERIC to GIMPLE to RTL to the assembly. The graph modifier writes
# a .dot beside the text dump, and that is the only place the real CFG edges exist.
corpus:
    {{py}} -m gxray record --program l1 --entry l1-O2 --gcc {{gcc}} \
        --dump tree-original-lineno --dump tree-ssa-lineno \
        --dump tree-optimized-lineno --dump rtl-expand \
        --dump tree-ssa-graph --dump tree-optimized-graph \
        -O2 -g

# The driver chains T01 reads. One entry per invocation the lesson shows, keyed on the exact
# flags, because the whole point of the lesson is that the chain changes with them.
corpus-t01:
    {{py}} -m gxray record --entry t01-driver --file corpora/programs/l1.c --gcc {{gcc}} \
        --dump tree-optimized \
        --chain="-O2 -E" --chain="-O2 -S" --chain="-O2 -c" --chain="-O2" --chain="-O0 -c" \
        -O2

# The same source on a differently configured GCC 16.2, which is the last section of T01.
# This one needs the network, and it is the only corpus entry that does.
corpus-t01-ce:
    {{py}} -m gxray record --backend ce --entry t01-driver-ce --file corpora/programs/l1.c \
        --dump tree-optimized --chain="-O2" -O2

# The gimplification bench T03 reads. -O0 so that nothing runs after gimplification and what
# comes out is the front end's work and nothing else, and the gimple dump rather than the
# optimized one because the whole lesson is about the shape GIMPLE arrives in.
corpus-t03:
    {{py}} -m gxray record --entry t03-bench --file corpora/programs/t03-bench.c --gcc {{gcc}} \
        --dump tree-original-lineno --dump tree-gimple-lineno \
        -O0 -g

# The pass tape T04 reads. Every tree dump of L1 at -O2, which is what fills the cells, plus
# the pass list at all five optimization levels, because the lesson is partly about how the
# list changes with the level and one level would not show that.
corpus-t04:
    {{py}} -m gxray record --entry t04-tape --program l1 --gcc {{gcc}} \
        --dump tree-all \
        --pipeline="-O0" --pipeline="-O1" --pipeline="-O2" --pipeline="-O3" --pipeline="-Os" \
        -O2 -g

# Rebuild the generated sections of every blueprint from GCC's own def files.
blueprints:
    {{py}} -m tools.bpc build

blueprints-check:
    {{py}} -m tools.bpc check

# The pinned GCC tree, about 1.3 GB shallow. Only refcheck needs it.
gcc-src:
    git submodule update --init --depth 1

# Resolve every path:line@tag citation in the prose against the pinned tree.
refcheck:
    {{py}} -m tools.refcheck check

# Rebuild the citation lockfile after adding a citation. Commit what changes.
refcheck-update:
    {{py}} -m tools.refcheck update

# Add the book build on top of the dev tools. Only needed for serve and build-site.
setup-site:
    .venv/bin/pip install -qe ".[dev,site]"

# Add a Jupyter kernel on top of the dev tools. Only needed for run-lessons.
setup-lessons:
    .venv/bin/pip install -qe ".[dev,lessons]"

# Serve the book locally. Islands are rebuilt on every edit, which takes a second or two.
serve:
    mkdocs serve -f site/mkdocs.yml

build-site:
    mkdocs build --strict -f site/mkdocs.yml

# Rebuild every lesson notebook from its build.py, and the course index from the lessons.
# The .ipynb files are generated, so this is the only thing that should ever write one.
build-lessons:
    {{py}} -m tools.nbbuild build

# Fail if a committed notebook or the index has drifted from what generates it.
lessons:
    {{py}} -m tools.nbbuild check

# Rebuild the claim ledger, which is every claim a lesson makes and the cell that proves it.
build-claims:
    {{py}} -m tools.nbbuild claims

claims:
    {{py}} -m tools.nbbuild verify

# Rebuild GLOSSARY.md from gxray/glossary.py, which is where the definitions actually live.
build-glossary:
    {{py}} -m gxray.glossary

# Run every lesson top to bottom in a real kernel. Needs the lessons extra.
# `just run-lessons --show` prints what each cell printed, which is the only way to catch a
# cell that succeeds and produces the wrong thing.
run-lessons *ARGS:
    {{py}} -m tools.nbbuild run {{ARGS}}

# Grade your own attempt at a boss fight.
grade ID:
    {{py}} lessons/{{ID}}/grade.py
