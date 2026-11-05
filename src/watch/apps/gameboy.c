/* SPDX-License-Identifier: Apache-2.0 */
/* apps/gameboy.c: a Game Boy (DMG) emulator, built on Peanut-GB (gb/peanut_gb.h, MIT, by Mahyar Koshkouei; see gb/README.md).
 *
 * The game is /user/gb/rom.gb (sent from the phone app or src/device/gb_send.py); it is read whole into the app heap (the watch gave 512 KB in one block, see bench.c), so
 * games up to a few hundred KB work. The cartridge RAM (the game's save) is /user/gb/rom.sav, read at start and written when the app is closed, in 1 KB writes, after a
 * 24-byte header with the game's title and global checksum: a save of another game (a new ROM sent over the old one) is not loaded, and is replaced when this game saves.
 *
 * Screen: the 160 x 144 picture is scaled 1.5x by this code into a 240 x 216 two-bit indexed image (LVGL's own zoom ran at 28 fps on the watch, an unzoomed indexed
 * image near 60), every second frame drawn. Controls under it: a D-pad, A and B; Select and Start at the top. One finger at a time (the touch panel reports one point).
 * The back gesture is easy to make by accident on the D-pad, so the first one only shows "Swipe again to exit"; a second within 2.5 s leaves. No sound (the watch has none).
 * Measured speed is shown at the top left (emulated frames per second; 60 is full speed). Freestanding: memset, memcpy and abort for Peanut-GB are defined below. */
#include "ui.h"
#include "icons.h"
#include <stddef.h>
#include <stdint.h>

/* what Peanut-GB needs from a C library: our own small versions (the app links no libc) */
void *memset(void *d, int c, size_t n) { u8 *p = (u8 *)d; while (n--) *p++ = (u8)c; return d; }
void *memcpy(void *d, const void *s, size_t n) { u8 *p = (u8 *)d; const u8 *q = (const u8 *)s; while (n--) *p++ = *q++; return d; }
void abort(void) { for (;;) { } }

#define ENABLE_SOUND 0
#define ENABLE_LCD 1
#define PEANUT_GB_IS_LITTLE_ENDIAN 1
#define PEANUT_GB_HIGH_LCD_ACCURACY 0                                    /* the faster sprite ordering */
#include "gb/peanut_gb.h"

#define keep_awake()                F(0x2c224f2c, void, (void))()        /* docs/details.md: call on every tick to keep the screen on */
#define lv_obj_invalidate(o)        F(0x2c2782a8, void, (lv_obj_t *))(o)
#define EV_PRESS_LOST 3
#define EV_RELEASED 8

#define ROM_PATH "/user/gb/rom.gb"
#define SAV_PATH "/user/gb/rom.sav"
#define ROM_MAX (1024u * 1024u)
#define OUT_W 240
#define OUT_H 216
#define PAL_BYTES 16
#define FB_BYTES (PAL_BYTES + OUT_W * OUT_H / 4)
#define NBTN 8
enum { K_A, K_B, K_SELECT, K_START, K_RIGHT, K_LEFT, K_UP, K_DOWN };   /* the bit order of Peanut-GB's joypad (JOYPAD_A = 1 ... JOYPAD_DOWN = 0x80) */

typedef struct {
    struct gb_s gb;                                                      /* first: the callbacks get &gb and cast it back */
    u8 *rom, *cram, *fb; u32 rom_size, cram_size;
    u8 keys, running, cram_dirty, drawn, error, pad[3];
    u32 back_t, fps_t, fps_n;
    Icon dsc;
    lv_obj_t *img, *btn[NBTN], *l_fps, *msg;
    lv_timer_t *timer;
    char t_fps[TXT_MAX], t_msg[TXT_MAX];
} Gb;

