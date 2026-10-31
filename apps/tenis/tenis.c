/* Tennis match tracker: tap a player's card to give that player a point; the app keeps points, games, sets, who serves, and when the match, each set and each game started and how long it took.
 * Best of 3 sets, tie-break to 7 at 6-6. "Undo" takes back the last points (16 deep, kept in RAM only). The match state (128 bytes) is saved to /user/tenis.sav 3 s after the last change and when the app closes;
 * the watch's file system is slow, so it is never written on every tap (a 2 KB write per tap restarted the watch). */
#include "f3game.h"
#undef TR
#define TR(pl, en) (en)                                  /* this app is English only: the watch language flag only tells Portuguese from the rest */

#define SAVE "/user/tenis.sav"
#define MAGIC 0x54454e32u
#define UNDO 16
#define MAXG 13                                         /* most games in a set: 7-6 */

typedef struct {
    u32 t_match, t_end, t_set[3], t_game;               /* seconds of the day */
    u16 gd[3][MAXG];                                    /* game durations in seconds, bit 15 set when B won the game */
    u8 p[2], s[2], g[3][2], ng[3];                      /* points in the game, sets won, games per set, games finished per set */
    u8 cur, srv, tbfirst, tb, started, over, winner, pad;
} Match;
typedef struct { u32 magic; Match m; Match undo[UNDO]; int uhead, ucount; } Save;

static Save S;
static int page, vset, arm, dirty;                             /* page 0 = score, 1 = statistics; viewed set; "new match" confirmation armed */
static u32 arm_t, dirty_t;

static void mcopy(void *d, const void *s, u32 n) { u8 *a = (u8 *)d; const u8 *b = (const u8 *)s; while (n--) *a++ = *b++; }

/* ---- time ---- */
static u32 now_s(void) {
    if (A->time) { F3Time t; A->time(&t); return (u32)(t.hour * 3600 + t.min * 60 + t.sec); }
    return A->ticks() / 1000u % 86400u;
}
static u32 dur(u32 a, u32 b) { return b >= a ? b - a : b + 86400u - a; }

/* ---- score ---- */
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

/* ---- persistence ---- */
static int match_ok(const Match *m) {
    if (m->cur > 2 || m->srv > 1 || m->tbfirst > 1 || m->tb > 1 || m->p[0] > 60 || m->p[1] > 60 || m->s[0] > 2 || m->s[1] > 2) return 0;
    for (int i = 0; i < 3; i++) if (m->ng[i] > MAXG || m->g[i][0] > 7 || m->g[i][1] > 7) return 0;
    return 1;
}
#define SAVED ((u32)((u8 *)(&S.m + 1) - (u8 *)&S))             /* magic + match state; the undo ring is not saved */
static void save(void) {
    int fd = A->fopen(SAVE, "w"); if (fd < 0) return;
    A->fwrite(fd, &S, SAVED); A->fclose(fd);
}
static void changed(void) { dirty = 1; dirty_t = A->ticks(); }
static void flush(void) { if (dirty) { dirty = 0; save(); } }
static int load(void) {
    int fd = A->fopen(SAVE, "r"); if (fd < 0) return 0;
    u32 got = 0; while (got < SAVED) { int n = A->fread(fd, (u8 *)&S + got, SAVED - got); if (n <= 0) break; got += (u32)n; }
    A->fclose(fd);
    if (got != SAVED || S.magic != MAGIC || !match_ok(&S.m)) return 0;
    fill8(S.undo, 0, sizeof S.undo); S.uhead = S.ucount = 0;
    return 1;
}
static void new_match(void) { fill8(&S, 0, sizeof S); S.magic = MAGIC; changed(); }
static void push_undo(void) { mcopy(&S.undo[S.uhead], &S.m, sizeof(Match)); S.uhead = (S.uhead + 1) % UNDO; if (S.ucount < UNDO) S.ucount++; }
static int pop_undo(void) {
    if (!S.ucount) return 0;
    S.uhead = (S.uhead + UNDO - 1) % UNDO; S.ucount--; mcopy(&S.m, &S.undo[S.uhead], sizeof(Match)); return 1;
}

