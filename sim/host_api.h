/* SPDX-License-Identifier: Apache-2.0 */
/* host_api.h: a software implementation of the loader's F3Api for the PC (used by the simulator and by logic tests). */
#ifndef HOST_API_H
#define HOST_API_H
#include "f3app.h"

/* Set up the API table and start the app (calls f3app_main). dir: folder that stands in for the watch's file system (only the last path component of a file name is used).
 * clock_secs: simulated time of day at start. Returns 0 on success, 1 when f3app_main refused to start. */
int host_init(const char *dir, int clock_secs);
/* One 33 ms frame of simulated time. Returns 0 once the app has quit. */
int host_step(int pressed, int x, int y);
const u16 *host_fb(void);
void host_close(void);                 /* calls the app's close() once */
int host_vibrations(void);             /* number of vibrate() calls so far (each one is also logged to stderr) */
int host_violations(void);             /* calls with arguments no real loader should get (negative sizes, absurd text scale, bad file descriptors) */
int host_leaks(void);                  /* malloc minus free so far */
void host_set_lang(int pt);
void host_set_battery(int pct);
void host_set_clock(int secs);
/* Random taps, swipes and long holds (6000 gestures, the language flips halfway); returns 1 if the app quit early or broke the rules above, else 0. */
int host_monkey(unsigned seed);
#endif
