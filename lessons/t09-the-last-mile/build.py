"""T09. The last mile.

T08 gave every value a real register. The function is now written entirely in things the
machine has, and it is still an in-memory data structure. This lesson is the pass that turns
it into text, and the table that pass reads to do it.

Everything here comes from three recordings. `t09-final` and `t09-sections` are Compiler
Explorer at GCC 16.1.0 for aarch64 Linux, and `t09-local` is the local compiler, GCC 16.2.0
for aarch64 Darwin. All three were recorded with `-dp`, which is the flag that makes GCC
write, next to every instruction, the name of the machine description pattern that emitted
it. Without that flag the last mile is a black box and this lesson would be a story.

The machine description itself is read out of `corpora/mdesc/aarch64.json`, which
`record.py` extracted from the pinned GCC checkout. A reader in Colab has the repository and
no GCC tree, and the tree is 1.3 GB, so the lesson brings the ten patterns it needs with it.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "t09-the-last-mile",
    "t09",
    title="The last mile",
    milestone="M1",
    summary=(
        "The pass that writes the assembly file, the annotation that says which machine "
        "description pattern emitted each line, why one pattern can emit five different "
        "instructions, and the thirty four lines of a forty six line file that are not "
        "instructions at all"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# T09. The last mile

{badge}

Everything so far has been GCC talking to itself. GIMPLE, RTL, the pass list, the allocator's
disposition: all of it is structure in memory, and none of it is anything the operating system
has ever heard of. At some point a compiler has to stop thinking and write a file.

That is this lesson. The pass is called {term("final")}, it is about as old as GCC, and it
does something none of the passes before it does. Every other pass reads the machine
description as a set of patterns to match against. `final` reads it as a set of templates to
print. The same file, used the other way round.

The nice thing about the last mile is that you can check every claim in it. The assembly is
text, the pattern that emitted each line is written in the margin, and the machine description
is a file in the GCC tree with line numbers. There is nothing here you have to take on trust.

You need a browser. There is no compiler here and no network.

**What you come away with**

- What `final` actually does, and what it does not do
- How to read the annotation `-dp` writes, and what the parts of it mean
- Being able to take a line of assembly and find the {term("define_insn")} that emitted it
- Why one pattern emits five different instructions, and what an {term("alternative")} is
- Why most of an assembly file is not instructions
- Where a variable goes and who decided, which is not the optimizer
""")

lesson.setup()

lesson.md(f"""
## The last pass

`pass_final` is at {cite("gcc/final.cc:4340@releases/gcc-16.2.0")} and the function it runs is
`final` at {cite("gcc/final.cc:2009@releases/gcc-16.2.0")}. It walks the insn chain one insn
at a time in `final_scan_insn` at {cite("gcc/final.cc:2888@releases/gcc-16.2.0")} and writes
to a `FILE *`. That is the whole shape of it.

What it does not do is decide anything. By the time `final` runs, which instruction to use was
decided at expansion and combine, which register to use was decided by IRA and LRA, and what
order to run them in was decided by the scheduler. `final` is a printer. If the assembly
surprises you, the pass that surprised you is somewhere else.

The interesting three lines in the whole pass are these, from `get_insn_template` at
{cite("gcc/final.cc:2024@releases/gcc-16.2.0")}:

```c
case INSN_OUTPUT_FORMAT_SINGLE:   return insn_data[code].output.single;
case INSN_OUTPUT_FORMAT_MULTI:    return insn_data[code].output.multi[which_alternative];
case INSN_OUTPUT_FORMAT_FUNCTION: return (*insn_data[code].output.function) (...);
```

Three ways a pattern can say what it prints. One string, a list of strings indexed by which
alternative was chosen, or a C function that works it out. We will meet all three, and
`insn_data` is the generated table at {cite("gcc/recog.h:510@releases/gcc-16.2.0")} that the
build makes out of the machine description.

## Forty six lines

Start with the file. This is `l1.c`, the four line loop from T01, at `-O2`.
""")

lesson.md(f"""
{claim("the assembly for a four line function is forty six lines, twelve of them instructions")}.
""")

lesson.code("""
from gxray import asm

record = gxray.corpus_store.load("t09-final")
listing = asm.parse(record.asm, "t09-final")

print(f"{record.compiler} for {record.target}")
print(listing)
print()
for kind in asm.KINDS:
    print(f"  {kind:<12} {listing.counts()[kind]:>3}")
""")

