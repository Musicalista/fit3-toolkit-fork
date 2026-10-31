/* SPDX-License-Identifier: Apache-2.0 */
/* loader_v2.c: the tennis match score tracker as a native LVGL window, replacing the stock World clock window (id 0x2b) like loader_v1.
 *
 * Same take-over as v1 (build_package.py --takeover-create/--takeover-event): world_create builds a fresh screen with LVGL objects styled after the stock pages
 * (docs/details.md, section 6): black screen, 254 px cards with radius 26 and colour 0x2124, pill buttons (radius 100, colour 0x5ade), Roboto from the firmware's
 * font tables. The scoring rules (best of 3 sets, tie-break at 6-6, 16 undo steps, one save of 132 bytes 3 s after
 * the last change and when the window is deleted).
 *
 * Side key: the stock behaviour (to the watch face), see world_event. Touch: a click on a card is a point for that player; the left strip of a card (the letter) toggles who serves before the first point. "Undo" takes a point back,
 * "Stats" shows an overlay with the match and set times and a "New" button that asks twice. Back gesture: closes the overlay, or leaves the window.
 * Time: ticks (ms) + a shift stored in the save file, so durations survive a restart of the watch (the RTC call has an unknown signature, so it is not used).
 * Freestanding C: no libc, no libgcc (hardware divide only), no static data (everything lives in one app-heap block). Firmware addresses: docs/symbols.csv. */
typedef unsigned int u32; typedef unsigned short u16; typedef unsigned char u8; typedef int i32;
typedef struct lv_obj lv_obj_t; typedef struct lv_timer lv_timer_t; typedef struct lv_event lv_event_t; typedef struct lv_indev lv_indev_t;

#define F(addr, ret, args) ((ret (*) args)(addr | 1))
#define lv_obj_create(p)            F(0x2c27cb84, lv_obj_t *, (lv_obj_t *))(p)
#define lv_obj_set_size(o, w, h)    F(0x2c277b2c, void, (lv_obj_t *, i32, i32))(o, w, h)
#define lv_obj_set_width(o, w)      F(0x2c277a5c, void, (lv_obj_t *, i32))(o, w)
#define lv_obj_set_pos(o, x, y)     F(0x2c277a24, void, (lv_obj_t *, i32, i32))(o, x, y)
#define lv_obj_add_flag(o, f)       F(0x2c27cbb8, void, (lv_obj_t *, u32))(o, f)
#define lv_obj_clear_flag(o, f)     F(0x2c27cc5c, void, (lv_obj_t *, u32))(o, f)
#define lv_obj_add_event_cb(o, cb, code, ud) F(0x2c27d9cc, void *, (lv_obj_t *, void (*)(lv_event_t *), u32, void *))(o, cb, code, ud)
#define lv_event_get_code(e)        F(0x2c27d988, u32, (lv_event_t *))(e)
#define lv_event_get_target(e)      F(0x2c27d980, lv_obj_t *, (lv_event_t *))(e)
#define lv_event_get_user_data(e)   F(0x2c27d994, void *, (lv_event_t *))(e)
#define lv_label_create(p)          F(0x2c28de90, lv_obj_t *, (lv_obj_t *))(p)
#define lv_label_set_text(o, s)     F(0x2c28e98c, void, (lv_obj_t *, const char *))(o, s)
#define lv_timer_create(cb, ms, ud) F(0x2c28a3f0, lv_timer_t *, (void (*)(lv_timer_t *), u32, void *))(cb, ms, ud)
#define lv_timer_del(t)             F(0x2c28a448, void, (lv_timer_t *))(t)
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

#ifndef WINDOW_ID
#define WINDOW_ID 0x2b                                           /* the window this build replaces (build_tennis.py --slot passes it); 0x2b = World clock */
#endif
#define FL_HIDDEN (1u << 0)
#define FL_SCROLLABLE (1u << 4)
#define EV_CLICKED 7
#define EV_GESTURE 12
#define EV_DELETE 33
#define ROBOTO_MEDIUM(i) (*(const void *const *)(0x2010b0e0 + 4 * (i)))   /* docs/details.md: 0:86 1:48 2:44 3:40 4:36 5:32 6:30 7:28 8:24 9:23 10:20 */
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

