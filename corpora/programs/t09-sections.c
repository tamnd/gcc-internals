/* Eight declarations that end up in six different places in the object file.
 *
 * Nothing here computes anything. The whole point is where each name lands and what the
 * assembler is told about it, because that is decided by `varasm.cc` on the basis of what
 * the declaration says rather than by anything an optimizer did.
 *
 * The things that decide it are: whether there is an initialiser, whether the initialiser
 * is all zeroes, whether the object is const, whether it is static, and whether the target
 * has somewhere better to put small read only things. Every one of those is visible in the
 * assembly as a different directive.
 *
 * Read the .s next to this file rather than the object file. The directives are the lesson
 * and the assembler is what turns them into section headers.
 */

/* Initialised and not zero, so it has to be written down somewhere. Writable, because it
 * is not const. That is .data, and the bytes are in the object file.
 */
int counter = 7;

/* Initialised to zero, which is the same thing as not initialised at all for a global in C.
 * Nothing needs writing down, only reserving, so it goes to .bss and the object file gets
 * a size rather than any bytes.
 */
int total = 0;

/* No initialiser at all. Identical treatment to the one above, and worth having both here
 * so a reader can see that the assembly does not distinguish them.
 */
int pending;

/* Const and initialised, so nothing will ever write to it and it can go somewhere the
 * loader can map read only. That is .rodata.
 */
const int limit = 100;

/* Static, so the name never leaves this file and there is no .global directive for it. It
 * is still const and initialised, so it still lands in .rodata.
 */
static const char tag[] = "gcc";

/* A pointer, which is two objects. The characters are an anonymous constant that goes in
 * .rodata with a compiler invented label, and the pointer itself is a writable eight byte
 * global that holds that label's address, so it goes in .data.
 */
const char *message = "the last mile";

/* Asking for more alignment than the type needs. The directive in front of it changes and
 * nothing else does, which is the cleanest way to see that alignment is a property the
 * assembler is told rather than something implied by the type.
 */
int wide __attribute__ ((aligned (64)));

/* Two functions, so that there is something in .text to compare all of that against, and so
 * that the globals above get read and cannot be dropped.
 */
int
sum (void)
{
  return counter + limit + (int) message[0];
}

/* The index has to come in at run time. Ask for `tag[0]` and the compiler folds the whole
 * thing to a number, the array is never read, and it does not reach the object file at all.
 */
char
letter (int i)
{
  return tag[i];
}
