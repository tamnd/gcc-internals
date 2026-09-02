"""The glossary, as data, so that one definition serves every lesson.

A course this long has two ways to go wrong with vocabulary. It can define a word once, in
the lesson where it first came up, and then assume it forty lessons later when the reader
has long since forgotten. Or it can redefine it every time, which trains the reader to skip
the first paragraph of everything. This module is the third option. There is one
definition, it lives here, and lessons link into it.

Everything here is content rather than machinery, which is why it sits in `gxray` next to
the rest of the toolkit instead of in the build tools. A lesson can import it and print a
definition in a cell, and `GLOSSARY.md` at the root of the repository is generated from it
so a reader can also just read the thing.

Two rules keep it honest. A term is only in here if a lesson has earned it, so there are no
entries for parts of the course that have not been written. And where a definition rests on
something in GCC's source rather than on general compiler vocabulary, it carries the
citation, which means `refcheck` resolves it against the pinned tree on every change like
every other claim in the project.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field

# The one place that knows how a citation turns into a link. Importing it here rather than
# writing the URL out again is the whole reason that function exists.
from tools.refcheck import url

__all__ = ["GROUPS", "TERMS", "Group", "Term", "anchor", "get", "link", "markdown", "names"]

#: Where the generated file lives, relative to the root of the repository. Lessons link to
#: the copy on GitHub rather than to this path, because a notebook opened in Colab has no
#: idea which repository it came from and a relative link would be broken for every reader
#: who arrived through the badge.
PATH = "GLOSSARY.md"

REPOSITORY = "https://github.com/tamnd/gcc-internals"


@dataclass(frozen=True)
class Term:
    """One entry. The short line is what a lesson quotes, the long one is why it matters."""

    #: Letters, digits, spaces and underscores, which is the subset of characters where the
    #: anchor GitHub makes from a heading is predictable. Backticks and punctuation go in
    #: `also` instead, where they cannot end up in a URL.
    name: str

    #: One sentence, the definition you would give somebody in passing.
    short: str

    #: A paragraph. Where there is a thing people reliably get wrong about the term, this is
    #: where it goes, because a glossary that only says what a word means is a dictionary
    #: and the reader already has one of those.
    long: str

    #: Other names for the same thing, including how it is spelled in the source.
    also: tuple[str, ...] = ()

    #: Where in GCC the definition comes from, when it comes from GCC at all.
    cite: str = ""

    #: Related terms, by name. Checked, so a rename cannot leave a dead link behind.
    see: tuple[str, ...] = ()

    #: The lesson where a reader first meets it.
    met: str = ""

    @property
    def anchor(self) -> str:
        """The fragment GitHub will generate for this term's heading."""
        return anchor(self.name)


@dataclass(frozen=True)
class Group:
    """A run of terms under one heading, in the order a reader meets them."""

    title: str
    blurb: str
    terms: tuple[Term, ...] = field(default_factory=tuple)


def anchor(name: str) -> str:
    """GitHub's heading slug, for the small subset of headings this file produces.

    GitHub lowercases the heading, drops punctuation and turns spaces into hyphens, but it
    keeps underscores, so `SSA_NAME` becomes `ssa_name` and not `ssa-name`. Getting that one
    wrong gives you links that look right and go nowhere.
    """
    return re.sub(r"[^a-z0-9_]+", "-", name.lower()).strip("-")