/* ---- match logic (tested on the PC by test_score.c and through the real LVGL objects by tools/emu/test_loader_v2.py) ---- */
#define MAXG 13
#define UNDO 16
typedef struct {
    u32 t_match, t_end, t_set[3], t_game;               /* seconds on our shifted clock */
    u16 gd[3][MAXG];                                    /* game durations in seconds, bit 15 set when B won the game */
    u8 p[2], s[2], g[3][2], ng[3];                      /* points in the game, sets won, games per set, games finished per set */
    u8 cur, srv, tbfirst, tb, started, over, winner, pad;
} Match;
typedef struct { u32 magic; Match m; u32 t_save; } SaveFile;      /* 4 + sizeof(Match) + 4 bytes, written as is */
#define MAGIC 0x54454e33u                                   /* "TEN3" */
#define SAVE_PATH "/user/tenis.sav"

enum { L_HDR, L_G0, L_G1, L_P0, L_P1, L_INFO, L_GAME, L_SET, L_ST_TIME, L_ST_S0, L_ST_S1, L_ST_S2, L_NEW, NLAB };
typedef struct {
    Match m, undo[UNDO]; int uhead, ucount;
    u32 shift, dirty_t; u8 dirty, armed, over_shown, pad_; u32 armed_t;
    lv_obj_t *scr, *card[2], *zone[2], *dot[2], *lab[NLAB], *b_undo, *b_stats, *b_new, *b_back, *ov, *undo_pill;
    lv_timer_t *timer;
    char txt[NLAB][28];                                 /* what each label shows now: a label is only touched when its text changes */
} State;

static void mcopy(void *d, const void *s, u32 n) { u8 *a = (u8 *)d; const u8 *b = (const u8 *)s; while (n--) *a++ = *b++; }
static void fill8(void *d, u8 v, u32 n) { u8 *a = (u8 *)d; while (n--) *a++ = v; }
static u32 dur(u32 a, u32 b) { return b >= a ? b - a : b + 86400u - a; }
static u32 now_s(const State *s) { return lv_tick_get() / 1000u + s->shift; }

static int server(const Match *m) { return m->tb ? (m->tbfirst ^ (((m->p[0] + m->p[1] + 1) >> 1) & 1)) : m->srv; }

/* gives w a point; returns 0 point, 1 game, 2 set, 3 match */
static int add_point(Match *m, int w, u32 now) {
    int o = 1 - w, c = m->cur;
    if (!m->started) { m->started = 1; m->t_match = m->t_set[0] = m->t_game = now; }
    m->p[w]++;
    if (m->p[w] < (m->tb ? 7 : 4) || m->p[w] - m->p[o] < 2) return 0;
    if (m->ng[c] < MAXG) { u32 d = dur(m->t_game, now); if (d > 0x7fff) d = 0x7fff; m->gd[c][m->ng[c]++] = (u16)(d | (w ? 0x8000u : 0u)); }
    m->g[c][w]++; m->p[0] = m->p[1] = 0; m->t_game = now;
    int gw = m->g[c][w], go = m->g[c][o];
    if ((gw >= 6 && gw - go >= 2) || gw == 7) {
        m->s[w]++;
        if (m->tb) { m->srv = (u8)(m->tbfirst ^ 1); m->tb = 0; } else m->srv ^= 1;
        if (m->s[w] == 2) { m->over = 1; m->winner = (u8)w; m->t_end = now; return 3; }
        m->cur++; m->t_set[m->cur] = now; return 2;
    }
    if (gw == 6 && go == 6) { m->tbfirst = m->srv ^ 1; m->tb = 1; } else m->srv ^= 1;
    return 1;
}
static int match_ok(const Match *m) {
    if (m->cur > 2 || m->srv > 1 || m->tbfirst > 1 || m->tb > 1 || m->p[0] > 60 || m->p[1] > 60 || m->s[0] > 2 || m->s[1] > 2) return 0;
    for (int i = 0; i < 3; i++) if (m->ng[i] > MAXG || m->g[i][0] > 7 || m->g[i][1] > 7) return 0;
    return 1;
}
static void push_undo(State *s) { mcopy(&s->undo[s->uhead], &s->m, sizeof(Match)); s->uhead = (s->uhead + 1) % UNDO; if (s->ucount < UNDO) s->ucount++; }
static int pop_undo(State *s) {
    if (!s->ucount) return 0;
    s->uhead = (s->uhead + UNDO - 1) % UNDO; s->ucount--; mcopy(&s->m, &s->undo[s->uhead], sizeof(Match)); return 1;
}

