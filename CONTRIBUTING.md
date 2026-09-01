# Contributing

Thanks for looking. This is a book about GCC that tries very hard to be right, so most of the rules below are about being right rather than about style.

## The short version

Run `just check` before you push. It runs the linter, the prose rules and the tests, and it is the same thing CI runs.

## What a lesson has to have

Nine blocks, in this order. `just new-lesson <id>` writes the skeleton so you never assemble it by hand.

1. The question, phrased as something a reader would actually wonder
2. The build banner, which says which compiler and which backend produced everything below it
3. The hook, under 150 words, with a surprise the reader can run right now
4. The tour, the prose, under 1500 words, every claim cited
5. One picture, not three
6. A Tier 0 experiment that runs in a browser and also runs with the network switched off
7. A Tier 1 experiment for people with a local toolchain
8. A boss fight with a grader that exits 0 or 1 and says something useful when it fails
9. The blueprint link, and what you can now do that you could not do before

## Rules that get enforced by a script

- No em dashes and no en dashes
<!-- prosecheck: off, this line has to quote the words it bans -->
- No "simply", "just", "obviously", "of course", "merely" or "trivially" in prose
<!-- prosecheck: on -->
- No sentence wrapped across two lines, because markdown joins them anyway and it only makes diffs worse
- No horizontal rules
- Every fenced code block declares a language

Code spans and code blocks are exempt from the first three, so `just build` and a raw GIMPLE dump are both fine.

## Rules that need a human

- Every dump excerpt says the exact command that produced it, including the target
- Never show a transformation without showing the before
- Never quote generated code as if somebody wrote it, so `insn-recog.cc` always appears next to the `.md` pattern it came from
- Say which target, because most back end observations are not universal
- Never present a heuristic as a rule, and show the `--param` that moves it
- Numbers come from generated JSON, never from memory

## Review

Two reviewers per lesson. One at or below the target reader's level, one at or above GCC contributor level. The beginner review is the one that gets skipped under pressure and it is the one that matters most.

The beginner reviewer answers: where did you get lost, which word was used before it was defined, what did you have to read twice, did the Tier 0 experiment work first time, and could you do the boss fight.

The expert reviewer answers: is anything wrong, is anything stale, is any citation misleading, is any target specific behaviour presented as universal, and does the blueprint actually specify the thing.

## Licence

By contributing you agree that prose goes out under CC BY-SA 4.0 and code goes out under GPLv3 or later.
