"""Every film, rebuilt from the recorded corpus.

    python -m gxmanim film

Same rule as the diagrams next door. Nothing in here places a box or picks a colour. Every
shot is a `Scene` built by `gxmanim.mobjects` out of a recording under `corpora/`, so when
the pinned compiler moves, the films move with it.

A film is worth making when the thing being explained is an order rather than a shape. A
control flow graph is a shape and gets a diagram. Which block the renamer visits first is an
order, and a reader looking at the finished dump has no way to recover it. That is the test
each of these six had to pass:

- three hundred passes run, and the interesting fact is how few of them do anything
- the SSA renamer walks a function in dominator order, and the dump does not say so
- one machine runs out of registers three functions before the other one does
- one line of C picks up a lane at a time as it goes down the pipeline
- twelve insns become twelve lines of text, one pattern at a time
- one C expression at a time comes apart into GIMPLE

Each builder takes no arguments, loads its own recording and returns a `Film`. They are a
second or two each, which is why the command builds them one at a time and prints as it
goes rather than doing all six and then printing.
"""

from __future__ import annotations

from dataclasses import replace

from gxmanim import mobjects
from gxmanim.film import Film, Shot
from gxray import asm, cfg, corpus_store, gimple, locs, mdesc, passes, regalloc, tape
from gxray.locs import LEVELS

#: The functions in the T08 bench, smallest first. The names are the number of live values
#: the program was written to need, so the list is also the x axis of the film.
BENCH = ("p04", "p10", "p14", "p20", "p30")

#: The T08 targets, in the order the film shows them. x86-64 first because it is the one
#: that runs out, and a reader who sees it run out first has a reason to care what happens
#: on the second machine.
TARGETS = ("x86-64", "aarch64")

#: The T02 source lines worth a run down the ladder. Line 5 is a plain assignment, line 6 is
#: the loop header and is the busiest line in the file, and line 8 is `return s;`, which is
#: the one that vanishes before the assembly.
FACES = (5, 6, 8)

#: The T03 bench, in the order the file writes them, which is also least to most unreasonable.
EXPRESSIONS = ("flat", "nested", "deeper", "calls", "shortcircuit", "ternary", "compound")


def _gimple_dumps(record) -> dict[str, gimple.Function]:
    """Every dump in a recording that holds exactly one function with basic blocks in it.

    The same filter T04 uses. Three of the 140 dumps in that recording print something other
    than a function, and the GENERIC dump has a body with no blocks in it and is not GIMPLE,
    so none of the four belong on a GIMPLE tape.
    """
    found = {}
    for key, text in record.dump_texts.items():
        functions = list(gimple.parse(text).functions.values())
        if len(functions) == 1 and functions[0].blocks:
            found[key] = functions[0]
    return found


def pass_tape() -> Film:
    """Three hundred passes arriving one handful at a time.

    The still picture of this tape is in T04 and it makes the point on its own. What it
    cannot show is that the marks are not spread evenly. They come in two clusters, one
    where the function is being lowered into GIMPLE and one in the middle of the optimizers,
    and there is a long stretch of nothing on either side of them. Watching the tape fill up
    is the only way to see that without counting.
    """
    record = corpus_store.load("t04-tape")
    pipeline = passes.parse(record.pass_texts["-O2"])
    cells = tape.cells(pipeline, _gimple_dumps(record))

    shots = []
    was = 0
    for step in range(1, 11):
        upto = round(len(cells) * step / 10)
        so_far = cells[:upto]
        # The title already carries the running total, so the caption is about the handful
        # that just arrived. A tenth of the tape at a time is roughly twenty eight passes,
        # and how many of those twenty eight did anything is the number that keeps changing.
        arrived = cells[was:upto]
        marked = len([c for c in arrived if c.changed])
        shots.append(
            Shot(
                scene=mobjects.pass_tape(so_far, per_row=48),
                caption=(
                    f"Passes {was + 1} to {upto} just went on, and {marked} of those "
                    f"{len(arrived)} changed anything. The last one is {arrived[-1].name}."
                ),
                seconds=7.0,
            )
        )
        was = upto
    return Film(
        name="pass-tape",
        title="Three hundred passes, and most of them leave the function alone",
        alt=(
            "The pass tape for one small function at -O2 fills in a tenth at a time until all "
            "281 cells are on screen. The 25 cells that changed the IR arrive in two clusters. "
            "The first runs from the early lowering passes through to release_ssa, the second "
            "covers the main optimizer run from vrp1 to crited1, and there is a gap of about "
            "fifty passes between them where nothing moved at all. After tree-optimized the "
            "tape goes quiet for good, because everything past that point is RTL and there is "
            "no GIMPLE dump left for the tape to compare."
        ),
        shots=tuple(shots),
    )