lesson.md(f"""
Twelve out of forty six. The rest is directives, labels, comments and one blank line, and we
come back to all of it later, because the part of the file that is not instructions is where
most of what an object file needs actually lives.

For now, the twelve.

## What `-dp` writes in the margin

`-dp` is the flag that makes this lesson possible. With it, GCC writes a comment at the end of
every instruction saying where the instruction came from. The function that writes it is
`output_asm_name` at {cite("gcc/final.cc:3219@releases/gcc-16.2.0")}, and it prints four
things.

```text
        add     w0, w0, w1      // 12   [c=4 l=4]  *addsi3_aarch64/1
```

- `12` is the uid of the RTL insn. The same number appears in the `.final` RTL dump.
- `c=4` is what the cost model thought this insn was worth.
- `l=4` is how many bytes GCC expects it to assemble to. Four, because aarch64.
- `*addsi3_aarch64` is the name of the pattern in the machine description that emitted it.
- `/1` is which {term("alternative")} of that pattern was used, and it is only printed
  sometimes. That is a rule with a reason and we get to it below.

The uid is the useful end of it, because it joins the text back to the RTL. Both recordings
carry the `.final` dump as well as the assembly, so the join can be done rather than asserted.
""")

lesson.md(f"""
{claim("every annotated line names an insn in the final RTL dump, and the two agree")}.
""")

lesson.code("""
from gxray import rtl

insns = rtl.parse(record.dump_texts["rtl-final"], "t09-final").only()

print(f"{len(insns)} insns in the dump, {len(insns.code)} of them code")
print(f"{len(listing.insns)} annotated lines in the assembly")
print()
print(f"{'uid':>5}  {'rtl says':<24}{'assembly says':<24}what came out")
for insn in insns.code:
    line = listing.by_uid(insn.uid)
    said = line.slot if line else ""
    text = line.text.strip().split("//")[0].strip() if line else "nothing at all"
    print(f"{insn.uid:>5}  {insn.name or '(no pattern)':<24}{said:<24}{text}")
""")

lesson.md("""
Two things worth noticing.

Every uid in the assembly is in the dump, and wherever both name a pattern they name the same
one. That is not a coincidence and it is not a check GCC runs. It is the same field printed
twice from the same place, and being able to see it is the reason `-dp` exists.

Four insns emitted nothing. They are all `(use (reg ...))`, which is not an instruction and
never was. A `use` exists to tell the dataflow passes that a register is still live at that
point, which is how the return value survives from the last `mov` to the `ret`. `final` walks
past them. So the insn chain has sixteen code insns in it and the file has twelve
instructions, and the four that vanish were never going to be anything.

## Five patterns

Twelve instructions. How many patterns emitted them?
""")

lesson.md(f"""
{claim("five patterns emitted all twelve instructions, and one of them emitted four")}.
""")

lesson.code("""
used = listing.patterns()
print(f"{len(used)} patterns for {len(listing.insns)} instructions")
print()
for name, lines in used.items():
    where = " ".join(sorted({str(x.alternative) for x in lines if x.alternative is not None}))
    print(f"  {name:<20} {len(lines)} time(s)   alternatives used: {where or 'none printed'}")
""")

lesson.md(f"""
Five patterns, and `*movsi_aarch64` did a third of the work on its own. That is normal. A
back end has a few thousand patterns in it and a handful of them cover almost everything an
ordinary function does.

Notice that `*movsi_aarch64` shows two different alternatives, `1` and `3`, and that two of
the five patterns printed no alternative at all.

## The pattern that emitted it

A {term("machine description")} is a file of patterns, and a {term("define_insn")} is the kind
that both matches RTL and prints text. The RTL definition of the form is at
{cite("gcc/rtl.def:885@releases/gcc-16.2.0")}, and for aarch64 the file is
`gcc/config/aarch64/aarch64.md`, which in GCC 16.2 is about eight thousand lines.

The lesson ships the ten patterns it needs, extracted from the pinned checkout with the file
and line each came from, so that a reader in a browser can follow the citation to GitHub and
see the same text.
""")

