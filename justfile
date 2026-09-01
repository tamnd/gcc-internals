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
check: lint prose test
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

# Where an SSA name comes from and everywhere it goes.
web NAME="s_1" FILE="corpora/programs/l1.c" OPT="-O2":
    {{py}} -m gxray web --name {{NAME}} --file {{FILE}} --gcc {{gcc}} {{OPT}}

# A page with every widget on it, built from the recorded dumps. No compiler, no network.
widgets:
    {{py}} -m gxwidgets demo --open

# Every diagram, redrawn from the recorded dumps, plus a contact sheet to look at them on.
diagrams:
    {{py}} -m gxmanim draw --index --open

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

# Serve the book locally.
serve:
    mkdocs serve -f site/mkdocs.yml

build-site:
    mkdocs build -f site/mkdocs.yml

# Scaffold a lesson with all nine blocks, so the structure is never assembled by hand.
new-lesson ID:
    {{py}} tools/new_lesson.py {{ID}}

# Grade your own attempt at a boss fight.
grade ID:
    {{py}} lessons/{{ID}}/grade.py
