/* SPDX-License-Identifier: Apache-2.0 */
/* loader_v1.c: replaces the stock World clock window (id 0x2b) completely, instead of drawing on top of its page (v0).
 *
 * build_package.py --takeover-create/--takeover-event puts a `b.w` at the entry of the two stock window functions, so the window manager (record 0x2c3b4a10 / RAM
 * 0x200fb4e4 + 0x2b*0x30) now calls ours:
 *   world_create (stock 0x2c1ecc64, +0x1c of the record): returns a fresh screen, `lv_obj_create(NULL)` like every stock window. The stock page is never built, so
 *     nothing of it can show before our page or come back after the screen sleeps (its window-event handler rebuilt it on LCD on; that is replaced too).
 *   world_event  (stock 0x2c1ecd68, +0x24): the stock one only rebuilds the page; ours keeps the one thing it set on entry (window +0x24 = 0x2b via 0x2c224d30).
 * The stock destroy (0x2c1ecee4, +0x2c) stays: with no stock state it only runs null-safe cleanup, then the window manager deletes our screen.
 * The screen shows what v0 showed (uptime, touch counters) plus the back gesture, done like the flashlight page: GESTURE (12) with lv_indev_get_gesture_dir == 2 (right)
 * -> wm_open(3, -1, 0, 0x14) (0x2c225ddc; the 4th argument is the transition: 0x14 slides the way the finger moves, 0 slid the other way) + ui_gesture_consume (0x2c224f04). DELETE (33) on the screen deletes our timer and frees the state.
 * Not handled (replaced stock behaviour): the World clock tile (param 0x67) and the time-change message (class 2, 0x3b): both are ignored here. */
typedef unsigned int u32; typedef unsigned short u16; typedef unsigned char u8; typedef int i32;
typedef struct lv_obj lv_obj_t; typedef struct lv_timer lv_timer_t; typedef struct lv_event lv_event_t; typedef struct lv_indev lv_indev_t;
typedef struct { i32 x, y; } lv_point_t;

#define F(addr, ret, args) ((ret (*) args)(addr | 1))
#define lv_obj_create(p)            F(0x2c27cb84, lv_obj_t *, (lv_obj_t *))(p)
#define lv_obj_set_size(o, w, h)    F(0x2c277b2c, void, (lv_obj_t *, i32, i32))(o, w, h)
#define lv_obj_set_pos(o, x, y)     F(0x2c277a24, void, (lv_obj_t *, i32, i32))(o, x, y)
#define lv_obj_clear_flag(o, f)     F(0x2c27cc5c, void, (lv_obj_t *, u32))(o, f)
#define lv_obj_add_event_cb(o, cb, code, ud) F(0x2c27d9cc, void *, (lv_obj_t *, void (*)(lv_event_t *), u32, void *))(o, cb, code, ud)
#define lv_event_get_code(e)        F(0x2c27d988, u32, (lv_event_t *))(e)
#define lv_event_get_user_data(e)   F(0x2c27d994, void *, (lv_event_t *))(e)
#define lv_label_create(p)          F(0x2c28de90, lv_obj_t *, (lv_obj_t *))(p)
#define lv_label_set_text(o, s)     F(0x2c28e98c, void, (lv_obj_t *, const char *))(o, s)
#define lv_timer_create(cb, ms, ud) F(0x2c28a3f0, lv_timer_t *, (void (*)(lv_timer_t *), u32, void *))(cb, ms, ud)
#define lv_timer_del(t)             F(0x2c28a448, void, (lv_timer_t *))(t)
#define lv_indev_get_act()          F(0x2c279240, lv_indev_t *, (void))()
#define lv_indev_get_point(i, p)    F(0x2c279310, void, (lv_indev_t *, lv_point_t *))(i, p)
#define lv_mem_alloc(n)             F(0x2c28a658, void *, (u32))(n)
#define lv_mem_free(p)              F(0x2c28a668, void, (void *))(p)
#define lv_indev_get_gesture_dir(i) F(0x2c279336, u32, (lv_indev_t *))(i)
#define ui_gesture_consume()        F(0x2c224f04, void, (void))()
#define wm_open(op, id, arg, anim)  F(0x2c225ddc, void, (i32, i32, i32, i32))(op, id, arg, anim)
#define wm_set_current(id)          F(0x2c224d30, void, (u16))(id)
#define set_bg_color(o, c)          F(0x2c27d53c, void, (lv_obj_t *, u16, u32))(o, c, 0)
#define set_bg_opa(o, v)            F(0x2c27d55c, void, (lv_obj_t *, u32, u32))(o, v, 0)
#define set_border_width(o, v)      F(0x2c27d5ae, void, (lv_obj_t *, i32, u32))(o, v, 0)
#define set_radius(o, v)            F(0x2c27d6f6, void, (lv_obj_t *, i32, u32))(o, v, 0)
#define set_text_color(o, c)        F(0x2c27d69a, void, (lv_obj_t *, u16, u32))(o, c, 0)
#define set_text_font(o, f)         F(0x2c27d6c4, void, (lv_obj_t *, const void *, u32))(o, f, 0)
#define set_pad_all(o, v)           do { F(0x2c27d500, void, (lv_obj_t *, i32, u32))(o, v, 0); F(0x2c27d50a, void, (lv_obj_t *, i32, u32))(o, v, 0); \
                                         F(0x2c27d514, void, (lv_obj_t *, i32, u32))(o, v, 0); F(0x2c27d51e, void, (lv_obj_t *, i32, u32))(o, v, 0); } while (0)