/* ---- persistence ---- */
static void save(State *s) {
    SaveFile f; f.magic = MAGIC; mcopy(&f.m, &s->m, sizeof(Match)); f.t_save = now_s(s);
    i32 fd = f_open(SAVE_PATH, "w"); if (fd < 0) return;
    f_write(fd, &f, sizeof f); f_close(fd);
}
static void changed(State *s) { s->dirty = 1; s->dirty_t = lv_tick_get(); }
static void flush(State *s) { if (s->dirty) { s->dirty = 0; save(s); } }
static void load(State *s) {
    SaveFile f; i32 fd = f_open(SAVE_PATH, "r"); if (fd < 0) return;
    u32 got = 0; while (got < sizeof f) { i32 n = f_read(fd, (u8 *)&f + got, sizeof f - got); if (n <= 0) break; got += (u32)n; }
    f_close(fd);
    if (got != sizeof f || f.magic != MAGIC || !match_ok(&f.m)) return;
    mcopy(&s->m, &f.m, sizeof(Match)); s->shift = f.t_save - lv_tick_get() / 1000u;     /* the clock continues from the moment of the save */
}

/* ---- text ---- */
static char *put(char *b, const char *s) { while (*s) *b++ = *s++; *b = 0; return b; }
static char *putn(char *b, u32 v, int pad) {
    char t[11]; int n = 0; do { t[n++] = (char)('0' + v % 10u); v /= 10u; } while (v && n < 10);
    while (n < pad && n < 10) t[n++] = '0';
    while (n) *b++ = t[--n];
    *b = 0; return b;
}
static char *fmt_dur(char *b, u32 s) { if (s >= 3600) { b = putn(b, s / 3600, 1); b = put(b, ":"); } b = putn(b, s / 60 % 60, s >= 3600 ? 2 : 1); b = put(b, ":"); return putn(b, s % 60, 2); }
static char *fmt_short(char *b, u32 s) { if (s < 3600) return fmt_dur(b, s); b = putn(b, s / 3600, 1); b = put(b, "h"); return putn(b, s / 60 % 60, 2); }
static void set_txt(State *s, int id, const char *t) {
    char *c = s->txt[id]; int i = 0;
    while (i < 27 && t[i] && c[i] == t[i]) i++;
    if (c[i] == t[i] && (i == 27 || !t[i])) return;                    /* unchanged */
    for (i = 0; i < 27 && t[i]; i++) c[i] = t[i];
    c[i] = 0; lv_label_set_text(s->lab[id], c);
}

