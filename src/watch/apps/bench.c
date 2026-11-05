/* SPDX-License-Identifier: Apache-2.0 */
/* apps/bench.c: measures what a Game Boy emulator would need from the watch. Tap "Run" and wait about 8 s.
 *
 *   CPU      a 3-cycle loop (subs + taken bne on a Cortex-M4): iterations per ms * 3 / 1000 ~ the clock in MHz
 *   Interp   a small switch-dispatch interpreter over 4 KB of opcodes: thousands of ops per second (a Game Boy runs ~1,050 k instructions/s, plus its video)
 *   Read     sequential reads of a stock image pack in 4 KB blocks, up to 256 KB: KB/s
 *   FPS 1x   a 160 x 144, 2-bit indexed image (the Game Boy screen) redrawn as fast as LVGL draws it, 2 s
 *   FPS 1.5x the same with lv_img_set_zoom(384): 240 x 216 on the screen
 *   Heap     the largest single app_malloc block, then the total in 16 KB blocks (all freed at once)
 *
 * The results are saved (64 bytes) in /user/bench.sav before each step, so if a step restarts the watch, opening the app again shows how far it got. The heap step is last on purpose: it is not known
 * whether app_malloc returns 0 on failure or asserts. Nothing else is written. */
#include "ui.h"
#include "icons.h"

#define lv_obj_invalidate(o)        F(0x2c2782a8, void, (lv_obj_t *))(o)
#define lv_img_set_zoom(o, z)       F(0x2c290f4c, void, (lv_obj_t *, u32))(o, z)

#define BENCH_PATH "/user/bench.sav"
#define BENCH_MAGIC 0x48434e42u                                          /* "BNCH" */
#define GB_W 160
#define GB_H 144
#define GB_PAL 16                                                        /* 4 entries of B, G, R, A */
#define GB_BYTES (GB_PAL + GB_W * GB_H / 4)
#define EV_DRAW_MAIN_END 22
#define NRES 6
#define NCHUNK 128
enum { R_CPU, R_INTERP, R_READ, R_FPS1, R_FPS15, R_HEAP };
enum { ST_IDLE, ST_CPU, ST_INTERP, ST_READ, ST_FPS1, ST_FPS15, ST_HEAP, ST_DONE };

typedef struct { u32 magic, stage, val[NRES], extra[NRES]; } BenchFile;   /* 56 bytes; val/extra per result, 0xffffffff = not run */
typedef struct {
    BenchFile r;
    u32 t0, frames, dirty, phase, fstart;
    lv_obj_t *res[NRES], *img, *b_run, *l_run, *status;
    lv_timer_t *timer, *ftimer;
    Icon dsc;                                                            /* lv_img_dsc_t of the frame */
    u8 *fb;                                                              /* GB_BYTES */
    void *chunk[NCHUNK];
    char t_res[NRES][TXT_MAX], t_status[TXT_MAX], t_run[TXT_MAX];
} Bench;

static const char *const RES_NAME[NRES] = { "CPU ", "Interp ", "Read ", "FPS 1x ", "FPS 1.5x ", "Heap " };
static const char *const READ_PATHS[] = {
    "/nand/system/image/common.res", "/system/image/common.res", "/nand/system/image/app_worldclock.res", "/system/image/app_worldclock.res", "/user/hub/a00.f3x",
};
#define NPATHS (sizeof READ_PATHS / sizeof READ_PATHS[0])

static void bench_save(Bench *s) { blob_save(BENCH_PATH, &s->r, sizeof s->r); }

static void bench_render(Bench *s) {
    char b[TXT_MAX], *e;
    for (int i = 0; i < NRES; i++) {
        u32 v = s->r.val[i], x = s->r.extra[i];
        e = put(b, RES_NAME[i]);
        if (v == 0xffffffffu) { put(e, "-"); set_txt(s->res[i], s->t_res[i], b); continue; }
        switch (i) {
        case R_CPU: e = put(e, "~"); e = putn(e, v, 1); put(e, " MHz"); break;
        case R_INTERP: e = putn(e, v, 1); put(e, " k op/s"); break;
        case R_READ: if (x == 0xffu) put(e, "no file"); else { e = putn(e, v, 1); e = put(e, " KB/s #"); putn(e, x, 1); } break;
        case R_FPS1: case R_FPS15: e = putn(e, v / 10, 1); e = put(e, "."); putn(e, v % 10, 1); break;
        case R_HEAP: e = putn(e, v, 1); e = put(e, "/"); e = putn(e, x, 1); put(e, " KB"); break;
        }
        set_txt(s->res[i], s->t_res[i], b);
    }
    static const char *const ST[] = { "Tap Run", "CPU...", "Interpreter...", "Reading...", "Drawing 1x...", "Drawing 1.5x...", "Heap...", "Done" };
    const char *st = s->r.stage < ST_DONE + 1 ? ST[s->r.stage] : "";
    if (s->r.stage != ST_IDLE && s->r.stage != ST_DONE && !s->timer) st = "Stopped here";      /* loaded from a file after a restart */
    set_txt(s->status, s->t_status, st);
    set_txt(s->l_run, s->t_run, s->r.stage == ST_DONE ? "Again" : "Run");
}

