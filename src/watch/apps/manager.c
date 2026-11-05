/* SPDX-License-Identifier: Apache-2.0 */
/* apps/manager.c: "App Manager", a settings-style page for the installed apps (.f3x files in /user/hub/a00..a15.f3x, docs/f3x.md). Built from counter.c.
 *
 * The page: a summary card (apps, free slots, space used), then one row per slot that holds something: the app's icon, its name and "Slot 03 · 5.2 kB" under it. A file the hub would
 * refuse (wrong firmware, damaged header) gets a row too, with a warning colour, so it can be cleared. Tap a row: a detail page with the icon, the size, the slot and a check of the file's
 * CRC (the same check the hub makes before it runs an app); "Remove" asks twice and then writes the 8-byte tombstone the hub ignores (the Bluetooth protocol has no delete).
 * The back gesture closes the detail page first. The hub's list is rebuilt when you return to it, so a removed app is gone there too. Nothing is written except the tombstone. */
#include "ui.h"
#include "icons.h"

#define MGR_DIR "/user/hub"
#define MGR_SELF "App Manager"
#define MAX_IMAGE 0x8000u
#define MAX_RELOC 0x2000u
#define ROW_H 90
#define ROW_GAP 10
#define C_OK 0x3ee9                                                    /* a green for "File OK" */
enum { E_EMPTY, E_GONE, E_BAD, E_OK };                                 /* what a slot holds */

typedef struct { Icon icon; char name[24]; u32 size, image; u8 state, slot, pad[2]; u8 data[F3X_ICON_SIZE]; } Entry;
typedef struct {
    Entry *e[F3X_SLOTS]; lv_obj_t *row[F3X_SLOTS]; int n, napps, ngone, nbad; u32 bytes;
    lv_obj_t *root, *list, *page, *b_rm, *l_rm, *l_check;
    int sel; u8 armed, pad[3]; u32 armed_t;
    lv_timer_t *timer;
    char t_rm[TXT_MAX];
} Mgr;

static char *mgr_path(char *b, int slot) { char *e = put(b, MGR_DIR "/a"); e = putn(e, (u32)slot, 2); return put(e, ".f3x"); }
static int mgr_read(i32 fd, void *p, u32 n) { u32 got = 0; while (got < n) { i32 r = f_read(fd, (u8 *)p + got, n - got); if (r <= 0) return 0; got += (u32)r; } return 1; }
static int mgr_hdr_ok(const F3xHeader *h) {                            /* the checks of hub.c (hdr_ok) */
    return h->magic == F3X_MAGIC && h->version == 1 && h->fw_id == F3X_FW && h->flags == 0 && h->image_size >= 16 && h->image_size <= MAX_IMAGE && (h->image_size & 3) == 0
        && h->reloc_len <= MAX_RELOC && (h->app_off & 3) == 0 && h->app_off + sizeof(App) <= h->image_size && h->name[0] && h->name[23] == 0;
}
static int mgr_streq(const char *a, const char *b) { while (*a && *a == *b) { a++; b++; } return *a == *b; }
static char *mgr_kb(char *b, u32 bytes) { u32 t = (bytes * 10u + 512u) / 1024u; b = putn(b, t / 10u, 1); b = put(b, "."); b = putn(b, t % 10u, 1); return put(b, " kB"); }

/* ---- scanning the slots ---- */
static Entry *mgr_scan(Mgr *m, int slot) {
    char path[32]; F3xHeader h; mgr_path(path, slot);
    i32 fd = f_open(path, "r"); if (fd < 0) return 0;                 /* never written: empty */
    u8 *raw = (u8 *)&h; fill8(&h, 0, sizeof h);
    i32 got = f_read(fd, raw, sizeof h);
    if (got >= 8 && raw[0] == 'F' && raw[1] == '3' && raw[2] == 'X' && raw[3] == '-' && raw[4] == 'G' && raw[5] == 'O' && raw[6] == 'N' && raw[7] == 'E') { f_close(fd); m->ngone++; return 0; }
    Entry *en = (Entry *)app_malloc(sizeof(Entry)); if (!en) { f_close(fd); return 0; }
    fill8(en, 0, sizeof(Entry)); en->slot = (u8)slot;
    if (got == (i32)sizeof h && mgr_hdr_ok(&h) && mgr_read(fd, en->data, F3X_ICON_SIZE)) {
        en->state = E_OK; mcopy(en->name, h.name, 24); en->image = h.image_size;
        en->size = (u32)sizeof h + F3X_ICON_SIZE + h.image_size + h.reloc_len;
        en->icon.hdr = ICON_HDR_I4(64, 64); en->icon.data_size = F3X_ICON_SIZE; en->icon.data = en->data;
        m->napps++; m->bytes += en->size;
    } else {
        en->state = E_BAD; put(en->name, h.magic == F3X_MAGIC && h.fw_id != F3X_FW ? "Other firmware" : "Damaged file"); m->nbad++;
    }
    f_close(fd); return en;
}
/* the CRC of everything after the header, read in 128-byte blocks (the hub's inst_load does the same before it runs an app) */
static int mgr_crc_ok(int slot) {
    char path[32]; F3xHeader h; u8 b[128]; u32 crc = 0; mgr_path(path, slot);
    i32 fd = f_open(path, "r"); if (fd < 0) return 0;
    int ok = 0;
    if (mgr_read(fd, &h, sizeof h) && mgr_hdr_ok(&h)) {
        u32 left = F3X_ICON_SIZE + h.image_size + h.reloc_len; ok = 1;
        while (left) { u32 n = left < sizeof b ? left : (u32)sizeof b; if (!mgr_read(fd, b, n)) { ok = 0; break; } crc = crc32_update(crc, b, n); left -= n; }
        if (ok && crc != h.crc) ok = 0;
    }
    f_close(fd); return ok;
}

