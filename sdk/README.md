# sdk/: build light apps for the Fit3

The SDK is three small files plus the compiler script `tools/appcc.py` (use it through `tools/build_app.py`). Everything here was written for this repository; the **binary format** is
the one defined by [Musicalista's loader](https://github.com/Musicalista/fit3-store-apps-games). We took only the interface from its published headers and format description (names, signatures, the
layout of structures and of the file) so that apps built here run on that loader (and on ours) and the other way round; no code, comments or text were copied. If this page and `f3app.h` ever disagree with a loader, the loader wins; please report it.

| File | What |
|---|---|
| `f3app.h` | the API table `F3Api`, the app object `F3App`, the entry point `f3app_main`, `F3Time`, `RGB()` |
| `f3game.h` | optional header-only helpers (touch gestures, number formatting, saved integers, colours); `static`, so unused ones cost nothing |
| `app.ld` | linker script: one flat image at address 0 |

## How an app runs

The loader copies the image into RAM (image + bss, `bss size` extra zeroed bytes), adds the load address to every word listed in the relocation table, and calls
`f3app_main(api)`. The function returns a pointer to an `F3App` (or 0 to refuse). Then, about every 33 ms, the loader calls `app->tick(app, pressed, x, y, tap)`; the app draws a whole
frame into `api->fb` and returns non-zero to keep running. Returning 0 quits; the loader then calls `app->close(app)` if it is not NULL. The loader draws its own close button at the
top right (x >= 216, y < 28): keep that corner free. `tap` is 1 for the one frame in which a tap was released; it is derived from the UI toolkit's click event and is lost when the toolkit
starts a scroll, so apps that care classify gestures from `pressed, x, y` themselves (`touch_update` in `f3game.h` does).

Rules for the code: freestanding C, no libc and no libgcc helpers (no `memcpy`, `memset`, `printf`, 64-bit division, ...; `appcc.py` rejects undefined symbols). Globals are fine: initialised
ones are in the image, zero ones in bss. Do not block in `tick`. Calls through F3Api use the hard-float ARM calling convention of `arm-none-eabi-gcc -mfloat-abi=hard` (integers only in practice).
Image limit: 40000 bytes (the compiler script refuses more). Strings are Latin-1 bytes (`-fexec-charset=ISO-8859-1`); the built-in font has ASCII only in practice.

## The `.f3a` file (little endian)

| Offset | Size | Field | Value |
|---|---|---|---|
| 0 | 4 | magic | `"F3A1"` |
| 4 | 2 | api version | 1 |
| 6 | 2 | flags | 0 |
| 8 | 4 | image size | bytes of the image that follows the header |
| 12 | 4 | bss size | zeroed bytes the loader appends after the image |
| 16 | 4 | entry offset | offset of `f3app_main` inside the image, Thumb bit cleared (the loader sets it) |
| 20 | 4 | CRC32 | zlib/IEEE CRC-32 of the image (not of the header or the relocations) |
| 24 | 4 | relocation count | number of u32 entries after the image |
| 28 | 4 | reserved | 0 |
| 32 | 16 | name, Portuguese | Latin-1, at most 15 bytes, NUL padded |
| 48 | 16 | name, English | same |
| 64 | image size | image | `.text`, `.rodata` and `.data` linked at address 0, in that order |
| 64 + image size | 4 x count | relocations | each a u32 offset into the image of a 4-aligned word that holds an absolute address; the loader adds the load address to it. Ascending order. |

Total file size = 64 + image size + 4 x relocation count. The image is padded with zeros up to `__image_end`, so section alignment gaps are zero bytes. The bss is not stored.
The loader's launcher list `/user/apps/index.txt` has one line per app, `id;BGRRGGBB;FGRRGGBB;Name PT;Name EN[;ICON]` (colours are written RRGGBB; ICON = 32x32 one-bit picture, 256 hex
digits, 4 bytes per row, most significant bit on the left). Ids are 1 to 11 characters from `a-z 0-9 _ -`. `apps/<app>/meta` holds this line, `tools/build_app.py` copies it to `build/<id>.meta`.

How `appcc.py` makes the image: compile with `-mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb -Os -ffreestanding -fno-builtin -fno-pic -mword-relocations
-ffunction-sections -fdata-sections` (plus `-fno-tree-loop-distribute-patterns`, which stops gcc from turning loops into `memset` calls), link with `ld -q --gc-sections -T app.ld`
(`-q` keeps the relocation records), then read the ELF: relocations of type `R_ARM_ABS32` (2) and `R_ARM_TARGET1` (38) in `.text` and `.data` become the table; the PC-relative Thumb types
(`THM_CALL`, `THM_JUMP24/19/11/8`, `THM_PC8/12`, `REL32`, `V4BX`) need nothing; anything else is an error. `-mword-relocations` is what makes every address literal a patchable word.