def dominator_order() -> Film:
    """The order the renamer walks a function in, one block at a time.

    Every textbook says SSA construction walks the dominator tree, and every dump shows you
    the finished thing with no hint of an order in it. This lights one block at a time in
    the order the walk visits them, so the reason a phi ends up where it does is something
    you watch rather than something you are told.
    """
    record = corpus_store.load("t05-boss-O2")
    graph = cfg.parse(record.dump_texts["tree-ssa-graph"])["g"]
    idom = graph.dominators()

    children: dict[int, list[int]] = {}
    for block, parent in sorted(idom.items()):
        children.setdefault(parent, []).append(block)

    order: list[int] = []

    def walk(index: int) -> None:
        order.append(index)
        for child in children.get(index, []):
            walk(child)

    walk(cfg.ENTRY)

    shots = []
    for index in order:
        block = graph.blocks[index]
        parent = idom.get(index)
        if parent is None:
            says = "The walk starts here, with nothing defined and nothing renamed yet."
        elif index == cfg.EXIT:
            says = (
                "EXIT, and there is nothing in it. Everything the function computes has "
                "already been renamed by the time the walk arrives here."
            )
        else:
            says = (
                f"{block.name} hangs off {graph.blocks[parent].name}, so every name defined "
                "up there is still good in here."
            )
        scene = mobjects.cfg_view(graph, focus=index)
        # The graph is the same drawing in all nine shots, so the title `g, 9 blocks and 10
        # edges` would sit there unchanged for the whole film and say nothing. The one thing
        # that does change between shots is which block the walk is standing on.
        scene.title = f"{graph.function}, standing on {block.name}"
        shots.append(Shot(scene=scene, caption=says, seconds=7.5))
    return Film(
        name="dominator-order",
        title="Renaming a function, one block at a time, in dominator order",
        alt=(
            "The control flow graph of a nine block function, with one block lit at a time "
            "in the order an SSA renamer visits them. The walk goes ENTRY, then bb 2, then "
            "bb 7, then bb 3, where it fans out across the three blocks in the loop body "
            "before coming back for bb 8 and EXIT. That is neither the order the blocks are "
            "numbered in nor the order they are printed in the dump. Every block is reached "
            "only after the block that all paths to it have to go through, which is what "
            "makes it safe to rename in a single walk and is why the phi nodes end up at the "
            "top of bb 7."
        ),
        shots=tuple(shots),
    )


