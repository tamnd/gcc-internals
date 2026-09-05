/* gxplug — a GCC plugin that watches and never touches.

   The text dumps tell you what the IR looked like. They do not tell you which pass ran,
   in what order, how long it took, or what the compiler believed about the IR at that
   moment. This plugin emits that as newline-delimited JSON and changes nothing else.

   The one rule, from 03-architecture.md: gxplug never changes what GCC compiles. A reader
   must be able to add -fplugin=gxplug.so to any command in the book and get byte identical
   code out, plus a stream of events. Everything here is read only for that reason. There
   is no pass registered, no gate overridden and no tree modified.

   Copyright the gcc-internals authors.
   SPDX-License-Identifier: GPL-3.0-or-later  */

#include "gcc-plugin.h"
#include "config.h"
#include "system.h"
#include "coretypes.h"
/* error() lives here, and it is the right way for a plugin to complain: it goes through
   GCC's diagnostic machinery, counts towards the error count, and makes the compilation
   fail rather than printing to stderr and carrying on.  */
#include "diagnostic-core.h"
#include "tm.h"
#include "tree.h"
#include "tree-pass.h"
#include "context.h"
#include "function.h"
#include "basic-block.h"
#include "gimple.h"
#include "gimple-iterator.h"
#include "cgraph.h"
/* For get_insns and NEXT_INSN, which are how the size of a function is measured once it
   is no longer GIMPLE.  */
#include "rtl.h"
/* emit-rtl.h declares need_atomic_barrier_p taking an `enum memmodel`, and does not
   include the header that defines it. GCC's own sources always include memmodel.h first,
   so the omission never shows up in tree; out of tree it is an error about an enum
   without a previous declaration, pointing at a line that has nothing to do with you.  */
#include "memmodel.h"
#include "emit-rtl.h"
#include "plugin-version.h"

/* Without this GCC refuses to load the plugin at all, which is the licence check and not
   a formality.  */
int plugin_is_GPL_compatible;

