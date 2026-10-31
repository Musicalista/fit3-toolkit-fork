/* SPDX-License-Identifier: Apache-2.0 */
/* Logic test of loader_v2.c on the PC: scoring, serve rotation, tie-break, undo, the save file and the time formats. The calls into the firmware are never executed here: only the plain functions.
 *   gcc -O1 -fsanitize=address,undefined -Wno-int-to-pointer-cast -Wno-pointer-to-int-cast -o /tmp/test_score tools/loader/test_score.c && /tmp/test_score
 * (the same rules are also played through the real LVGL objects by tools/emu/test_loader_v2.py) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "loader_v2.c"

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)
static unsigned T;
static int pt(Match *m, int w, int n) { int r = 0; while (n--) r = add_point(m, w, T += 7); return r; }
static void game(Match *m, int w) { pt(m, w, 4); }
static void games(Match *m, int w, int n) { while (n--) game(m, w); }

int main(void) {
    Match m;
    /* love game, server flips */
    fill8(&m, 0, sizeof m); CHECK(server(&m) == 0);
    CHECK(pt(&m, 0, 3) == 0 && m.p[0] == 3); CHECK(pt(&m, 0, 1) == 1); CHECK(m.g[0][0] == 1 && m.p[0] == 0 && server(&m) == 1);
    /* deuce / advantage */
    fill8(&m, 0, sizeof m); pt(&m, 0, 3); pt(&m, 1, 3); pt(&m, 0, 1); CHECK(m.p[0] == 4 && m.g[0][0] == 0);          /* AD A */
    pt(&m, 1, 1); CHECK(m.g[0][0] == 0 && m.g[0][1] == 0);                                                          /* back to deuce */
    pt(&m, 0, 2); CHECK(m.g[0][0] == 1 && m.ng[0] == 1 && !(m.gd[0][0] & 0x8000));                                   /* A wins the game */
    /* 6-0 set, then match 2-0 */
    fill8(&m, 0, sizeof m); games(&m, 0, 5); CHECK(m.cur == 0 && m.g[0][0] == 5); CHECK(pt(&m, 0, 4) == 2); CHECK(m.s[0] == 1 && m.cur == 1 && m.g[1][0] == 0);
    games(&m, 0, 5); CHECK(pt(&m, 0, 4) == 3); CHECK(m.over && m.winner == 0 && m.s[0] == 2 && m.cur == 1);
    /* 6-5 does not end the set; 7-5 does */
    fill8(&m, 0, sizeof m); games(&m, 0, 5); games(&m, 1, 5); game(&m, 0); CHECK(m.g[0][0] == 6 && m.cur == 0 && !m.tb); CHECK(pt(&m, 0, 4) == 2); CHECK(m.s[0] == 1 && m.g[0][0] == 7);
    /* tie-break at 6-6: server rotates 1,2,2,2..., set 7-6, next set starts with the player who received first */
    fill8(&m, 0, sizeof m); games(&m, 0, 5); games(&m, 1, 5); game(&m, 0); game(&m, 1);                           /* 6-6, 12 games so server is A again */
    CHECK(m.tb == 1 && m.g[0][0] == 6 && m.g[0][1] == 6);
    CHECK(server(&m) == 0); pt(&m, 0, 1); CHECK(server(&m) == 1); pt(&m, 1, 1); CHECK(server(&m) == 1); pt(&m, 1, 1); CHECK(server(&m) == 0); pt(&m, 0, 1); CHECK(server(&m) == 0);
    pt(&m, 0, 5);                                                                                                    /* tie-break ends 7:2 */
    CHECK(m.s[0] == 1 && m.g[0][0] == 7 && m.tb == 0 && m.cur == 1 && server(&m) == 1);
    /* tie-break needs a 2 point margin */
    fill8(&m, 0, sizeof m); games(&m, 0, 5); games(&m, 1, 5); game(&m, 0); game(&m, 1);
    pt(&m, 0, 6); pt(&m, 1, 6); CHECK(m.tb == 1 && m.p[0] == 6 && m.p[1] == 6); pt(&m, 0, 1); CHECK(m.tb == 1); pt(&m, 1, 1); CHECK(m.tb == 1 && m.p[0] == 7); pt(&m, 0, 2); CHECK(m.s[0] == 1 && m.g[0][0] == 7);
    /* game durations are recorded with the B-win bit */
    fill8(&m, 0, sizeof m); T = 1000; add_point(&m, 1, T); for (int i = 0; i < 3; i++) add_point(&m, 1, T + 30 + i); CHECK(m.ng[0] == 1 && (m.gd[0][0] & 0x8000) && (m.gd[0][0] & 0x7fff) == 32 && m.t_match == 1000);
    /* midnight wrap */
    CHECK(dur(86390, 20) == 30);
    /* undo ring: 16 deep, the oldest falls out */
    State *S = calloc(1, sizeof(State));
    for (int i = 0; i < 20; i++) { push_undo(S); add_point(&S->m, i & 1, T += 3); }
    CHECK(S->ucount == UNDO); int back = 0; while (pop_undo(S)) back++; CHECK(back == UNDO);
    fill8(S, 0, sizeof(State)); push_undo(S); add_point(&S->m, 0, 5); CHECK(S->m.started); CHECK(pop_undo(S) && !S->m.started && !pop_undo(S));
    free(S);
    /* the save file: 132 bytes, a valid match is accepted, impossible values are refused */
    CHECK(sizeof(SaveFile) == 132 && sizeof(Match) == 124);
    fill8(&m, 0, sizeof m); games(&m, 0, 3); pt(&m, 1, 2); CHECK(match_ok(&m));
    Match bad;
    bad = m; bad.cur = 3; CHECK(!match_ok(&bad)); bad = m; bad.srv = 2; CHECK(!match_ok(&bad)); bad = m; bad.p[1] = 61; CHECK(!match_ok(&bad)); bad = m; bad.s[0] = 3; CHECK(!match_ok(&bad));
    bad = m; bad.ng[1] = MAXG + 1; CHECK(!match_ok(&bad)); bad = m; bad.g[2][1] = 8; CHECK(!match_ok(&bad));
    /* number and time formats (hardware divide only, no libgcc) */
    char b[40]; putn(b, 5, 3); CHECK(strcmp(b, "005") == 0); putn(b, 0, 1); CHECK(strcmp(b, "0") == 0); putn(b, 123456, 1); CHECK(strcmp(b, "123456") == 0);
    fmt_dur(b, 65); CHECK(strcmp(b, "1:05") == 0); fmt_dur(b, 5); CHECK(strcmp(b, "0:05") == 0); fmt_dur(b, 3725); CHECK(strcmp(b, "1:02:05") == 0);
    fmt_short(b, 65); CHECK(strcmp(b, "1:05") == 0); fmt_short(b, 3725); CHECK(strcmp(b, "1h02") == 0);
    printf(fails ? "score logic: %d FAILED\n" : "score logic: all ok\n", fails); return fails != 0;
}
