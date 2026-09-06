"""F03. The C parser can see four tokens.

The third lesson of Part II. F02 finished with a stream of tokens coming out of libcpp. This
is the program that reads them, and the one place in the compiler where the amount of
machinery is smaller than anybody expects.

The lesson has one idea and everything else is a consequence of it. GCC's C parser is
recursive descent written by hand, its entire memory of your program is four token slots and
the symbol table, and nearly everything people find strange about C error messages falls out
of those two facts. Eight programs that all leave out the same semicolon get eight different
sentences. Seven of them put the caret in one place and the eighth puts it two columns later.
Three missing semicolons come out as two errors. One error points at a bracket on the line
above. Each of those is a thing to be irritated by until you know why, and then it is a thing
you can predict.

The parser has no dump flag, because it has no output of its own; what it builds is GENERIC
and that belongs to F04. So the readout here is the diagnostic, which turns out to carry far
more than the sentence: a primary location, secondary locations, and a machine applicable
repair, all of which GCC will print as SARIF if you ask.

Everything runs out of `corpora/diag/f03.json`: fifteen programs, twenty two diagnostics, and
two counts taken off the pinned tree. The source spans are in `corpora/source/f03.json`, so a
reader who cloned shallow and has no `vendor/gcc` sees the same parser code as everybody else.

The reader is expected to have done F02. This lesson does not re-explain what a token is.
"""

from tools.nbbuild import Lesson

lesson = Lesson(
    "f03-four-tokens",
    "f03",
    title="The C parser can see four tokens",
    milestone="M3",
    summary=(
        "That GCC's C parser is hand written recursive descent whose whole memory is four "
        "token slots and the symbol table; why one missing semicolon produces eight "
        "different messages; why the caret is on the line above the mistake; why three "
        "mistakes come out as two errors; and why `A * b;` needs a symbol table to read"
    ),
)
badge = lesson.badge
cite = lesson.cite
term = lesson.term
claim = lesson.claim


lesson.md(f"""
# F03. The C parser can see four tokens

{badge}

Here is a line of C.

```c
A * b;
```

You cannot tell what it means. If `A` is a type, it declares `b` as a pointer to `A`. If `A`
is a variable, it multiplies two numbers and throws the answer away. The tokens are identical
in both cases, so no amount of staring at them will settle it, and neither will any grammar
written over token types alone.

GCC settles it by asking the symbol table, in the middle of lexing, before the {term("parser")}
has decided what it is reading. That one compromise is the seam this whole lesson runs along,
and the other end of it is every error message you have ever sworn at.

You need a browser. Everything below runs on a recording of fifteen small programs, so you see
what the lesson saw.

**What you come away with**

- Knowing that the C parser is written by hand, is recursive descent, and can see exactly four
  tokens
- Being able to explain why `A * b;` needs a {term("typedef name")} lookup, and what breaks
  when the lookup happens at the wrong moment
- Being able to predict which of eight versions of the same mistake gets which sentence
- Knowing why the caret is on the line above the mistake, and when it is not
- Knowing what {term("error recovery")} is and why the first error is the only one to trust
- Being able to read a {term("diagnostic")} as a structure rather than as a line of text
- Knowing how big the C parser is, and how little of it is about C
""")

lesson.setup()

lesson.md(f"""
## One word, two meanings

Start with the measurement from the top. Two programs. They differ in one word on line 1, and
line 3 is byte for byte the same in both.
{claim("the same line of C means two different things depending on a declaration above it")}.
""")

lesson.code("""
from gxray import cparse

rec = cparse.load("f03")
a, b = rec["meaning-typedef"], rec["meaning-variable"]

print(f"recorded {rec.recorded}")
print(f"{rec.compiler} for {rec.target}")
print()
for one in (a, b):
    print(f"--- {one.name}: {one.about}")
    print(one.source)

print(f"line 3 is the same in both: {a.line(3) == b.line(3)}")
print(f"  {a.line(3)!r}")
""")

