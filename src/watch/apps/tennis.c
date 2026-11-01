/* SPDX-License-Identifier: Apache-2.0 */
/* apps/tennis.c: the tennis match score tracker, as an app of the hub (or as the only app of a window: src/watch/hub.c).
 *
 * The page is built from native LVGL objects styled after the stock pages (docs/details.md, section 6): black screen, 254 px cards with radius 26 and colour 0x2124, pill buttons
 * (radius 100, colour 0x5ade), Roboto from the firmware's font tables. The scoring rules: best of 3 sets, tie-break at 6-6, 16 undo steps, one save of 132 bytes 3 s after
 * the last change and when the app is closed.
 *
 * Touch: a click on a card is a point for that player; the left strip of a card (the letter) toggles who serves before the first point. "Undo" takes a point back,
 * "Stats" shows an overlay with the match and set times and a "New" button that asks twice. Back gesture: closes the overlay, otherwise the host leaves the app.
 * Time: ticks (ms) + a shift stored in the save file, so durations survive a restart of the watch (the RTC call has an unknown signature, so it is not used). */
#include "ui.h"
#include "icons.h"

/* ---- match logic (tested on the PC by test_score.c and through the real LVGL objects by src/emu/test_tennis.py) ---- */
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
    lv_obj_t *root, *card[2], *zone[2], *dot[2], *lab[NLAB], *b_undo, *b_stats, *b_new, *b_back, *ov, *undo_pill;
    lv_timer_t *timer;
    char txt[NLAB][28];                                 /* what each label shows now: a label is only touched when its text changes */
} State;

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
    blob_save(SAVE_PATH, &f, sizeof f);
}
static void changed(State *s) { s->dirty = 1; s->dirty_t = lv_tick_get(); }
static void flush(State *s) { if (s->dirty) { s->dirty = 0; save(s); } }
static void load(State *s) {
    SaveFile f;
    if (!blob_load(SAVE_PATH, &f, sizeof f) || f.magic != MAGIC || !match_ok(&f.m)) return;
    mcopy(&s->m, &f.m, sizeof(Match)); s->shift = f.t_save - lv_tick_get() / 1000u;     /* the clock continues from the moment of the save */
}

static void set_t(State *s, int id, const char *t) { set_txt(s->lab[id], s->txt[id], t); }