## `F3Api` (what the loader hands to `f3app_main`)

Pointers are 32 bits on the watch. Offsets in bytes from the start of the table; the table is 108 bytes. A function pointer is called as an ordinary C function.

| Offset | Member | Type | Meaning |
|---|---|---|---|
| 0 | `version` | u32 | 1 |
| 4 | `fb` | u16 * | canvas, RGB565, 256 x 402, row stride = `w` |
| 8 | `w` | int | 256 |
| 12 | `h` | int | 402 |
| 16 | `malloc` | `void *(*)(u32 n)` | heap; 0 on failure |
| 20 | `free` | `void (*)(void *p)` | |
| 24 | `ticks` | `u32 (*)(void)` | milliseconds |
| 28 | `vibrate` | `void (*)(int id)` | 1 short, 4 long, 5 error (5 untested on hardware) |
| 32 | `rect` | `void (*)(u16 *fb, int x, int y, int w, int h, u16 color)` | filled rectangle, clipped |
| 36 | `rrect` | `void (*)(u16 *fb, int x, int y, int w, int h, int radius, u16 color)` | rounded rectangle |
| 40 | `disc` | `void (*)(u16 *fb, int cx, int cy, int r, u16 color)` | filled circle |
| 44 | `text` | `void (*)(u16 *fb, int x, int y, const char *s, int scale, u16 color)` | 8x12 font times `scale`, (x, y) top left |
| 48 | `ctext` | same signature, `cx` instead of `x` | horizontally centred on `cx` |
| 52 | `num` | `void (*)(u16 *fb, int x, int y, int value, int scale, u16 color)` | signed decimal |
| 56 | `fopen` | `int (*)(const char *path, const char *mode)` | mode `"r"` or `"w"`; descriptor, negative on error; stay under `/user/` |
| 60 | `fread` | `int (*)(int fd, void *buf, u32 n)` | bytes read |
| 64 | `fwrite` | `int (*)(int fd, const void *buf, u32 n)` | bytes written |
| 68 | `fclose` | `int (*)(int fd)` | |
| 72 | `lang_pt` | u32 | non-zero when the watch language is Portuguese |
| 76 | `time` | `void (*)(F3Time *t)` | **may be NULL** (loaders before v1.7) |
| 80 | `battery` | `int (*)(void)` | percent; **may be NULL** |
| 84 | `reserved[6]` | u32 x 6 | zero; new members are only ever added here |

`F3Time` (28 bytes, seven `int`s): `year` 0, `month` 4 (1-12), `day` 8, `hour` 12, `min` 16, `sec` 20, `wday` 24 (as the firmware reports it).

`F3App` (8 bytes): `tick` at 0, `int (*)(F3App *self, int pressed, int x, int y, int tap)`; `close` at 4, `void (*)(F3App *self)`, optional. An app usually embeds `F3App` as the first member of
its state struct, so the pointer returned from `f3app_main` is also the state.

## `f3game.h`

Needs the app to set the global `A` (the `F3Api *`) in `f3app_main`. Provides: `FB`, `TR(pt, en)`; colours `C_BG`, `C_TEXT`, `C_MUTED`; `iabs`, `clampi`, `in_rect`, `rng_next`; `clear`, `fill8`
(memset), `itoa_pad`; `Touch`, `touch_update` (tap or four swipe directions, decided on release; `T_NONE`, `T_TAP`, `T_LEFT`, `T_RIGHT`, `T_UP`, `T_DOWN`); `saved_int_load`, `saved_int_store`.
Apps may define their own helpers instead (`apps/touchlab` and `apps/styledemo` do).

## Build and test

```
python3 -I tools/build_app.py tenis        # -> build/tenis.f3a, build/tenis.meta   (needs arm-none-eabi-gcc and arm-none-eabi-ld)
python3 -I tools/appcc.py my.c --id my --pt "Meu" --en "My" -I some/include -o build/my.f3a
sim/run.sh tenis                           # PC simulator, see sim/README.md
```

Compatibility check done when this SDK was written: the apps in `apps/` compiled with this `appcc.py` against the loader author's own headers give files byte-identical to the loader
author's compiler script (header, image, relocations); see `docs/apps.md`.