/* ---- the measurements ---- */
static u32 cpu_mhz(void) {
    u32 n = 4000000u, t = lv_tick_get();
    __asm__ volatile("1: subs %0, %0, #1\n bne 1b" : "+r"(n) : : "cc");
    t = lv_tick_get() - t; if (!t) t = 1;
    return 4000000u / t * 3u / 1000u;
}
static u32 interp_kops(u8 *code) {                                       /* code: 4096 bytes */
    u32 x = 0x12345678u;
    for (int i = 0; i < 4096; i++) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; code[i] = (u8)x; }
    u32 a = 1, b = 2, pc = 0, ops = 0, t = lv_tick_get();
    for (int rep = 0; rep < 250; rep++) {                                /* 1,024,000 ops */
        for (int k = 0; k < 4096; k++) {
            u8 op = code[pc];
            switch (op & 7) {
            case 0: a += op; break;
            case 1: b ^= a; break;
            case 2: a = (a << 1) | (a >> 31); break;
            case 3: b += code[(pc + 1) & 4095]; break;
            case 4: code[(pc + 7) & 4095] = (u8)a; break;
            case 5: if (a & 1) pc += 2; break;
            case 6: a -= b; break;
            default: b = (b >> 1) + op; break;
            }
            pc = (pc + 1) & 4095; ops++;
        }
    }
    t = lv_tick_get() - t; if (!t) t = 1;
    code[0] = (u8)(a + b);                                               /* keep the result alive */
    return ops / t;                                                      /* ops per ms = k ops/s */
}
static void read_test(Bench *s, u8 *buf) {
    for (u32 p = 0; p < NPATHS; p++) {
        i32 fd = f_open(READ_PATHS[p], "r"); if (fd < 0) continue;
        u32 got = 0, t = lv_tick_get();
        while (got < 256u * 1024u) { i32 r = f_read(fd, buf, 4096); if (r <= 0) break; got += (u32)r; }
        t = lv_tick_get() - t; f_close(fd); if (!t) t = 1;
        s->r.val[R_READ] = got * 1000u / 1024u / t; s->r.extra[R_READ] = p; return;
    }
    s->r.val[R_READ] = 0; s->r.extra[R_READ] = 0xffu;
}
static void heap_test(Bench *s) {
    u32 lo = 0, hi = 0, sz;
    for (sz = 4u << 20; sz >= 1024u; sz >>= 1) { void *p = app_malloc(sz); if (p) { app_free(p); lo = sz; hi = sz * 2; break; } }
    while (hi - lo > 1024u) { u32 mid = (lo + hi) / 2 & ~1023u; void *p = app_malloc(mid); if (p) { app_free(p); lo = mid; } else hi = mid; }
    u32 n = 0; while (n < NCHUNK && (s->chunk[n] = app_malloc(16384u)) != 0) n++;
    while (n) app_free(s->chunk[--n]);
    for (n = 0; n < NCHUNK && s->chunk[n]; n++) {}
    s->r.val[R_HEAP] = lo / 1024u; s->r.extra[R_HEAP] = n * 16u;
}

/* ---- drawing: a moving diagonal pattern in the four Game Boy greens; a frame is counted each time LVGL has drawn the image ---- */
static void fb_fill(Bench *s) {
    u8 *px = s->fb + GB_PAL; u32 f = s->frames;
    for (int y = 0; y < GB_H; y++)
        for (int x = 0; x < GB_W / 4; x++) {
            u32 c = (u32)(x * 4 + y + f) >> 3, v = 0;
            for (int k = 0; k < 4; k++) v = (v << 2) | ((c + (u32)k / 4u) & 3u);
            px[y * (GB_W / 4) + x] = (u8)v;
        }
}
static void bench_drawn(lv_event_t *e) { Bench *s = (Bench *)lv_event_get_user_data(e); if (lv_event_get_code(e) == EV_DRAW_MAIN_END && s->phase) { s->frames++; s->dirty = 0; } }
static void bench_frame(lv_timer_t *t) {
    Bench *s = (Bench *)timer_user_data(t);
    if (s->dirty) return;                                                /* the last change is not drawn yet */
    fb_fill(s); s->dirty = 1; lv_obj_invalidate(s->img);
}
static void fps_start(Bench *s, u32 zoom) {
    lv_obj_clear_flag(s->img, FL_HIDDEN); lv_img_set_zoom(s->img, zoom);
    s->frames = 0; s->dirty = 0; s->phase = 1; s->fstart = lv_tick_get();
    s->ftimer = lv_timer_create(bench_frame, 1, s);
}
static u32 fps_stop(Bench *s) {
    u32 t = lv_tick_get() - s->fstart; if (!t) t = 1;
    if (s->ftimer) { lv_timer_del(s->ftimer); s->ftimer = 0; } s->phase = 0;
    return s->frames * 10000u / t;                                       /* frames per second * 10 */
}