/* ---- text helpers ---- */
static char *put(char *b, const char *s) { while (*s) *b++ = *s++; *b = 0; return b; }
static char *putn(char *b, u32 v, int pad) { char t[12]; return put(b, itoa_pad(t, (int)v, pad)); }
static char *fmt_dur(char *b, u32 s) { if (s >= 3600) { b = putn(b, s / 3600, 1); b = put(b, ":"); } b = putn(b, s / 60 % 60, s >= 3600 ? 2 : 1); b = put(b, ":"); return putn(b, s % 60, 2); }
static char *fmt_short(char *b, u32 s) { if (s < 3600) return fmt_dur(b, s); b = putn(b, s / 3600, 1); b = put(b, "h"); return putn(b, s / 60 % 60, 2); }
static char *fmt_clock(char *b, u32 s) { b = putn(b, s / 3600 % 24, 2); b = put(b, ":"); return putn(b, s / 60 % 60, 2); }

/* ---- drawing ---- */
#define C_CARD RGB(26, 34, 58)
#define C_WIN RGB(24, 70, 48)
#define C_BTN RGB(60, 70, 120)
static const u16 pcol[2] = { RGB(120, 200, 255), RGB(255, 170, 110) };

static void btn(int x, int y, int w, const char *s, u16 col) { A->rrect(FB, x, y, w, 32, 10, col); A->ctext(FB, x + w / 2, y + 4, s, 2, C_TEXT); }
static void bar(const char *left) { A->rect(FB, 0, 0, F3_W, 34, RGB(24, 28, 48)); A->text(FB, 8, 9, left, 2, C_TEXT); }

static void draw_score(u32 now) {
    const Match *m = &S.m; char b[32], *e; u32 ref = m->over ? m->t_end : now;
    clear(C_BG);
    if (m->started) { e = put(b, "M "); fmt_dur(e, dur(m->t_match, ref)); bar(b); } else bar(TR("Tenis", "Tennis"));
    for (int w = 0; w < 2; w++) {
        int y0 = w ? 190 : 40, o = 1 - w, won = m->over && m->winner == w;
        A->rrect(FB, 6, y0, 244, 146, 12, won ? C_WIN : C_CARD);
        A->ctext(FB, 30, y0 + 14, w ? "B" : "A", 4, pcol[w]);
        if (!m->over && server(m) == w) A->disc(FB, 30, y0 + 86, 8, RGB(255, 230, 80));
        for (int i = 0; i <= m->cur; i++) {
            int live = i == m->cur && !m->over, lead = m->g[i][w] > m->g[i][o];
            A->num(FB, 56 + i * 32, y0 + 56, m->g[i][w], 3, live || lead ? RGB(255, 255, 255) : C_MUTED);
        }
        A->rect(FB, 162, y0 + 16, 2, 114, RGB(50, 60, 90));
        if (m->over) { if (won) A->ctext(FB, 207, y0 + 55, "WIN", 3, RGB(255, 230, 80)); continue; }
        int a = m->p[w], c = m->p[o]; const char *s;
        if (m->tb) s = itoa_pad(b, a, 1);
        else if (a >= 3 && c >= 3) s = a > c ? "AD" : "40";
        else s = a == 0 ? "0" : a == 1 ? "15" : a == 2 ? "30" : "40";
        A->ctext(FB, 207, y0 + 49, s, 4, C_TEXT);
    }
    if (m->over) A->ctext(FB, 128, 341, TR("Koniec meczu", "Match over"), 2, RGB(255, 230, 80));
    else if (m->started) { e = put(b, "G "); e = fmt_short(e, dur(m->t_game, now)); e = put(e, "  S "); fmt_short(e, dur(m->t_set[m->cur], now)); A->ctext(FB, 128, 341, b, 2, C_MUTED); }
    else { A->ctext(FB, 128, 340, TR("Dotknij pole = punkt", "Tap a card = point"), 1, C_MUTED); A->ctext(FB, 128, 352, TR("Dotknij A/B = serwis", "Tap A/B = who serves"), 1, C_MUTED); }
    btn(6, 368, 116, TR("Cofnij", "Undo"), S.ucount ? C_BTN : RGB(40, 44, 64)); btn(134, 368, 116, TR("Staty", "Stats"), C_BTN);
}

