/* SPDX-License-Identifier: Apache-2.0 */
/* ui.h: what every piece of watch code shares: the firmware functions we call (addresses: docs/symbols.csv), the colours and fonts of the native look (docs/details.md, section 6),
 * small text and file helpers, and the widgets (cards, texts, pills). Freestanding C: no libc, no libgcc (hardware divide only), no static data.
 * This header is included by hub.c and by every app (the files in src/watch/apps); all of it is one translation unit, so unused helpers cost nothing (gc-sections drops them). */
#ifndef F3_UI_H
#define F3_UI_H
typedef unsigned int u32; typedef unsigned short u16; typedef unsigned char u8; typedef int i32;
typedef struct lv_obj lv_obj_t; typedef struct lv_timer lv_timer_t; typedef struct lv_event lv_event_t; typedef struct lv_indev lv_indev_t;
#define H static __attribute__((unused))

#define F(addr, ret, args) ((ret (*) args)(addr | 1))
#define lv_obj_create(p)            F(0x2c27cb84, lv_obj_t *, (lv_obj_t *))(p)
#define lv_obj_del(o)               F(0x2c27b164, void, (lv_obj_t *))(o)
#define lv_obj_set_size(o, w, h)    F(0x2c277b2c, void, (lv_obj_t *, i32, i32))(o, w, h)
#define lv_obj_set_width(o, w)      F(0x2c277a5c, void, (lv_obj_t *, i32))(o, w)
#define lv_obj_set_pos(o, x, y)     F(0x2c277a24, void, (lv_obj_t *, i32, i32))(o, x, y)
#define lv_obj_add_flag(o, f)       F(0x2c27cbb8, void, (lv_obj_t *, u32))(o, f)
#define lv_obj_clear_flag(o, f)     F(0x2c27cc5c, void, (lv_obj_t *, u32))(o, f)
#define lv_obj_set_scrollbar_mode(o, m) F(0x2c27b5c8, void, (lv_obj_t *, u32))(o, m)       /* 0 = off */
#define lv_obj_add_event_cb(o, cb, code, ud) F(0x2c27d9cc, void *, (lv_obj_t *, void (*)(lv_event_t *), u32, void *))(o, cb, code, ud)
#define lv_event_get_code(e)        F(0x2c27d988, u32, (lv_event_t *))(e)
#define lv_event_get_target(e)      F(0x2c27d980, lv_obj_t *, (lv_event_t *))(e)
#define lv_event_get_user_data(e)   F(0x2c27d994, void *, (lv_event_t *))(e)
#define lv_label_create(p)          F(0x2c28de90, lv_obj_t *, (lv_obj_t *))(p)
#define lv_label_set_text(o, s)     F(0x2c28e98c, void, (lv_obj_t *, const char *))(o, s)
#define lv_img_create(p)            F(0x2c2905ac, lv_obj_t *, (lv_obj_t *))(p)
#define lv_img_set_src(o, d)        F(0x2c29064c, void, (lv_obj_t *, const void *))(o, d)
#define lv_timer_create(cb, ms, ud) F(0x2c28a3f0, lv_timer_t *, (void (*)(lv_timer_t *), u32, void *))(cb, ms, ud)
#define lv_timer_del(t)             F(0x2c28a448, void, (lv_timer_t *))(t)
#define timer_user_data(t)          (*(void **)((u8 *)(t) + 12))                       /* lv_timer_t.user_data */
#define lv_indev_get_act()          F(0x2c279240, lv_indev_t *, (void))()
#define lv_indev_get_gesture_dir(i) F(0x2c279336, u32, (lv_indev_t *))(i)
#define lv_tick_get()               F(0x2c288ef4, u32, (void))()
#define app_malloc(n)               F(0x2c0eb00c, void *, (u32))(n)
#define app_free(p)                 F(0x2c0eb018, void, (void *))(p)
#define f_open(path, mode)          F(0x2c0c575c, i32, (const char *, const char *))(path, mode)
#define f_read(fd, buf, n)          F(0x2c142dcc, i32, (i32, void *, u32))(fd, buf, n)
#define f_write(fd, buf, n)         F(0x2c142ee0, i32, (i32, const void *, u32))(fd, buf, n)
#define f_close(fd)                 F(0x2c142c24, u32, (i32))(fd)
#define motor_once(id, flag)        F(0x2c1423f8, u32, (u32, i32))(id, flag)         /* flag != 0: respects the user's vibration setting */
#define ui_gesture_consume()        F(0x2c224f04, void, (void))()
#define wm_open(op, id, arg, anim)  F(0x2c225ddc, void, (i32, i32, i32, i32))(op, id, arg, anim)
#define wm_set_current(id)          F(0x2c224d30, void, (u16))(id)
#define set_bg_color(o, c)          F(0x2c27d53c, void, (lv_obj_t *, u16, u32))(o, c, 0)
#define set_bg_opa(o, v)            F(0x2c27d55c, void, (lv_obj_t *, u32, u32))(o, v, 0)
#define set_border_width(o, v)      F(0x2c27d5ae, void, (lv_obj_t *, i32, u32))(o, v, 0)
#define set_radius(o, v)            F(0x2c27d6f6, void, (lv_obj_t *, i32, u32))(o, v, 0)
#define set_text_color(o, c)        F(0x2c27d69a, void, (lv_obj_t *, u16, u32))(o, c, 0)
#define set_text_font(o, f)         F(0x2c27d6c4, void, (lv_obj_t *, const void *, u32))(o, f, 0)
#define set_text_align(o, a)        F(0x2c27d6ec, void, (lv_obj_t *, u32, u32))(o, a, 0)
#define set_pad_all(o, v)           do { F(0x2c27d500, void, (lv_obj_t *, i32, u32))(o, v, 0); F(0x2c27d50a, void, (lv_obj_t *, i32, u32))(o, v, 0); \
                                         F(0x2c27d514, void, (lv_obj_t *, i32, u32))(o, v, 0); F(0x2c27d51e, void, (lv_obj_t *, i32, u32))(o, v, 0); } while (0)