lesson.md("""
Same line. Now what GCC said about each of them, with `-Wall -Wshadow` on so that it has
something to say at all. Neither program is wrong; the question is what GCC thinks line 3 is.
""")

lesson.code("""
for one in (a, b):
    print(f"--- {one.name}")
    print(one.text)
""")

lesson.md("""
Read the two carefully, because they are not two versions of one complaint. They are two
different readings of one line.

In the first, `A` is a type, so `A * b;` declares a variable called `b`, and GCC warns that it
shadows the `b` at file scope and then that nobody uses it. In the second, `A` is an `int`, so
`A * b;` is a multiplication whose result goes nowhere, and GCC warns about a statement with no
effect. The caret moves too: column 20 in the first, under the `b` being declared, and column
18 in the second, spanning the whole expression with `~~^~~`.

One word on line 1 changed which of two grammar rules line 3 matched. That is the thing C has
that most languages do not, and it is the reason the next section is about a struct rather than
about a grammar.
""")

lesson.code("""
for one in (a, b):
    kinds = [f"{d.level}: {d.message}" for d in one.diagnostics]
    print(f"{one.name:<18}{len(one.diagnostics)} diagnostics")
    for text in kinds:
        print(f"    {text}")
""")

lesson.md(f"""
## Four slots

The C parser is not generated. There is no grammar file, no table, and nothing that looks like
yacc. It is a few hundred functions that call each other, one per construct in the language,
and its entire state is one struct. Here is the top of it.
""")

lesson.code("""
from gxray import source

cuts = source.load_extract("f03")
row = cuts["slots"]

print(f"{row.span}  ({row.citation})")
print(row.about)
print()
print(row.numbered())
""")

lesson.md(f"""
`c_token tokens_buf[4]`. Four. That is how much of your program the parser can see at once, and
the comment above the struct says two, which was true when somebody wrote it and has not been
true for years. The buffer is the whole of the {term("lookahead")}, and nothing anywhere widens
it.

Note what is not in that struct: your file. There is no buffer of text, no array of every
token, no tree of what has been read so far. Tokens arrive one at a time, are looked at, and
are gone. The C++ front end does lex the whole file up front, and the C front end has a comment
about wishing it did.
""")

lesson.code("""
print(cuts["intermediates"].numbered())
""")

lesson.md(f"""
Two more things worth having in your head before the evidence starts.

The first is that everything the parser will ever know about your program arrives through one
function. This is the seam F02 finished at, seen from the other side.
""")

lesson.code("""
print(cuts["handover"].numbered())
""")

lesson.md("""
`c_lex_with_flags`. One token, out of libcpp, into a `c_token`. Every fact in this lesson is
downstream of that call, and the parser has no other way of finding anything out.

The second is that the top level of the C language, the rule that says what a whole file is, is
six lines of code.
""")

lesson.code("""
print(cuts["loop"].numbered())
""")

lesson.md(f"""
A `do` loop calling `c_parser_external_declaration` until the next token is the end of the file,
with a garbage collection on each turn. A {term("translation unit")} is a list of declarations,
and the code says so about as directly as code can.

## The symbol table answers early

Back to `A * b;`. Somebody has to decide whether `A` is a type, and the place it happens is not
where you would guess. It is in the lexer, while the token is being made.
""")

lesson.code("""
print(cuts["lookup"].numbered())
""")

lesson.md(f"""
`lookup_name`, then `TYPE_DECL`, then the answer written into the token as `C_ID_TYPENAME` or
`C_ID_ID`. The token stops being an identifier and becomes an identifier-that-names-a-type,
permanently, at the moment it is first lexed.

Permanently is the problem. A token can be peeked while one scope is open and used after that
scope has closed, and then it is carrying an answer from a symbol table that no longer looks
like that. Here is the smallest program anybody found that does it.
{claim("swapping which of two declarations is the typedef changes whether a later line compiles")}.
""")

lesson.code("""
first, second = rec["scope-typedef"], rec["scope-variable"]

for one in (first, second):
    print(f"--- {one.name}: {one.about}")
    print(one.source)
""")

