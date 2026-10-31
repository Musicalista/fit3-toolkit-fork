# Roadmap: a native-feeling entry for our apps

**Goal:** our tennis app opens from the stock app list, in the slot of an app nobody uses (World clock), and looks like a stock app. Nothing below is built yet unless the
[status](status.md) says so.

## Decisions so far

- The stock **World clock** list entry is the slot to take over, not Settings > Extra apps.
- Keep a loader, so apps stay installable in seconds over Bluetooth. Compiling an app into the firmware would mean an 18 MB over-the-air update for every change.
- The loader should become **ours** (a small clean-room one): no menu in front of the app, a fix for the page scrolling under the finger, and no dependency on binaries we may not publish.
- Look and feel: until now we drew into the frame buffer with the watch's own Roboto fonts and a palette sampled from the stock UI (`apps/include/`). The Ghidra research ([research/](research/),
  [symbols.csv](symbols.csv)) now gives the LVGL addresses and the stock page recipes, so phase 2 can build native LVGL objects; this is still untested on a watch.

## Phases

| # | What | Why first | Risk |
|---|---|---|---|
| 1 (try 1: label ok, hook not reached; try 1b built) | Replace the `bl` that builds the World clock page (`0x2c1ecd30`) by a stub that runs it and then schedules the existing loader's menu with an 80 ms timer; rename the label | cheapest way to prove, on the real watch, that the list entry reaches that code and that a loader page opened on its fresh root behaves (scroll, close) | one flash with our package |
| 2 | Our own loader in the free flash (`0x2c3a4525..0x2c3af920`, 46 KB): load `.f3a`, API, canvas, timer, touch; start the app directly; create `/user/apps` with the firmware's `mkdir_p` (to be located) | removes the menu, fixes scrolling, ends the `/user/a_*` workaround | the hook only runs when the entry is opened |
| 3 | `tools/firmware/build_package.py`: stock package + spp patches + our loader + hooks + strings, all checksums repaired | publishable as code and a recipe: you bring the stock firmware | as phase 2 |
| 4 | Icon and label: find the icon of the World clock row in the image packs (`app_applist.res`?), replace that record in a copy pulled from *your* watch, ship it as an OTA component | looks native in the list | package carries a changed `/nand/system/image` file |
| 5 | Optional: our own API version (touch events that are not lost on scroll, fonts and images from the firmware, vibration patterns) | | |

Why a faulty hook is not a brick: nothing of ours runs at boot. A broken stub restarts the watch when someone opens World clock; the watch still boots, so a package can be flashed
over Bluetooth again. A package that does not pass `tools/firmware/validate_fwd.py`, or that touches code that runs at boot, is what can brick a watch.

## Dependencies on third-party code

| Used today | For | Replaced by | When |
|---|---|---|---|
| SDK `apps/appcc.py`, `app.ld` | compile and link `.f3a` | our own script and linker file (the format is documented) | phase 2 |
| SDK `apps/f3app.h`, `f3game.h` | the API the loader provides, helpers | our own header with the same layout (an interface) | phase 2 |
| SDK `apps/host_game.c` | the simulator's fake API | our own harness (about 100 lines) | phase 2 |
| Musicalista's patched packages | loader and spp patch | `build_package.py` | phase 3 |
| fit3-flasher / Fit3 Manager | send a package | stays (we do not reimplement the flashing UI) | |

After phase 3 the `fit3-store/` checkout is no longer needed.