#define FL_HIDDEN (1u << 0)
#define FL_CLICKABLE (1u << 1)
#define FL_SCROLLABLE (1u << 4)
#define EV_CLICKED 7
#define EV_GESTURE 12
#define EV_DELETE 33
#define ALIGN_LEFT 0
#define ALIGN_CENTER 2
#define BACK_ANIM 0x14                                                  /* 4th argument of wm_open for "back": the slide the stock windows use (docs/details.md) */
#define SCREEN_W 256
#define SCREEN_H 402

#define ROBOTO_MEDIUM(i) (*(const void *const *)(0x2010b0e0 + 4 * (i)))   /* docs/details.md: 0:86 1:48 2:44 3:40 4:36 5:32 6:30 7:28 8:24 9:23 10:20 */
#define FT_HUGE ROBOTO_MEDIUM(0)
#define FT_POINT ROBOTO_MEDIUM(2)
#define FT_GAMES ROBOTO_MEDIUM(4)
#define FT_NAME ROBOTO_MEDIUM(5)
#define FT_BTN ROBOTO_MEDIUM(7)
#define FT_SMALL ROBOTO_MEDIUM(8)

/* palette (RGB565; docs/details.md for the UI colours, the players' colours are our choice) */
#define C_BLACK 0x0000
#define C_WHITE 0xffff
#define C_CARD 0x2124
#define C_WIN 0x1b28
#define C_BTN 0x5ade
#define C_BTN_OFF 0x2124
#define C_MUTED 0xadd8
#define C_LINE 0x4a49
#define C_SERVE 0xff2a
#define C_A 0x7e5f
#define C_B 0xfd4d
#define C_WARN 0xc986

/* ---- the app interface (src/watch/README.md) ---- */
typedef struct {
    u32 hdr, data_size; const void *data, *pad;                         /* lv_img_dsc_t, 16 bytes: the firmware copies 16 when it takes an image variable */
} Icon;
#define ICON_HDR_I4(w, h) (9u | ((u32)(w) << 10) | ((u32)(h) << 21))     /* LV_IMG_CF_INDEXED_4BIT */
typedef struct {
    const char *name;                                                   /* shown in the hub's list */
    const Icon *icon;                                                   /* 40 x 40, four-bit indexed (src/assets/mkicon.py); 0 = none */
    void *(*create)(lv_obj_t *root);                                    /* build the app's page as children of root (a full-screen black container, or the screen itself), return its state */
    int (*back)(void *state);                                           /* the back gesture: return 1 if the app used it (closed an overlay), 0 to leave the app */
    void (*destroy)(void *state);                                       /* the app is closed or the window deleted: stop timers, save, free the state. Its widgets are deleted by the host */
} App;

