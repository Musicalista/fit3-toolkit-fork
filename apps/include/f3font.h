/* f3font.h: reads LVGL binary fonts (lv_font_conv --format bin), such as the watch's own /nand/system/font/FONT_ROBOTO_*_GBK_en.bin, and draws
 * anti-aliased text into the RGB565 frame buffer. Header-only, freestanding (no libc), needs f3app.h. See docs/assets.md for the format.
 * Supported: uncompressed glyphs, any bpp (the watch's fonts use 2), cmap formats 0..3, advance in whole pixels or 1/16 px. No kerning. */
#ifndef F3FONT_H
#define F3FONT_H
#include "f3app.h"

typedef struct {
    u8 *d;                                                   /* the whole font file (malloc'ed); 0 when not loaded */
    int size, ascent, descent, bpp, adv_fmt, loc_fmt, xy_bits, wh_bits, adv_bits;
    u32 cmap_at, loca_n, loca_at, glyf_at;                   /* offsets of the tables inside d */
} F3Font;

static u32 lf_u16(const u8 *p) { return (u32)p[0] | ((u32)p[1] << 8); }
static u32 lf_u32(const u8 *p) { return (u32)p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) | ((u32)p[3] << 24); }
static u32 lf_bits(const u8 *d, u32 *bit, int n) { u32 v = 0; while (n--) { v = (v << 1) | ((d[*bit >> 3] >> (7 - (*bit & 7))) & 1u); (*bit)++; } return v; }
static int lf_sbits(const u8 *d, u32 *bit, int n) { int v = (int)lf_bits(d, bit, n); return (v >> (n - 1)) ? v - (1 << n) : v; }
static int lf_tag(const u8 *t, const char *s) { return t[0] == (u8)s[0] && t[1] == (u8)s[1] && t[2] == (u8)s[2] && t[3] == (u8)s[3]; }

/* 0 = ok, -1 cannot open, -2 no memory, -3 not a usable font, -4 bigger than `cap` bytes */
static int f3font_load(F3Font *f, const F3Api *api, const char *path, u32 cap) {
    f->d = 0; int fd = api->fopen(path, "r"); if (fd < 0) return -1;
    u8 *b = (u8 *)api->malloc(cap); if (!b) { api->fclose(fd); return -2; }
    u32 got = 0; for (;;) { u32 want = cap - got; if (want > 1024) want = 1024; if (!want) break; int n = api->fread(fd, b + got, want); if (n <= 0) break; got += (u32)n; }
    api->fclose(fd); if (got >= cap) { api->free(b); return -4; }
    u32 pos = 0, head = 0, cmap = 0, loca = 0, glyf = 0; int have = 0;
    while (pos + 8 <= got) {
        u32 ln = lf_u32(b + pos); if (ln < 8 || pos + ln > got) break; const u8 *t = b + pos + 4;
        if (lf_tag(t, "head")) { head = pos; have |= 1; } else if (lf_tag(t, "cmap")) { cmap = pos; have |= 2; }
        else if (lf_tag(t, "loca")) { loca = pos; have |= 4; } else if (lf_tag(t, "glyf")) { glyf = pos; have |= 8; }
        pos += ln;
    }
    if (have != 15 || head + 48 > got || b[head + 8 + 33] != 0) { api->free(b); return -3; }          /* byte 33 of the header = compression id: only 0 (none) */
    const u8 *h = b + head + 8;
    f->size = (int)lf_u16(h + 6); f->ascent = (int)lf_u16(h + 8); f->descent = (short)lf_u16(h + 10);
    f->loc_fmt = h[26]; f->adv_fmt = h[28]; f->bpp = h[29]; f->xy_bits = h[30]; f->wh_bits = h[31]; f->adv_bits = h[32];
    f->cmap_at = cmap; f->loca_n = lf_u32(b + loca + 8); f->loca_at = loca + 12; f->glyf_at = glyf;
    if (f->bpp < 1 || f->bpp > 4 || f->loca_at + f->loca_n * (f->loc_fmt ? 4u : 2u) > got) { api->free(b); return -3; }
    f->d = b; return 0;
}
static void f3font_free(F3Font *f, const F3Api *api) { if (f->d) api->free(f->d); f->d = 0; }