lesson.md("""
Line 4 opens a `for` header, which is a scope. It declares `T` inside that scope, one way in
each program. Line 7, after the loop has closed, uses `T`. Predict what happens to line 7 in
each before running the next cell.
""")

lesson.code("""
for one in (first, second):
    print(f"--- {one.name}")
    print(one.text or "nothing at all")
""")

lesson.md(f"""
In the first, `T` is a file scope type shadowed by a local variable, the shadow ends with the
loop, and `T *x;` on line 7 declares a pointer. Two unused variable warnings and no errors.

In the second the two are swapped, so `T` is a file scope variable shadowed by a local typedef,
and by line 7 the typedef is out of scope, so `T *x;` is a multiplication of `T` by an undeclared
`x`. GCC says `'x' undeclared`, which is a strange thing to be told about a line that looks like
a declaration, and is exactly right.

The reason the first one works is a function that exists to undo the early answer.
""")

lesson.code("""
print(cuts["reclassify"].numbered())
""")

lesson.md(f"""
`c_parser_maybe_reclassify_token`, and the comment names the bug: PR67784, a `for` loop with an
`if` and no `else` in the body. Both of the programs above are distilled from that bug's test
cases, which are in the tree at `gcc/testsuite/gcc.dg/pr67784-1.c` and `-2.c`. The fix is to
look the identifier up again, after the scope closes, and overwrite the answer.

Two things to take from this. One is that the lexer hack is not a metaphor: the classification
is literally stored in the token. The other is that when a design has a seam in it, the bugs
gather at the seam, and the patches are named after the bug reports.

## One mistake, eight sentences

Now the part of the lesson that is worth the price of admission.

Eight programs. Every one of them is the same mistake: a missing semicolon after `return 1`.
They differ in what comes next, and nothing else.
{claim("one missing semicolon produces eight different messages depending on what follows it")}.
""")

lesson.code("""
same = ("brace", "name", "number", "string", "char", "keyword", "pragma", "eof")

for key in same:
    one = rec[key]
    print(f"{key:<10}{one.line(1)!r}")
""")

lesson.md("""
Eight programs, one mistake. Now the messages. Read the list before reading the paragraph after
it, because the shape of the list is the point.
""")

lesson.code("""
for key in same:
    error = rec[key].errors[0]
    print(f"{key:<10}{str(error.at):<10}{error.message}")

sentences = {rec[k].errors[0].message for k in same}
print()
print(f"{len(sentences)} different sentences from {len(same)} copies of one mistake")
""")

lesson.md(f"""
Eight sentences. The parser wanted a semicolon in every one of them and the semicolon was
missing in every one of them, and it said eight different things, because the second half of
the sentence is chosen by the token it happened to be looking at when it gave up.

Look at the column too. Seven of the eight say 23. One says 25. Hold on to that; it is the next
section but one.

## Where the sentence is made

There is one function that finishes these sentences, and it is shared by the C and C++ front
ends. A parser function passes in a complaint like `expected ';'` and the token type, and gets
back a whole sentence.
""")

lesson.code("""
print(cuts["suffixes"].numbered())
""")

lesson.md(f"""
`catenate_messages (gmsgid, " at end of input")`. That is the first of thirteen branches, and
the rest are the same shape. `gxray` has all thirteen transcribed, so you can see the range of
endings a complaint can be given.
""")

lesson.code("""
for one in cparse.SUFFIXES:
    kinds = ", ".join(one.types) or "everything else"
    print(f"{one.text!r}")
    print(f"    {one.about}")
    print(f"    {kinds}")
""")

lesson.md(f"""
Thirteen endings, and the last is a catch-all with a range test rather than a list, which is
where every punctuation mark in the language ends up. That is why `expected ';' before '}}'
token` has the word `token` on the end and `expected ';' before numeric constant` does not: two
different branches wrote them.

Now the check. Take the eight recorded messages and ask which branch could have produced each.
{claim("every parser error message ends in one of thirteen phrases chosen by token type")}.
""")