def pressure_ramp() -> Film:
    """The same five functions on two machines, and only one of them runs out.

    The still picture in T08 is one target at a time, and a reader who sees the x86-64 lane
    turn red has no way to tell whether that is the program's fault or the machine's. Here
    the ramp is built twice out of the same recording, so the second half is the answer to
    the first half.
    """
    ira = {
        target: regalloc.parse(corpus_store.load(f"t08-{target}").dump_texts["rtl-ira"])
        for target in TARGETS
    }
    rows = {name: {target: ira[target][name] for target in TARGETS} for name in BENCH}

    shots = []
    for target in TARGETS:
        for step in range(1, len(BENCH) + 1):
            name = BENCH[step - 1]
            alloc = rows[name][target]
            spilled = len(alloc.spilled)
            if spilled:
                went = f"{spilled} of them went to memory"
            else:
                went = "every one of them got a register"
            shots.append(
                Shot(
                    scene=mobjects.pressure_ramp({row: rows[row] for row in BENCH[:step]}, target),
                    caption=(
                        f"{name} keeps {alloc.peak()} values alive at once, and on {target} {went}."
                    ),
                    seconds=7.0,
                )
            )
    return Film(
        name="pressure-ramp",
        title="Where the registers run out, on two machines",
        alt=(
            "Five functions, each needing more values alive at once than the last, are added "
            "one lane at a time to a chart of register pressure. On x86-64, with fifteen "
            "registers to hand out, the lanes run off the end of the register file at the "
            "third function and the marks for values kept in memory start appearing. The "
            "chart then rebuilds for aarch64, which has thirty registers, and the same five "
            "functions fit until the very last one. Same source, same flags, same compiler, "
            "and the only thing that changed is how many registers the machine has."
        ),
        shots=tuple(shots),
        still=len(BENCH) - 1,
    )


def five_faces() -> Film:
    """One line of C picking up a lane at a time.

    Three lines, four lanes each. The last of the three is `return s;`, which has a lane at
    GENERIC and a lane at GIMPLE and then nothing at RTL and nothing in the assembly, and
    the empty lanes arriving is the whole point of running the film to the end.
    """
    record = corpus_store.load("l1-O2")
    function = gimple.parse(record.dump_texts["tree-optimized"]).only()
    ladder = locs.ladder(
        record.source,
        generic=record.dump_texts["tree-original"],
        gimple=record.dump_texts["tree-optimized"],
        rtl=record.dump_texts["rtl-expand"],
        asm=record.asm,
        function=function.name,
    )

    shots = []
    for line in FACES:
        rung = ladder.rung(line)
        for depth in range(1, len(LEVELS) + 1):
            level = LEVELS[depth - 1]
            found = len(rung.at(level))
            name = locs.LEVEL_NAMES[level]
            if found:
                says = f"{found} {name} for `{rung.source.strip()}`."
            else:
                says = f"Nothing at {name}. The line has run out of pipeline to go down."
            shots.append(
                Shot(
                    scene=mobjects.ir_ladder(replace(ladder, levels=LEVELS[:depth]), line),
                    caption=says,
                    seconds=6.0,
                )
            )
    return Film(
        name="five-faces",
        title="One line of C, growing a lane per level",
        alt=(
            "Three lines from a nine line C file each grow a lane at a time as they go down "
            "the pipeline, from GENERIC to GIMPLE to RTL to the assembly. The assignment on "
            "line 5 keeps roughly the same amount of work at every level. The loop header on "
            "line 6 is one line of C and picks up six pieces of RTL and six instructions. The "
            "return on line 8 has something at GENERIC and something at GIMPLE and then two "
            "empty lanes, because by the time the compiler is choosing instructions the value "
            "is already sitting in the register the function returns in."
        ),
        shots=tuple(shots),
        # The loop header with all four lanes on it, which is the fullest the ladder ever
        # gets. The last shot is `return s;` with two empty lanes, and a poster frame with
        # two empty lanes on it looks like the drawing failed rather than like the point.
        still=len(LEVELS) * 2 - 1,
    )


