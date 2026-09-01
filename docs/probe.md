# Can a browser compile C here

This page exists to answer one question, and it answers it by doing the thing rather than by arguing about it.

Every Tier 0 experiment in this book is a marimo notebook running Pyodide in your browser, and every one of them needs to reach the Compiler Explorer API to get a real compiler. That request has to work from a static site, from a page served by GitHub Pages, under whatever content security policy the site ends up with, through Pyodide's fetch shim, with a response that can run to hundreds of kilobytes. Any one of those could break it, and finding out in month ten with forty lessons built on top would be an expensive way to learn.

So here is the request, on the real site, with nothing in front of it. No proxy, no mock, no recorded response. Press the button, wait for Python to start, then compile.

<!-- island: site/notebooks/ce-probe.py -->

## What you should see

Python starts, which is Pyodide coming down from a CDN and takes a few seconds the first time and no time at all after that. The button then posts your program to `godbolt.org/api/compiler/cg162/compile` with `-O2 -fdump-tree-ssa=stderr`, and what comes back is the GIMPLE the real GCC 16.2 built, in SSA form, before any optimizer has touched it.

If it worked, the cell prints the exit code, how many bytes of dump came back, how long the round trip took, and the first two dozen lines. If it did not, it prints the exception, which is the useful part.

## What happens when it does not work

Every lesson has an offline fallback. `gxray` ships a recorded corpus of dumps for the canonical programs, and a notebook that cannot reach the network falls back to it and says so in a banner. You lose the ability to compile your own code, which matters, but nothing in a lesson breaks.

The results of this probe, and what we decided to do about them, are in [open question 1](https://github.com/tamnd/gcc-internals/issues/1).