static void draw_stats(u32 now) {
    const Match *m = &S.m; char b[32], *e; u32 ref = m->over ? m->t_end : now;
    clear(C_BG); bar(TR("Statystyki", "Stats"));
    e = put(b, TR("Start ", "Start ")); if (m->started) fmt_clock(e, m->t_match); else put(e, "--:--"); A->text(FB, 8, 44, b, 2, C_TEXT);
    e = put(b, TR("Czas ", "Time ")); if (m->started) fmt_dur(e, dur(m->t_match, ref)); else put(e, "-"); A->text(FB, 8, 68, b, 2, C_TEXT);
    for (int i = 0; i < 3; i++) {
        int on = i <= m->cur && m->started, sel = i == vset;
        e = put(b, "S"); e = putn(e, (u32)i + 1, 1);
        btn(6 + i * 82, 98, 74, b, sel ? RGB(90, 110, 200) : on ? C_BTN : RGB(40, 44, 64));
    }
    if (vset <= m->cur && m->started) {
        u32 end = vset < m->cur ? m->t_set[vset + 1] : ref;
        e = putn(b, m->g[vset][0], 1); e = put(e, ":"); e = putn(e, m->g[vset][1], 1); e = put(e, " "); e = fmt_clock(e, m->t_set[vset]); e = put(e, " "); fmt_short(e, dur(m->t_set[vset], end));
        A->text(FB, 8, 136, b, 2, C_TEXT);
        for (int k = 0; k < m->ng[vset]; k++) {
            int x = 6 + k / 7 * 126, y = 164 + k % 7 * 26, bw = m->gd[vset][k] >> 15;
            e = putn(b, (u32)k + 1, 1); put(e, bw ? " B" : " A"); A->text(FB, x, y + 6, b, 1, C_MUTED);
            fmt_short(b, m->gd[vset][k] & 0x7fffu); A->text(FB, x + 34, y, b, 2, pcol[bw]);
        }
    }
    btn(6, 368, 116, arm ? TR("Pewnie?", "Sure?") : TR("Nowy", "New"), arm ? RGB(200, 70, 70) : C_BTN); btn(134, 368, 116, TR("Wroc", "Back"), C_BTN);
}

/* ---- app ---- */
static Touch tc;
static int tick(F3App *self, int pressed, int x, int y, int tap_) {
    (void)self; (void)tap_;
    int tap = touch_update(&tc, pressed, x, y) == T_TAP;
    u32 now = now_s(), t = A->ticks();
    if (arm && t - arm_t > 2500) arm = 0;
    if (tap) {
        x = tc.sx; y = tc.sy;
        if (page == 0) {
            if (y >= 366) {
                if (x < 128) { if (pop_undo()) changed(); A->vibrate(1); } else { page = 1; vset = S.m.cur; arm = 0; }
            } else if (y >= 40 && y < 336 && !S.m.over) {
                int w = y >= 188;
                if (!S.m.started && x < 56) { S.m.srv ^= 1; A->vibrate(1); changed(); }
                else { push_undo(); int r = add_point(&S.m, w, now); A->vibrate(r == 0 ? 1 : 4); changed(); }
            }
        } else if (y >= 366) {
            if (x >= 128) { page = 0; arm = 0; }
            else if (arm) { new_match(); page = 0; arm = 0; A->vibrate(4); }
            else { arm = 1; arm_t = t; A->vibrate(1); }
        } else if (y >= 98 && y < 130 && x >= 6) { int i = (x - 6) / 82; if (i <= S.m.cur && S.m.started) vset = i; }
    }
    if (dirty && t - dirty_t > 3000) flush();
    if (page == 0) draw_score(now); else draw_stats(now);
    return 1;
}
static void close_(F3App *self) { (void)self; flush(); }

static F3App app_;
F3App *f3app_main(const F3Api *api) {
    A = api; fill8(&app_, 0, sizeof app_); page = vset = arm = dirty = 0; arm_t = dirty_t = 0; fill8(&tc, 0, sizeof tc);
    if (!load()) { fill8(&S, 0, sizeof S); S.magic = MAGIC; }
    app_.tick = tick; app_.close = close_; return &app_;
}
