/* SPDX-License-Identifier: Apache-2.0 */
/* f3game.h: small helpers for apps built on f3app.h. Header-only and all static, so what an app does not use costs nothing in the image.
 * The including app must set the global A (the F3Api pointer it got in f3app_main) before using anything that draws or reads time. */
#ifndef F3GAME_H
#define F3GAME_H
#include "f3app.h"

static const F3Api *A;                                  /* assigned by the app in f3app_main */
#define FB (A->fb)
#define TR(pt, en) (A->lang_pt ? (pt) : (en))           /* pick the Portuguese or the English string */

/* the default palette of the apps in this repository: a night blue, a near-white and a blue-grey */
#define C_BG RGB(12, 16, 30)
#define C_TEXT RGB(232, 238, 248)
#define C_MUTED RGB(136, 148, 176)

static int absi(int v) { return v < 0 ? -v : v; }
static int clampi(int v, int lo, int hi) { if (v < lo) return lo; if (v > hi) return hi; return v; }
static int in_rect(int x, int y, int rx, int ry, int rw, int rh) { return x >= rx && y >= ry && x - rx < rw && y - ry < rh; }

/* linear congruential step on *state; returns 24 usable bits */
static u32 rng_next(u32 *state) { *state = *state * 1664525u + 1013904223u; return *state >> 8; }

static void clear(u16 color) { A->rect(FB, 0, 0, F3_W, F3_H, color); }

/* memset without libc (the compiler may not call one for us, see appcc.py) */
static void fill8(void *p, int v, u32 n) { u8 *d = (u8 *)p; u32 i; for (i = 0; i < n; i++) d[i] = (u8)v; }

/* Writes v in decimal to buf, left-padded with zeros to at least `pad` digits (at most 10 are produced for the number part),
 * plus a sign if negative, plus the terminator: buf needs 12 bytes. Returns buf. */
static char *itoa_pad(char *buf, int v, int pad) {
    char rev[12]; int n = 0, k = 0;
    u32 m = v < 0 ? 0u - (u32)v : (u32)v;
    do { rev[n++] = (char)('0' + m % 10u); m /= 10u; } while (m && n < 10);
    while (n < pad && n < 10) rev[n++] = '0';
    if (v < 0) buf[k++] = '-';
    while (n > 0) buf[k++] = rev[--n];
    buf[k] = 0;
    return buf;
}

/* One-finger gesture tracker. Feed it every tick; it reports once, on release: a tap when the finger stayed within 16 px, otherwise the dominant swipe direction.
 * sx, sy = where the finger went down; lx, ly = last position seen while down. */
typedef struct { int sx, sy; int lx, ly; int down; } Touch;
enum {
    T_NONE,     /* nothing to report this tick */
    T_TAP,
    T_LEFT, T_RIGHT, T_UP, T_DOWN
};

/* TAP_SLOP: how far (in pixels, per axis) the finger may wander and still count as a tap */
#define TAP_SLOP 16
static int touch_update(Touch *t, int pressed, int x, int y) {
    if (pressed) {
        if (!t->down) { t->down = 1; t->sx = x; t->sy = y; }
        t->lx = x; t->ly = y;
        return T_NONE;
    }
    if (t->down == 0) return T_NONE;                    /* nothing was being tracked */
    t->down = 0;
    int dx = t->lx - t->sx, dy = t->ly - t->sy;
    int horizontal = absi(dx) >= absi(dy);
    if ((horizontal ? absi(dx) : absi(dy)) < TAP_SLOP && absi(dx) < TAP_SLOP && absi(dy) < TAP_SLOP) return T_TAP;
    if (horizontal) return dx < 0 ? T_LEFT : T_RIGHT;
    return dy < 0 ? T_UP : T_DOWN;
}

/* A 4-byte integer kept in a file (a high score, say). Missing or short files read as 0; write failures are ignored. */
static int saved_int_load(const char *path) {
    int v = 0, fd = A->fopen(path, "r");
    if (fd < 0) return 0;
    if (A->fread(fd, &v, 4) != 4) v = 0;
    A->fclose(fd);
    return v;
}
static void saved_int_store(const char *path, int v) {
    int fd = A->fopen(path, "w");
    if (fd < 0) return;
    A->fwrite(fd, &v, 4);
    A->fclose(fd);
}
#endif
