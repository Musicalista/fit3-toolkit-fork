/* SPDX-License-Identifier: Apache-2.0 */
/* Live simulator core: a thin C interface over host_api.c that sim_gui.py loads with ctypes. Link it with the app's source (the app's f3app_main is
 * resolved at link time). Build: see run.sh. */
#include "host_api.h"

int sim_init(const char *dir, int clock_secs) { return host_init(dir, clock_secs); }
int sim_tick(int pressed, int x, int y) { return host_step(pressed, x, y); }      /* one 33 ms step; returns 0 when the app has exited */
const unsigned short *sim_fb(void) { return host_fb(); }
int sim_vibrations(void) { return host_vibrations(); }
int sim_violations(void) { return host_violations(); }
int sim_leaks(void) { return host_leaks(); }
void sim_set_lang(int pt) { host_set_lang(pt); }
int sim_monkey(unsigned seed) { return host_monkey(seed); }
void sim_close(void) { host_close(); }