/* ---- Peanut-GB callbacks ---- */
static uint8_t gb_rom_read(struct gb_s *g, const uint_fast32_t a) { Gb *s = (Gb *)g; return a < s->rom_size ? s->rom[a] : 0xff; }
static uint8_t gb_cram_read(struct gb_s *g, const uint_fast32_t a) { Gb *s = (Gb *)g; return a < s->cram_size ? s->cram[a] : 0xff; }
static void gb_cram_write(struct gb_s *g, const uint_fast32_t a, const uint8_t v) { Gb *s = (Gb *)g; if (a < s->cram_size && s->cram[a] != v) { s->cram[a] = v; s->cram_dirty = 1; } }
static void gb_on_error(struct gb_s *g, const enum gb_error_e e, const uint16_t addr) { Gb *s = (Gb *)g; (void)addr; s->error = (u8)(e + 1); s->running = 0; }

/* one line of 160 pixels (shade in bits 0-1) -> 1.5x: source columns 2k, 2k+1 -> 3k, 3k+1 | 3k+2; source lines 2k, 2k+1 -> 3k, 3k+1 | 3k+2 */
static void put_row(u8 *row, const uint8_t *px) {
    u32 o = 0, acc = 0, n = 0;
    for (int x = 0; x < LCD_WIDTH; x++) {
        u32 v = px[x] & 3, reps = (x & 1) ? 1 : 2;
        while (reps--) { acc = (acc << 2) | v; if (++n == 4) { row[o++] = (u8)acc; acc = 0; n = 0; } }
    }
}
static void gb_line(struct gb_s *g, const uint8_t *pixels, const uint_fast8_t line) {
    Gb *s = (Gb *)g; u8 *base = s->fb + PAL_BYTES; u32 y = line;
    if (y >= LCD_HEIGHT) return;
    u32 d = y / 2 * 3 + (y & 1 ? 2 : 0);
    put_row(base + d * (OUT_W / 4), pixels);
    if (!(y & 1)) mcopy(base + (d + 1) * (OUT_W / 4), base + d * (OUT_W / 4), OUT_W / 4);
    if (y == LCD_HEIGHT - 1) s->drawn = 1;
}

/* ---- files ---- */
static int read_all_fd(i32 fd, u8 *p, u32 n) { u32 got = 0; while (got < n) { i32 r = f_read(fd, p + got, n - got > 4096 ? 4096 : n - got); if (r <= 0) break; got += (u32)r; } return got == n; }
/* the ROM: its size from the header (byte 0x148: 32 KB << n), then the whole file into one block */
static const char *load_rom(Gb *s) {
    u8 head[0x150]; i32 fd = f_open(ROM_PATH, "r");
    if (fd < 0) return "No game";
    if (!read_all_fd(fd, head, sizeof head) || head[0x148] > 8) { f_close(fd); return "Not a Game Boy ROM"; }
    u32 size = 0x8000u << head[0x148];
    if (size > ROM_MAX) { f_close(fd); return "Game too big"; }
    s->rom = (u8 *)app_malloc(size);
    if (!s->rom) { f_close(fd); return "Not enough memory"; }
    mcopy(s->rom, head, sizeof head);
    int ok = read_all_fd(fd, s->rom + sizeof head, size - sizeof head); f_close(fd);
    if (!ok) return "The ROM file is short";
    s->rom_size = size; return 0;
}
typedef struct { u32 magic; u8 title[16]; u16 gsum; u16 pad; } SavHeader;      /* the header of rom.sav: which game the cartridge RAM belongs to */
#define SAV_MAGIC 0x31534247u                                            /* "GBS1" */
static void sav_header(Gb *s, SavHeader *h) {
    fill8(h, 0, sizeof *h); h->magic = SAV_MAGIC; mcopy(h->title, s->rom + 0x134, 16); h->gsum = (u16)(s->rom[0x14e] << 8 | s->rom[0x14f]);
}
static void load_cram(Gb *s) {
    SavHeader want, got; sav_header(s, &want);
    i32 fd = f_open(SAV_PATH, "r"); if (fd < 0) return;
    if (read_all_fd(fd, (u8 *)&got, sizeof got)) {
        const u8 *a = (const u8 *)&want, *b = (const u8 *)&got; u32 i = 0; while (i < sizeof got && a[i] == b[i]) i++;
        if (i == sizeof got && !read_all_fd(fd, s->cram, s->cram_size)) fill8(s->cram, 0xff, s->cram_size);     /* a short file: start empty */
    }
    f_close(fd);
}
static void save_cram(Gb *s) {
    if (!s->cram || !s->cram_dirty) return;
    SavHeader h; sav_header(s, &h);
    i32 fd = f_open(SAV_PATH, "w"); if (fd < 0) return;
    f_write(fd, &h, sizeof h);
    for (u32 o = 0; o < s->cram_size; o += 1024) f_write(fd, s->cram + o, s->cram_size - o > 1024 ? 1024 : s->cram_size - o);
    f_close(fd); s->cram_dirty = 0;
}

