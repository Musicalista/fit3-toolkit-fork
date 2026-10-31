/* SPDX-License-Identifier: Apache-2.0 */
/* Touch lab: shows what the loader delivers for touches, to tell lost taps from slow frames. Counters: tick interval (frame time), press edges (pressed 0->1 as seen by this app),
 * release edges, `tap` flags (the loader's click event), taps that arrived with no press ever seen (shorter than a tick), presses that never got a click flag.
 * Do 20 taps in the middle, then 10 swipes, then Reset (tap the bottom bar) and read the numbers. Nothing is stored. */
#include "f3app.h"

typedef struct {
    F3App base; u32 last; int started, prev, px, py;
    int dt, dt_sum, dt_n, dt_avg, dt_max, down, up, flags, flag_only, noflag, awaiting, saw_press, run, run_last, run_max, move, move_max;
    int sx, sy; u32 t_down; int press_ms;
} St;
static const F3Api *A;
static St *S;

static void fill8(void *p, int v, u32 n) { u8 *b = (u8 *)p; while (n--) *b++ = (u8)v; }
static void line(int row, const char *label, int v) { A->text(A->fb, 6, 8 + row * 15, label, 1, RGB(200, 200, 200)); A->num(A->fb, 6 + 8 * 26, 8 + row * 15, v, 1, RGB(255, 255, 255)); }
static void reset(void) { S->dt_sum = S->dt_n = S->dt_max = S->down = S->up = S->flags = S->flag_only = S->noflag = S->awaiting = S->saw_press = S->run_last = S->run_max = S->move_max = 0; }

static int tick(F3App *self, int pressed, int x, int y, int tap) {
    (void)self; u32 now = A->ticks();
    if (S->started) { S->dt = (int)(now - S->last); S->dt_sum += S->dt; S->dt_n++; if (S->dt_n >= 30) { S->dt_avg = S->dt_sum / S->dt_n; S->dt_sum = S->dt_n = 0; } if (S->dt > S->dt_max) S->dt_max = S->dt; }
    S->started = 1; S->last = now;
    if (pressed) {
        if (!S->prev) { S->down++; S->saw_press = 1; S->run = 0; S->t_down = now; S->sx = x; S->sy = y; S->move = 0; if (S->awaiting) S->noflag++; S->awaiting = 1; }
        S->run++; { int dx = x - S->sx, dy = y - S->sy; int m = (dx < 0 ? -dx : dx) + (dy < 0 ? -dy : dy); if (m > S->move) S->move = m; }
        S->px = x; S->py = y;
    } else if (S->prev) { S->up++; S->run_last = S->run; if (S->run > S->run_max) S->run_max = S->run; S->press_ms = (int)(now - S->t_down); if (S->move > S->move_max) S->move_max = S->move; }
    S->prev = pressed;
    if (tap) {
        if (x >= 0 && y > 370 && x < 256) { reset(); }
        else { S->flags++; if (!S->saw_press) S->flag_only++; S->awaiting = 0; S->saw_press = 0; S->px = x; S->py = y; }
    }
    A->rect(A->fb, 0, 0, F3_W, F3_H, RGB(0, 0, 0));
    A->text(A->fb, 6, 0, S->prev ? "PRESSED" : "-", 1, S->prev ? RGB(80, 255, 120) : RGB(120, 120, 120));
    line(1, "tick ms now", S->dt); line(2, "tick ms avg (30)", S->dt_avg); line(3, "tick ms max", S->dt_max);
    line(4, "press down edges", S->down); line(5, "press up edges", S->up); line(6, "tap flags (clicks)", S->flags);
    line(7, "taps w/o press seen", S->flag_only); line(8, "presses w/o click", S->noflag);
    line(9, "last press ticks", S->run_last); line(10, "last press ms", S->press_ms); line(11, "max movement px", S->move_max);
    A->text(A->fb, 6, 8 + 12 * 15, "x", 1, RGB(200, 200, 200)); A->num(A->fb, 20, 8 + 12 * 15, S->px, 1, RGB(255, 255, 255)); A->text(A->fb, 70, 8 + 12 * 15, "y", 1, RGB(200, 200, 200)); A->num(A->fb, 84, 8 + 12 * 15, S->py, 1, RGB(255, 255, 255));
    A->rect(A->fb, S->px - 12, S->py, 25, 1, RGB(255, 80, 80)); A->rect(A->fb, S->px, S->py - 12, 1, 25, RGB(255, 80, 80));
    A->rrect(A->fb, 8, 372, 240, 26, 12, RGB(40, 40, 40)); A->ctext(A->fb, 128, 379, "Reset (tap here)", 1, RGB(255, 255, 255));
    return 1;
}
static void close_(F3App *self) { (void)self; A->free(S); }
F3App *f3app_main(const F3Api *api) {
    A = api; S = (St *)api->malloc(sizeof(St)); if (!S) return 0; fill8(S, 0, sizeof(St)); S->px = 128; S->py = 200; S->base.tick = tick; S->base.close = close_; return &S->base;
}