DRIVING = Group(
    "Driving the compiler",
    "What actually runs when you type `gcc`, and how to make it show you its work. T01 and T04 are the lessons that cover this ground.",
    (
        Term(
            name="driver",
            short="The program called `gcc`, which compiles nothing and runs the things that do.",
            long="It reads your command line, works out which language you are in, and then runs a compiler, an assembler and a linker as separate processes. This is worth knowing early because almost every option you pass to `gcc` is really an option for one of those, and `gcc -v` prints the four command lines it built so you can see which. The driver is a few thousand lines of argument shuffling and it is not where the compiler lives.",
            also=("`gcc`", "`gcc.cc`"),
            see=("cc1", "spec"),
            met="T01",
        ),
        Term(
            name="cc1",
            short="The actual C compiler. One process, one translation unit, C in and assembly out.",
            long="Everything this course is about happens inside `cc1`. It is not on your PATH and it is not meant to be run by hand, which is why `gcc -v` is how you find it. There is one of these per language: `cc1plus` for C++, `f951` for Fortran, and so on, all built from the same middle end and back end with a different front end bolted on the front.",
            cite="gcc/gcc.cc:1234@releases/gcc-16.2.0",
            see=("driver", "spec", "front end"),
            met="T01",
        ),
        Term(
            name="spec",
            short="A small string language the driver uses to build the command lines it runs.",
            long="A spec is a template full of conditionals like `%{save-temps:...}` that expands into arguments. They are almost unreadable and you will not need to write one, but recognising the syntax stops `gcc -dumpspecs` from looking like line noise, and knowing they exist explains why an option you passed shows up in a completely different form in the `cc1` command line.",
            see=("driver", "cc1"),
            met="T01",
        ),
        Term(
            name="collect2",
            short="A wrapper the driver runs instead of the linker, which then runs the linker.",
            long="Its job is static constructors. On a target whose linker cannot collect them by itself, `collect2` links once, reads the symbol table looking for constructor and destructor symbols, generates a small C file holding a table of them, compiles it and links again. On a modern target with `.init_array` none of that is needed and it passes almost everything straight through, which is why it looks like a pointless extra process in `-###` output. It is still there because removing a program from the middle of every link on every target is not the kind of change anybody makes casually.",
            cite="gcc/collect2.cc:25@releases/gcc-16.2.0",
            see=("driver", "cc1"),
            met="T01",
        ),
        Term(
            name="dump file",
            short="A text file GCC writes showing the function after one particular pass.",
            long="Ask for one with `-fdump-tree-ssa` or `-fdump-rtl-expand` and GCC writes the whole function out in that pass's representation. This is the main window this course looks through, and the important thing about it is that it is a rendering rather than the data structure: the dump has no explicit edges, no pointers, and no types unless you ask for them with a modifier. Add `-graph` and you get a `.dot` beside it that does have the edges.",
            cite="gcc/dumpfile.h:522@releases/gcc-16.2.0",
            also=("`-fdump-tree-all`",),
            see=("pass",),
            met="T01",
        ),
        Term(
            name="pass",
            short="One transformation or analysis, run over one function, in a fixed order.",
            long="The whole middle end and back end is a list of these. A pass has a name, a gate that decides whether it runs at all, and an execute function. The list is much longer than people expect and most of what it contains does nothing at `-O0`, which is why the count you get from `-fdump-passes` depends on the optimisation level. Passes are the unit everything else in this course is organised around, because a dump file is named after one.",
            cite="gcc/tree-pass.h:73@releases/gcc-16.2.0",
            see=("dump file", "pass manager"),
            met="T01",
        ),
        Term(
            name="pass manager",
            short="The loop that walks the pass list and runs each pass on each function.",
            long="It is also the thing that opens the dump file, checks the gate, verifies the IR afterwards when checking is on, and keeps track of which analyses are still valid. When a pass appears to have been skipped, the pass manager is where the answer is, and the answer is almost always the gate.",
            cite="gcc/passes.cc:2579@releases/gcc-16.2.0",
            see=("pass",),
            met="T04",
        ),
        Term(
            name="gate",
            short="The method a pass answers with yes or no when asked whether it should run.",
            long="It is a virtual function on the pass, so the condition lives with the pass rather than in a table somewhere, and it is asked again for every function. That is why the answer is not a property of your command line: two functions in one file can get different answers from the same gate. `-fdump-passes` prints the answer for one function at one moment, and a gate that depends on how far compilation has got, such as the one guarding the passes that run after register allocation, will print the answer for that moment rather than for the moment the pass is reached.",
            cite="gcc/tree-pass.h:90@releases/gcc-16.2.0",
            see=("pass", "pass manager"),
            met="T04",
        ),
        Term(
            name="front end",
            short="The half of the compiler that knows a language, as opposed to the half that does not.",
            long="A front end parses one language and hands the middle end a function body in GENERIC. Everything after that point is shared, which is the single most important structural fact about GCC: twelve languages, one optimiser, one code generator. It is also why an optimisation bug is almost never a C bug.",
            see=("GENERIC", "middle end"),
            met="T01",
        ),
        Term(
            name="middle end",
            short="Everything between the front end and the back end, where the optimisation happens.",
            long="It takes GENERIC in and hands RTL out, and in between it works on GIMPLE in SSA form. The name is a joke that stuck, since a thing with two ends does not have a middle, but it is what everybody calls it and what the source calls it.",
            see=("front end", "GIMPLE", "back end"),
            met="T01",
        ),
        Term(
            name="back end",
            short="The half that knows a machine, from RTL down to the assembly text.",
            long="It is generated, mostly. A target is described by a `.md` file full of patterns and a `.cc` file full of hooks, and a pile of build time programs turn those into the C that actually runs. This is why grepping for the function that emitted an instruction so often lands you in a file that does not exist in the source tree.",
            see=("RTL", "middle end"),
            met="T01",
        ),
    ),
)