lesson.md(f"""
{claim("*addsi3_aarch64 is written *add<mode>3_aarch64 and lives at aarch64.md line 2694")}.
""")

lesson.code("""
from gxray import mdesc

machine = mdesc.load_extract("aarch64")
add = machine["patterns"]["*addsi3_aarch64"]

print("annotation says   *addsi3_aarch64")
print(f"the file says     {add['written']}")
print(f"which is at       {add['citation']}")
print(f"and it is a       {add['kind']}, {add['form']} form, {len(add['alternatives'])} rows")
print()
print("\\n".join(add["text"].splitlines()[:8]))
""")

lesson.md(f"""
The name in the file is not the name in the annotation, and that gap is worth a paragraph.

`<mode>` is a {term("mode iterator")}. `define_mode_iterator` at
{cite("gcc/read-rtl.cc:1482@releases/gcc-16.2.0")} declares a name that stands for a list of
machine modes, and the reader that loads the machine description expands every pattern
containing one into a copy per mode. `GPI` is `[SI DI]`, so `*add<mode>3_aarch64` becomes
`*addsi3_aarch64` and `*adddi3_aarch64`, and by the time `final` prints a name, the copy is
what exists. Writing it once is how a back end stays a readable size.

This is why searching `aarch64.md` for the name in the annotation often finds nothing. You
have to guess which part of the name was an iterator. The extract here does the reverse
mapping, so it can be checked rather than guessed.

## Alternatives

Now the part that surprises people. Here is the whole of `*addsi3_aarch64`.
""")

lesson.code("""
print(f"operands:   {'  '.join(add['cons_heads'])}")
print(f"attributes: {'  '.join(add['attr_heads'])}")
print()
for row in add["alternatives"]:
    cons = "  ".join(f"{c:<4}" for c in row["cons"])
    print(f"  /{row['index']}   {cons}   {row['template']}")
""")

lesson.md(f"""
Eight rows, and they are all the same pattern. The RTL they match is identical: a `plus` of
two things assigned to a register. What differs is where the operands are, and that is what
the letters say.

A {term("constraint")} is one letter that says what an operand is allowed to be. The list of
them is a file of its own, `gcc/config/aarch64/constraints.md`, and the machinery that reads
it is at {cite("gcc/genpreds.cc:669@releases/gcc-16.2.0")}. Four of them appear above:

- `r` is a general register.
- `k` is the stack pointer, at {cite("gcc/config/aarch64/constraints.md:21@releases/gcc-16.2.0")}.
- `I` is a constant that fits in an `add`, at
  {cite("gcc/config/aarch64/constraints.md:87@releases/gcc-16.2.0")}.
- `J` is a constant that fits in a `sub` once you negate it, at
  {cite("gcc/config/aarch64/constraints.md:121@releases/gcc-16.2.0")}.

Read row 3 with that. Destination a register, first operand a register, second operand a
constant that fits a `sub` once negated, and the text it prints is `sub`. So `x + (-8)` and
`x - 8` are the same insn in RTL and the same pattern in the machine description, and the
choice of which mnemonic comes out is a row in a table.

Which row got used is in a global variable. `which_alternative` at
{cite("gcc/recog.h:363@releases/gcc-16.2.0")} is set by the recognizer before the template is
printed, and it is the index `get_insn_template` uses. It is also the number after the slash.

The two `mov` instructions in our function make the point without needing the aarch64 manual.
""")

lesson.md(f"""
{claim("the two movs used different rows, and the rows differ in one constraint letter")}.
""")

lesson.code("""
mov = machine["patterns"]["*movsi_aarch64"]
mine = sorted({x.alternative for x in used["*movsi_aarch64"]})

print(f"*movsi_aarch64 has {len(mov['alternatives'])} alternatives, this function used {mine}")
print()
for index in mine:
    row = mov["alternatives"][index]
    lines = [x for x in used["*movsi_aarch64"] if x.alternative == index]
    print(f"  /{index}  operands {row['cons']}  template {row['template']}")
    for x in lines:
        print(f"        line {x.number}:  {x.text.strip().split('//')[0].strip()}")
""")