/* ---- the list ---- */
static void mgr_open_page(Mgr *m, int i);
static void mgr_row_click(lv_event_t *e) {
    Mgr *m = (Mgr *)lv_event_get_user_data(e); lv_obj_t *t = lv_event_get_target(e);
    if (lv_event_get_code(e) != EV_CLICKED || m->page) return;
    for (int i = 0; i < m->n; i++) if (t == m->row[i]) { motor_once(1, 1); mgr_open_page(m, i); return; }
}
static void mgr_build(Mgr *m) {
    for (int i = 0; i < m->n; i++) app_free(m->e[i]);
    m->n = m->napps = m->ngone = m->nbad = 0; m->bytes = 0;
    for (int s = 0; s < F3X_SLOTS; s++) { Entry *en = mgr_scan(m, s); if (en) m->e[m->n++] = en; }

    lv_obj_t *l = m->list; lv_obj_clean(l); fill8(m->row, 0, sizeof m->row);
    char b[40], *p;
    /* summary card */
    lv_obj_t *c = mk_box(l, 1, 6, 254, 112, 26, C_CARD);
    p = putn(b, (u32)m->napps, 1); put(p, m->napps == 1 ? " app installed" : " apps installed");
    mk_text(c, 20, 14, 214, FT_BTN, C_WHITE, ALIGN_LEFT, b);
    p = putn(b, (u32)(F3X_SLOTS - m->n), 1); p = put(p, " of 16 slots free");
    mk_text(c, 20, 50, 214, FT_SMALL, C_MUTED, ALIGN_LEFT, b);
    p = mgr_kb(b, m->bytes); put(p, " used");
    mk_text(c, 20, 78, 214, FT_SMALL, C_MUTED, ALIGN_LEFT, b);

    int y = 6 + 112 + ROW_GAP;
    for (int i = 0; i < m->n; i++, y += ROW_H + ROW_GAP) {
        Entry *en = m->e[i];
        lv_obj_t *r = m->row[i] = mk_box(l, 1, y, 254, ROW_H, 26, C_CARD);
        lv_obj_add_event_cb(r, mgr_row_click, 0, m);
        if (en->state == E_OK) { lv_obj_t *im = lv_img_create(r); lv_img_set_src(im, &en->icon); lv_obj_set_pos(im, 12, (ROW_H - 64) / 2); }
        else { lv_obj_t *d = mk_box(r, 12, (ROW_H - 64) / 2, 64, 64, 32, C_WARN); mk_text(d, 0, 16, 64, FT_BTN, C_WHITE, ALIGN_CENTER, "!"); lv_obj_clear_flag(d, FL_CLICKABLE); }
        mk_text(r, 84, 14, 160, FT_BTN, en->state == E_OK ? C_WHITE : C_WARN, ALIGN_LEFT, en->name);
        p = put(b, "Slot "); p = putn(p, en->slot, 2);
        if (en->state == E_OK) { p = put(p, "  "); mgr_kb(p, en->size); }
        mk_text(r, 84, 52, 160, FT_SMALL, C_MUTED, ALIGN_LEFT, b);
    }
    if (!m->n) {
        mk_text(l, 0, y + 30, SCREEN_W, FT_NAME, C_WHITE, ALIGN_CENTER, "No apps yet");
        mk_text(l, 14, y + 80, 228, FT_SMALL, C_MUTED, ALIGN_CENTER, "Add apps from a PC");
    }
    lv_obj_scroll_to_y(l, 0, 0);
}

