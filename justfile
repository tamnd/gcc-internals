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
check: lint prose lessons claims tier0 dumpparse matrix-check test
    @echo "all green"

lint:
    ruff check .
    ruff format --check .

prose:
    {{py}} -m tools.prosecheck README.md CONTRIBUTING.md LICENSE.md GLOSSARY.md docs lessons blueprints containers corpora/programs gxplug

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

# Every film, redrawn from the recorded dumps, plus the page that shows them.
# These go to docs/assets/films and are committed, unlike the diagrams, because the book
# needs real files on disk. Commit whatever this changes.
films:
    {{py}} -m gxmanim film --index --open

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

# The four entries T06 reads. A script rather than a command line, because half of what it
# records is derived from a diff of two flag tables and then found by compiling fifty times.
# See the comment at the top of the script for what comes out.
corpus-t06:
    {{py}} lessons/t06-what-o2-actually-turns-on/record.py {{gcc}}

# The four targets T07 compares. Compiler Explorer, because nobody has four cross compilers
# on their laptop, and 16.1.0 on all four because that is the newest version the site has
# built for every one of them. A comparison with two variables in it is not a comparison, so
# x86-64 steps down from 16.2 here even though the rest of the book uses 16.2.
# This needs the network. Everything else T07 reads is already in l1-O2.
corpus-t07:
    {{py}} -m gxray record --backend ce --compiler-id cg161 --entry t07-x86-64 \
        --file corpora/programs/l1.c --dump tree-optimized --dump rtl-expand -O2 -g
    {{py}} -m gxray record --backend ce --compiler-id carm64g1610 --entry t07-aarch64 \
        --file corpora/programs/l1.c --dump tree-optimized --dump rtl-expand -O2 -g
    {{py}} -m gxray record --backend ce --compiler-id rv64-cgcc1610 --entry t07-riscv64 \
        --file corpora/programs/l1.c --dump tree-optimized --dump rtl-expand -O2 -g
    {{py}} -m gxray record --backend ce --compiler-id cppc64leg1610 --entry t07-power64le \
        --file corpora/programs/l1.c --dump tree-optimized --dump rtl-expand -O2 -g

# The three configurations T08 compares. Two through Compiler Explorer at 16.1.0, one from
# the local compiler, and the third one is not redundant: Apple reserves x18 as the platform
# register, so aarch64 Darwin allocates twenty nine general registers where aarch64 Linux
# allocates thirty, and the same program spills one more value. One dump each, because the
# ira dump already carries the costs, the live ranges, the conflicts, the pressure, the
# colouring trace and the disposition, and it is 600 KB on its own.
# The first two need the network.
corpus-t08:
    {{py}} -m gxray record --backend ce --compiler-id cg161 --entry t08-x86-64 \
        --file corpora/programs/t08-pressure.c --dump rtl-ira -O2
    {{py}} -m gxray record --backend ce --compiler-id carm64g1610 --entry t08-aarch64 \
        --file corpora/programs/t08-pressure.c --dump rtl-ira -O2
    {{py}} -m gxray record --entry t08-local --file corpora/programs/t08-pressure.c \
        --gcc {{gcc}} --dump rtl-ira -O2

# What T09 reads. Two flags here are doing more work than they look like they are.
# `-dp` is what makes the assembly say which machine description pattern emitted each line,
# and it writes that as a trailing comment, which is the first thing Compiler Explorer throws
# away. `--raw-asm` turns off the site's filters so the directives, the labels and those
# comments all survive, and `-g0` cancels the `-g` the site adds, which otherwise buries a
# forty line function under three hundred lines of `.debug_info`.
# The rtl-final dump is the other half of the join. Every insn in it carries a uid and a
# pattern name, and every instruction in the assembly carries the same uid, so a reader can
# walk from one to the other without being asked to take anything on trust.
# The first two need the network.
corpus-t09:
    {{py}} -m gxray record --backend ce --compiler-id carm64g1610 --raw-asm --entry t09-final \
        --file corpora/programs/l1.c --dump rtl-final -O2 -g0 -dp
    {{py}} -m gxray record --backend ce --compiler-id carm64g1610 --raw-asm --entry t09-sections \
        --file corpora/programs/t09-sections.c --dump rtl-final -O2 -g0 -dp
    {{py}} -m gxray record --entry t09-local --file corpora/programs/l1.c \
        --gcc {{gcc}} --dump rtl-final -O2 -dp

