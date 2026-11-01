/* SPDX-License-Identifier: Apache-2.0 */
/* apps/dice.c: one or two dice. Tap a die or "Roll": the faces flicker for about 0.8 s, then settle. The second pill switches between one and two dice (two show their sum).
 * Randomness: xorshift32, stirred with the millisecond tick at every roll (no hardware generator is known); nothing is saved. */
#include "ui.h"
#include "icons.h"

typedef struct {
    u32 rng; u8 ndice, anim, val[2], pad;
    lv_obj_t *die[2], *dot[2][7], *l_n, *l_sum, *b_roll, *b_n;
    lv_timer_t *timer;
    char t_n[TXT_MAX], t_sum[TXT_MAX];
} Dice;
/* the seven dot places (columns x rows of a 3 x 3 grid) and which of them each face uses */
static const u8 DOT_COL[7] = { 0, 2, 0, 1, 2, 0, 2 }, DOT_ROW[7] = { 0, 0, 1, 1, 1, 2, 2 };
static const u8 FACE[7] = { 0, 0x08, 0x41, 0x49, 0x63, 0x6b, 0x77 };       /* bit k = dot k: 1 centre; 2 corners; 3 + centre; 4 corners; 5 + centre; 6 two columns of three */

static u32 dice_rand(Dice *s) { u32 x = s->rng ^ lv_tick_get(); x ^= x << 13; x ^= x >> 17; x ^= x << 5; s->rng = x ? x : 0x9e3779b9u; return s->rng; }
static void dice_layout(Dice *s) {
    int two = s->ndice == 2, D = two ? 112 : 168;
    for (int i = 0; i < 2; i++) {
        if (i && !two) { lv_obj_add_flag(s->die[1], FL_HIDDEN); continue; }
        lv_obj_clear_flag(s->die[i], FL_HIDDEN);
        lv_obj_set_size(s->die[i], D, D); lv_obj_set_pos(s->die[i], two ? 10 + i * 124 : 44, two ? 100 : 80);
        for (int k = 0; k < 7; k++) {
            int d = D / 6, off = D * 11 / 40;                                   /* dot diameter; distance between the dot columns/rows */
            lv_obj_set_size(s->dot[i][k], d, d);
            lv_obj_set_pos(s->dot[i][k], D / 2 - d / 2 + (DOT_COL[k] - 1) * off, D / 2 - d / 2 + (DOT_ROW[k] - 1) * off);
        }
    }
}
static void dice_show(Dice *s) {
    for (int i = 0; i < s->ndice; i++)
        for (int k = 0; k < 7; k++) { if ((FACE[s->val[i]] >> k) & 1) lv_obj_clear_flag(s->dot[i][k], FL_HIDDEN); else lv_obj_add_flag(s->dot[i][k], FL_HIDDEN); }
    char b[TXT_MAX], *e;
    if (s->ndice == 2) { e = put(b, "Sum "); putn(e, (u32)s->val[0] + s->val[1], 1); set_txt(s->l_sum, s->t_sum, b); } else set_txt(s->l_sum, s->t_sum, "");
    set_txt(s->l_n, s->t_n, s->ndice == 2 ? "2 dice" : "1 die");
}
static void dice_click(lv_event_t *e) {
    Dice *s = (Dice *)lv_event_get_user_data(e); lv_obj_t *t = lv_event_get_target(e);
    if (lv_event_get_code(e) != EV_CLICKED) return;
    if (t == s->b_n) { s->ndice = (u8)(3 - s->ndice); s->anim = 0; dice_layout(s); dice_show(s); motor_once(1, 1); }
    else { s->anim = 8; motor_once(1, 1); }                                     /* a die or the Roll pill */
}
static void dice_tick(lv_timer_t *t) {
    Dice *s = (Dice *)timer_user_data(t);
    if (!s->anim) return;
    for (int i = 0; i < s->ndice; i++) s->val[i] = (u8)(dice_rand(s) % 6u + 1u);
    if (--s->anim == 0) motor_once(4, 1);
    dice_show(s);
}
static void *dice_create(lv_obj_t *root) {
    Dice *s = (Dice *)app_malloc(sizeof(Dice)); if (!s) return 0;
    fill8(s, 0, sizeof(Dice)); s->ndice = 1; s->rng = lv_tick_get() | 1u; s->val[0] = 6; s->val[1] = 1;
    mk_text(root, 0, 8, 256, FT_SMALL, C_MUTED, ALIGN_CENTER, "Dice");
    for (int i = 0; i < 2; i++) {
        s->die[i] = mk_box(root, 0, 0, 10, 10, 26, C_WHITE); lv_obj_add_event_cb(s->die[i], dice_click, 0, s);
        for (int k = 0; k < 7; k++) { s->dot[i][k] = mk_box(s->die[i], 0, 0, 10, 10, 100, C_BLACK); lv_obj_clear_flag(s->dot[i][k], FL_CLICKABLE); }
    }
    s->l_sum = mk_text(root, 0, 270, 256, FT_BTN, C_MUTED, ALIGN_CENTER, "");
    s->b_roll = mk_pill(root, 6, 344, 118, "Roll", 0, dice_click, s);
    s->b_n = mk_pill(root, 132, 344, 118, "", &s->l_n, dice_click, s);
    s->timer = lv_timer_create(dice_tick, 100, s);
    dice_layout(s); dice_show(s);
    return s;
}
static int dice_back(void *st) { (void)st; return 0; }
static void dice_destroy(void *st) { Dice *s = (Dice *)st; if (s->timer) lv_timer_del(s->timer); s->timer = 0; app_free(s); }
APP_EXPORT(dice, "Dice", &ICON_DICE, dice_create, dice_back, dice_destroy)
