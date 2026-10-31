/* SPDX-License-Identifier: Apache-2.0 */
/* Style demo: the watch's own fonts (Roboto, read from /nand/system/font at run time) and widgets in its look: black background, dark rounded cards,
 * a switch, pill buttons. Tap the switch, Start/Stop (the number then moves) or Reset. A line at the bottom shows how many fonts could be opened,
 * and why not (open failed = -1 means the loader does not let apps read /nand). Nothing is copied from the firmware; nothing is written. */
#include "f3font.h"
#include "f3ui.h"

#define NFONT 5
enum { R20, R24, M28, M48, B60 };
static const char *const PATH[NFONT] = {
    "/nand/system/font/FONT_ROBOTO_20_GBK_en.bin", "/nand/system/font/FONT_ROBOTO_24_GBK_en.bin", "/nand/system/font/FONT_ROBOTO_MEDIUM_28_GBK_en.bin",
    "/nand/system/font/FONT_ROBOTO_MEDIUM_48_GBK_en.bin", "/nand/system/font/FONT_ROBOTO_BOLD_60_GBK_en.bin" };
static const u32 CAP[NFONT] = { 8192, 10240, 12288, 24576, 8192 };

typedef struct { F3App base; F3Font f[NFONT]; int err[NFONT]; int loaded; int sw, bpm, running, down, sx, sy, lx, ly; u32 t0; } St;
static const F3Api *A;
static St *S;

static void fill8(void *p, int v, u32 n) { u8 *b = (u8 *)p; while (n--) *b++ = (u8)v; }
static char *itoa(char *b, int v) { char t[12]; int n = 0, k = 0; if (v < 0) { b[k++] = '-'; v = -v; } do { t[n++] = (char)('0' + v % 10); v /= 10; } while (v && n < 10); while (n) b[k++] = t[--n]; b[k] = 0; return b; }
static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }
static int ok(int i) { return S->f[i].d != 0; }
/* text with a font, or with the built-in 8x12 font when that font could not be loaded */
static void txt(int i, int x, int base, const char *s, u16 c) { if (ok(i)) f3font_text(A, &S->f[i], x, base, s, c); else A->text(A->fb, x, base - 12, s, 1, c); }
static void ctxt(int i, int cx, int base, const char *s, u16 c) { if (ok(i)) f3font_ctext(A, &S->f[i], cx, base, s, c); else A->ctext(A->fb, cx, base - 12, s, 1, c); }
static int wid(int i, const char *s) { return ok(i) ? f3font_width(A, &S->f[i], s) : 8 * slen(s); }

static void draw(void) {
    char b[24]; ui_clear(A);
    txt(R24, 16, 28, "Style demo", UI_DIM);
    ui_card(A, 12, 40, 232, 140);                                                             /* heart-rate style card */
    txt(R20, 30, 76, "Heart rate", UI_DIM);
    txt(B60, 30, 146, itoa(b, S->bpm), UI_TEXT); txt(R24, 30 + wid(B60, b) + 8, 146, "bpm", UI_DIM);
    ui_card(A, 12, 192, 232, 76);                                                             /* a row with a switch */
    txt(M28, 30, 240, "Water lock", UI_TEXT); ui_switch(A, 172, 214, S->sw);
    ui_pill(A, 12, 280, 112, 56, S->running ? UI_RED : UI_BLUE); ctxt(M28, 68, 316, S->running ? "Stop" : "Start", UI_TEXT);
    ui_pill(A, 132, 280, 112, 56, UI_CARD_HI); ctxt(M28, 188, 316, "Reset", UI_TEXT);
    if (S->loaded == NFONT) { txt(R20, 16, 372, itoa(b, S->loaded), UI_DIM); txt(R20, 16 + wid(R20, b), 372, "/5 fonts loaded", UI_DIM); }
    else for (int i = 0, y = 360; i < NFONT; i++) if (S->err[i]) { char m[24]; itoa(m, i); A->text(A->fb, 12, y, "font", 1, UI_RED); A->text(A->fb, 52, y, m, 1, UI_RED); A->text(A->fb, 68, y, "err", 1, UI_RED); itoa(m, S->err[i]); A->text(A->fb, 100, y, m, 1, UI_RED); y += 14; }
}

static int tick(F3App *self, int pressed, int x, int y, int tap_) {
    (void)self; (void)tap_; int tap = 0;
    if (pressed) { if (!S->down) { S->down = 1; S->sx = x; S->sy = y; } S->lx = x; S->ly = y; }
    else if (S->down) { S->down = 0; int dx = S->lx - S->sx, dy = S->ly - S->sy; tap = dx > -16 && dx < 16 && dy > -16 && dy < 16; }
    if (tap) {
        if (ui_in(S->sx, S->sy, 12, 192, 232, 76)) { S->sw ^= 1; A->vibrate(1); }
        else if (ui_in(S->sx, S->sy, 12, 280, 112, 56)) { S->running ^= 1; S->t0 = A->ticks(); A->vibrate(1); }
        else if (ui_in(S->sx, S->sy, 132, 280, 112, 56)) { S->running = 0; S->bpm = 72; A->vibrate(1); }
    }
    if (S->running) S->bpm = 72 + (int)((A->ticks() - S->t0) / 600 % 25);
    draw(); return 1;
}
static void close_(F3App *self) { (void)self; for (int i = 0; i < NFONT; i++) f3font_free(&S->f[i], A); A->free(S); }

F3App *f3app_main(const F3Api *api) {
    A = api; S = (St *)api->malloc(sizeof(St)); if (!S) return 0; fill8(S, 0, sizeof(St)); S->bpm = 72;
    for (int i = 0; i < NFONT; i++) { S->err[i] = f3font_load(&S->f[i], A, PATH[i], CAP[i]); if (!S->err[i]) S->loaded++; }
    S->base.tick = tick; S->base.close = close_; return &S->base;
}
