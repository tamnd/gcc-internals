/* Five functions that ask the register allocator for more registers than it may have.
 *
 * Each one keeps N values alive at the same time and rotates them, so that no value can be
 * recomputed later and none can be left in memory until the end. The loop is the point: a
 * value that is live across the back edge has to be in a register at the top and at the
 * bottom, and there is no arrangement of the body that lets two of them share one.
 *
 * N goes 4, 10, 14, 20, 30. x86-64 has sixteen general registers and cannot use all of
 * them, aarch64 has thirty one and can use nearly all. Somewhere in that ramp the two
 * machines start disagreeing, and finding where is the exercise.
 *
 * Nothing here is a benchmark and none of it computes anything meaningful. The values are
 * read from memory so that the compiler cannot fold them, and returned as a sum so that it
 * cannot delete them.
 */

/* Read a value in, once, before the loop. Marked so that the loads cannot be sunk into the
 * loop body, which would let the allocator keep fewer values live at a time.
 */
#define IN(name, index) long name = v[index]

/* One step of the rotation. Every variable takes the value of the next one along, so the
 * whole set has to survive from one iteration to the next.
 */
#define STEP(a, b) a += b

long p04(const long *v, int n) {
    IN(a, 0);
    IN(b, 1);
    IN(c, 2);
    IN(d, 3);
    for (int i = 0; i < n; i++) {
        STEP(a, b);
        STEP(b, c);
        STEP(c, d);
        STEP(d, a);
    }
    return a + b + c + d;
}

long p10(const long *v, int n) {
    IN(a, 0);
    IN(b, 1);
    IN(c, 2);
    IN(d, 3);
    IN(e, 4);
    IN(f, 5);
    IN(g, 6);
    IN(h, 7);
    IN(i2, 8);
    IN(j, 9);
    for (int i = 0; i < n; i++) {
        STEP(a, b);
        STEP(b, c);
        STEP(c, d);
        STEP(d, e);
        STEP(e, f);
        STEP(f, g);
        STEP(g, h);
        STEP(h, i2);
        STEP(i2, j);
        STEP(j, a);
    }
    return a + b + c + d + e + f + g + h + i2 + j;
}

long p14(const long *v, int n) {
    IN(a, 0);
    IN(b, 1);
    IN(c, 2);
    IN(d, 3);
    IN(e, 4);
    IN(f, 5);
    IN(g, 6);
    IN(h, 7);
    IN(i2, 8);
    IN(j, 9);
    IN(k, 10);
    IN(l, 11);
    IN(m, 12);
    IN(o, 13);
    for (int i = 0; i < n; i++) {
        STEP(a, b);
        STEP(b, c);
        STEP(c, d);
        STEP(d, e);
        STEP(e, f);
        STEP(f, g);
        STEP(g, h);
        STEP(h, i2);
        STEP(i2, j);
        STEP(j, k);
        STEP(k, l);
        STEP(l, m);
        STEP(m, o);
        STEP(o, a);
    }
    return a + b + c + d + e + f + g + h + i2 + j + k + l + m + o;
}

long p20(const long *v, int n) {
    IN(a, 0);
    IN(b, 1);
    IN(c, 2);
    IN(d, 3);
    IN(e, 4);
    IN(f, 5);
    IN(g, 6);
    IN(h, 7);
    IN(i2, 8);
    IN(j, 9);
    IN(k, 10);
    IN(l, 11);
    IN(m, 12);
    IN(o, 13);
    IN(p, 14);
    IN(q, 15);
    IN(r, 16);
    IN(s, 17);
    IN(t, 18);
    IN(u, 19);
    for (int i = 0; i < n; i++) {
        STEP(a, b);
        STEP(b, c);
        STEP(c, d);
        STEP(d, e);
        STEP(e, f);
        STEP(f, g);
        STEP(g, h);
        STEP(h, i2);
        STEP(i2, j);
        STEP(j, k);
        STEP(k, l);
        STEP(l, m);
        STEP(m, o);
        STEP(o, p);
        STEP(p, q);
        STEP(q, r);
        STEP(r, s);
        STEP(s, t);
        STEP(t, u);
        STEP(u, a);
    }
    return a + b + c + d + e + f + g + h + i2 + j + k + l + m + o + p + q + r + s + t + u;
}

long p30(const long *v, int n) {
    IN(a, 0);
    IN(b, 1);
    IN(c, 2);
    IN(d, 3);
    IN(e, 4);
    IN(f, 5);
    IN(g, 6);
    IN(h, 7);
    IN(i2, 8);
    IN(j, 9);
    IN(k, 10);
    IN(l, 11);
    IN(m, 12);
    IN(o, 13);
    IN(p, 14);
    IN(q, 15);
    IN(r, 16);
    IN(s, 17);
    IN(t, 18);
    IN(u, 19);
    IN(w, 20);
    IN(x, 21);
    IN(y, 22);
    IN(z, 23);
    IN(a2, 24);
    IN(b2, 25);
    IN(c2, 26);
    IN(d2, 27);
    IN(e2, 28);
    IN(f2, 29);
    for (int i = 0; i < n; i++) {
        STEP(a, b);
        STEP(b, c);
        STEP(c, d);
        STEP(d, e);
        STEP(e, f);
        STEP(f, g);
        STEP(g, h);
        STEP(h, i2);
        STEP(i2, j);
        STEP(j, k);
        STEP(k, l);
        STEP(l, m);
        STEP(m, o);
        STEP(o, p);
        STEP(p, q);
        STEP(q, r);
        STEP(r, s);
        STEP(s, t);
        STEP(t, u);
        STEP(u, w);
        STEP(w, x);
        STEP(x, y);
        STEP(y, z);
        STEP(z, a2);
        STEP(a2, b2);
        STEP(b2, c2);
        STEP(c2, d2);
        STEP(d2, e2);
        STEP(e2, f2);
        STEP(f2, a);
    }
    return a + b + c + d + e + f + g + h + i2 + j + k + l + m + o + p + q + r + s + t + u + w +
           x + y + z + a2 + b2 + c2 + d2 + e2 + f2;
}
