/* SPDX-License-Identifier: Apache-2.0 */
/* apps/counter.c: a tally counter, the smallest complete app and the template for new ones (src/watch/README.md).
 *
 * Tap the big card: +1. "-1" takes one back, "Reset" asks twice. The count (0..9999) is kept in /user/counter.sav, written 3 s after the last change and when the app is closed. */
#include "ui.h"
#include "icons.h"

#define COUNTER_PATH "/user/counter.sav"
#define COUNTER_MAGIC 0x434e5431u                                /* "CNT1" */
#define COUNTER_MAX 9999
typedef struct { u32 magic; i32 n; } CounterFile;
typedef struct {
    i32 n; u8 dirty, armed, pad[2]; u32 dirty_t, armed_t;
    lv_obj_t *card, *val, *b_minus, *b_reset, *l_reset;
    lv_timer_t *timer;
    char t_val[TXT_MAX], t_reset[TXT_MAX];
} Counter;

static void counter_save(Counter *s) { CounterFile f; f.magic = COUNTER_MAGIC; f.n = s->n; blob_save(COUNTER_PATH, &f, sizeof f); }
static void counter_flush(Counter *s) { if (s->dirty) { s->dirty = 0; counter_save(s); } }
static void counter_changed(Counter *s) { s->dirty = 1; s->dirty_t = lv_tick_get(); }
static void counter_render(Counter *s) {
    char b[TXT_MAX]; putn(b, (u32)s->n, 1); set_txt(s->val, s->t_val, b);
    set_txt(s->l_reset, s->t_reset, s->armed ? "Sure?" : "Reset");
    set_bg_color(s->b_reset, s->armed ? C_WARN : C_BTN);
    set_bg_color(s->b_minus, s->n ? C_BTN : C_BTN_OFF);
}
static void counter_click(lv_event_t *e) {
    Counter *s = (Counter *)lv_event_get_user_data(e); lv_obj_t *t = lv_event_get_target(e);
    if (lv_event_get_code(e) != EV_CLICKED) return;
    if (t == s->card || t == s->val) { if (s->n < COUNTER_MAX) { s->n++; counter_changed(s); } motor_once(1, 1); }
    else if (t == s->b_minus) { if (s->n) { s->n--; counter_changed(s); } motor_once(1, 1); }
    else if (t == s->b_reset) {
        if (s->armed) { s->armed = 0; s->n = 0; counter_changed(s); motor_once(4, 1); }
        else { s->armed = 1; s->armed_t = lv_tick_get(); motor_once(1, 1); }
    }
    counter_render(s);
}
static void counter_tick(lv_timer_t *t) {
    Counter *s = (Counter *)timer_user_data(t);
    if (s->armed && lv_tick_get() - s->armed_t > 2500) { s->armed = 0; counter_render(s); }
    if (s->dirty && lv_tick_get() - s->dirty_t > 3000) counter_flush(s);
}
static void *counter_create(lv_obj_t *root) {
    Counter *s = (Counter *)app_malloc(sizeof(Counter)); if (!s) return 0;
    fill8(s, 0, sizeof(Counter));
    CounterFile f; if (blob_load(COUNTER_PATH, &f, sizeof f) && f.magic == COUNTER_MAGIC && f.n >= 0 && f.n <= COUNTER_MAX) s->n = f.n;
    mk_text(root, 0, 8, 256, FT_SMALL, C_MUTED, ALIGN_CENTER, "Counter");
    s->card = mk_box(root, 1, 42, 254, 290, 26, C_CARD); lv_obj_add_event_cb(s->card, counter_click, 0, s);
    s->val = mk_text(s->card, 0, 80, 254, FT_HUGE, C_WHITE, ALIGN_CENTER, "");
    mk_text(s->card, 0, 238, 254, FT_SMALL, C_MUTED, ALIGN_CENTER, "Tap to add");
    s->b_minus = mk_pill(root, 6, 344, 118, "-1", 0, counter_click, s);
    s->b_reset = mk_pill(root, 132, 344, 118, "Reset", &s->l_reset, counter_click, s);
    s->timer = lv_timer_create(counter_tick, 500, s);
    counter_render(s);
    return s;
}
static int counter_back(void *st) { (void)st; return 0; }
static void counter_destroy(void *st) { Counter *s = (Counter *)st; if (s->timer) lv_timer_del(s->timer); s->timer = 0; counter_flush(s); app_free(s); }
APP_EXPORT(counter, "Counter", &ICON_COUNTER, counter_create, counter_back, counter_destroy)
