# src/watch: our code in the free flash of the firmware

Freestanding C (no libc, no libgcc, no static data) linked at `0x2c3a0524`, the start of the zeros in the stock image (`0x2c3a0524..0x2c3af920`, 62,460 bytes). One translation unit: `hub.c`
includes the apps chosen at build time. `build_loader.py` compiles it into a flat binary; `src/firmware/build_package.py` places it and patches the firmware to call it.
All firmware addresses used are in `docs/symbols.csv`.

| File | What it is |
|---|---|
| `hub.c` | the window that replaces one entry of the app list: **single-app mode** (one app owns the window) or the **Application Hub** (a native-style list; a tap opens an app, the back gesture closes it). The window manager's answers (key policy, swipe queries) and the back gesture live here, once, for every app. |
| `ui.h` | what the code shares: the firmware functions we call, colours, fonts, text helpers, small file helpers (`blob_save`/`blob_load`), widgets (`mk_box`, `mk_text`, `mk_pill`), and the `App` interface. |
| [`apps/`](apps/README.md) | the demo apps (Tennis Score, Counter, Dice, Mars Production) and the guide to writing your own. `counter.c` is the smallest complete one. |
| `gen.py` | writes the two generated headers into a build directory (never into the repository): `icons.h` (the 64 x 64 four-bit icons, drawn by `src/assets/mkicon.py`) and `gen_apps.h` (`HUB_MODE`, which apps, in which order). |
| `build_loader.py` | compiles `hub.c` (arm-none-eabi-gcc, `-Os`, freestanding), refuses libc/libgcc calls and any `.data`/`.bss`. |
| `loader.ld` | linker script: `.text.entry` first (`world_create` is the first function), `.text.entry.*` kept, no `.data`/`.bss`. |
| `test_score.c` | the scoring rules of `apps/tennis.c` on the PC (with sanitizers). |

## How an app opens

By default (`--hub`) every app is a window of its own, id `0x10`: the hub asks the window manager for `wm_open(2, 0x10, arg, 0xf)` and the manager slides the app in like a stock one (details: docs/details.md,
section 2). `--no-native-transitions` builds the fallback: the app is a container inside the hub's window, without the slide. In both modes the back gesture goes to the app first (an overlay may close), then
the app closes. A long press on the row of an **installed** app opens a sheet that removes it (Remove asks twice; the slot is overwritten with the 8-byte tombstone `F3X-GONE`).

## Build modes

```
python3 -I src/build_firmware.py <stock.bin> <out.bin> --app tennis                 # one app owns the window (default)
python3 -I src/build_firmware.py <stock.bin> <out.bin> --hub tennis,counter,dice    # the Application Hub; the list follows the order given
```

The build prints how much of the free flash it used (the numbers are printed, not promised here: they change with every app). Each app adds its code plus its 64 x 64 four-bit icon, 2,112 bytes.

## Writing an app

See [apps/README.md](apps/README.md): the `App` interface, the rules (no globals, no libc, rare small writes) and the commands.

## Rules of the window manager (more in [docs/details.md](../../docs/details.md))

- The window's event function `(class, kind, data)` is **asked questions**; its return value is used. `(0, 8)` is the key policy mask (bit 6 set: the short press of the side key goes to the
  watch face by itself); `(0, 6)`, `(0, 7)`, `(0, 9)` must return 0, or the manager runs its own swipe-back with its own transition. An event function that returns garbage looks like
  a working window with a wrong back animation and a dead side key.
- Arguments of that function arrive unmasked: use only the low byte.
- A screen is `lv_obj_create(NULL)` returned from the create function; the manager loads it, and deletes it (sending `LV_EVENT_DELETE` = 33) when the window is left. Free your timer and state there.
- Everything runs in the LVGL task: no `osDelay`, no `rm -rf` (`0x2c1437f0`), small and rare file writes (128 bytes 3 s after a change; 2 KB writes after every tap restarted the watch).

## Which window is replaced (`WINDOW_ID`)

`hub.c` is the same code for every slot: `build_firmware.py --slot <entry>` compiles it with `-DWINDOW_ID=<window id>` (it enters its own id with `wm_set_current`), and
`build_package.py` puts the branches at the entry of that entry's stock create and event functions. The other functions of the window record (post-enter `+0x20`, `+0x28`, destroy
`+0x2c`) become `bx lr`: they would run on stock state that never exists, except World clock's destroy, which is null-safe and was verified as it ships. The 11 replaceable
windows have no direct callers of these functions (checked with the Ghidra call graph of R390XXU0AZA3); `src/emu/test_slots.py` builds and tests them all.