/* ---- memory and text ---- */
H void mcopy(void *d, const void *s, u32 n) { u8 *a = (u8 *)d; const u8 *b = (const u8 *)s; while (n--) *a++ = *b++; }
H void fill8(void *d, u8 v, u32 n) { u8 *a = (u8 *)d; while (n--) *a++ = v; }
H char *put(char *b, const char *s) { while (*s) *b++ = *s++; *b = 0; return b; }
H char *putn(char *b, u32 v, int pad) {
    char t[11]; int n = 0; do { t[n++] = (char)('0' + v % 10u); v /= 10u; } while (v && n < 10);
    while (n < pad && n < 10) t[n++] = '0';
    while (n) *b++ = t[--n];
    *b = 0; return b;
}
H char *fmt_dur(char *b, u32 s) { if (s >= 3600) { b = putn(b, s / 3600, 1); b = put(b, ":"); } b = putn(b, s / 60 % 60, s >= 3600 ? 2 : 1); b = put(b, ":"); return putn(b, s % 60, 2); }
H char *fmt_short(char *b, u32 s) { if (s < 3600) return fmt_dur(b, s); b = putn(b, s / 3600, 1); b = put(b, "h"); return putn(b, s / 60 % 60, 2); }

/* a label is only touched when its text changes: `cache` (TXT_MAX bytes) holds what it shows now */
#define TXT_MAX 28
H void set_txt(lv_obj_t *lab, char *cache, const char *t) {
    int i = 0;
    while (i < TXT_MAX - 1 && t[i] && cache[i] == t[i]) i++;
    if (cache[i] == t[i] && (i == TXT_MAX - 1 || !t[i])) return;       /* unchanged */
    for (i = 0; i < TXT_MAX - 1 && t[i]; i++) cache[i] = t[i];
    cache[i] = 0; lv_label_set_text(lab, cache);
}

/* ---- files: one small blob per app under /user (the directory exists on the watch) ---- */
H void blob_save(const char *path, const void *p, u32 n) { i32 fd = f_open(path, "w"); if (fd < 0) return; f_write(fd, p, n); f_close(fd); }
H int blob_load(const char *path, void *p, u32 n) {
    i32 fd = f_open(path, "r"); if (fd < 0) return 0;
    u32 got = 0; while (got < n) { i32 r = f_read(fd, (u8 *)p + got, n - got); if (r <= 0) break; got += (u32)r; }
    f_close(fd); return got == n;
}

/* ---- widgets ---- */
H lv_obj_t *mk_box(lv_obj_t *parent, i32 x, i32 y, i32 w, i32 h, i32 radius, u16 color) {
    lv_obj_t *o = lv_obj_create(parent);
    lv_obj_set_size(o, w, h); lv_obj_set_pos(o, x, y); lv_obj_clear_flag(o, FL_SCROLLABLE);
    set_bg_color(o, color); set_bg_opa(o, 255); set_border_width(o, 0); set_radius(o, radius); set_pad_all(o, 0);
    return o;
}
H lv_obj_t *mk_text(lv_obj_t *parent, i32 x, i32 y, i32 w, const void *font, u16 color, u32 align, const char *text) {
    lv_obj_t *l = lv_label_create(parent);
    lv_obj_set_pos(l, x, y); lv_obj_set_width(l, w); set_text_color(l, color); set_text_align(l, align);
    /* the text first, then the font: a new label shows "Text", and setting the font measures it; FT_HUGE has only the digits and ":-/", and a missing glyph falls back to a pointer that
     * lv_font_load does not necessarily initialise (the emulator's heap shows it as 0xa5a5a5a5). Every text set on such a label must use those characters only. */
    lv_label_set_text(l, text);
    if (font) set_text_font(l, font);
    return l;
}
/* a pill button 52 px high; *lab (optional) receives its caption label */
H lv_obj_t *mk_pill(lv_obj_t *parent, i32 x, i32 y, i32 w, const char *text, lv_obj_t **lab, void (*cb)(lv_event_t *), void *ud) {
    lv_obj_t *b = mk_box(parent, x, y, w, 52, 100, C_BTN);
    /* y = 13 puts the capitals in the middle of the 52 px pill: measured on the rendered page (src/emu/screenshot.py), the label box of this font reserves room for descenders that
     * none of our words use, so with y = 9 the text had 11 px above and 20 px below; 13 gives 15 and 16 */
    lv_obj_t *l = mk_text(b, 0, 13, w, FT_BTN, C_WHITE, ALIGN_CENTER, text);
    if (lab) *lab = l;
    lv_obj_add_event_cb(b, cb, 0, ud);
    return b;
}
/* a full-screen black container for an app inside the hub */
H lv_obj_t *mk_root(lv_obj_t *scr) { return mk_box(scr, 0, 0, SCREEN_W, SCREEN_H, 0, C_BLACK); }
#endif