SHAPES = Group(
    "The four shapes a function takes",
    "The same function, written down four different ways on its way to assembly. T02, T03 and T07 are the lessons.",
    (
        Term(
            name="tree",
            short="GCC's universal node type. One tagged union for every kind of thing.",
            long="A `tree` is a pointer to a union with a code on the front telling you which member is live. Types are trees, declarations are trees, constants are trees, and expressions are trees, which is why the accessor macros are shouty and everywhere. It is the oldest data structure in the compiler and reading anything in the front end means being comfortable with it.",
            cite="gcc/tree-core.h:2186@releases/gcc-16.2.0",
            also=("`tree_node`",),
            see=("GENERIC", "GIMPLE"),
            met="T02",
        ),
        Term(
            name="GENERIC",
            short="The language independent tree a front end hands over. Still a tree, still nested.",
            long="GENERIC is what the C parser produces: a whole function as one expression tree, with loops and conditionals and function calls nested inside each other exactly the way you wrote them. It is close enough to the source that you can read your program back out of it, which is the point, and far enough from the source that a Fortran front end can produce the same thing.",
            see=("tree", "GIMPLE", "gimplification"),
            met="T02",
        ),
        Term(
            name="GIMPLE",
            short="A flattened three address form. One operation per statement, no nesting.",
            long="Every expression is broken up until each statement does exactly one thing, with temporaries invented to hold the middle results. This is the representation the entire middle end works on, and the reason for it is that a pass that has to handle arbitrary nesting is a pass nobody can write correctly. What you lose is readability, which is why the dumps look like somebody ran your code through a shredder.",
            cite="gcc/gimple.h:222@releases/gcc-16.2.0",
            see=("GENERIC", "gimplification", "SSA", "basic block"),
            met="T02",
        ),
        Term(
            name="gimplification",
            short="The pass that turns GENERIC into GIMPLE by flattening the nesting out.",
            long="It walks the tree and, every time it finds an expression that is too complicated to be a statement on its own, it invents a temporary, assigns the sub-expression to it, and puts the assignment before. Everything else about GIMPLE follows from that one move. The function that does it is one of the largest switch statements in the compiler and it is worth looking at once.",
            cite="gcc/gimplify.cc:20296@releases/gcc-16.2.0",
            see=("GENERIC", "GIMPLE"),
            met="T03",
        ),
        Term(
            name="three address form",
            short="At most one operation per statement, and every operand already a value.",
            long="The name is older than GCC and comes from the shape of the statement: a destination and two sources, three addresses. What it really means is that an operand may be a variable or a constant and may not be another expression, which is one predicate in the source and the entire reason the middle end is writable. A pass reads one operator and two operands and is finished, rather than recursing into a tree of unknown depth.",
            cite="gcc/gimple-expr.cc:836@releases/gcc-16.2.0",
            also=("`is_gimple_val`",),
            see=("GIMPLE", "gimplification", "temporary"),
            met="T03",
        ),
        Term(
            name="temporary",
            short="A variable gimplification invented to hold a value that had nowhere to go.",
            long="Printed as `_1`, `_2` and so on in the dumps, and there is one for every interior node of an expression that had to be flattened. They are not in your source and they are not a sign that anything went wrong. The related name `D.4635` is a different thing: that is the slot a function returns through, made by the front end for every function rather than by gimplification for a particular expression.",
            cite="gcc/gimplify.cc:683@releases/gcc-16.2.0",
            see=("gimplification", "three address form", "SSA name"),
            met="T03",
        ),
        Term(
            name="RTL",
            short="Register Transfer Language. Machine operations on unlimited virtual registers.",
            long="RTL is the back end's representation and it is a Lisp-like expression describing what an instruction does to registers and memory, not what the instruction is called. A target matches those expressions against its patterns to pick real instructions. The move from GIMPLE to RTL is the point where the compiler stops being about your program and starts being about a machine.",
            cite="gcc/rtl.h:314@releases/gcc-16.2.0",
            also=("`rtx`",),
            see=("expand", "back end"),
            met="T02",
        ),
        Term(
            name="expand",
            short="The pass that turns GIMPLE into RTL, one statement at a time.",
            long="It is the hinge of the whole compiler and it is not reversible: after expand there is no going back to GIMPLE, so every optimisation that wants to reason about your program rather than about a machine has to have happened already. It is also where the stack frame gets laid out and where a virtual register first appears.",
            cite="gcc/cfgexpand.cc:7015@releases/gcc-16.2.0",
            see=("GIMPLE", "RTL"),
            met="T07",
        ),
    ),
)


