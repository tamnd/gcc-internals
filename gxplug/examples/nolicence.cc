/* nolicence — a plugin that is refused, on purpose.

   Identical to hello.cc with one symbol deleted. GCC looks for plugin_is_GPL_compatible by
   name after dlopen and before it calls plugin_init, and a plugin without it never runs a
   line of its own code.

   This file exists so that the diagnostic is something a reader has seen once, in a lesson,
   rather than the first thing they meet on their own plugin at eleven at night.

   Copyright the gcc-internals authors.
   SPDX-License-Identifier: GPL-3.0-or-later  */

#include "gcc-plugin.h"
#include "config.h"
#include "system.h"
#include "coretypes.h"
#include "tree.h"
#include "plugin-version.h"

/* The line that is missing:

     int plugin_is_GPL_compatible;  */

int
plugin_init (plugin_name_args * /*info*/, plugin_gcc_version *version)
{
  if (!plugin_default_version_check (version, &gcc_version))
    return 1;
  fprintf (stderr, "nolicence: this line never prints\n");
  return 0;
}
