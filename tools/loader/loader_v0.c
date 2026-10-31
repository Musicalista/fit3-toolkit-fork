/* loader_v0.c: first own loader for R390XXU0AZA3. A diagnostic page, not an app launcher.
 *
 * Runs from the World clock hook (build_package.py): an 80 ms timer calls loader_entry(timer) with the stock page's root object as user data.
 * It builds a full-screen black panel as a child of that root (what the old loader did, so leaving the page by the stock back gesture still works) and shows
 *   - an uptime counter driven by our own 250 ms timer (proves the timer runs; after the screen sleeps and wakes it shows whether the timer survived),
 *   - press / click / release counters and the last touch point, read with lv_indev_get_point(lv_indev_get_act()) in the LVGL event handler (no panel driver calls).
 * Lifetime (docs/research/T4-app-framework.md, hypothesis): the panel gets an LV_EVENT_DELETE (33) handler that deletes our timer and frees the state, so no timer
 * outlives its objects. Nothing here writes files, calls blocking functions, or touches the registry.
 * Firmware addresses: docs/symbols.csv. Freestanding C: no libc, no libgcc (no division), no static data (state lives in an LVGL-heap block). */
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
#define EV_DELETE 33
#define FONT_ROBOTO_MEDIUM_32 (*(const void *const *)0x2010b0f4)   /* T3: slot of the table filled by fonts_init */

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
    if (code == EV_PRESSED || code == EV_CLICKED || code == EV_RELEASED) {
        lv_point_t p; lv_indev_get_point(lv_indev_get_act(), &p);
        if (code == EV_PRESSED) { s->presses++; s->x = p.x; s->y = p.y; } else if (code == EV_CLICKED) s->clicks++; else s->releases++;
    }
}

static lv_obj_t *mk_label(lv_obj_t *parent, i32 y, u16 color, const char *text) {
    lv_obj_t *l = lv_label_create(parent); set_text_color(l, color); if (FONT_ROBOTO_MEDIUM_32) set_text_font(l, FONT_ROBOTO_MEDIUM_32);
    lv_obj_set_pos(l, 16, y); lv_label_set_text(l, text); return l;
}

/* the timer callback that build_package.py points the World clock stub at (the first function of the image: its address is the load address | 1) */
__attribute__((section(".text.entry"))) void loader_entry(lv_timer_t *t) {
    lv_obj_t *root = *(lv_obj_t **)((u8 *)t + 12);
    lv_timer_del(t);
    State *s = (State *)lv_mem_alloc(sizeof(State)); if (!s) return;
    { u8 *z = (u8 *)s; for (u32 i = 0; i < sizeof(State); i++) z[i] = 0; }
    s->panel = lv_obj_create(root);
    lv_obj_set_size(s->panel, 256, 402); lv_obj_set_pos(s->panel, 0, 0); lv_obj_clear_flag(s->panel, FLAG_SCROLLABLE);
    set_bg_color(s->panel, 0x0000); set_bg_opa(s->panel, 255); set_border_width(s->panel, 0); set_radius(s->panel, 0); set_pad_all(s->panel, 0);
    s->l_title = mk_label(s->panel, 40, 0xffff, "Loader v0");
    s->l_up = mk_label(s->panel, 120, 0x047f, "0"); s->l_cnt = mk_label(s->panel, 190, 0xffff, "p0 c0 r0"); s->l_xy = mk_label(s->panel, 250, 0xadd8, "0,0");
    lv_obj_add_event_cb(s->panel, on_event, 0, s);                 /* 0 = LV_EVENT_ALL: pressed, clicked, released, and DELETE (33) */
    s->timer = lv_timer_create(on_tick, 250, s);
    refresh(s);
}
