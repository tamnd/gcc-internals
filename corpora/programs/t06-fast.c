/* T06: a float sum, which is the shortest way to show what -Ofast gives up.
   Adding floats is not associative, so the order of the additions is part of
   the answer, and -O3 has to keep it. -Ofast is allowed to change it. */
float
total (const float *a, int n)
{
  float s = 0.0f;
  for (int i = 0; i < n; i++)
    s += a[i];
  return s;
}