/* ---- widgets ---- */
static lv_obj_t *mk_box(lv_obj_t *parent, i32 x, i32 y, i32 w, i32 h, i32 radius, u16 color) {
    lv_obj_t *o = lv_obj_create(parent);
    lv_obj_set_size(o, w, h); lv_obj_set_pos(o, x, y); lv_obj_clear_flag(o, FL_SCROLLABLE);
    set_bg_color(o, color); set_bg_opa(o, 255); set_border_width(o, 0); set_radius(o, radius); set_pad_all(o, 0);
    return o;
}
static lv_obj_t *mk_text(lv_obj_t *parent, i32 x, i32 y, i32 w, const void *font, u16 color, u32 align, const char *text) {
    lv_obj_t *l = lv_label_create(parent);
    lv_obj_set_pos(l, x, y); lv_obj_set_width(l, w); set_text_color(l, color); set_text_align(l, align);
    if (font) set_text_font(l, font);
    lv_label_set_text(l, text); return l;
}
static lv_obj_t *mk_pill(State *s, lv_obj_t *parent, i32 x, i32 y, i32 w, const char *text, int lab_id, void (*cb)(lv_event_t *)) {
    lv_obj_t *b = mk_box(parent, x, y, w, 52, 100, C_BTN);
    /* y = 13 puts the capitals in the middle of the 52 px pill: measured on the rendered page (tools/emu/screenshot.py), the label box of this font reserves room for descenders that
     * none of our words use, so with y = 9 the text had 11 px above and 20 px below; 13 gives 15 and 16 */
    lv_obj_t *l = mk_text(b, 0, 13, w, FT_BTN, C_WHITE, 1 + 1, text);          /* LV_TEXT_ALIGN_CENTER = 2 */
    if (lab_id >= 0) s->lab[lab_id] = l;
    lv_obj_add_event_cb(b, cb, 0, s);
    return b;
}

/* ---- refresh: everything shown follows from the match state ---- */
static void render(State *s) {
    const Match *m = &s->m; char b[28], *e; u32 now = now_s(s), ref = m->over ? m->t_end : now;
    if (m->started) { e = put(b, "Match "); fmt_dur(e, dur(m->t_match, ref)); set_txt(s, L_HDR, b); } else set_txt(s, L_HDR, "");
    for (int w = 0; w < 2; w++) {
        int o = 1 - w, won = m->over && m->winner == w; const char *p;
        e = b; for (int i = 0; i <= m->cur; i++) { if (i) e = put(e, " "); e = putn(e, m->g[i][w], 1); }
        set_txt(s, L_G0 + w, b);
        if (m->over) p = won ? "WIN" : "";
        else if (m->tb) p = (putn(b, m->p[w], 1), b);
        else { int a = m->p[w], c = m->p[o]; p = (a >= 3 && c >= 3) ? (a > c ? "AD" : "40") : a == 0 ? "0" : a == 1 ? "15" : a == 2 ? "30" : "40"; }
        set_txt(s, L_P0 + w, p);
        set_bg_color(s->card[w], won ? C_WIN : C_CARD);
        if (!m->over && server(m) == w) lv_obj_clear_flag(s->dot[w], FL_HIDDEN); else lv_obj_add_flag(s->dot[w], FL_HIDDEN);
    }
    /* the game and set clocks sit right above the two buttons, each centred over its button; a finished match shows one centred line instead */
    if (m->over) { set_txt(s, L_INFO, "Match over"); set_txt(s, L_GAME, ""); set_txt(s, L_SET, ""); }
    else {
        set_txt(s, L_INFO, "");
        if (m->started) {
            e = put(b, "G "); fmt_short(e, dur(m->t_game, now)); set_txt(s, L_GAME, b);
            e = put(b, "S "); fmt_short(e, dur(m->t_set[m->cur], now)); set_txt(s, L_SET, b);
        } else { set_txt(s, L_GAME, ""); set_txt(s, L_SET, ""); }
    }
    set_bg_color(s->b_undo, s->ucount ? C_BTN : C_BTN_OFF);
    /* stats overlay */
    e = put(b, "Time "); if (m->started) fmt_dur(e, dur(m->t_match, ref)); else put(e, "-"); set_txt(s, L_ST_TIME, b);
    for (int i = 0; i < 3; i++) {
        if (i <= m->cur && m->started) {
            u32 end = i < m->cur ? m->t_set[i + 1] : ref;
            e = put(b, "S"); e = putn(e, (u32)i + 1, 1); e = put(e, "  "); e = putn(e, m->g[i][0], 1); e = put(e, "-"); e = putn(e, m->g[i][1], 1); e = put(e, "  "); fmt_short(e, dur(m->t_set[i], end));
        } else b[0] = 0;
        set_txt(s, L_ST_S0 + i, b);
    }
    set_txt(s, L_NEW, s->armed ? "Sure?" : "New");
    set_bg_color(s->b_new, s->armed ? C_WARN : C_BTN);
}
static void show_stats(State *s, int on) {
    s->over_shown = (u8)on; s->armed = 0;
    if (on) lv_obj_clear_flag(s->ov, FL_HIDDEN); else lv_obj_add_flag(s->ov, FL_HIDDEN);
    render(s);
}
static void point(State *s, int w) {
    if (s->m.over) return;
    push_undo(s); int r = add_point(&s->m, w, now_s(s)); motor_once(r == 0 ? 1 : 4, 1); changed(s); render(s);
}

