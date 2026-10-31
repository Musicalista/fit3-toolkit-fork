/* SPDX-License-Identifier: Apache-2.0 */
/* Logic test for apps/tenis/tenis.c (scoring, serve rotation, tie-break, undo, persistence format).
 * gcc -O1 -I sdk -I apps/include -finput-charset=UTF-8 -fexec-charset=ISO-8859-1 -o /tmp/tenis_logic apps/tenis/test_logic.c && /tmp/tenis_logic */
#include <stdio.h>
#include "tenis.c"

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
    pt(&m, 0, 2); CHECK(m.g[0][0] == 1 && m.ng[0] == 1 && !(m.gd[0][0] & 0x8000));      /* A wins the game */
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
    /* game durations recorded and B-win bit */
    fill8(&m, 0, sizeof m); T = 1000; add_point(&m, 1, T); for (int i = 0; i < 3; i++) add_point(&m, 1, T + 30 + i); CHECK(m.ng[0] == 1 && (m.gd[0][0] & 0x8000) && (m.gd[0][0] & 0x7fff) == 32 && m.t_match == 1000);
    /* midnight wrap */
    CHECK(dur(86390, 20) == 30);
    /* undo ring */
    fill8(&S, 0, sizeof S); S.magic = MAGIC;
    for (int i = 0; i < 20; i++) { push_undo(); add_point(&S.m, i & 1, T += 3); }
    CHECK(S.ucount == UNDO); int back = 0; while (pop_undo()) back++; CHECK(back == UNDO);
    fill8(&S, 0, sizeof S); S.magic = MAGIC; push_undo(); add_point(&S.m, 0, 5); CHECK(S.m.started); CHECK(pop_undo() && !S.m.started && !pop_undo());
    printf(fails ? "tenis logic: %d FAILED\n" : "tenis logic: all ok\n", fails); return fails != 0;
}
