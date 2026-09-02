# GCC Internals

Twelve lessons are written and the rest are not. [The lessons](lessons.md) lists what exists, with a Colab badge on each one, and [the glossary](glossary.md) is the one place every term in them is defined.

[The films](films.md) is the shortest way in if you would rather watch than read. Six of them, a minute or so each, each one showing the part of the pipeline that only makes sense as a sequence.

[The blueprints](blueprints.md) are the other half of the project and are not lessons. A blueprint says what GCC does precisely enough to implement against, with every claim citing a line of the pinned source. Nine of a planned fifty eight exist, one of them finished. Read a lesson to understand something, read a blueprint to build it.

The plan is in the [milestones](https://github.com/tamnd/gcc-internals/milestones), and what could still change it is in the [open questions](https://github.com/tamnd/gcc-internals/issues?q=is%3Aissue+label%3Akind%2Fopen-question).

One more page is worth a look. [Can a browser compile C here](probe.md) is a live Python notebook sitting in the middle of a documentation page, and pressing the button on it sends your C to a real GCC 16 and shows you the GIMPLE that comes back. Every hands on part of every lesson is going to work that way, so it is the first thing that had to be proved.
