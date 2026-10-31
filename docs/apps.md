# Writing apps

Apps are "light apps" for the loader of [Musicalista/fit3-store-apps-games](https://github.com/Musicalista/fit3-store-apps-games): freestanding C compiled for Cortex-M4
into a `.f3a` that the loader copies to RAM and calls. The file format and the API (our own headers, compatible with that loader) are described in [`sdk/README.md`](../sdk/README.md); `sdk/f3app.h` is the header.
Essentials: a 256 x 402 RGB565 frame buffer you redraw every tick (about 33 ms), taps and drags as `pressed, x, y`, `rect/rrect/disc/text`, `fopen/fread/fwrite/fclose`,
`time()`, `battery()`, `malloc/free`, `vibrate()`. No libc, so no `printf`, `memcpy` or `malloc` from the C library; the compiler script refuses undefined symbols.

## Build and test

```
python3 -I tools/build_app.py tenis                 # -> build/tenis.f3a and build/tenis.meta  (needs arm-none-eabi-gcc and ld; the SDK is `sdk/`, nothing else)
sim/run.sh tenis                                    # run it in a window on the PC
python3 -I tools/device/f3_install.py install build/tenis.f3a
```

`apps/<name>/meta` is the launcher line `id;BGRRGGBB;FGRRGGBB;Name PT;Name EN[;32x32 1-bit icon as 256 hex digits]`. `apps/include/` is on the include path.
`apps/tenis/test_logic.c` is an example of testing the logic on the PC; run it (`gcc -O1 -I sdk -I apps/include -finput-charset=UTF-8 -fexec-charset=ISO-8859-1 -o /tmp/tenis_logic apps/tenis/test_logic.c && /tmp/tenis_logic`) and the simulator's random-tap mode
(`python3 -I sim/sim_gui.py build/libsim_tenis.so --monkey <seed>`, exit status 1 if the app quits or misuses the API) with
`-fsanitize=address,undefined` (Fedora: `dnf install libasan libubsan`).

## House style and lessons learned

- **Text is ASCII.** The built-in font is 8x12 Latin-1 and the Samsung fonts cover ASCII only. Polish diacritics are not available.
- **The watch language flag is `lang_pt` (Portuguese or not)**, so `TR(pt, en)` from `sdk/f3game.h` picks English for every non-Portuguese watch. `tenis` forces one language instead.
- **Do not write files on every tap.** A 2 KB save after each tap restarted the watch on exit and on undo; saving 128 bytes 3 s after the last change did not. Keep saves small and rare.
- **Do not trust `tap`.** The loader derives it from LVGL's click event, which is lost as soon as LVGL starts a scroll. `tenis` and `styledemo` classify the gesture from `pressed, x, y` themselves.
- **`vibrate(5)` ("error") has not been tried on a real watch**; the others have.
- **Greys are multiples of 8 in RGB565** (5-6-5 bits), otherwise they look green. `apps/include/f3ui.h` uses that.
- The loader draws its own red close button at the top right (x >= 216, y < 28): keep that corner free.

## Look and feel

`apps/include/f3ui.h` has the palette (black, dark grey cards, blue accent) and widgets (card, pill, switch, chevron) and `apps/include/f3font.h` draws text with the watch's own
Roboto fonts, read from `/nand/system/font/` when the app starts. The colours are our estimates; photographs of the stock screens would let us match them. `apps/styledemo` shows both.

## SDK compatibility check

`sdk/`, `tools/appcc.py` and `sim/host_api.c` replace the loader author's SDK files, which this repository no longer needs. To check the binary compatibility the apps in `apps/` were built twice
from the same sources, outside the repository: (1) with the loader author's own `appcc.py`, `f3app.h`, `f3game.h` and `app.ld`; (2) with our `appcc.py` pointed at those same headers and linker script.
For `tenis`, `styledemo` and `touchlab` the two `.f3a` files are **byte-identical** (header, names, CRC, image, relocation table), so our compiler script produces exactly the same format.
With our own headers (the normal build) `styledemo` and `touchlab` are still identical; `tenis` differs only in the code of the helpers that we wrote differently (`itoa_pad`, `touch_update`):
image 3906 B instead of 3882 B, 79 relocations, header otherwise the same layout. An app from the other SDK that uses its helpers `hs_load`, `title`, `press_update` and so on needs those
helpers copied into the app, since `sdk/f3game.h` only has the ones our apps use; `hello.c` from that SDK (it uses only `f3app.h`) builds with our `appcc.py`.
Not tested on a watch: the new build has not been installed; run `tools/build_app.py tenis` and compare with the previous `build/tenis.f3a` if you want to be sure.