CONTROL = Group(
    "The shape of a function",
    "Blocks, edges and the questions you can ask about them. T05 needs the first four of these, G02 and G03 go deeper.",
    (
        Term(
            name="basic block",
            short="A run of statements with one way in at the top and one way out at the bottom.",
            long="Nothing branches into the middle of a block and nothing branches out of the middle, so if the first statement runs then all of them run. That guarantee is what makes a block the unit every analysis works in. In a dump they are the things labelled `<bb 3>`, and the two numbered 0 and 1 are the entry and exit blocks, which hold no statements and exist so that every real block has somewhere to come from and go to.",
            cite="gcc/basic-block.h:117@releases/gcc-16.2.0",
            also=("`<bb 3>`",),
            see=("control flow graph", "edge"),
            met="T05",
        ),
        Term(
            name="control flow graph",
            short="The blocks of a function plus the edges saying which can follow which.",
            long="The important thing about the CFG is that it is a real data structure with real edges, and the text dump is not it. A fallthrough from one block to the next shows up in the dump as nothing at all, because there is no goto to print, so counting edges by reading a dump gives the wrong answer. Ask for `-graph` and GCC writes the edges out properly.",
            also=("CFG",),
            see=("basic block", "edge", "dominance"),
            met="T05",
        ),
        Term(
            name="edge",
            short="One possible jump from the end of one block to the start of another.",
            long="Edges carry flags, and the flags are where the interesting cases live: a back edge closes a loop, an abnormal edge is one the compiler cannot reason about normally, an EH edge is the path taken when something throws. A block with two outgoing edges ends in a condition, and which edge is the true one is a flag rather than an ordering.",
            see=("basic block", "control flow graph", "loop"),
            met="T05",
        ),
        Term(
            name="dominance",
            short="Block A dominates block B if every path to B goes through A first.",
            long="This is the question the whole middle end keeps asking, because it is how you know a value is available: if the block that defines it dominates the block that uses it, the definition has definitely already run. Entry dominates everything. A block always dominates itself, which sounds like a technicality and matters constantly.",
            cite="gcc/dominance.cc:856@releases/gcc-16.2.0",
            see=("immediate dominator", "basic block", "SSA"),
            met="T05",
        ),
        Term(
            name="immediate dominator",
            short="The closest block that dominates a given block, not counting the block itself.",
            long="Every block except entry has exactly one, which means the dominance relation of a whole function fits in one number per block and the dominator tree is that array read as a tree. GCC computes it lazily and a pass has to ask for it, which is why you see `calculate_dominance_info` at the top of so many passes.",
            also=("idom", "dominator tree"),
            see=("dominance",),
            met="T05",
        ),
        Term(
            name="loop",
            short="A back edge and everything that can reach it without leaving.",
            long="GCC finds loops rather than being told about them, which is why a loop written with `goto` and a loop written with `for` end up identical here, and why a `for` loop that the compiler proved runs a fixed number of times may not be a loop by the time you look. Loops nest, and the nesting is a tree with a fake outermost loop at the root standing for the function.",
            cite="gcc/cfgloop.h:120@releases/gcc-16.2.0",
            see=("edge", "control flow graph"),
            met="T05",
        ),
    ),
)