# The two recordings T10 reads. Both are L2 rather than L1, and that is the only interesting
# choice here: L1 has one function, so the interprocedural passes have nothing to do and the
# lesson that is supposed to show the whole pipeline would show a quarter of it with no work
# in it. L2 has a static helper that gets inlined, which is what puts einline on the trace.
# The first entry is the wide one: every tree dump, five named RTL dumps, the pass list at -O2
# and the assembly with -dp so the pattern names survive. The second is narrow and exists only
# for the ladder, which needs the lineno modifier on three dumps and the graph modifier on two.
# One recording cannot be both, because -lineno and plain are the same dump under one name.
corpus-t10:
    {{py}} -m gxray record --entry t10-whole --program l2 --gcc {{gcc}} \
        --dump tree-all --dump ipa-inline \
        --dump rtl-expand --dump rtl-combine --dump rtl-ira --dump rtl-reload --dump rtl-final \
        --pipeline="-O2" --asm="-O2 -dp" \
        -O2 -g
    {{py}} -m gxray record --entry t10-ladder --program l2 --gcc {{gcc}} \
        --dump tree-original-lineno --dump tree-ssa-lineno --dump tree-optimized-lineno \
        --dump rtl-expand --dump tree-ssa-graph --dump tree-optimized-graph \
        --asm="-O2 -g -dp" \
        -O2 -g

# Z01 is the one lesson that does not record a compilation, because it reads the compiler
# rather than anything a compiler produced. This cuts eighteen spans out of the pinned tree
# and writes them to corpora/source/z01.json, so a reader in Colab with no vendor/gcc still
# sees the real lines. It needs the submodule, and it is the only corpus recipe that does.
# The same spans are written again as citations inside record.py, so refcheck fails when one
# of them moves and this is the file you come back to fix.
corpus-z01:
    {{py}} lessons/z01-cpp-for-reading/record.py

# Z02 reads the compiler too, but the whole of it rather than eighteen spans. This counts
# every source file in the tree, lists the ports, works out which file defines each pass in
# passes.def, and writes the lot to corpora/layout/gcc.json. It also needs the submodule, and
# it takes about twenty seconds because it opens every .cc under gcc/ to find the pass table.
corpus-z02:
    {{py}} lessons/z02-where-things-are/record.py

# Every Tier 0 experiment, run out of the corpus and then out of the cached Compiler Explorer
# responses, and checked against each other. No network either way. See tools/tier0 for what
# the three kinds of experiment are and why a recorded one is compared byte for byte while a
# paired one is compared on shape.
tier0:
    {{py}} -m tools.tier0 check

# What is registered, what each experiment asks, and which lessons read it.
tier0-list:
    {{py}} -m tools.tier0 list

# Fetch the Compiler Explorer responses a new experiment needs. This is the only command in
# the project that talks to the live API, it is never run by CI, and what it writes under
# tools/cecache/store belongs in the same pull request as the experiment that needed it.
# Compiler Explorer is free and run by volunteers. Do not put this in a loop.
ce-refresh:
    {{py}} -m tools.tier0 refresh

# Every dump in the corpus read by the parser its name calls for, and the four numbers that
# come out compared against tools/dumpparse/baseline.json. Both parsers tolerate what they do
# not recognise rather than throwing, so something has to count what got tolerated. This is it.
dumpparse:
    {{py}} -m tools.dumpparse check

# The dumps the parsers understand least, worst first. Where to look for the next fix.
dumpparse-worst:
    {{py}} -m tools.dumpparse worst

# Write the baseline again. Run it after a parser change or a re-recorded corpus entry, read
# the diff, and commit it with the change that caused it.
dumpparse-record:
    {{py}} -m tools.dumpparse record

# Rebuild the generated sections of every blueprint from GCC's own def files.
blueprints:
    {{py}} -m tools.bpc build