/* ---- events ---- */
static void on_button(lv_event_t *e) {
    State *s = (State *)lv_event_get_user_data(e); lv_obj_t *t = lv_event_get_target(e);
    if (lv_event_get_code(e) != EV_CLICKED) return;
    if (t == s->b_undo) { if (pop_undo(s)) changed(s); motor_once(1, 1); render(s); }
    else if (t == s->b_stats) show_stats(s, 1);
    else if (t == s->b_back) show_stats(s, 0);
    else if (t == s->b_new) {
        if (s->armed) { fill8(&s->m, 0, sizeof(Match)); s->ucount = s->uhead = 0; changed(s); motor_once(4, 1); show_stats(s, 0); }
        else { s->armed = 1; s->armed_t = lv_tick_get(); motor_once(1, 1); render(s); }
    }
}
static void on_card(lv_event_t *e) {
    State *s = (State *)lv_event_get_user_data(e); lv_obj_t *t = lv_event_get_target(e);
    if (lv_event_get_code(e) != EV_CLICKED) return;
    for (int w = 0; w < 2; w++) {
        if (t == s->zone[w] && !s->m.started) { s->m.srv ^= 1; changed(s); motor_once(1, 1); render(s); return; }     /* before the first point: the letter picks who serves */
        if (t == s->zone[w] || t == s->card[w]) { point(s, w); return; }
    }
}
#define BACK_ANIM 0x14                                                  /* 4th argument of wm_open for "back": the slide the stock windows use (docs/details.md) */
/* back gesture: close the stats overlay first, then leave the window */
static void go_back(State *s) {
    if (s->over_shown) show_stats(s, 0);
    else wm_open(3, -1, 0, BACK_ANIM);
}
static void on_screen(lv_event_t *e) {
    State *s = (State *)lv_event_get_user_data(e); u32 code = lv_event_get_code(e);
    if (code == EV_DELETE) { if (s->timer) lv_timer_del(s->timer); s->timer = 0; flush(s); app_free(s); return; }
    if (code == EV_GESTURE && lv_indev_get_gesture_dir(lv_indev_get_act()) == 2) {
        go_back(s);
        ui_gesture_consume();
    }
}
static void on_tick(lv_timer_t *t) {
    State *s = *(State **)((u8 *)t + 12);
    if (s->armed && lv_tick_get() - s->armed_t > 2500) s->armed = 0;
    if (s->dirty && lv_tick_get() - s->dirty_t > 3000) flush(s);
    render(s);
}