STATIC_SINGLE = Group(
    "SSA",
    "The one idea that makes the middle end tractable, and the vocabulary that comes with it. T05 is the lesson.",
    (
        Term(
            name="SSA",
            short="Static Single Assignment. Every name is assigned exactly once in the text of the function.",
            long="A variable that was written three times becomes three separate names. That sounds like bookkeeping and it is actually the thing that makes optimisation possible, because once a name has one definition, finding that definition is a pointer dereference rather than a search. Static is the load bearing word: a definition inside a loop runs many times, it just appears once.",
            cite="gcc/tree.def:1035@releases/gcc-16.2.0",
            see=("SSA name", "phi node", "out of SSA"),
            met="T05",
        ),
        Term(
            name="SSA name",
            short="One version of one variable, written `s_4` in a dump.",
            long="The part before the underscore is the variable it came from and the number after it is the version, so `s_4` and `s_7` are the same variable at two different points in the function. Versions are handed out from a single counter and are never reused, so the numbers in a dump are not consecutive and the gaps mean nothing. A name knows the single statement that defines it, and that is the property everything else is built on.",
            cite="gcc/tree-ssanames.cc:351@releases/gcc-16.2.0",
            also=("`SSA_NAME`", "version"),
            see=("SSA", "definition", "phi node"),
            met="T05",
        ),
        Term(
            name="definition",
            short="The single statement that gives an SSA name its value.",
            long="Every SSA name has exactly one, and going from a name to it is one step. That is the difference between SSA and what came before, where answering the same question meant walking backwards through the CFG and giving up at the first join.",
            also=("def",),
            see=("SSA name", "use"),
            met="T05",
        ),
        Term(
            name="use",
            short="Any place an SSA name is read.",
            long="The uses of a name are kept as a list hanging off the name, so going the other way is also one step. A pass that changes a value walks that list to find everything affected, and a name whose use list is empty is dead, which is the entire algorithm behind one of the passes that runs most often.",
            also=("def-use chain",),
            see=("definition", "SSA name"),
            met="T05",
        ),
        Term(
            name="default definition",
            short="The version of a name that was already there when the function started.",
            long="It is written with a `(D)` after it, as in `n_5(D)`, and no statement anywhere defines it. Parameters have one, because their value arrives from the caller. So does a local read before it was ever written, which is the compiler saying out loud that your program has undefined behaviour and it is going to carry on anyway. Seeing a `(D)` on something that is not a parameter is worth a second look.",
            also=("`(D)`",),
            see=("SSA name", "definition"),
            met="T05",
        ),
        Term(
            name="phi node",
            short="A statement at the top of a block that picks a value based on which edge you came in on.",
            long="It exists because SSA needs one name per definition and a join point has two definitions arriving. A phi is not a real instruction and nothing computes it, it is a note saying that this name is whichever of these names the path you took defined. It has exactly one argument per incoming edge and the arguments are positional, which is why deleting an edge means editing every phi in the block.",
            cite="gcc/gimple.h:474@releases/gcc-16.2.0",
            also=("`PHI`", "`gphi`"),
            see=("SSA name", "basic block", "out of SSA"),
            met="T05",
        ),
        Term(
            name="out of SSA",
            short="The pass that removes phi nodes by putting real copies on the incoming edges.",
            long="It has to happen because no machine has an instruction that means whichever way you came. Doing it naively costs a copy per phi argument, so the real pass spends most of its effort proving that two SSA names can share one location and dropping the copy. This is the last thing that happens on GIMPLE before expand.",
            see=("phi node", "SSA", "expand"),
            met="T05",
        ),
    ),
)