lesson.code("""
for key in same:
    error = rec[key].errors[0]
    found = error.suffixes
    which = found[0].about if len(found) == 1 else f"cannot tell: {len(found)} branches match"
    print(f"{key:<10}{error.message:<42}{which}")
""")

lesson.md("""
Six of the eight are pinned to one branch. Two are not, and the reason is worth a moment.

`char` and `name` both end in a single character inside single quotes. One of them is a
character constant, printed by the branch for character constants. The other is a one letter
identifier, printed by the branch that quotes identifiers back at you with `%qE`. Rendered as
text they are indistinguishable, and no amount of care in this module can separate them.

That is a real limit and it is worth naming rather than papering over. The recorded message is
all a notebook has. GCC, which had the token, knew perfectly well which one it was.

## Where the caret goes

Back to the column. Seven of the eight put the caret at 23 and one puts it at 25.
""")

lesson.code("""
for key in same:
    error = rec[key].errors[0]
    hint = f"fix-it: insert {error.fixes[0].insert!r}" if error.fixes else "no fix-it"
    print(f"{key:<10}column {error.at.column:<4}{hint}")
""")

lesson.md(f"""
The split is exact. Seven carry a {term("fix-it hint")} and sit at column 23. One has no hint
and sits at column 25. Here is the odd one out with its caret, next to one of the seven.
""")

lesson.code("""
for key in ("brace", "name"):
    print(f"--- {key}")
    print(rec[key].text)
""")

lesson.md(f"""
Column 23 is one past the `1` in `return 1`, which is where the semicolon should have gone.
Column 25 is the `b`, which is the token that upset the parser. So the seven point at the
mistake and the odd one points at the symptom, and the difference between them is whether GCC
was willing to suggest a repair.

It will suggest one for seven token types, and no others.
""")

lesson.code("""
print(cuts["insertion"].numbered())
""")

lesson.md(f"""
Two go before the next token, five go after the previous one, and everything else gets nothing.
`gxray` keeps the same table, so a notebook can talk about it.
""")

lesson.code("""
for token, side in cparse.INSERTION.items():
    print(f"    {token!r:<6}goes {side}")

print()
print(f"{sum(1 for s in cparse.INSERTION.values() if s == 'before')} before the next token")
print(f"{sum(1 for s in cparse.INSERTION.values() if s == 'after')} after the previous one")
""")

lesson.md(f"""
And then the part that actually moves the caret. When GCC works out where the missing token
should go, it decides that the repair is a better place to point than the token that tripped
over. So it swaps them: the fix-it location becomes the primary one and the old primary becomes
a secondary. GCC explains this in its own comment, with a diagram.
{claim("GCC moves the caret from the token it choked on to the place the fix-it hint goes")}.
""")

lesson.code("""
print(cuts["swap"].numbered())
""")

lesson.md("""
That comment is the single most useful thing in this lesson to have read once. Every time an
error about a semicolon points at the line above the one you were editing, this is why, and it
is deliberate, and it is right.

The swap leaves evidence. The old primary location is still on the diagnostic, as a secondary,
and the recording keeps those.
""")

lesson.code("""
one = rec["brace"]
error = one.errors[0]

print(f"caret at    {error.at}")
print(f"fix-it at   {error.fixes[0].at}, inserting {error.fixes[0].insert!r}")
print(f"secondary   {', '.join(str(s) for s in error.related)}")
print(f"caret moved {error.moved}")
print()
print(f"    {one.line(1)}")
print(f"    {one.under(error)}   the caret, at the missing semicolon")
""")

lesson.md(f"""
The secondary is at 1:24, which is the `}}`. The caret is at 1:23, which is the gap. Both are
on the diagnostic and only one of them is drawn with a `^`.

Two functions produce parser errors and the difference between them is exactly this. One puts
the caret on the token it can see.
""")

lesson.code("""
print(cuts["report"].numbered())
""")

lesson.md(f"""
The other knows which token you left out, and so can offer a hint and move the caret.
""")

lesson.code("""
print(cuts["require"].numbered())
""")

