# src/loader: our code in the free flash of the firmware

Freestanding C (no libc, no libgcc, no static data) linked at `0x2c3a0524`, the start of the zeros in the stock image (`0x2c3a0524..0x2c3af920`). `build_loader.py` compiles one
source into a flat binary; `src/firmware/build_package.py` places it and patches the firmware to call it. All firmware addresses used are in `docs/symbols.csv`.
`loader_v2.c` is the product.

| File | What it is |
|---|---|
| `loader_v2.c` | the tennis score tracker as native LVGL objects, with the right answers to the window manager (key policy, swipe queries), a save file, the back gesture. |
| `loader.ld` | linker script: `.text.entry` first (`world_create` is the first function), `.text.entry.*` kept, no `.data`/`.bss`. |

## Rules of the window manager that cost us time (more in [docs/details.md](../../docs/details.md))

- The window's event function `(class, kind, data)` is **asked questions**; its return value is used. `(0, 8)` is the key policy mask (bit 6 set: the short press of the side key goes to the
  watch face by itself); `(0, 6)`, `(0, 7)`, `(0, 9)` must return 0, or the manager runs its own swipe-back with its own transition. An event function that returns garbage looks like
  a working window with a wrong back animation and a dead side key.
- Arguments of that function arrive unmasked: use only the low byte.
- A screen is `lv_obj_create(NULL)` returned from the create function; the manager loads it, and deletes it (sending `LV_EVENT_DELETE` = 33) when the window is left. Free your timer and state there.
- Everything runs in the LVGL task: no `osDelay`, no `rm -rf` (`0x2c1437f0`), small and rare file writes (128 bytes 3 s after a change; 2 KB writes after every tap restarted the watch).

## Which window is replaced (`WINDOW_ID`)

`loader_v2.c` is the same code for every slot: `build_tennis.py --slot <entry>` compiles it with `-DWINDOW_ID=<window id>` (it enters its own id with `wm_set_current`), and
`build_package.py` puts the branches at the entry of that entry's stock create and event functions. The other functions of the window record (post-enter `+0x20`, `+0x28`, destroy
`+0x2c`) become `bx lr`: they would run on stock state that never exists, except World clock's destroy, which is null-safe and was verified as it ships. The 11 replaceable
windows have no direct callers of these functions (checked with the Ghidra call graph of R390XXU0AZA3); `src/emu/test_slots.py` builds and tests them all.
