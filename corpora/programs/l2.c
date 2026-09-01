/* L2: pointers, a struct, and a static function worth inlining.
   The first program where alias analysis and the interprocedural passes have work to do. */
struct P { int x, y; };

static int
dist2 (const struct P *a, const struct P *b)
{
  int dx = a->x - b->x;
  int dy = a->y - b->y;
  return dx * dx + dy * dy;
}

int
nearest (const struct P *pts, int n, struct P q)
{
  int best = 0;
  int bestd = dist2 (&pts[0], &q);
  for (int i = 1; i < n; i++)
    {
      int d = dist2 (&pts[i], &q);
      if (d < bestd)
        {
          bestd = d;
          best = i;
        }
    }
  return best;
}
