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
    {{py}} -m tools.prosecheck README.md lessons blueprints

test:
    {{py}} -m pytest -q

# Which GCC are we actually looking at.
banner:
    {{py}} -m gxray banner --gcc {{gcc}}

# Dump everything GCC will tell you about one file. Writes into a temp dir and lists it.
dumps FILE="corpora/programs/l1.c" OPT="-O2":
    {{py}} -m gxray dumps {{FILE}} {{OPT}} --gcc {{gcc}}

# The pass list that actually ran, which is not the same as the pass list in passes.def.
passes FILE="corpora/programs/l1.c" OPT="-O2":
    {{py}} -m gxray passes {{FILE}} {{OPT}} --gcc {{gcc}}

# Regenerate the recorded dumps that Tier 0 falls back on when the network is gone.
corpus:
    {{py}} -m gxray corpus build --gcc {{gcc}}

# Rebuild the generated sections of every blueprint from GCC's own def files.
blueprints:
    {{py}} -m tools.bpc build

blueprints-check:
    {{py}} -m tools.bpc check

# Resolve every path:line@tag citation in the prose against the pinned tree.
refcheck:
    {{py}} -m tools.refcheck check

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