/* world_create: first function of the image (--takeover-create gets its address | 1) */
__attribute__((section(".text.entry"))) lv_obj_t *world_create(u32 param, u32 param2) {
    (void)param; (void)param2;
    lv_obj_t *scr = lv_obj_create(0);
    State *s = (State *)app_malloc(sizeof(State)); if (!s) return scr;
    fill8(s, 0, sizeof(State)); s->scr = scr;
    *(void **)((u8 *)scr + 0x10) = s;                                  /* lv_obj_t.user_data: world_event finds the state through the window record's screen */
    load(s);
    lv_obj_clear_flag(scr, FL_SCROLLABLE); set_bg_color(scr, C_BLACK); set_bg_opa(scr, 255);
    s->lab[L_HDR] = mk_text(scr, 0, 8, 256, FT_SMALL, C_MUTED, 2, "");
    for (int w = 0; w < 2; w++) {
        lv_obj_t *c = s->card[w] = mk_box(scr, 1, 42 + w * 136, 254, 130, 26, C_CARD);
        lv_obj_add_event_cb(c, on_card, 0, s);
        s->zone[w] = mk_box(c, 0, 0, 62, 130, 26, C_CARD); set_bg_opa(s->zone[w], 0);                  /* the letter strip: transparent, clickable */
        lv_obj_add_event_cb(s->zone[w], on_card, 0, s);
        mk_text(c, 14, 12, 40, FT_NAME, w ? C_B : C_A, 2, w ? "B" : "A");
        s->dot[w] = mk_box(c, 25, 92, 14, 14, 7, C_SERVE);
        s->lab[L_G0 + w] = mk_text(c, 62, 40, 96, FT_GAMES, C_WHITE, 0, "");
        mk_box(c, 160, 19, 2, 92, 0, C_LINE);
        s->lab[L_P0 + w] = mk_text(c, 164, 36, 90, FT_POINT, C_WHITE, 2, "");
    }
    s->lab[L_INFO] = mk_text(scr, 0, 312, 256, FT_SMALL, C_MUTED, 2, "");
    s->lab[L_GAME] = mk_text(scr, 6, 316, 118, FT_SMALL, C_MUTED, 2, "");        /* over the Undo pill (x 6, width 118); y 316 leaves 8 px of text-free space above the pill, measured on the rendered page */
    s->lab[L_SET] = mk_text(scr, 132, 316, 118, FT_SMALL, C_MUTED, 2, "");       /* over the Stats pill (x 132, width 118) */
    s->b_undo = mk_pill(s, scr, 6, 344, 118, "Undo", -1, on_button);
    s->b_stats = mk_pill(s, scr, 132, 344, 118, "Stats", -1, on_button);
    /* stats overlay: hidden until "Stats" */
    s->ov = mk_box(scr, 0, 0, 256, 402, 0, C_BLACK);
    mk_text(s->ov, 0, 8, 256, FT_NAME, C_WHITE, 2, "Stats");
    s->lab[L_ST_TIME] = mk_text(s->ov, 16, 62, 224, FT_BTN, C_WHITE, 0, "");
    for (int i = 0; i < 3; i++) s->lab[L_ST_S0 + i] = mk_text(s->ov, 16, 114 + i * 46, 224, FT_BTN, C_MUTED, 0, "");
    s->b_new = mk_pill(s, s->ov, 6, 344, 118, "New", L_NEW, on_button);
    s->b_back = mk_pill(s, s->ov, 132, 344, 118, "Back", -1, on_button);
    lv_obj_add_flag(s->ov, FL_HIDDEN);
    lv_obj_add_event_cb(scr, on_screen, 0, s);                         /* 0 = LV_EVENT_ALL: gesture and DELETE (33) */
    s->timer = lv_timer_create(on_tick, 500, s);
    render(s);
    return scr;
}

/* world_event(class, kind, data): the window manager's callback of window 0x2b (docs/details.md, section 2). Every answer matters: the manager uses the return value.
 *   (0, 0)  window entered     -> remember the window id as the stock one did (wm_set_current)
 *   (0, 8)  key policy query   -> a bit mask. 0x2c4 is what the stock windows answer; with bit 6 set the manager sends the short press of the side key to the watch face
 *                                 by itself (wm_request(1, 2, ...)), exactly as in the stock apps, so we do nothing for the key.
 *   everything else -> 0. In particular the queries 6, 7 and 9 must be 0: a non-zero answer makes the manager run its own swipe-back with its own animation (docs/details.md).
 * The arguments arrive without sign or zero extension, so they are masked. */
__attribute__((section(".text.entry.event"))) u32 world_event(u32 cls, u32 kind, void *data) {
    (void)data; cls &= 0xff; kind &= 0xff;
    if (cls == 0 && kind == 0) { wm_set_current(WINDOW_ID); return 0; }
    if (cls == 0 && kind == 8) return 0x2c4;
    return 0;
}
