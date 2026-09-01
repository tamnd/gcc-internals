# Licence

This repository holds two kinds of thing and they carry two different licences.

## Prose, diagrams, animations and notebook narrative

Creative Commons Attribution ShareAlike 4.0 International, in `LICENSE-CONTENT.txt`.

That covers `lessons/**/lesson.md`, `lessons/**/tier1.md`, `blueprints/`, `README.md` and every animation and diagram. Share it, translate it, teach from it, sell a course built on it. Keep the attribution and pass the same freedom on.

## Code

GNU General Public License version 3 or later, in `LICENSE-CODE.txt`.

That covers `gxray/`, `gxplug/`, `gxwidgets/`, `gxmanim/`, `tools/`, `capstones/`, `conformance/`, every `grade.py` and every notebook cell.

`gxplug` has to be GPL compatible whatever we would have preferred, because GCC only loads plugins that declare a GPL compatible licence, and everything else in the project talks to it. Matching GCC's own licence is the simple answer.

## Not covered

GCC itself is not in this repository. It arrives as a git submodule pinned to `releases/gcc-16.2.0` and stays under its own licence, which is GPLv3 with the GCC Runtime Library Exception.
