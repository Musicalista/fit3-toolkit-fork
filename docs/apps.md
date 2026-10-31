# Writing apps

Apps are "light apps" for the loader of [Musicalista/fit3-store-apps-games](https://github.com/Musicalista/fit3-store-apps-games): freestanding C compiled for Cortex-M4
into a `.f3a` that the loader copies to RAM and calls. The file format and the API are described in that project's `docs/APP_FORMAT.md` and `apps/f3app.h`.
Essentials: a 256 x 402 RGB565 frame buffer you redraw every tick (about 33 ms), taps and drags as `pressed, x, y`, `rect/rrect/disc/text`, `fopen/fread/fwrite/fclose`,
`time()`, `battery()`, `malloc/free`, `vibrate()`. No libc, so no `printf`, `memcpy` or `malloc` from the C library; the compiler script refuses undefined symbols.

## Build and test

```
python3 -I tools/build_app.py tenis                 # -> build/tenis.f3a and build/tenis.meta  (needs arm-none-eabi-gcc and the SDK checkout)
sim/run.sh tenis                                    # run it in a window on the PC
python3 -I tools/device/f3_install.py install build/tenis.f3a
```

`apps/<name>/meta` is the launcher line `id;BGRRGGBB;FGRRGGBB;Name PT;Name EN[;32x32 1-bit icon as 256 hex digits]`. `apps/include/` is on the include path.
`apps/tenis/test_logic.c` is an example of testing the logic on the PC; run it and the simulator's random-tap mode (`host_game <prefix> "" <seed>` from the SDK) with
`-fsanitize=address,undefined` (Fedora: `dnf install libasan libubsan`).

## House style and lessons learned

- **Text is ASCII.** The built-in font is 8x12 Latin-1 and the Samsung fonts cover ASCII only. Polish diacritics are not available.
- **The watch language flag is `lang_pt` (Portuguese or not)**, so `TR(pt, en)` from the SDK picks English for every non-Portuguese watch. `tenis` forces one language instead.
- **Do not write files on every tap.** A 2 KB save after each tap restarted the watch on exit and on undo; saving 128 bytes 3 s after the last change did not. Keep saves small and rare.
- **Do not trust `tap`.** The loader derives it from LVGL's click event, which is lost as soon as LVGL starts a scroll. `tenis` and `styledemo` classify the gesture from `pressed, x, y` themselves.
- **`vibrate(5)` ("error") has not been tried on a real watch**; the others have.
- **Greys are multiples of 8 in RGB565** (5-6-5 bits), otherwise they look green. `apps/include/f3ui.h` uses that.
- The loader draws its own red close button at the top right (x >= 216, y < 28): keep that corner free.

## Look and feel

`apps/include/f3ui.h` has the palette (black, dark grey cards, blue accent) and widgets (card, pill, switch, chevron) and `apps/include/f3font.h` draws text with the watch's own
Roboto fonts, read from `/nand/system/font/` when the app starts. The colours are our estimates; photographs of the stock screens would let us match them. `apps/styledemo` shows both.