namespace {

/* Where the stream goes. Default is stderr, so that a reader who adds -fplugin= and
   nothing else sees something. stdout is left alone on purpose: -S writes assembly there
   and the whole point is that it comes out unchanged.  */
FILE *stream = nullptr;
bool close_stream_at_end = false;

/* Sequence number across the whole compilation, so a consumer can order records without
   trusting timestamps.  */
unsigned long seq = 0;

/* The pass we last announced. PLUGIN_PASS_EXECUTION fires before a pass runs and there is
   no matching event for after it, so a pass is closed by the arrival of the next one and
   the state recorded then is that pass's result. The last pass of a function is closed by
   PLUGIN_ALL_PASSES_END.  */
const char *open_pass = nullptr;
int open_pass_number = -1;
double open_started = 0.0;

double
now_seconds ()
{
  struct timespec ts;
  /* CLOCK_MONOTONIC rather than the wall clock, because the interesting number is a
     duration and a clock that can step backwards makes negative ones.  */
  if (clock_gettime (CLOCK_MONOTONIC, &ts) != 0)
    return 0.0;
  return (double) ts.tv_sec + (double) ts.tv_nsec / 1e9;
}

void
emit_json_string (const char *s)
{
  fputc ('"', stream);
  for (const unsigned char *p = (const unsigned char *) s; *p; p++)
    switch (*p)
      {
      case '"':  fputs ("\\\"", stream); break;
      case '\\': fputs ("\\\\", stream); break;
      case '\n': fputs ("\\n", stream); break;
      case '\r': fputs ("\\r", stream); break;
      case '\t': fputs ("\\t", stream); break;
      default:
	if (*p < 0x20)
	  fprintf (stream, "\\u%04x", *p);
	else
	  fputc (*p, stream);
      }
  fputc ('"', stream);
}

/* Is the current function in RTL yet? This matters more than it looks. A basic block
   holds either a GIMPLE sequence or an RTL insn chain, in a union, and walking it as the
   wrong one does not fail a check, it reads whichever pointer happens to be there and
   segfaults in *rest_of_compilation. Which is exactly what the first version of this
   plugin did.  */
bool
in_rtl ()
{
  return cfun && (cfun->curr_properties & PROP_rtl) != 0;
}

/* GIMPLE statements in the current function, or -1 when there are none to count: no
   function at all, which is every IPA pass, no CFG yet, or the function has already been
   lowered to RTL.  */
long
statement_count ()
{
  if (!cfun || !cfun->cfg || in_rtl ())
    return -1;
  long n = 0;
  basic_block bb;
  FOR_EACH_BB_FN (bb, cfun)
    for (gimple_stmt_iterator gsi = gsi_start_bb (bb); !gsi_end_p (gsi); gsi_next (&gsi))
      n++;
  return n;
}

/* The other half of the same question, for after the function becomes RTL. Counted off
   the insn chain rather than per block, because the chain is intact even in the late
   passes that have thrown the CFG away.  */
long
insn_count ()
{
  if (!in_rtl ())
    return -1;
  long n = 0;
  for (rtx_insn *insn = get_insns (); insn; insn = NEXT_INSN (insn))
    n++;
  return n;
}

/* Basic blocks, which is the one count that means the same thing on both sides of the
   GIMPLE to RTL boundary. Null once pass_free_cfg has run.  */
long
block_count ()
{
  if (!cfun || !cfun->cfg)
    return -1;
  return n_basic_blocks_for_fn (cfun);
}

const char *
current_function_name_or_null ()
{
  if (!cfun || !cfun->decl)
    return nullptr;
  return IDENTIFIER_POINTER (DECL_ASSEMBLER_NAME (cfun->decl));
}

void
emit_count (const char *key, long value)
{
  if (value < 0)
    fprintf (stream, ",\"%s\":null", key);
  else
    fprintf (stream, ",\"%s\":%ld", key, value);
}

/* One record. `event` is what happened, `pass` is the pass it happened to.  */
void
emit_event (const char *event, const char *pass, int pass_number, double duration)
{
  if (!stream)
    return;

  fprintf (stream, "{\"seq\":%lu,\"event\":", seq++);
  emit_json_string (event);

  fputs (",\"pass\":", stream);
  if (pass)
    emit_json_string (pass);
  else
    fputs ("null", stream);

  fprintf (stream, ",\"pass_number\":%d", pass_number);

  fputs (",\"function\":", stream);
  const char *fn = current_function_name_or_null ();
  if (fn)
    emit_json_string (fn);
  else
    fputs ("null", stream);

  /* What the compiler currently believes is true of this function's IR. This is the
     dynamic property set, not the pass's declared one, which is the difference between
     what is and what was asked for.  */
  if (cfun)
    fprintf (stream, ",\"properties\":%u", (unsigned) cfun->curr_properties);
  else
    fputs (",\"properties\":null", stream);

  /* Null rather than -1 for a count that does not apply here, so a consumer can tell
     "nothing to count" from "counted, and it was zero".  */
  emit_count ("statements", statement_count ());
  emit_count ("insns", insn_count ());
  emit_count ("blocks", block_count ());

  if (duration >= 0.0)
    fprintf (stream, ",\"seconds\":%.9f", duration);
  else
    fputs (",\"seconds\":null", stream);

  fputs ("}\n", stream);
}

/* Close whichever pass is open, attributing to it the state as it is now. Called when the
   next pass starts and when the pass manager finishes.  */
void
close_open_pass ()
{
  if (!open_pass)
    return;
  emit_event ("pass-end", open_pass, open_pass_number, now_seconds () - open_started);
  open_pass = nullptr;
  open_pass_number = -1;
}

void
on_pass_execution (void *gcc_data, void * /*user_data*/)
{
  opt_pass *pass = (opt_pass *) gcc_data;
  if (!pass)
    return;

  close_open_pass ();

  emit_event ("pass-start", pass->name, pass->static_pass_number, -1.0);
  open_pass = pass->name;
  open_pass_number = pass->static_pass_number;
  open_started = now_seconds ();
}

void
on_all_passes_end (void * /*gcc_data*/, void * /*user_data*/)
{
  close_open_pass ();
}

void
on_finish_unit (void * /*gcc_data*/, void * /*user_data*/)
{
  close_open_pass ();
  if (stream)
    {
      fflush (stream);
      if (close_stream_at_end)
	fclose (stream);
      stream = nullptr;
    }
}

/* -fplugin-arg-gxplug-out=PATH writes to a file, -fplugin-arg-gxplug-fd=N to an already
   open descriptor, which is how a notebook reads the stream without a temporary file.
   Neither given means stderr.  */
bool
open_stream (plugin_name_args *info)
{
  const char *path = nullptr;
  const char *fd_arg = nullptr;

  for (int i = 0; i < info->argc; i++)
    {
      if (strcmp (info->argv[i].key, "out") == 0)
	path = info->argv[i].value;
      else if (strcmp (info->argv[i].key, "fd") == 0)
	fd_arg = info->argv[i].value;
      else
	{
	  error ("gxplug: unknown argument %qs", info->argv[i].key);
	  return false;
	}
    }

  if (path && fd_arg)
    {
      error ("gxplug: give %qs or %qs, not both", "out", "fd");
      return false;
    }

  if (path)
    {
      stream = fopen (path, "w");
      if (!stream)
	{
	  error ("gxplug: cannot write to %qs", path);
	  return false;
	}
      close_stream_at_end = true;
    }
  else if (fd_arg)
    {
      char *end = nullptr;
      long fd = strtol (fd_arg, &end, 10);
      if (!end || *end || fd < 0 || fd > 1024)
	{
	  error ("gxplug: fd= wants a small non-negative integer, got %qs", fd_arg);
	  return false;
	}
      stream = fdopen ((int) fd, "w");
      if (!stream)
	{
	  error ("gxplug: cannot write to file descriptor %ld", fd);
	  return false;
	}
      close_stream_at_end = true;
    }
  else
    stream = stderr;

  return true;
}

} /* anonymous namespace */

int
plugin_init (plugin_name_args *info, plugin_gcc_version *version)
{
  /* A plugin built against one GCC and loaded into another is undefined behaviour that
     usually shows up as a crash in the middle of a lesson. Refusing here is the whole
     reason the plug image builds the plugin rather than shipping one.  */
  if (!plugin_default_version_check (version, &gcc_version))
    {
      error ("gxplug: built against GCC %s, loaded into GCC %s", gcc_version.basever,
	     version->basever);
      return 1;
    }

  if (!open_stream (info))
    return 1;

  static plugin_info about
    = { "0.1", "gxplug: pass events as newline delimited JSON, and no change to codegen" };
  register_callback (info->base_name, PLUGIN_INFO, nullptr, &about);

  register_callback (info->base_name, PLUGIN_PASS_EXECUTION, on_pass_execution, nullptr);
  register_callback (info->base_name, PLUGIN_ALL_PASSES_END, on_all_passes_end, nullptr);
  register_callback (info->base_name, PLUGIN_FINISH_UNIT, on_finish_unit, nullptr);

  return 0;
}
