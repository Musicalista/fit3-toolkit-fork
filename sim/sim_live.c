/* Live simulator core: reuses the SDK's host_game.c (software F3Api, 256x402 RGB565 frame buffer) and exports a tiny C interface for sim_gui.py (ctypes).
 * Build (see run.sh): gcc -shared -fPIC -I fit3-store/apps -I sim -o sim/libsim_<app>.so sim/sim_live.c fit3-store/apps/src/<app>.c */
#define main host_main
#include "host_game.c"
#undef main

int sim_init(const char *dir, int clock_secs) {
    snprintf(hsdir, sizeof hsdir, "%s", dir);
    api.version = F3_API_VERSION; api.fb = fb; api.w = F3_W; api.h = F3_H; api.malloc = h_malloc; api.free = h_free; api.ticks = h_ticks; api.vibrate = h_vib;
    api.rect = h_rect; api.rrect = h_rrect; api.disc = h_disc; api.text = h_text; api.ctext = h_ctext; api.num = h_num;
    api.fopen = h_fopen; api.fread = h_fread; api.fwrite = h_fwrite; api.fclose = h_fclose; api.lang_pt = 0; api.time = h_time; api.battery = h_battery;
    clk_base = clock_secs; clk_now0 = (int)now;
    app = f3app_main(&api); return app ? 0 : 1;
}
int sim_tick(int p, int x, int y) { step(p, x, y); return alive; }           /* one 33 ms step of simulated time; returns 0 when the app exited */
const unsigned short *sim_fb(void) { return fb; }
int sim_vibrations(void) { return vib; }
void sim_close(void) { if (alive && app && app->close) app->close(app); alive = 0; }