#define FLAG_SCROLLABLE (1u << 4)
#define EV_PRESSED 1
#define EV_CLICKED 7
#define EV_RELEASED 8
#define EV_GESTURE 12
#define EV_DELETE 33
#define FONT_ROBOTO_MEDIUM_32 (*(const void *const *)0x2010b0f4)   /* slot of the table filled by fonts_init */

typedef struct {
    lv_obj_t *panel, *l_title, *l_up, *l_cnt, *l_xy;
    lv_timer_t *timer;
    u32 ticks, presses, clicks, releases; i32 x, y;
    char up[16], cnt[40], xy[24];
} State;

/* decimal without division: only for 0 <= v < 1e9 */
static char *put_u(char *d, u32 v) {
    static const u32 p10[] = {100000000, 10000000, 1000000, 100000, 10000, 1000, 100, 10, 1};
    int started = 0;
    for (int i = 0; i < 9; i++) { char c = '0'; while (v >= p10[i]) { v -= p10[i]; c++; } if (c != '0' || started || i == 8) { *d++ = c; started = 1; } }
    return d;
}
static char *put_s(char *d, const char *s) { while (*s) *d++ = *s++; return d; }
static char *put_i(char *d, i32 v) { if (v < 0) { *d++ = '-'; v = -v; } if (v > 999999) v = 999999; return put_u(d, (u32)v); }

static void refresh(State *s) {
    char *d = put_u(s->up, s->ticks >> 2); d = put_s(d, "."); *d++ = (char)('0' + ((s->ticks & 3) * 25 >= 50 ? ((s->ticks & 3) == 2 ? 5 : 7) : ((s->ticks & 3) == 1 ? 2 : 0))); *d = 0;
    lv_label_set_text(s->l_up, s->up);
    d = put_s(s->cnt, "p"); d = put_u(d, s->presses); d = put_s(d, " c"); d = put_u(d, s->clicks); d = put_s(d, " r"); d = put_u(d, s->releases); *d = 0;
    lv_label_set_text(s->l_cnt, s->cnt);
    d = put_i(s->xy, s->x); d = put_s(d, ","); d = put_i(d, s->y); *d = 0;
    lv_label_set_text(s->l_xy, s->xy);
}

static void on_tick(lv_timer_t *t) { State *s = *(State **)((u8 *)t + 12); s->ticks++; refresh(s); }

static void on_event(lv_event_t *e) {
    State *s = (State *)lv_event_get_user_data(e); u32 code = lv_event_get_code(e);
    if (code == EV_DELETE) { if (s->timer) lv_timer_del(s->timer); s->timer = 0; lv_mem_free(s); return; }
    if (code == EV_GESTURE) {
        if (lv_indev_get_gesture_dir(lv_indev_get_act()) == 2) { wm_open(3, -1, 0, 0x14); ui_gesture_consume(); }   /* 0x14 = the "back" slide: the stock World clock page calls exactly this (0x2c1ecb82) */
        return;
    }
    if (code == EV_PRESSED || code == EV_CLICKED || code == EV_RELEASED) {
        lv_point_t p; lv_indev_get_point(lv_indev_get_act(), &p);
        if (code == EV_PRESSED) { s->presses++; s->x = p.x; s->y = p.y; } else if (code == EV_CLICKED) s->clicks++; else s->releases++;
    }
}

static lv_obj_t *mk_label(lv_obj_t *parent, i32 y, u16 color, const char *text) {
    lv_obj_t *l = lv_label_create(parent); set_text_color(l, color); if (FONT_ROBOTO_MEDIUM_32) set_text_font(l, FONT_ROBOTO_MEDIUM_32);
    lv_obj_set_pos(l, 16, y); lv_label_set_text(l, text); return l;
}

/* world_create: first function of the image (the address build_package.py gets as --takeover-create is its address | 1) */
__attribute__((section(".text.entry"))) lv_obj_t *world_create(u32 param, u32 param2) {
    (void)param; (void)param2;
    lv_obj_t *scr = lv_obj_create(0);
    State *s = (State *)lv_mem_alloc(sizeof(State)); if (!s) return scr;
    { u8 *z = (u8 *)s; for (u32 i = 0; i < sizeof(State); i++) z[i] = 0; }
    s->panel = scr;
    lv_obj_clear_flag(scr, FLAG_SCROLLABLE); set_bg_color(scr, 0x0000); set_bg_opa(scr, 255);
    s->l_title = mk_label(scr, 40, 0xffff, "Loader v1b");
    s->l_up = mk_label(scr, 120, 0x047f, "0"); s->l_cnt = mk_label(scr, 190, 0xffff, "p0 c0 r0"); s->l_xy = mk_label(scr, 250, 0xadd8, "0,0");
    lv_obj_add_event_cb(scr, on_event, 0, s);                      /* 0 = LV_EVENT_ALL */
    s->timer = lv_timer_create(on_tick, 250, s);
    refresh(s);
    return scr;
}

/* world_event(class, kind, data): class 0 = window life cycle (kind 0 entered, 1 leaving, 2 LCD off, 3 LCD on), class 2 = messages */
__attribute__((section(".text.entry.event"))) void world_event(char cls, char kind, void *data) {
    (void)data;
    if (cls == 0 && kind == 0) wm_set_current(0x2b);
}
