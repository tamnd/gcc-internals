/* T05 boss fight: a loop with a branch in the body, so the joins nest.
   Two things make it harder than l1.c. The if-else inside the loop is a join of its own, so
   `total` needs a phi there as well as at the loop header. And `flag` is a parameter that is
   never written, so it gets a default definition and no phi at all. */
int g (int n, int flag)
{
  int total = 0;
  for (int k = 0; k < n; k++)
    {
      if (flag)
        total += k;
      else
        total -= k;
    }
  return total;
}
