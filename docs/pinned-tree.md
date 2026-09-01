# The pinned tree and how citations work

Every claim this book makes about GCC's code points at a file, a line and a release tag:

```text
gcc/passes.cc:855@releases/gcc-16.2.0
```

`vendor/gcc` is a git submodule holding the GCC source at exactly that tag, and `refcheck` resolves every citation against it on every push. It hashes the cited line together with two lines either side, and records the hash in `citations.lock.json`. When the hash changes, the build fails and a person has to reread the claim.

## Why go to the trouble

Three reasons, in order of how much they matter.

The first is that the book has to survive a version bump. GCC releases twice a year. Without machine checked citations, a bump means rereading every claim in the book by hand, which means the bump never happens, which is how writing about compilers ends up accurate about GCC 4.4 and quietly wrong about everything after it. That is the failure mode this project is trying hardest to avoid, and it is a tooling problem before it is a writing problem.

The second is that citing the wrong line is easy and embarrassing. Off by one is the usual version. A hash over a small window catches it while the author is still writing, not in a reader's bug report two years later.

The third is that a citation makes "I read this in the source" checkable by a stranger. `refcheck show` prints the lines any citation points at, so a reader can look without cloning anything.

```console
$ refcheck show gcc/passes.cc:855@releases/gcc-16.2.0
     853       and to specify dump file name and option.
     854       The latter two might want something short which is not quite unique; for
>    855       that reason, we may have a disambiguating prefix, followed by a space
     856       to mark the start of the following dump file name / option string.  */
     857    name = strchr (pass->name, ' ');

hash 427de223d27ef038
```

## The rules

**One tag at a time.** A citation naming a tag other than the pinned one is refused. Moving the book to a new GCC release is a deliberate act with its own pull request, not something that happens one citation at a time.

**Never cite a generated file.** `gimple-match.cc`, `insn-recog.cc`, `options.cc` and their relatives do not exist until GCC is built, and their line numbers depend on the build. A citation into one is meaningless to a reader. `refcheck` refuses it and says which file to cite instead, so a claim about a match pattern points at `gcc/match.pd` and names the generated file as context.

**A new citation has to be locked before it passes.** `refcheck check` fails on a citation that is not in the lockfile, so `refcheck update` has to run and the new hash shows up in the diff. A citation entering the book is a thing a reviewer sees. This is the same rule as the Compiler Explorer response cache, for the same reason: anything that reaches outside the repository should be visible in review.

**The window is five lines.** The cited line and two either side. Wider windows fail the build for edits that have nothing to do with the claim, and a check that cries wolf gets switched off within a month. Narrower windows miss the off by one, which is most of what this catches.

## What it already found

The submodule paid for itself before the tool was finished.

`gxray` reads GCC's pass list out of `-fdump-passes` and derives the dump file name from the pass name. Two passes at `-O2` have a space in the name, `rtl-rtl pre` and `rtl-no-opt dfinit`, and `gxray` was building the dump names `rtl-rtl pre` and `rtl-no-opt dfinit` from them. The real dumps are called `rtl-pre` and `rtl-dfinit`.

The reason is in the source, four lines of comment above the code that does it:

```text
gcc/passes.cc:855@releases/gcc-16.2.0

  /* The name is both used to identify the pass for the purposes of plugins,
     and to specify dump file name and option.
     The latter two might want something short which is not quite unique; for
     that reason, we may have a disambiguating prefix, followed by a space
     to mark the start of the following dump file name / option string.  */
  name = strchr (pass->name, ' ');
  name = name ? name + 1 : pass->name;
```

A pass name may carry a disambiguating prefix, then a space, then the name to use for the dump. The dump takes the part after the space. The pass list prints the whole thing, prefixed again with the phase, which is why `rtl pre` shows up as `rtl-rtl pre`.

Guessing at that from the outside would have produced a rule that looked right and was wrong. Reading it took two minutes because the tree was already sitting there at the right tag.

## Passes with no name

Two lines of the pass list at `-O2` read `(null)`.

That is not GCC being coy. The pass list prints a name looked up in a table, and falls back to the pass's own name only for the first instance of a pass:

```text
gcc/passes.cc:974@releases/gcc-16.2.0

  if (pass->static_pass_number <= 0)
    pn = pass->name;
  else
    pn = pass_tab[pass->static_pass_number];
```

The table is cleared and then filled by walking the map of registered pass names, and passes whose name begins with `*` are never registered, since the star is how GCC marks a pass with no dump file of its own. An entry nobody filled stays null, and `%s` on a null pointer prints `(null)`.

One of the two is `pass_ipa_asm_wpa`. It is the second instance of a pass whose data declares the name `ipa-asm`, and the first instance is the line above it in the list, printed as `ipa-ipa-asm`. So the pass list is showing the same pass twice and only naming it once.

`gxray` keeps these rather than dropping them, and marks them. The first version of the parser skipped every line it did not recognise and reported 391 passes where GCC had printed 395. Nothing crashed. The number was wrong, in a way no reader could have caught, which is the exact failure this whole apparatus exists to prevent.

## Working with the submodule

The tree is about 1.3 GB shallow, so it is not cloned unless you ask for it:

```console
git submodule update --init --depth 1
```

Everything except `refcheck` works without it. `refcheck` says so plainly rather than failing in a confusing way.

```console
refcheck check         # verify every citation
refcheck update        # rebuild the lockfile after adding one
refcheck list          # every citation and where it is written
refcheck show CITE     # print the lines a citation points at
```