static int f3font_gid(const F3Font *f, u32 cp) {
    const u8 *c = f->d + f->cmap_at; u32 n = lf_u32(c + 8);
    for (u32 i = 0; i < n; i++) {
        const u8 *e = c + 12 + i * 16; u32 off = lf_u32(e), rs = lf_u32(e + 4), rl = lf_u16(e + 8), gs = lf_u16(e + 10), cnt = lf_u16(e + 12); int fmt = e[14];
        if (cp < rs || cp >= rs + rl) continue;
        u32 k = cp - rs; const u8 *dat = c + off;
        if (fmt == 0) return dat[k] ? (int)(gs + dat[k]) : 0;                                          /* format0_full: one byte per code */
        if (fmt == 2) return (int)(gs + k);                                                            /* format0_tiny: consecutive */
        for (u32 j = 0; j < cnt; j++) if (lf_u16(dat + 2 * j) == k) return fmt == 3 ? (int)(gs + j) : (int)lf_u16(dat + 2 * cnt + 2 * j);   /* sparse tiny / full */
    }
    return 0;
}

/* walks the string; with fb != 0 draws it. x is in pixels, `base` is the baseline row; returns the advance in 1/16 px */
static int f3font_run(const F3Api *A, const F3Font *f, int x, int base, const char *s, u16 color, int draw) {
    int xq = x * 16, L = (1 << f->bpp) - 1;
    for (; *s; s++) {
        int g = f3font_gid(f, (u8)*s);
        if (g <= 0 || (u32)g >= f->loca_n) { xq += (f->size / 2) * 16; continue; }
        u32 off = f->loc_fmt ? lf_u32(f->d + f->loca_at + 4u * (u32)g) : lf_u16(f->d + f->loca_at + 2u * (u32)g);
        u32 bit = (f->glyf_at + off) * 8u; const u8 *d = f->d;
        int adv = (int)lf_bits(d, &bit, f->adv_bits), gx = lf_sbits(d, &bit, f->xy_bits), gy = lf_sbits(d, &bit, f->xy_bits);
        int w = (int)lf_bits(d, &bit, f->wh_bits), h = (int)lf_bits(d, &bit, f->wh_bits);
        if (draw) for (int j = 0; j < h; j++) for (int i = 0; i < w; i++) {
            int a = (int)lf_bits(d, &bit, f->bpp); if (!a) continue;
            int px = (xq >> 4) + gx + i, py = base - gy - h + j; if (px < 0 || py < 0 || px >= F3_W || py >= F3_H) continue;
            u16 dst = A->fb[py * F3_W + px];
            int r = ((color >> 11) * a + (dst >> 11) * (L - a)) / L, gg = (((color >> 5) & 63) * a + ((dst >> 5) & 63) * (L - a)) / L, bb = ((color & 31) * a + (dst & 31) * (L - a)) / L;
            A->fb[py * F3_W + px] = (u16)((r << 11) | (gg << 5) | bb);
        }
        xq += f->adv_fmt ? adv : adv * 16;
    }
    return xq - x * 16;
}
static void f3font_text(const F3Api *A, const F3Font *f, int x, int base, const char *s, u16 color) { f3font_run(A, f, x, base, s, color, 1); }
static int f3font_width(const F3Api *A, const F3Font *f, const char *s) { return (f3font_run(A, f, 0, 0, s, 0, 0) + 8) >> 4; }
static void f3font_ctext(const F3Api *A, const F3Font *f, int cx, int base, const char *s, u16 color) { f3font_text(A, f, cx - f3font_width(A, f, s) / 2, base, s, color); }
static void f3font_rtext(const F3Api *A, const F3Font *f, int rx, int base, const char *s, u16 color) { f3font_text(A, f, rx - f3font_width(A, f, s), base, s, color); }
#endif