/* ---- the screen ---- */
static void show_msg(Gb *s, const char *m) { set_txt(s->msg, s->t_msg, m); if (m[0]) lv_obj_clear_flag(s->msg, FL_HIDDEN); else lv_obj_add_flag(s->msg, FL_HIDDEN); }
static void on_btn(lv_event_t *e) {
    Gb *s = (Gb *)lv_event_get_user_data(e); lv_obj_t *t = lv_event_get_target(e); u32 c = lv_event_get_code(e);
    for (int i = 0; i < NBTN; i++) if (t == s->btn[i]) {
        if (c == EV_PRESSED) { s->keys |= (u8)(1u << i); set_bg_color(t, C_BTN); motor_once(1, 1); }
        else if (c == EV_RELEASED || c == EV_PRESS_LOST) { s->keys &= (u8)~(1u << i); set_bg_color(t, C_CARD); }
        s->gb.direct.joypad = (u8)~s->keys;                              /* active low */
        return;
    }
}
static lv_obj_t *mk_btn(Gb *s, lv_obj_t *root, int k, i32 x, i32 y, i32 w, i32 h, i32 r, const char *t) {
    lv_obj_t *b = s->btn[k] = mk_box(root, x, y, w, h, r, C_CARD);
    lv_obj_t *l = mk_text(b, 0, (h - 30) / 2, w, FT_SMALL, C_WHITE, ALIGN_CENTER, t); lv_obj_clear_flag(l, FL_CLICKABLE);
    lv_obj_add_event_cb(b, on_btn, 0, s);
    return b;
}

static void tick(lv_timer_t *t) {
    Gb *s = (Gb *)timer_user_data(t);
    keep_awake();
    u32 now = lv_tick_get();
    if (s->back_t && now - s->back_t > 2500) { s->back_t = 0; show_msg(s, ""); }
    if (!s->running) return;
    gb_run_frame(&s->gb); s->fps_n++;
    if (s->drawn) { s->drawn = 0; lv_obj_invalidate(s->img); }
    if (s->error) { show_msg(s, "Emulation error"); return; }
    if (now - s->fps_t >= 2000) {
        char b[TXT_MAX], *p; u32 f10 = s->fps_n * 10000u / (now - s->fps_t);
        p = putn(b, f10 / 10, 1); p = put(p, "."); p = putn(p, f10 % 10, 1); put(p, " fps");
        set_txt(s->l_fps, s->t_fps, b); s->fps_t = now; s->fps_n = 0;
    }
}