def emit_path() -> Film:
    """Every insn in a small function taking the same four steps out to text.

    T09 draws this chain once, for the add. Drawing it twelve times is a different argument:
    the chain never changes. The same four cards, the same order, the same two places the
    middle two come from, for a move and a compare and a branch and a return.
    """
    record = corpus_store.load("t09-final")
    listing = asm.parse(record.asm)
    machine = mdesc.load_extract("aarch64")["patterns"]

    shots = []
    for line in listing:
        if not line.annotated:
            continue
        pattern = machine.get(line.pattern)
        text = str(line).split("  [")[0].strip()
        where = pattern["citation"] if pattern else "a pattern not in the extract"
        # The file position rather than the insn number, because `mov w0, 0` is printed
        # twice by two different insns and the caption is the only line that can tell a
        # reader which of the two they are looking at.
        shots.append(
            Shot(
                scene=mobjects.emit_path(line, pattern),
                caption=(
                    f"Line {line.number} of the file. `{text}` came out of {line.pattern}, "
                    f"which is at {where}."
                ),
                seconds=6.0,
            )
        )
    return Film(
        name="emit-path",
        title="Twelve insns, twelve lines of assembly, one path",
        alt=(
            "Each of the twelve real instructions in a small aarch64 function is followed "
            "down the same chain, from the RTL insn, to the machine description pattern that "
            "matched it, to the alternative in that pattern the register allocator picked, to "
            "the template string, and out to the line of text in the file. Moves, compares, "
            "branches and returns all take the same path. The two branches and the two "
            "returns come out three cards long instead of five, because their patterns have "
            "no alternatives to choose between and there is nothing to put on the missing "
            "cards. The only thing that changes from one insn to the next is which pattern "
            "in aarch64.md the middle of the chain came out of."
        ),
        shots=tuple(shots),
        # The add, which is the one T09 draws as a still and the only one in the function
        # where every card in the chain has something interesting on it.
        still=next(n for n, s in enumerate(shots) if "addsi3" in s.caption),
    )


def gimple_flattening() -> Film:
    """Seven C expressions, each taken apart into three address statements.

    The bench was written so that the only thing differing between the functions is the
    shape of the expression, which makes the sequence a ramp: one operation, two, four, a
    pair of calls, a short circuit, a conditional, and an assignment buried inside a
    multiply. Watching the GIMPLE lane get longer while the C lane stays one line is what
    gimplification is.
    """
    record = corpus_store.load("t03-bench")

    shots = []
    for name in EXPRESSIONS:
        ladder = replace(
            locs.ladder(
                record.source,
                generic=record.dump_texts["tree-original"],
                gimple=record.dump_texts["tree-gimple"],
                function=name,
            ),
            levels=("generic", "gimple"),
        )
        rung = next(
            r for r in ladder.rungs if r.at("generic") and r.source.strip().startswith("return")
        )
        statements = len(rung.at("gimple"))
        shots.append(
            Shot(
                scene=mobjects.ir_ladder(ladder, rung.line),
                caption=(
                    f"{name}: one expression in, {statements} GIMPLE "
                    f"{'statement' if statements == 1 else 'statements'} out."
                ),
                seconds=9.0,
            )
        )
    return Film(
        name="gimple-flattening",
        title="Seven C expressions, taken apart",
        alt=(
            "Seven functions from the same file, each one line of C returning a different "
            "shape of expression, are shown with what gimplification made of them. The first "
            "is a single addition and comes out as two statements. Each one after it is a "
            "little less reasonable, and the lane of GIMPLE statements underneath gets "
            "longer while the line of C above it stays one line. The worst of them puts "
            "seven operators in one expression and comes out as eight statements in a row, "
            "and not one statement anywhere in the film has two operators in it."
        ),
        shots=tuple(shots),
        # `deeper`, one line of C and eight GIMPLE statements, which is the widest gap in
        # the bench between what the programmer wrote and what the compiler got.
        still=EXPRESSIONS.index("deeper"),
    )


#: Every film, by the name its file gets. Ordered the way the course meets them, so the
#: contact sheet reads top to bottom like the lessons do.
BUILDERS = {
    "five-faces": five_faces,
    "gimple-flattening": gimple_flattening,
    "pass-tape": pass_tape,
    "dominator-order": dominator_order,
    "pressure-ramp": pressure_ramp,
    "emit-path": emit_path,
}


