/* L1: a loop with an induction variable and an accumulator.
   Enough for SSA to be interesting, small enough to read the whole dump. */
int f (int n)
{
  int s = 0;
  for (int i = 0; i < n; i++)
    s += i;
  return s;
}