static void *gb_create(lv_obj_t *root) {
    Gb *s = (Gb *)app_malloc(sizeof(Gb)); if (!s) return 0;
    fill8(s, 0, sizeof(Gb));
    mkdir_p("/user/gb");
    s->fb = (u8 *)app_malloc(FB_BYTES); if (!s->fb) { app_free(s); return 0; }
    fill8(s->fb, 0, FB_BYTES);
    static const u8 PAL[PAL_BYTES] = { 0x0f, 0xbc, 0x9b, 0xff,  0x0f, 0xac, 0x8b, 0xff,  0x30, 0x62, 0x30, 0xff,  0x0f, 0x38, 0x0f, 0xff };   /* B, G, R, A: shade 0 lightest */
    mcopy(s->fb, PAL, PAL_BYTES);
    s->dsc.hdr = 8u | ((u32)OUT_W << 10) | ((u32)OUT_H << 21);             /* LV_IMG_CF_INDEXED_2BIT */
    s->dsc.data_size = FB_BYTES; s->dsc.data = s->fb;

    /* layout: Select / Start and the speed at the top, the picture, the controls under it */
    s->l_fps = mk_text(root, 6, 2, 100, FT_SMALL, C_MUTED, ALIGN_LEFT, "");
    mk_btn(s, root, K_SELECT, 112, 0, 68, 28, 14, "Select");
    mk_btn(s, root, K_START, 184, 0, 68, 28, 14, "Start");
    s->img = lv_img_create(root); lv_obj_set_pos(s->img, 8, 32); lv_img_set_src(s->img, &s->dsc);
    mk_btn(s, root, K_UP, 50, 252, 48, 48, 12, "^");
    mk_btn(s, root, K_LEFT, 2, 300, 48, 48, 12, "<");
    mk_btn(s, root, K_RIGHT, 98, 300, 48, 48, 12, ">");
    mk_btn(s, root, K_DOWN, 50, 348, 48, 48, 12, "v");
    mk_btn(s, root, K_A, 198, 262, 56, 56, 28, "A");
    mk_btn(s, root, K_B, 150, 322, 56, 56, 28, "B");
    s->msg = mk_text(root, 8, 120, 240, FT_BTN, C_WHITE, ALIGN_CENTER, "");
    set_bg_color(s->msg, C_CARD); set_bg_opa(s->msg, 230); set_radius(s->msg, 16); lv_obj_add_flag(s->msg, FL_HIDDEN);

    const char *err = load_rom(s);
    if (!err) {
        enum gb_init_error_e ie = gb_init(&s->gb, gb_rom_read, gb_cram_read, gb_cram_write, gb_on_error, s);
        if (ie == GB_INIT_INVALID_CHECKSUM) err = "Bad ROM checksum";
        else if (ie != GB_INIT_NO_ERROR) err = "Cartridge not supported";
    }
    if (!err) {
        size_t n = 0;
        if (gb_get_save_size_s(&s->gb, &n) == 0 && n) {
            s->cram = (u8 *)app_malloc((u32)n);
            if (!s->cram) err = "Not enough memory";
            else { s->cram_size = (u32)n; fill8(s->cram, 0xff, s->cram_size); load_cram(s); }
        }
    }
    if (!err) {
        gb_init_lcd(&s->gb, gb_line);
        s->gb.direct.frame_skip = 1;                                     /* draw every second frame */
        s->gb.direct.joypad = 0xff;
        s->running = 1;
    } else show_msg(s, err);
    s->fps_t = lv_tick_get();
    s->timer = lv_timer_create(tick, 16, s);
    return s;
}
static int gb_back(void *st) {
    Gb *s = (Gb *)st; u32 now = lv_tick_get();
    if (!s->running) return 0;                                           /* nothing to lose: leave at once */
    if (s->back_t && now - s->back_t <= 2500) return 0;
    s->back_t = now ? now : 1; show_msg(s, "Swipe again to exit"); return 1;
}
static void gb_destroy(void *st) {
    Gb *s = (Gb *)st;
    if (s->timer) { lv_timer_del(s->timer); s->timer = 0; }
    save_cram(s);
    if (s->cram) app_free(s->cram);
    if (s->rom) app_free(s->rom);
    app_free(s->fb); app_free(s);
}
APP_EXPORT(gameboy, "Game Boy", &ICON_GAMEBOY, gb_create, gb_back, gb_destroy)