lesson.md("""
`maybe_suggest_missing_token_insertion`, then `add_location_if_nearby`, then the error. The
`name` case went through the first function, because `expected ',' or ';'` names two possible
tokens and `type_is_unique` is false, and you cannot suggest inserting one of two things. So no
hint, no swap, and the caret stays on the `b`.

One error message, one extra token in the program, and a whole different code path. That is
what the column 23 against column 25 split was telling you.

## Three mistakes, two errors

Next irritation. Here is a function with three missing semicolons in it.
{claim("three missing semicolons produce two errors, not three")}.
""")

lesson.code("""
one = rec["recovery"]

print(one.source)
print(one.text)
print(f"{len(one.errors)} errors for three mistakes")
""")

lesson.md(f"""
Two errors for three mistakes, and the second one is not about a semicolon at all. It says
`expected declaration or statement at end of input`, pointing at the closing brace on line 6,
which is a fine and correct closing brace.

Two things happened. The first is {term("error recovery")}: after complaining on line 4 the
parser threw tokens away looking for somewhere to start again, and what it found was the end of
the function. The second is a latch.
""")

lesson.code("""
print(cuts["latch"].numbered())
""")

lesson.md(f"""
`if (parser->error) return false;` and then `parser->error = true;`. Once the parser has
complained, it will not complain again until something clears the flag, which is what stops one
missing brace from producing four hundred errors.

The rule to carry away is short. **The first error is the one to trust.** Everything after it
was produced by a parser that had already lost its place, and the usual outcome of fixing the
first one is that the rest go away.

## The bracket it points back at

One more piece of the diagnostic structure, because it is the one people notice and cannot
explain. Here is an unclosed bracket.
""")

lesson.code("""
one = rec["paren"]

print(one.source)
print(one.text)
""")

lesson.md(f"""
Look at what that drew. A caret on line 4, a `~` under the `(` on line 4, and another `~` under
the `g` on line 5. Three places, one message, two lines apart.
{claim("one diagnostic can point at three places on two lines")}.
""")

lesson.code("""
error = one.errors[0]

print(f"caret     {error.at}")
print(f"fix-it    {error.fixes[0].at}, inserting {error.fixes[0].insert!r}")
for span in error.related:
    print(f"secondary {span}   {one.line(span.line)!r}")
""")

lesson.md("""
That is `matching_location` in `c_parser_require`, the argument the last section walked past.
When a parser function asks for a closing bracket it passes the location of the opening one, and
`add_location_if_nearby` folds it into the same diagnostic if it will fit on the display.

Which is why the message is `expected ')' before 'g'` and not `expected ')'`: three locations,
one sentence, and enough for you to see the bracket you left open without going to look for it.

## The deepest it ever looks

The parser has four slots. The obvious question is what needs the fourth, and the answer is not
a C construct.
""")

lesson.code("""
one = rec["conflict"]

print(one.source)
print(one.text)
""")

lesson.md(f"""
Three errors, all the same sentence, each one seven columns wide. That is not a parse error. It
is GCC recognising that somebody committed a merge conflict.
""")

lesson.code("""
print(cuts["conflict"].numbered())
""")

lesson.md(f"""
`c_parser_peek_2nd_token`, then `peek_nth_token (parser, 3)`, then `peek_nth_token (parser, 4)`.
A run of seven `<` characters arrives from the lexer as three `CPP_LSHIFT` tokens and one
`CPP_LESS`, so recognising it takes four tokens, which is exactly how many there are. Then a
column check, because a conflict marker is at the start of a line and `a << b << c << d` is not.

Count how often the parser looks that far.
""")

lesson.code("""
look = rec.lookahead

print(f"{look.slots} token slots in the struct")
print(f"{look.peeks} calls to c_parser_peek_token, which looks at one")
print(f"{look.seconds} calls to c_parser_peek_2nd_token, which looks at two")
print()
for depth in sorted(look.depths):
    print(f"{look.depths[depth]:>3} calls to peek_nth_token with a constant {depth}")
print(f"deepest constant peek: {look.deepest}")
""")