/* ---- the detail page of one app ---- */
static void mgr_close_page(Mgr *m) { if (m->page) { lv_obj_del(m->page); m->page = 0; } m->armed = 0; }
static void mgr_render_rm(Mgr *m) {
    if (!m->b_rm) return;
    set_txt(m->l_rm, m->t_rm, m->armed ? "Sure?" : "Remove");
    set_bg_color(m->b_rm, m->armed ? C_WARN : C_BTN);
}
static void mgr_page_click(lv_event_t *e) {
    Mgr *m = (Mgr *)lv_event_get_user_data(e);
    if (lv_event_get_code(e) != EV_CLICKED || !m->page || lv_event_get_target(e) != m->b_rm) return;
    if (!m->armed) { m->armed = 1; m->armed_t = lv_tick_get(); motor_once(1, 1); mgr_render_rm(m); return; }
    char path[32]; mgr_path(path, m->e[m->sel]->slot); blob_save(path, "F3X-GONE", 8);
    motor_once(4, 1); mgr_close_page(m); mgr_build(m);
}
static void mgr_open_page(Mgr *m, int i) {
    Entry *en = m->e[i]; char b[40], *p;
    m->sel = i; m->armed = 0; m->b_rm = 0; fill8(m->t_rm, 0, TXT_MAX);
    lv_obj_t *pg = m->page = mk_root(m->root);
    lv_obj_add_flag(pg, FL_CLICKABLE);                                 /* taps stop here, not on the list below */
    if (en->state == E_OK) { lv_obj_t *im = lv_img_create(pg); lv_img_set_src(im, &en->icon); lv_obj_set_pos(im, 96, 20); }
    else { lv_obj_t *d = mk_box(pg, 96, 20, 64, 64, 32, C_WARN); mk_text(d, 0, 16, 64, FT_BTN, C_WHITE, ALIGN_CENTER, "!"); }
    mk_text(pg, 14, 96, 228, FT_NAME, C_WHITE, ALIGN_CENTER, en->name);
    lv_obj_t *c = mk_box(pg, 1, 172, 254, 152, 26, C_CARD);
    p = put(b, "Slot "); putn(p, en->slot, 2);
    mk_text(c, 20, 14, 214, FT_SMALL, C_MUTED, ALIGN_LEFT, b);
    if (en->state == E_OK) {
        p = put(b, "Size "); mgr_kb(p, en->size); mk_text(c, 20, 46, 214, FT_SMALL, C_MUTED, ALIGN_LEFT, b);
        p = put(b, "Code "); mgr_kb(p, en->image); mk_text(c, 20, 78, 214, FT_SMALL, C_MUTED, ALIGN_LEFT, b);
        int ok = mgr_crc_ok(en->slot);
        m->l_check = mk_text(c, 20, 110, 214, FT_SMALL, ok ? C_OK : C_WARN, ALIGN_LEFT, ok ? "File OK" : "Damaged: will not open");
    } else mk_text(c, 20, 46, 214, FT_SMALL, C_WARN, ALIGN_LEFT, "The hub ignores this file");
    if (!mgr_streq(en->name, MGR_SELF)) m->b_rm = mk_pill(pg, 69, 340, 118, "Remove", &m->l_rm, mgr_page_click, m);
    else mk_text(pg, 14, 352, 228, FT_SMALL, C_MUTED, ALIGN_CENTER, "This app");
    mgr_render_rm(m);
}

static void mgr_tick(lv_timer_t *t) {
    Mgr *m = (Mgr *)timer_user_data(t);
    if (m->armed && lv_tick_get() - m->armed_t > 2500) { m->armed = 0; mgr_render_rm(m); }
}
static void *mgr_create(lv_obj_t *root) {
    Mgr *m = (Mgr *)app_malloc(sizeof(Mgr)); if (!m) return 0;
    fill8(m, 0, sizeof(Mgr)); m->root = root;
    mkdir_p(MGR_DIR);
    mk_text(root, 0, 8, SCREEN_W, FT_NAME, C_WHITE, ALIGN_CENTER, "Manage apps");
    lv_obj_t *l = m->list = lv_obj_create(root);
    lv_obj_set_size(l, SCREEN_W, SCREEN_H - 50); lv_obj_set_pos(l, 0, 50);
    set_bg_opa(l, 0); set_border_width(l, 0); set_radius(l, 0); set_pad_all(l, 0); lv_obj_set_scrollbar_mode(l, 0);
    mgr_build(m);
    m->timer = lv_timer_create(mgr_tick, 500, m);
    return m;
}
static int mgr_back(void *st) { Mgr *m = (Mgr *)st; if (m->page) { mgr_close_page(m); return 1; } return 0; }
static void mgr_destroy(void *st) {
    Mgr *m = (Mgr *)st;
    if (m->timer) { lv_timer_del(m->timer); m->timer = 0; }
    for (int i = 0; i < m->n; i++) app_free(m->e[i]);                 /* the host deletes the widgets (which point at these icons) before it calls destroy */
    app_free(m);
}
APP_EXPORT(manager, "App Manager", &ICON_MANAGER, mgr_create, mgr_back, mgr_destroy)