blueprints-check:
    {{py}} -m tools.bpc check

# The blueprint pages of the site: the index, and one include page per document so there is
# one copy of every blueprint and not two. Reads the blueprints, not the pinned tree.
blueprint-pages:
    {{py}} -m tools.bpc pages

# The build matrix. What GCC gets built, how, and on what.
matrix:
    {{py}} -m tools.matrix jobs --on weekly --pretty

# One configuration, expanded, exactly the way the build sees it. `just matrix-show chk`.
matrix-show id:
    {{py}} -m tools.matrix show {{id}}

# Rewrite the table in containers/README.md from matrix.toml. The table is generated, so a
# hand edit to it is a hand edit the next run of this throws away.
matrix-table:
    {{py}} -m tools.matrix table

matrix-check:
    {{py}} -m tools.matrix table --check

# Build one image locally. You do not need to, everything pulls the published ones, but B01
# is a lesson about building GCC and a lesson nobody can follow is not a lesson.
image id:
    #!/usr/bin/env bash
    set -euo pipefail
    job=$({{py}} -m tools.matrix jobs --on weekly | {{py}} -c \
      'import json,sys; print(json.dumps(next(j for j in json.load(sys.stdin)["include"] if j["id"]=="{{id}}" and j["arch"]=="amd64")))')
    read -r file tag flags cflags mk inst smoke pkgs < <({{py}} -c \
      'import json,shlex,sys; j=json.loads(sys.argv[1]); print(*(shlex.quote(j[k]) for k in ("dockerfile","tag","flags","cflags","make","install","smoke","packages")))' "$job")
    eval docker build -f "containers/$file" \
      --build-arg GCC_TAG="$tag" \
      --build-arg CONFIGURE_FLAGS="$flags" \
      --build-arg CFLAGS_FOR_GCC="$cflags" \
      --build-arg MAKE_TARGET="$mk" \
      --build-arg INSTALL_TARGET="$inst" \
      --build-arg CONFIG_ID="{{id}}" \
      --build-arg SMOKE="$smoke" \
      --build-arg EXTRA_PACKAGES="$pkgs" \
      -t "gcc-internals/{{id}}" .

# Build gxplug against {{gcc}}. Needs that compiler's plugin headers, which most
# distributions package separately. See gxplug/README.md.
plugin:
    make -C gxplug GCC={{gcc}}

# Which compiler, which headers, and what the two portability probes decided. The first
# thing to run when a build fails somewhere unfamiliar.
plugin-probe:
    make -C gxplug probe GCC={{gcc}}

# The guarantee: same program, compiled with and without the plugin, assembly compared byte
# for byte. If this fails, nothing built on gxplug can be trusted.
plugin-check:
    make -C gxplug check GCC={{gcc}}

# Write a stream for one file and say what is in it. `just plugin-run corpora/programs/l1.c`
plugin-run FILE OPT="-O2": plugin
    #!/usr/bin/env bash
    set -euo pipefail
    out=$(mktemp -t gxplug.XXXXXX)
    trap 'rm -f "$out" "$out.s"' EXIT
    {{gcc}} {{OPT}} -S -fplugin=./gxplug/gxplug.so \
      -fplugin-arg-gxplug-out="$out" {{FILE}} -o "$out.s"
    {{py}} - "$out" <<'PY'
    import sys
    from gxray import plug

    stream = plug.load(sys.argv[1])
    runs = stream.runs
    changed = [r for r in runs if r.changed]
    print(f"{len(stream.events)} events, {len(runs)} passes ran, {len(changed)} left a mark")
    print("functions:", ", ".join(stream.functions))
    print(f"{stream.seconds:.4f} seconds inside passes")
    for run in sorted(changed, key=lambda r: r.seconds or 0, reverse=True)[:10]:
        print(f"  {run.seconds or 0:8.6f}  {run.name}")
    PY

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

build-site: island-check
    mkdocs build --strict -f site/mkdocs.yml

# A syntax error in island.js fails no build. The page renders, the button renders, and
# pressing it does nothing, which is the worst way to find out.
island-check:
    node --check docs/assets/island.js

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
