# tools/loader: our code in the free flash of the firmware

Freestanding C (no libc, no libgcc, no static data) linked at `0x2c3a0524`, the start of the zeros in the stock image (`0x2c3a0524..0x2c3af920`). `build_loader.py` compiles one
source into a flat binary; `tools/firmware/build_package.py` places it and patches the firmware to call it. All firmware addresses used are in `docs/symbols.csv`.
Each version is a small, working example of one step of the technique; `loader_v2.c` is the product.

| File | What it is |
|---|---|
| `loader_v0.c` | a diagnostic page drawn as a child of the stock World clock page, started by a timer hook. Showed that LVGL's own touch input is as fast as the stock apps, and that a `LV_EVENT_DELETE` (33) handler is how an object's timer should end. The stock page still showed for a moment and came back after the screen woke. |
| `loader_v1.c` | takes over the World clock **window**: `b.w` at the entry of the stock create (`0x2c1ecc64`) and window-event (`0x2c1ecd68`) functions, own screen. |
| `loader_v2.c` | the tennis score tracker as native LVGL objects, with the right answers to the window manager (key policy, swipe queries), a save file, the back gesture. |
| `loader.ld` | linker script: `.text.entry` first (`world_create` is the first function), `.text.entry.*` kept, no `.data`/`.bss`. |

## Rules of the window manager that cost us time (research T4, T7, T8)

- The window's event function `(class, kind, data)` is **asked questions**; its return value is used. `(0, 8)` is the key policy mask (bit 6 set: the short press of the side key goes to the
  watch face by itself); `(0, 6)`, `(0, 7)`, `(0, 9)` must return 0, or the manager runs its own swipe-back with its own transition. An event function that returns garbage looks like
  a working window with a wrong back animation and a dead side key.
- Arguments of that function arrive unmasked: use only the low byte.
- A screen is `lv_obj_create(NULL)` returned from the create function; the manager loads it, and deletes it (sending `LV_EVENT_DELETE` = 33) when the window is left. Free your timer and state there.
- Everything runs in the LVGL task: no `osDelay`, no `rm -rf` (`0x2c1437f0`), small and rare file writes (128 bytes 3 s after a change; 2 KB writes after every tap restarted the watch).