lesson.md("""
Seven hundred and twenty nine one token peeks, ninety nine two token peeks, and eleven that name
a depth as a constant. Three of those eleven are the four deep ones, and all three are in the
conflict marker function you have on the screen.

So the fourth slot exists for a thing that is not part of C, and the entire C language is parsed
in three. That is not a criticism of anybody. It is what a language designed to be compiled in
one pass on a PDP-11 looks like from the inside, and it is the reason the error messages are the
shape they are: a parser that can see three tokens cannot know what you meant.

## The size of the thing

Two counts to finish, both taken off the pinned tree rather than described.
""")

lesson.code("""
grammar = rec.grammar
parts = grammar.dialects

print(f"{len(grammar)} functions named c_parser_* in gcc/c/c-parser.cc")
print()
for name, names in sorted(parts.items(), key=lambda kv: -len(kv[1])):
    share = 100 * len(names) / len(grammar)
    print(f"{name:<22}{len(names):>4}  {share:4.1f}%")
""")

lesson.md(f"""
Under half the C parser is for C. There are more functions for OpenMP than for the language, and
the total is three hundred once you add OpenACC, Objective-C and transactional memory. If you go
looking for the function that parses a `while` loop and find yourself in a file whose contents
are mostly pragma directives for a parallelism standard, that is why.

Here is a sample of the ones that are about C, so the naming convention is visible.
""")

lesson.code("""
wanted = ("declaration", "statement", "expression", "initializer", "struct", "label", "typeof")

for name in grammar.named(*wanted):
    print(f"    {name}")
""")

lesson.md(f"""
`c_parser_` and then the name of the thing in the grammar. Once you know that, finding the code
for any construct in C is one search, which is the practical thing this section is for.

## Same parser, different machine

One last check, and it is the one that says which of the facts above are about C and which are
about this laptop. Three of the programs were also compiled by an x86-64 Linux GCC of the same
release, through Compiler Explorer.
{claim("the same program produces character for character the same diagnostics on two targets")}.
""")

lesson.code("""
shared = [one for one in rec if one.elsewhere]

for one in shared:
    print(f"{one.name:<20}{'same' if one.agrees else 'DIFFERENT'}   {one.about}")

print()
print(f"{len(shared)} programs compiled twice, on {rec.target} and on x86-64 Linux")
""")

lesson.md(f"""
Identical. Which is the shape of the subject, the same as it was in F02: whether `A * b;` is a
declaration is a fact about C, and it will read the same on a compiler for a processor nobody
has built yet. The target gets a say in what `int` is worth. It gets no say at all in what the
parser thinks you wrote.

## Boss fight

No new tools. Three questions, answerable from the recording:

1. Eight programs, one missing semicolon each, eight different sentences. Seven of them put the
   caret at column 23. Which one does not, and what is different about it?
2. Thirteen phrases can end a parser complaint, and two of the eight recorded messages cannot be
   pinned to one of them from the text alone. Which two, and why not?
3. The parser has four token slots. How many calls in the whole file pass a constant 4 to
   `c_parser_peek_nth_token`, and what are they all for?

Then check yourself:

```text
python lessons/f03-four-tokens/grade.py
```

or, from a checkout, `just grade f03-four-tokens`. It takes answers on the command line too, so
`--odd name --unsure char,name --deep 3` is a whole submission. Every answer it marks against is
worked out from the recording rather than written down.

## What to read next

F04 is GENERIC, which is what this parser produces. The parser has been throwing tokens away
this whole lesson and building something out of them, and F04 is the something.

F02 is the lesson before this one, if you have not done it. It is where the tokens come from.

If you have a GCC on your machine, every measurement here is one command.
`printf 'int f(void) {{ return 1 }}' | gcc -fsyntax-only -xc -` is the first one, and
`-fdiagnostics-format=sarif-stderr` on the end of it is the structure behind the sentence. Change
the `}}` to a `1` and watch the column move.
""")

raise SystemExit(lesson.save())
