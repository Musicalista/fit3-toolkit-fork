# Status

Legend: **verified** = seen working on a real watch (SM-R390, R390XXU0AZA3); **analysis** = from reading the firmware, not tried; **open** = unknown.

| Area | State | Notes |
|---|---|---|
| Flash a package over Bluetooth (Fit3 Manager) | verified | `fit3-spp-only` (2 one-instruction patches) and `fit3-store-base-spp` (loader) both boot |
| Serial service reachable without pairing, from Linux | verified | RFCOMM channel 29 with plain BlueZ sockets, after the spp patch |
| Native apps (`.f3a`) run from RAM | verified | `hello`, `tenis` |
| Loader needs `/user/apps/` | verified, **bug upstream** | the directory does not exist and nothing creates it (`open error:-2, 331`); `tools/firmware/make_flat_pkg.py` moves the files to `/user/a_*` |
| Install / list / remove apps from a PC | verified | `tools/device/f3_install.py`, reads the file back before touching the app list |
| `tenis` (score tracker) | verified | after cutting its saves from 2 KB per tap to 128 B 3 s after the last change, undo and exit no longer restart the watch (cause not proven) |
| Read `/nand/system/{font,image}` from a PC | verified | `tools/device/f3_pull.py`, read-only |
| Samsung fonts decoded | verified (PC) | LVGL binary fonts, `tools/assets/lvfont.py`; drawn in the simulator |
| Samsung images (`app_*.res`) | partial | first record type (indexed 8 bit) decodes; other record types not yet |
| An app reads `/nand/...` itself (`styledemo`) | **open** | being tested: the footer of the app says how many fonts opened |
| Loader page scrolls under the finger | solved by the World clock entry | with a fresh full-screen root (`lv_obj_create(NULL)`) the canvas does not scroll |
| Replace the stock *World clock* entry by our menu | analysis | hook site, helper addresses and free space found, nothing built or flashed ([docs/firmware.md](firmware.md)) |
| Rename the World clock entry | verified | "Tennis" shows in the app list (in-place string edit in the English language files); the icon is still the globe |
| Stage-1 hook on the **tile** call (`0x2c1ecd1c`) | verified **not reached** | tapping the list entry still opened the stock World clock: the list takes the other branch of `app_worldclock_init` |
| Stage-1b hook on the **page** call (`0x2c1ecd30`), stock page built first | verified | tapping "Tennis" in the app list opens the loader's menu at once, with no scrolling; `tools/firmware/world_clock_takeover.py`, 36 bytes of the main image |
| Loader buttons respond poorly even without scrolling | verified, cause under test | scrolling was not the cause; the loader reads touch by calling the panel driver itself inside the event handler (see firmware.md); `apps/touchlab` measures what is delivered |
| Start an app directly from a list entry (no menu) | open | needs changes to the loader itself |
| Factory file commands (`FI^MKDIR`, `FI^LS`, ...) | open | exist in the firmware, syntax unknown; the same set has `FORMAT`, **do not guess** |
| Galaxy Wearable after our experiments | observed | once stuck on "Updating info" after aborted transfers; a watch restart cleared it |
| Ghidra pipeline (`tools/re/`) | verified (PC) | 15,478 functions, 22,390 strings and the decompiled C exported from the stock main image; the flash alias `0x0c......` is mapped (otherwise jump tables fail) |
| LVGL version and API addresses | analysis | LVGL 8.3.x; 286 functions in [symbols.csv](symbols.csv) ([T1](research/T1-lvgl.md)); `LV_EVENT_DELETE` is **33** |
| Display and stock UI patterns | analysis | 256 x 402 RGB565; cards, pills, image-based switches and round buttons ([T2](research/T2-ui-patterns.md)) |
| Image packs (`.res`) and the app-list icon | analysis | two record types decode (`tools/assets/lvres.py`); the World clock row icon is image ID 21 in `app_applist.res` ([T3](research/T3-resources.md)) |
| Window registry and lifecycle | analysis | 166 records of 48 bytes at `0x2c3b4200`; the app list is a static 12-row table; the restart-after-wake cause is a hypothesis ([T4](research/T4-app-framework.md)) |
| Own loader v0 (`tools/loader/`) | built, **not yet flashed** | a diagnostic page under the World clock root: uptime timer, touch counters read through LVGL, a `LV_EVENT_DELETE` (33) handler that deletes our timer. 12/12 checks on the real LVGL code in the emulator (`tools/emu/test_loader_v0.py`); package `fit3-loader-v0.bin` passes `validate_fwd.py`. It tests the restart-after-wake and the touch hypotheses |
| Loader v0 on the watch | verified | touch as responsive as stock apps (LVGL indev instead of the panel driver, hypothesis from T1/T4 confirmed); back gesture works; after the screen sleeps the **stock World clock page reappears** (its window-event fn rebuilds it on LCD on) and it shows for a moment before our page on entry |
| Loader v1 (`tools/loader/loader_v1.c`) | built, **not yet flashed** | replaces the stock World clock window completely: `b.w` at the entry of the stock create (`0x2c1ecc64`) and window-event (`0x2c1ecd68`) functions, own screen via `lv_obj_create(NULL)`, back gesture like the flashlight page; 12/12 checks on the patched image in the emulator (`tools/emu/test_loader_v1.py`) |
| Loader v1 on the watch | verified | no flash of the stock page, our page survives sleep and wake. Back gesture worked but slid the wrong way: the 4th argument of `wm_open` is the transition, the stock World clock uses `0x14` for "back" (`0x2c1ecb82`), we passed 0. Fixed in v1b (`fit3-loader-v1b.bin`, not yet flashed) |
| Loader v2 (`tools/loader/loader_v2.c`) | built, **not yet flashed** | the tennis score tracker as a native LVGL window in the World clock slot: cards, Undo, Stats overlay with a two-step New, save of 132 bytes 3 s after a change (`/user/tenis.sav`, new format "TEN3", the old app's file is ignored), back gesture with the stock transition, list label "Tennis match score". 34/34 checks in the emulator (`tools/emu/test_loader_v2.py`); fonts are the firmware's Roboto Medium slots, **text sizes and layout are unchecked** (the emulator has no display) |
| Loader v2 on the watch | verified | the native tennis window works and looks right. Found on the watch: the side key did not go back and the back animation ran the wrong way, **both caused by `world_event` returning garbage** to the window manager's queries (key policy, `0,7`, `0,9`). Fixed in the rebuilt `fit3-loader-v2.bin` (not yet flashed): it answers 0.284 for the key policy and 0 for the swipe queries; see [T7](research/T7-side-key.md), [T8](research/T8-transitions.md). Title and hint text removed, list label "Tennis Score" |
| Icon (route B) | verified | `mkicon.py` draws a 64 x 64 tennis ball on a blue disc in the stock style; the app-list row of the entry points at an `lv_img_dsc_t` in the free flash. Shows in the list on the watch, the list works normally. (Emulator: the stock decoder rejects the non-string source and the built-in one opens it, `tools/emu/test_icon.py`.) Build with `--no-icon` to keep the stock globe |
| Side key | verified | stock behaviour (to the watch face): the window event answers `0x2c4` to the key-policy query |
| Back transition direction | reported correct | after the fix (the window event answers 0 to the queries 6, 7, 9, see T8) the back gesture was reported fine together with the other fixes; no separate measurement |
| The tennis tracker as a whole | verified | native LVGL window in the World clock slot, own label "Tennis Score" and icon, save and restore, back gesture, side key, wake from screen-off |
