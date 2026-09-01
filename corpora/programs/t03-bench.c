/* T03: one C expression per function, getting less reasonable as you go down.
   Every function returns an int and takes the same three arguments, so the only
   thing that differs between them is the shape of the expression, which is the
   only thing the lesson is about. Compiled at -O0 with -fdump-tree-gimple, so
   what comes out is gimplification and nothing else. */

extern int g (int);
extern int h (int);

/* One operation. GIMPLE and C agree, and this is the only one where they do. */
int
flat (int a, int b, int c)
{
  return a + b;
}

/* Two operations in one expression, which GIMPLE is not allowed to have. */
int
nested (int a, int b, int c)
{
  return (a + b) * (a - c);
}

/* Deeper, to show that the number of temporaries follows the shape of the tree
   rather than the length of the line. */
int
deeper (int a, int b, int c)
{
  return ((a + b) * (a - c)) + ((b + c) * (b - a));
}

/* A call is an operation too, and its arguments have to be values first. */
int
calls (int a, int b, int c)
{
  return g (a + b) + h (b + c);
}

/* && is not an operator here. It is a branch, and gimplification is where it
   stops being an expression. */
int
shortcircuit (int a, int b, int c)
{
  return a > 0 && b > 0;
}

/* Same again for ?:, which is an expression in C and two basic blocks here. */
int
ternary (int a, int b, int c)
{
  return a > b ? a + c : b + c;
}

/* A compound assignment is two things at once, a write and a value, and GIMPLE
   is only allowed to do one thing at a time. */
int
compound (int a, int b, int c)
{
  return (a += b) * c;
}