lesson.md(f"""
Row 1 takes its source from a register and prints `%w1`, which is operand 1 as a 32 bit
register name. Row 3 takes a constant that fits a 32 bit `mov` immediate, at
{cite("gcc/config/aarch64/constraints.md:140@releases/gcc-16.2.0")}, and prints `%1`, which is
operand 1 as itself. One letter apart in the table, and `mov w2, w0` against `mov w1, 0` in
the file.

The `%` sequences are the substitution language. `output_asm_insn` at
{cite("gcc/final.cc:3428@releases/gcc-16.2.0")} walks the {term("output template")} character
by character, copies most of it out unchanged, and where it finds a `%` followed by a digit it
prints that operand. A letter between the two, as in `%w1`, hands the job to the target, which
is how the same operand prints as `w0` in one place and `x0` in another.

## The slash that is not always there

Two of our five patterns printed no alternative. That is not a gap in the annotation, it is
information, and the reason is one line of `output_asm_name`:

```c
if (insn_data[insn_code].n_alternatives > 1)
  fprintf (asm_out_file, "/%d", which_alternative);
```

A pattern with one alternative has nothing to choose between, so there is no number worth
printing. `aarch64_bcond` and `*do_return` are both in that position, and both for the same
reason: their output is a C block rather than a table, so there is exactly one of it.
""")

lesson.md(f"""
{claim("across all three recordings the slash appears exactly when the pattern has more than one row")}.
""")

lesson.code("""
print(f"{'pattern':<30}{'rows':>6}{'slash':>8}   uses")
seen = {}
for entry in ["t09-final", "t09-sections", "t09-local"]:
    other = asm.parse(gxray.corpus_store.load(entry).asm, entry)
    for name, lines in other.patterns().items():
        seen.setdefault(name, []).extend(lines)

for name in sorted(seen):
    lines = seen[name]
    rows = len(machine["patterns"][name]["alternatives"])
    slash = any(x.alternative is not None for x in lines)
    print(f"{name:<30}{rows:>6}{('yes' if slash else 'no'):>8}   {len(lines)}")
    assert slash == (rows > 1), name

print()
print(f"{len(seen)} patterns, {sum(len(v) for v in seen.values())} annotated instructions")
""")

lesson.md(f"""
The two with no slash are the two whose output is C. `*do_return` is the clearest example in
the whole back end of the third form `get_insn_template` knows about:

```c
{{
  const char *ret = NULL;
  if (aarch64_return_address_signing_enabled ())
    ret = "retaa";
  else
    ret = "ret";
  output_asm_insn (ret, operands);
  return "";
}}
```

The reader in this lesson reports zero rows for those two rather than one, because there is no
table in the file to count. GCC's own `n_alternatives` says one, worked out from the operand
constraints. Either way it is not more than one, and the slash stays off.

That is not a template with a hole in it. It is a program, run at compile time, that decides
between two mnemonics on the basis of a compiler flag. Nothing earlier in the pipeline knows
which one it will pick, because nothing earlier in the pipeline runs this code.

So the machine description is a table for most of the compiler and a program for `final`, and
that is the sentence worth keeping from this lesson.

## Everything that is not an instruction

Back to the other thirty four lines. Compare the same function on two targets.
""")

lesson.md(f"""
{claim("the same twelve instructions come wrapped in thirty four other lines on Linux and forty four on Darwin")}.
""")

lesson.code("""
elf = listing
macho = asm.parse(gxray.corpus_store.load("t09-local").asm, "t09-local")

print(f"{'':<12}{'linux':>10}{'darwin':>10}")
for kind in ["instruction", "directive", "label", "comment", "blank"]:
    print(f"{kind:<12}{elf.counts()[kind]:>10}{macho.counts()[kind]:>10}")
print(f"{'total':<12}{elf.counts()['total']:>10}{macho.counts()['total']:>10}")
print()
print(f"comment character: linux {elf.mark!r}, darwin {macho.mark!r}")

same = [(x.name, x.args.lstrip(".")) for x in elf.instructions]
also = [(x.name, x.args.lstrip(".")) for x in macho.instructions]
print(f"the twelve instructions are identical: {same == also}")
""")

lesson.md("""
Identical instructions, and everything else different. Even the comment character is a target
decision: ELF aarch64 says `//` and Mach-O aarch64 says `;`, out of the same compiler.

That is the honest summary of what an assembly file is. A small amount of machine code and a
large amount of bookkeeping about where to put it, what to call it, who else may see it, and
how to unwind through it. The instructions are the part everybody looks at and the smaller
part of the file.

## Where a variable goes

The bookkeeping is not a formality, and the clearest place to see that is a file with no
interesting code in it at all. `t09-sections.c` declares seven variables and two functions and
computes almost nothing. The whole point is where each name lands.
""")

