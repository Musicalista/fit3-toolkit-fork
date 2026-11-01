/* SPDX-License-Identifier: Apache-2.0 */
/* apps/mars.c: the six production tracks of Terraforming Mars (the base game): Credits, Steel, Titanium, Plants, Energy, Heat. Only the production is counted here; the stock of each resource
 * stays on the board as cubes. One row per track: its name in the colour of the game, a round "-" button, the value, a round "+" button. Credits go from -5 to 99, the others from 0 to 99.
 * "Reset" (asks twice) zeroes everything for a new game. The values are saved in /user/mars.sav 3 s after the last change and when the app is closed. */
#include "ui.h"
#include "icons.h"

typedef signed char i8;
#define MARS_PATH "/user/mars.sav"
#define MARS_MAGIC 0x3152414du                                  /* "MAR1" */
#define MARS_N 6
#define MARS_MAX 99
typedef struct { u32 magic; i8 v[MARS_N]; u8 pad[2]; } MarsFile;
typedef struct {
    i8 v[MARS_N]; u8 dirty, armed; u32 dirty_t, armed_t;
    lv_obj_t *val[MARS_N], *btn[MARS_N][2], *b_reset, *l_reset;
    lv_timer_t *timer;
    char t_val[MARS_N][TXT_MAX], t_reset[TXT_MAX];
} Mars;
static const char *const MARS_NAME[MARS_N] = { "Credits", "Steel", "Titanium", "Plants", "Energy", "Heat" };
static const u16 MARS_COLOR[MARS_N] = { 0xfe45, 0xb367, 0x9515, 0x564b, 0xab3b, 0xf2c6 };    /* yellow, brown, light grey, green, purple, red-orange: the colours of the cubes, a little lighter for a black screen */
static int mars_min(int i) { return i == 0 ? -5 : 0; }

static void mars_save(Mars *s) { MarsFile f; fill8(&f, 0, sizeof f); f.magic = MARS_MAGIC; mcopy(f.v, s->v, MARS_N); blob_save(MARS_PATH, &f, sizeof f); }
static void mars_flush(Mars *s) { if (s->dirty) { s->dirty = 0; mars_save(s); } }
static void mars_changed(Mars *s) { s->dirty = 1; s->dirty_t = lv_tick_get(); }
static void mars_render(Mars *s) {
    for (int i = 0; i < MARS_N; i++) {
        char b[TXT_MAX], *e = b; int v = s->v[i];
        if (v < 0) { e = put(e, "-"); v = -v; }
        putn(e, (u32)v, 1); set_txt(s->val[i], s->t_val[i], b);
        set_bg_color(s->btn[i][0], s->v[i] > mars_min(i) ? C_BTN : C_BTN_OFF);
        set_bg_color(s->btn[i][1], s->v[i] < MARS_MAX ? C_BTN : C_BTN_OFF);
    }
    set_txt(s->l_reset, s->t_reset, s->armed ? "Sure?" : "Reset");
    set_bg_color(s->b_reset, s->armed ? C_WARN : C_BTN);
}
static void mars_click(lv_event_t *e) {
    Mars *s = (Mars *)lv_event_get_user_data(e); lv_obj_t *t = lv_event_get_target(e);
    if (lv_event_get_code(e) != EV_CLICKED) return;
    if (t == s->b_reset) {
        if (s->armed) { s->armed = 0; fill8(s->v, 0, MARS_N); mars_changed(s); motor_once(4, 1); }
        else { s->armed = 1; s->armed_t = lv_tick_get(); motor_once(1, 1); }
    } else for (int i = 0; i < MARS_N; i++) {
        if (t == s->btn[i][0] && s->v[i] > mars_min(i)) { s->v[i]--; mars_changed(s); motor_once(1, 1); break; }
        if (t == s->btn[i][1] && s->v[i] < MARS_MAX) { s->v[i]++; mars_changed(s); motor_once(1, 1); break; }
    }
    mars_render(s);
}
static void mars_tick(lv_timer_t *t) {
    Mars *s = (Mars *)timer_user_data(t);
    if (s->armed && lv_tick_get() - s->armed_t > 2500) { s->armed = 0; mars_render(s); }
    if (s->dirty && lv_tick_get() - s->dirty_t > 3000) mars_flush(s);
}
/* a round 42 px button with its sign centred */
static lv_obj_t *mars_round(lv_obj_t *parent, i32 x, const char *sign, Mars *s) {
    lv_obj_t *b = mk_box(parent, x, 5, 42, 42, 21, C_BTN);
    mk_text(b, 0, 8, 42, FT_BTN, C_WHITE, ALIGN_CENTER, sign);
    lv_obj_add_event_cb(b, mars_click, 0, s);
    return b;
}
static void *mars_create(lv_obj_t *root) {
    Mars *s = (Mars *)app_malloc(sizeof(Mars)); if (!s) return 0;
    fill8(s, 0, sizeof(Mars));
    MarsFile f; if (blob_load(MARS_PATH, &f, sizeof f) && f.magic == MARS_MAGIC) {
        int ok = 1; for (int i = 0; i < MARS_N; i++) if (f.v[i] < mars_min(i) || f.v[i] > MARS_MAX) ok = 0;
        if (ok) mcopy(s->v, f.v, MARS_N);
    }
    for (int i = 0; i < MARS_N; i++) {
        lv_obj_t *row = mk_box(root, 1, 4 + i * 56, 254, 52, 26, C_CARD);
        mk_text(row, 12, 11, 104, FT_SMALL, MARS_COLOR[i], ALIGN_LEFT, MARS_NAME[i]);
        s->btn[i][0] = mars_round(row, 116, "-", s);
        s->val[i] = mk_text(row, 158, 15, 40, FT_NAME, C_WHITE, ALIGN_CENTER, "");
        s->btn[i][1] = mars_round(row, 200, "+", s);
    }
    s->b_reset = mk_pill(root, 6, 344, 244, "Reset", &s->l_reset, mars_click, s);
    s->timer = lv_timer_create(mars_tick, 500, s);
    mars_render(s);
    return s;
}
static int mars_back(void *st) { (void)st; return 0; }
static void mars_destroy(void *st) { Mars *s = (Mars *)st; if (s->timer) lv_timer_del(s->timer); s->timer = 0; mars_flush(s); app_free(s); }
APP_EXPORT(mars, "Mars Production", &ICON_MARS, mars_create, mars_back, mars_destroy)
