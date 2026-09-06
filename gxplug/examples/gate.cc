/* gate — switching one of GCC's own passes off from outside.

   PLUGIN_OVERRIDE_GATE is the only event whose data is written rather than read. The pass
   manager has just asked a pass whether it wants to run, and it hands the plugin the
   address of the answer. Assigning through that pointer changes the decision.

   There is no command line flag for most of the passes this can reach, and no patch
   involved. It is also the point at which a plugin stops being an observer: the assembly
   that comes out is different, and it is different because of you.

     gcc-16 -O2 -S -fplugin=./examples/gate.so -fplugin-arg-gate-off=ivopts t.c -o t.s

   The name to give is the pass name, not the dump name. -fdump-tree-cddce1 is the pass
   called "cddce" on its first instance, and asking to switch off "cddce1" matches nothing
   and reports nothing, which is why this prints a count.

   Copyright the gcc-internals authors.
   SPDX-License-Identifier: GPL-3.0-or-later  */

#include "gcc-plugin.h"
#include "config.h"
#include "system.h"
#include "coretypes.h"
#include "diagnostic-core.h"
#include "tree.h"
#include "tree-pass.h"
#include "context.h"
#include "function.h"
#include "plugin-version.h"

int plugin_is_GPL_compatible;

namespace {

const char *turn_off = nullptr;
int refusals = 0;

void
on_gate (void *gcc_data, void * /*user_data*/)
{
  bool *gate_status = (bool *) gcc_data;

  /* Which pass is being asked is not in the data. It is in current_pass, a global the pass
     manager sets before it asks, which is the sort of thing that is obvious once you have
     read passes.cc and undiscoverable before.  */
  if (!current_pass || !current_pass->name || !turn_off)
    return;
  if (strcmp (current_pass->name, turn_off) != 0)
    return;

  /* Only ever turning a pass off. Turning one *on* by writing true here runs a pass whose
     own gate said no, which usually means its preconditions are not met.  */
  if (*gate_status)
    {
      *gate_status = false;
      refusals++;
    }
}

void
on_finish (void * /*gcc_data*/, void * /*user_data*/)
{
  fprintf (stderr, "gate: refused %s %d time(s)\n", turn_off ? turn_off : "(nothing)",
	   refusals);
}

} /* anonymous namespace */

int
plugin_init (plugin_name_args *info, plugin_gcc_version *version)
{
  if (!plugin_default_version_check (version, &gcc_version))
    return 1;

  for (int i = 0; i < info->argc; i++)
    if (strcmp (info->argv[i].key, "off") == 0)
      turn_off = info->argv[i].value;

  if (!turn_off)
    {
      error ("gate: give %qs, the name of a pass to switch off", "off=");
      return 1;
    }

  register_callback (info->base_name, PLUGIN_OVERRIDE_GATE, on_gate, nullptr);
  register_callback (info->base_name, PLUGIN_FINISH, on_finish, nullptr);
  return 0;
}