/* ---- refresh: everything shown follows from the match state ---- */
static void render(State *s) {
    const Match *m = &s->m; char b[28], *e; u32 now = now_s(s), ref = m->over ? m->t_end : now;
    if (m->started) { e = put(b, "Match "); fmt_dur(e, dur(m->t_match, ref)); set_t(s, L_HDR, b); } else set_t(s, L_HDR, "");
    for (int w = 0; w < 2; w++) {
        int o = 1 - w, won = m->over && m->winner == w; const char *p;
        e = b; for (int i = 0; i <= m->cur; i++) { if (i) e = put(e, " "); e = putn(e, m->g[i][w], 1); }
        set_t(s, L_G0 + w, b);
        if (m->over) p = won ? "WIN" : "";
        else if (m->tb) p = (putn(b, m->p[w], 1), b);
        else { int a = m->p[w], c = m->p[o]; p = (a >= 3 && c >= 3) ? (a > c ? "AD" : "40") : a == 0 ? "0" : a == 1 ? "15" : a == 2 ? "30" : "40"; }
        set_t(s, L_P0 + w, p);
        set_bg_color(s->card[w], won ? C_WIN : C_CARD);
        if (!m->over && server(m) == w) lv_obj_clear_flag(s->dot[w], FL_HIDDEN); else lv_obj_add_flag(s->dot[w], FL_HIDDEN);
    }
    /* the game and set clocks sit right above the two buttons, each centred over its button; a finished match shows one centred line instead */
    if (m->over) { set_t(s, L_INFO, "Match over"); set_t(s, L_GAME, ""); set_t(s, L_SET, ""); }
    else {
        set_t(s, L_INFO, "");
        if (m->started) {
            e = put(b, "G "); fmt_short(e, dur(m->t_game, now)); set_t(s, L_GAME, b);
            e = put(b, "S "); fmt_short(e, dur(m->t_set[m->cur], now)); set_t(s, L_SET, b);
        } else { set_t(s, L_GAME, ""); set_t(s, L_SET, ""); }
    }
    set_bg_color(s->b_undo, s->ucount ? C_BTN : C_BTN_OFF);
    /* stats overlay */
    e = put(b, "Time "); if (m->started) fmt_dur(e, dur(m->t_match, ref)); else put(e, "-"); set_t(s, L_ST_TIME, b);
    for (int i = 0; i < 3; i++) {
        if (i <= m->cur && m->started) {
            u32 end = i < m->cur ? m->t_set[i + 1] : ref;
            e = put(b, "S"); e = putn(e, (u32)i + 1, 1); e = put(e, "  "); e = putn(e, m->g[i][0], 1); e = put(e, "-"); e = putn(e, m->g[i][1], 1); e = put(e, "  "); fmt_short(e, dur(m->t_set[i], end));
        } else b[0] = 0;
        set_t(s, L_ST_S0 + i, b);
    }
    set_t(s, L_NEW, s->armed ? "Sure?" : "New");
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
static void on_tick(lv_timer_t *t) {
    State *s = (State *)timer_user_data(t);
    if (s->armed && lv_tick_get() - s->armed_t > 2500) s->armed = 0;
    if (s->dirty && lv_tick_get() - s->dirty_t > 3000) flush(s);
    render(s);
}
/* ---- the App interface ---- */
static void *tennis_create(lv_obj_t *root) {
    State *s = (State *)app_malloc(sizeof(State)); if (!s) return 0;
    fill8(s, 0, sizeof(State)); s->root = root;
    load(s);
    s->lab[L_HDR] = mk_text(root, 0, 8, 256, FT_SMALL, C_MUTED, ALIGN_CENTER, "");
    for (int w = 0; w < 2; w++) {
        lv_obj_t *c = s->card[w] = mk_box(root, 1, 42 + w * 136, 254, 130, 26, C_CARD);
        lv_obj_add_event_cb(c, on_card, 0, s);
        s->zone[w] = mk_box(c, 0, 0, 62, 130, 26, C_CARD); set_bg_opa(s->zone[w], 0);                  /* the letter strip: transparent, clickable */
        lv_obj_add_event_cb(s->zone[w], on_card, 0, s);
        mk_text(c, 14, 12, 40, FT_NAME, w ? C_B : C_A, ALIGN_CENTER, w ? "B" : "A");
        s->dot[w] = mk_box(c, 25, 92, 14, 14, 7, C_SERVE);
        s->lab[L_G0 + w] = mk_text(c, 62, 40, 96, FT_GAMES, C_WHITE, ALIGN_LEFT, "");
        mk_box(c, 160, 19, 2, 92, 0, C_LINE);
        s->lab[L_P0 + w] = mk_text(c, 164, 36, 90, FT_POINT, C_WHITE, ALIGN_CENTER, "");
    }
    s->lab[L_INFO] = mk_text(root, 0, 312, 256, FT_SMALL, C_MUTED, ALIGN_CENTER, "");
    s->lab[L_GAME] = mk_text(root, 6, 316, 118, FT_SMALL, C_MUTED, ALIGN_CENTER, "");        /* over the Undo pill (x 6, width 118); y 316 leaves 8 px of text-free space above the pill, measured on the rendered page */
    s->lab[L_SET] = mk_text(root, 132, 316, 118, FT_SMALL, C_MUTED, ALIGN_CENTER, "");       /* over the Stats pill (x 132, width 118) */
    s->b_undo = mk_pill(root, 6, 344, 118, "Undo", 0, on_button, s);
    s->b_stats = mk_pill(root, 132, 344, 118, "Stats", 0, on_button, s);
    /* stats overlay: hidden until "Stats" */
    s->ov = mk_box(root, 0, 0, 256, 402, 0, C_BLACK);
    mk_text(s->ov, 0, 8, 256, FT_NAME, C_WHITE, ALIGN_CENTER, "Stats");
    s->lab[L_ST_TIME] = mk_text(s->ov, 16, 62, 224, FT_BTN, C_WHITE, ALIGN_LEFT, "");
    for (int i = 0; i < 3; i++) s->lab[L_ST_S0 + i] = mk_text(s->ov, 16, 114 + i * 46, 224, FT_BTN, C_MUTED, ALIGN_LEFT, "");
    s->b_new = mk_pill(s->ov, 6, 344, 118, "New", &s->lab[L_NEW], on_button, s);
    s->b_back = mk_pill(s->ov, 132, 344, 118, "Back", 0, on_button, s);
    lv_obj_add_flag(s->ov, FL_HIDDEN);
    s->timer = lv_timer_create(on_tick, 500, s);
    render(s);
    return s;
}
/* back gesture: close the stats overlay first, then the host leaves the app */
static int tennis_back(void *st) { State *s = (State *)st; if (!s->over_shown) return 0; show_stats(s, 0); return 1; }
static void tennis_destroy(void *st) { State *s = (State *)st; if (s->timer) lv_timer_del(s->timer); s->timer = 0; flush(s); app_free(s); }
static const App app_tennis = { "Tennis Score", &ICON_TENNIS, tennis_create, tennis_back, tennis_destroy };