lesson.md(f"""
{claim("nine names land in five different sections and nothing in the C says which")}.
""")

lesson.code("""
places = asm.parse(gxray.corpus_store.load("t09-sections").asm, "t09-sections")

print(f"{len(places.symbols)} names, {len(places.sections)} sections in the file")
print()
print(f"{'name':<10}{'section':<20}{'kind':<10}{'scope':<9}size")
for name, sym in places.symbols.items():
    size = "" if sym.size is None else f"{sym.size} bytes"
    print(
        f"{name:<10}{sym.section:<20}{sym.kind.lstrip('%@') or '?':<10}"
        f"{('global' if sym.exported else 'local'):<9}{size}"
    )
""")

lesson.md(f"""
Read that against the source and every row is a decision somebody made.

`counter = 7` is initialised and writable, so its bytes have to be in the object file, and it
goes in `.data`. `total = 0` and `pending` with no initialiser at all are treated identically
and go in `.bss`, which reserves space and stores no bytes, because zero is what fresh memory
already is. `bss_initializer_p` at {cite("gcc/varasm.cc:1107@releases/gcc-16.2.0")} is the
function that decides that, and it is worth knowing that `int total = 0;` and `int pending;`
produce byte for byte the same output.

`limit` is const, so nothing will write to it and it can go somewhere the loader maps read
only, which is `.rodata`. `tag` is static as well as const, so it lands in `.rodata` too and
gets no `.global` directive, which is the whole of what `static` means at this level.

`message` is the interesting one, because it is two objects. The characters are an anonymous
constant that goes in a mergeable string section with a compiler invented label, and the
pointer itself is eight writable bytes that hold that label's address.

The function that makes these calls is `categorize_decl_for_section` at
{cite("gcc/varasm.cc:7368@releases/gcc-16.2.0")}, reached from `assemble_variable` at
{cite("gcc/varasm.cc:2517@releases/gcc-16.2.0")}. None of it is an optimization. It reads the
declaration and nothing else, and it would make the same choices at `-O0`.

## Alignment is a directive

One variable in that file asks for something unusual.

```c
int wide __attribute__ ((aligned (64)));
```
""")

lesson.md(f"""
{claim("wide is four bytes and the section it sits in is aligned to sixty four")}.
""")

lesson.code("""
for name, section in places.sections.items():
    aligns = [x for x in section.lines if x.name in (".align", ".p2align", ".balign")]
    if not aligns:
        continue
    for x in aligns:
        after = next(
            (y.name for y in section.lines if y.kind == "label" and y.number > x.number), "?"
        )
        print(f"  {name:<18}{x.name} {x.args:<8}(2**{x.args.split(',')[0]} bytes)  before {after}")

print()
wide = places.symbols["wide"]
print(f"and `wide` itself is {wide.size} bytes, sitting in {wide.section}")
""")

lesson.md(f"""
`.align 6` on aarch64 means two to the sixth, which is sixty four. Everything else in `.bss`
follows it at its natural alignment, because once the section is aligned to sixty four the
four byte objects after it are aligned as well.

`assemble_align` at {cite("gcc/varasm.cc:2294@releases/gcc-16.2.0")} is what emits it. The
attribute did not change the code, it did not change the type, and it did not change the size.
It changed one directive, and the assembler is what makes that mean anything.

Which is the point of the whole section, and it is the point of {term("assembler directive")}
as a concept. A directive is not an instruction. It is an instruction to the assembler.

## The file is not an object file

`final` finishes, GCC writes the last line, and what exists is a text file. Nothing in it is
machine code yet. `add w0, w0, w1` is fourteen characters, and the four bytes it stands for do
not exist anywhere until `as` runs.

What the assembler adds:

- The encoding. Each mnemonic and its operands become the bytes the hardware decodes.
- The {term("section")} table. `.text` and `.data` stop being directives and become headers
  with sizes and offsets.
- The symbol table. Every `.globl`, `.type` and `.size` becomes an entry the linker can see.
- Relocations. `.xword .LC0` is an address nobody knows yet, so it becomes a note that says
  patch eight bytes here once you know where `.LC0` ended up.

Then the linker resolves the relocations and the loader maps the sections. Three separate
programs after GCC, and the reason a compiler stops here is that everything past this line is
the same for every language.

You can watch the handover. `gcc -S` stops at the text and `gcc -c` runs the assembler, and
the assembler GCC runs is a separate binary that you can also run yourself.

```text
gcc-16 -O2 -dp -S l1.c        # writes l1.s, which is what this lesson has been reading
as -o l1.o l1.s               # the same file, now an object file
```

## The widget

Every line of the file, selectable. Click a line and the panel says what put it there. For an
instruction that means the pattern, the row of the pattern, the template and the substitution
that produced the text you are looking at, with the whole alternative table underneath and the
row that was used marked. For a directive it says what the assembler does with it.

The buttons at the top cut forty six lines down to the twelve that are instructions, which is
the same key the RTL widget in T07 used to cut the insn chain down to the code insns.
""")