#: Which lesson each film belongs beside, and where that lesson's notebook lives. A film
#: with no lesson to sit next to is a film nobody asked for, so this covers all six.
GOES_WITH = {
    "five-faces": ("T02", "t02-five-faces/t02"),
    "gimple-flattening": ("T03", "t03-gimple-is-c-with-the-fun-removed/t03"),
    "pass-tape": ("T04", "t04-three-hundred-and-ninety-five-passes/t04"),
    "dominator-order": ("T05", "t05-ssa-in-one-lesson/t05"),
    "pressure-ramp": ("T08", "t08-registers-are-a-lie-until-they-are-not/t08"),
    "emit-path": ("T09", "t09-the-last-mile/t09"),
}

#: Where the films live on disk, relative to the root of the repository. `docs` rather than
#: `build` because these are committed, and committed because the book needs real files and
#: because a generated file that regenerates byte for byte is one CI can check.
DIRECTORY = "docs/assets/films"

#: The page. Generated, like `GLOSSARY.md`, so the alt text on the page and the alt text in
#: the film cannot drift apart.
PAGE = "docs/films.md"

REPOSITORY = "https://github.com/tamnd/gcc-internals"

INTRO = """# The films

A diagram is for a shape and a film is for an order. A control flow graph is a shape, so it gets a picture. The order the SSA renamer walks that graph in is not a shape, and the finished dump does not record it anywhere, so it gets a film.

There are six. Each one runs between sixty and ninety seconds, loops forever, and is built out of the same recorded dumps the lessons and the diagrams are built from, so when the pinned compiler moves the films move with it. Rebuild them with `just films`, and look at the lot on one page with `python -m gxmanim film --index --open`.

They are animated SVG rather than video, which is a deliberate departure from the spec. This project has no runtime dependencies and encoding video needs some. `gxmanim` was already an SVG renderer, so a film is the renderer it already has plus a stylesheet. And an SVG is text, which means a film diffs, is reproducible byte for byte, and can be checked by CI against the corpus it was drawn from, none of which is true of a WebM.

Every film degrades to one whole readable shot when animation is off or when a reader has asked for no motion. The paragraph above each one is its description, and the image itself carries no alt text, because a screen reader that finds the same sentences twice reads them twice.

This page is generated by `python -m gxmanim film`. Edit `gxmanim/films.py` rather than editing here.
"""

#: Where a lesson links to when it wants to point at its film. The anchor is spelled out
#: rather than left to the heading, because the heading is the film's title and a title is
#: allowed to change without breaking six links.
ANCHOR = "https://tamnd.github.io/gcc-internals/films/#film-{name}"

SECTION = """
## {title} {{ #film-{name} }}

{alt}

![]({directory}/{name}.svg){{ loading=lazy }}

{shots} shots, {seconds:.0f} seconds. Goes with [{lesson}]({repository}/blob/main/lessons/{slug}.ipynb).
"""


def markdown(reels: dict[str, Film] | None = None) -> str:
    """The films page, with every description taken from the film it describes."""
    reels = films() if reels is None else reels
    out = [INTRO]
    for name, reel in reels.items():
        lesson, slug = GOES_WITH[name]
        out.append(
            SECTION.format(
                title=reel.title,
                alt=reel.alt,
                directory=DIRECTORY.removeprefix("docs/"),
                name=name,
                shots=len(reel.shots),
                seconds=reel.seconds(),
                lesson=lesson,
                slug=slug,
                repository=REPOSITORY,
            )
        )
    return "".join(out)


def build(name: str) -> Film:
    """One film by name, with the list in the error when the name is wrong."""
    try:
        builder = BUILDERS[name]
    except KeyError:
        raise KeyError(
            f"no film called {name!r}. There are {len(BUILDERS)}: " + ", ".join(BUILDERS)
        ) from None
    return builder()


def films() -> dict[str, Film]:
    """Every film, built. A minute or so, because each one loads its own recording."""
    return {name: builder() for name, builder in BUILDERS.items()}
