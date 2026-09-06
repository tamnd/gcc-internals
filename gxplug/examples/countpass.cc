/* countpass — a pass of your own, inserted between two of GCC's.

   The interesting half of the plugin mechanism. A callback watches; a registered pass is
   *in* the pipeline, gets its own entry in -fdump-passes, its own dump file, and runs at a
   point you choose relative to a pass that already exists.

   The choice is three fields of one struct. reference_pass_name names an existing pass,
   ref_pass_instance_number says which run of it (1 for the first, 0 for every one), and
   pos_op says before, after, or instead of. Here: after the first run of the pass named
   "ssa", which is where the function has just acquired SSA form.

   This pass reads and prints. It does not modify the IR, so the assembly comes out
   unchanged, which examples/check in the Makefile insists on.

     gcc-16 -O2 -S -fplugin=./examples/countpass.so t.c -o t.s

   Copyright the gcc-internals authors.
   SPDX-License-Identifier: GPL-3.0-or-later  */

#include "gcc-plugin.h"
#include "config.h"
#include "system.h"
#include "coretypes.h"
#include "tree.h"
#include "tree-pass.h"
#include "context.h"
#include "function.h"
#include "basic-block.h"
#include "gimple.h"
#include "gimple-iterator.h"
#include "ssa.h"
#include "plugin-version.h"

int plugin_is_GPL_compatible;

namespace {

/* Everything a pass has to say about itself before the pass manager will take it. The
   fields are positional and the order is fixed by the struct in tree-pass.h; getting one
   wrong is a compile error here rather than something that goes wrong at run time.  */
const pass_data count_pass_data = {
  GIMPLE_PASS,		/* type: what IR this pass wants */
  "gxcount",		/* name: appears in -fdump-passes and names the dump file */
  OPTGROUP_NONE,	/* optinfo_flags */
  TV_NONE,		/* tv_id: no timer of its own */
  PROP_ssa,		/* properties_required: refuse to run before SSA exists */
  0,			/* properties_provided */
  0,			/* properties_destroyed */
  0,			/* todo_flags_start */
  0,			/* todo_flags_finish: nothing to clean up, because nothing changed */
};

class count_pass : public gimple_opt_pass
{
public:
  count_pass (gcc::context *ctxt) : gimple_opt_pass (count_pass_data, ctxt) {}

  /* Every pass has a gate and a body. A gate returning false is why -fdump-passes prints
     OFF next to a pass on a given function.  */
  bool gate (function *) final override { return true; }

  unsigned int execute (function *fun) final override
  {
    int statements = 0, phis = 0;
    basic_block bb;
    FOR_EACH_BB_FN (bb, fun)
      {
	for (gphi_iterator gsi = gsi_start_phis (bb); !gsi_end_p (gsi); gsi_next (&gsi))
	  phis++;
	for (gimple_stmt_iterator gsi = gsi_start_bb (bb); !gsi_end_p (gsi); gsi_next (&gsi))
	  statements++;
      }
    fprintf (stderr, "gxcount: %s has %d block(s), %d phi(s), %d statement(s)\n",
	     function_name (fun), n_basic_blocks_for_fn (fun), phis, statements);

    /* The return value is a TODO mask: what the pass manager should do now that this pass
       has run. Zero means nothing changed and nothing needs cleaning up. A pass that
       modified the IR and returned zero is how a plugin corrupts a compilation.  */
    return 0;
  }
};

} /* anonymous namespace */

int
plugin_init (plugin_name_args *info, plugin_gcc_version *version)
{
  if (!plugin_default_version_check (version, &gcc_version))
    return 1;

  /* PLUGIN_PASS_MANAGER_SETUP is not an event. It is never fired; register_callback sees
     the name and does the insertion there and then, using the fourth argument, which for
     every real event would be user data handed back to a callback later.  */
  struct register_pass_info info_for_pass;
  info_for_pass.pass = new count_pass (g);
  info_for_pass.reference_pass_name = "ssa";
  info_for_pass.ref_pass_instance_number = 1;
  info_for_pass.pos_op = PASS_POS_INSERT_AFTER;

  register_callback (info->base_name, PLUGIN_PASS_MANAGER_SETUP, nullptr, &info_for_pass);
  return 0;
}