lesson.code("""
from IPython.display import HTML, display

from gxwidgets.__main__ import listing as make_listing

widget = make_listing()
display(HTML(widget.render()))

# The same conclusion as text, so this cell proves something where HTML does not render.
facts = widget.data()
print(f"{facts['counts']['total']} lines, {facts['counts']['instruction']} instructions")
print(f"machine description extract taken at {facts['tag']}")
for name, uses in facts["patterns"].items():
    print(f"  {name:<22}{uses} line(s)")
""")

lesson.md("""
## The same thing as pictures

Two stills. The first is the whole file, one cell per line, coloured by kind, which is the
forty six against twelve argument as a shape. The second is one insn walking the four steps to
becoming a line of text.
""")

lesson.code("""
from IPython.display import SVG

import gxmanim

tape = gxmanim.mobjects.asm_tape(listing)
display(SVG(gxmanim.svg.document(tape)))
print(tape.describe().splitlines()[0])
print(tape.caption)
""")

lesson.code("""
path = gxmanim.mobjects.emit_path(listing.by_uid(12), add)
display(SVG(gxmanim.svg.document(path)))
print(path.describe())
""")

lesson.md("""
## The picture

The whole last mile, from the insn chain to the file the assembler reads, with the machine
description sitting to one side of it because it is not part of the pipeline and everything in
the back end reads it, is drawn in
[`diagrams/the-last-mile.excalidraw`](https://github.com/tamnd/gcc-internals/blob/main/lessons/t09-the-last-mile/diagrams/the-last-mile.excalidraw).
Open it at excalidraw.com and you can move things around.

## Where to read more

`BP-FINAL` in
[`blueprints/BP-FINAL.md`](https://github.com/tamnd/gcc-internals/blob/main/blueprints/BP-FINAL.md)
is the reference version of this lesson. It has the annotation grammar written out, the three
output template forms with what each one compiles to, the compact alternative syntax GCC 16
uses and what every symbol in it means, and the section selection rules as a table.

## Boss fight

The reverse of the lesson. You get three lines of assembly with the annotation stripped off,
and you name the pattern that emitted each one.

```text
mov     w0, 0
add     w1, w1, 1
ret
```

Then two questions about the rule that decides whether a slash appears.

The grader checks against the recordings, so it is checking against what GCC actually printed
and not against an answer somebody wrote down.

```text
python lessons/t09-the-last-mile/grade.py
```

or `just grade t09-the-last-mile`. It takes the answers on the command line too, so
`--patterns *movsi_aarch64,*addsi3_aarch64,*do_return --no-slash 2 --rows 21` is a complete
submission.

The one to think about is the third. There are two `ret` instructions in the file, they come
from two different insns, and they carry no slash. Say why before you look.

## What to read next

T10 is the whole map. Ten lessons in, you have seen the front end hand off to GIMPLE, GIMPLE
become SSA and back, the pass list run, RTL appear, registers get handed out and text get
written. T10 puts all of it on one page and finishes `BP-PIPELINE`.

After that, M2 goes back to the beginning and reads the front end properly, and M5 is the back
end, where this lesson turns into four: the machine description as a language, the recognizer,
the scheduler and the target hooks.
""")

raise SystemExit(lesson.save())