GROUPS: tuple[Group, ...] = (DRIVING, SHAPES, CONTROL, STATIC_SINGLE)

#: Every term, flattened.
TERMS: tuple[Term, ...] = tuple(term for group in GROUPS for term in group.terms)

_BY_NAME = {term.name.lower(): term for term in TERMS}


def names() -> list[str]:
    """Every term, alphabetically, which is the order somebody looking one up expects."""
    return sorted(term.name for term in TERMS)


def get(name: str) -> Term:
    """Look a term up. Raises rather than returning nothing, so a bad link fails the build."""
    try:
        return _BY_NAME[name.strip().lower()]
    except KeyError:
        raise KeyError(f"no glossary entry for {name!r}. There are {len(TERMS)} of them.") from None


def link(name: str, text: str = "") -> str:
    """A markdown link into the glossary on GitHub, for a lesson to drop into a sentence.

    The URL is absolute rather than relative because a notebook opened from a Colab badge
    has no idea which repository it came from, and a relative link would be broken for every
    reader who arrived that way.
    """
    term = get(name)
    return f"[{text or term.name}]({REPOSITORY}/blob/main/{PATH}#{term.anchor})"


def _entry(term: Term) -> list[str]:
    lines = [f"### {term.name}", "", f"**{term.short}**", "", term.long]
    notes = []
    if term.also:
        notes.append("Also written " + ", ".join(term.also) + ".")
    if term.met:
        notes.append(f"First met in {term.met}.")
    if term.see:
        related = ", ".join(f"[{other}](#{anchor(other)})" for other in term.see)
        notes.append(f"See also {related}.")
    if term.cite:
        # The full citation stays as the visible label rather than being shortened into
        # friendly link text. It is what `refcheck` scans for, so a definition whose source
        # moved fails the build here the same way it would in a lesson.
        notes.append(f"In the source: [`{term.cite}`]({url(term.cite)}).")
    if notes:
        lines += ["", " ".join(notes)]
    return lines


def markdown() -> str:
    """The whole of `GLOSSARY.md`, which is generated from this module rather than edited."""
    lines = [
        "# Glossary",
        "",
        "One definition per term, in one place, so a lesson can use a word without stopping to explain it and without assuming you remember it from forty lessons ago. Lessons link into this file rather than repeating themselves.",
        "",
        "The order below is the order you meet these things, not alphabetical, because reading it straight through is a reasonable thing to do. If you are looking one up, the index is next.",
        "",
        "This file is generated from `gxray/glossary.py`. Edit that and run `just build-glossary`.",
        "",
        "## Index",
        "",
        " | ".join(f"[{name}](#{anchor(name)})" for name in names()),
        "",
    ]
    for group in GROUPS:
        lines += [f"## {group.title}", "", group.blurb, ""]
        for term in group.terms:
            lines += _entry(term)
            lines += [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    """Write `GLOSSARY.md`, relative to wherever this was run from.

    `just build-glossary` runs it from the root of the repository, which is where the file
    belongs. There is no checker recipe next to it because the test suite already compares
    the committed file against this module, and one check is enough.
    """
    path = pathlib.Path(PATH)
    text = markdown()
    if path.exists() and path.read_text(encoding="utf-8") == text:
        print(f"{PATH} is up to date, {len(TERMS)} terms")
        return 0
    path.write_text(text, encoding="utf-8")
    print(f"wrote {PATH}, {len(TERMS)} terms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