/* one step per tick, so the screen shows each result before the next step blocks */
static void bench_tick(lv_timer_t *t) {
    Bench *s = (Bench *)timer_user_data(t);
    u32 now = lv_tick_get();
    switch (s->r.stage) {
    case ST_CPU: s->r.val[R_CPU] = cpu_mhz(); s->r.stage = ST_INTERP; bench_save(s); break;
    case ST_INTERP: s->r.val[R_INTERP] = interp_kops(s->fb); s->r.stage = ST_READ; bench_save(s); break;
    case ST_READ: read_test(s, s->fb); s->r.stage = ST_FPS1; bench_save(s); fps_start(s, 256); s->t0 = now; break;
    case ST_FPS1: if (now - s->t0 < 2000) return; s->r.val[R_FPS1] = fps_stop(s); s->r.stage = ST_FPS15; bench_save(s); fps_start(s, 384); s->t0 = now; break;
    case ST_FPS15: if (now - s->t0 < 2000) return; s->r.val[R_FPS15] = fps_stop(s); lv_obj_add_flag(s->img, FL_HIDDEN); s->r.stage = ST_HEAP; bench_save(s); break;
    case ST_HEAP: heap_test(s); s->r.stage = ST_DONE; bench_save(s); lv_timer_del(s->timer); s->timer = 0; lv_obj_clear_flag(s->b_run, FL_HIDDEN); motor_once(4, 1); break;
    default: break;
    }
    bench_render(s);
}
static void bench_click(lv_event_t *e) {
    Bench *s = (Bench *)lv_event_get_user_data(e);
    if (lv_event_get_code(e) != EV_CLICKED || s->timer) return;
    for (int i = 0; i < NRES; i++) s->r.val[i] = s->r.extra[i] = 0xffffffffu;
    s->r.stage = ST_CPU; lv_obj_add_flag(s->b_run, FL_HIDDEN); motor_once(1, 1);
    s->timer = lv_timer_create(bench_tick, 50, s);
    bench_render(s);
}

static void *bench_create(lv_obj_t *root) {
    Bench *s = (Bench *)app_malloc(sizeof(Bench)); if (!s) return 0;
    fill8(s, 0, sizeof(Bench));
    s->fb = (u8 *)app_malloc(GB_BYTES < 4096 ? 4096 : GB_BYTES); if (!s->fb) { app_free(s); return 0; }
    fill8(s->fb, 0, GB_BYTES);
    static const u8 PAL[GB_PAL] = { 0x0f, 0x38, 0x0f, 0xff,  0x30, 0x62, 0x30, 0xff,  0x0f, 0xac, 0x8b, 0xff,  0x0f, 0xbc, 0x9b, 0xff };   /* B, G, R, A: the DMG greens */
    mcopy(s->fb, PAL, GB_PAL);
    s->dsc.hdr = 8u | ((u32)GB_W << 10) | ((u32)GB_H << 21);            /* LV_IMG_CF_INDEXED_2BIT */
    s->dsc.data_size = GB_BYTES; s->dsc.data = s->fb;

    BenchFile f;
    if (blob_load(BENCH_PATH, &f, sizeof f) && f.magic == BENCH_MAGIC && f.stage <= ST_DONE) s->r = f;
    else { s->r.magic = BENCH_MAGIC; s->r.stage = ST_IDLE; for (int i = 0; i < NRES; i++) s->r.val[i] = s->r.extra[i] = 0xffffffffu; }

    mk_text(root, 0, 8, 256, FT_SMALL, C_MUTED, ALIGN_CENTER, "Benchmark");
    lv_obj_t *card = mk_box(root, 1, 40, 254, 196, 26, C_CARD);
    for (int i = 0; i < NRES; i++) s->res[i] = mk_text(card, 20, 12 + i * 29, 220, FT_SMALL, C_WHITE, ALIGN_LEFT, "");
    s->status = mk_text(root, 0, 244, 256, FT_SMALL, C_MUTED, ALIGN_CENTER, "");
    s->img = lv_img_create(root); lv_obj_set_pos(s->img, 48, 250); lv_img_set_src(s->img, &s->dsc); lv_obj_add_flag(s->img, FL_HIDDEN);
    lv_obj_add_event_cb(s->img, bench_drawn, EV_DRAW_MAIN_END, s);
    s->b_run = mk_pill(root, 69, 344, 118, "Run", &s->l_run, bench_click, s);
    bench_render(s);
    return s;
}
static int bench_back(void *st) { (void)st; return 0; }
static void bench_destroy(void *st) {
    Bench *s = (Bench *)st;
    if (s->ftimer) { lv_timer_del(s->ftimer); s->ftimer = 0; }
    if (s->timer) { lv_timer_del(s->timer); s->timer = 0; }
    app_free(s->fb); app_free(s);
}
APP_EXPORT(bench, "Benchmark", &ICON_BENCH, bench_create, bench_back, bench_destroy)
