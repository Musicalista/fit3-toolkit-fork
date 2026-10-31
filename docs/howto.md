# How to

**Read [legal.md](legal.md) first.** You need: a Galaxy Fit3 (SM-R390) on exactly `R390XXU0AZA3` (Settings > About > Software information), Linux with Bluetooth and Python 3
(numpy, Pillow), `arm-none-eabi-gcc`, a phone for flashing (Fit3 Manager, Android), and a watch charged to 50 % or more.

## The tennis score tracker (the current route)

1. Get the stock package `stock-aza3.bin` (SHA-256 `25e692badec82afe111c517c19c5dbdb1d28c8558c2b027143c43f5c8d05998a`), e.g. from the fit3-flasher project, and **keep a copy**.
2. Build: `python3 -I tools/build_tennis.py stock-aza3.bin out.bin` (options: `--label "Tennis Score"`, `--slot`, `--languages`, `--no-icon`, see below). It compiles the loader, draws the icon, patches your stock
   package and runs `validate_fwd.py` on the result. It refuses to build when the stock package is not exactly R390XXU0AZA3.
3. Check what changed: `python3 -I tools/firmware/fwx.py list out.bin`, and compare the main image with the stock one (the differences are the image CRC, two spp patches,
   two 4-byte branches at `0x2c1ecc64` and `0x2c1ecd68`, the loader and the icon in the free flash from `0x2c3a0524`, and the label in the English language files).
4. Flash `out.bin` with **Fit3 Manager** (phone, tab *Firmware*; the Bluetooth patches are part of the package). It cannot be cancelled;
   do not switch the watch off.
5. Open the app list: the entry that used to be *World clock* has your label and icon. Flash the stock package the same way to go back.

### Replace another entry than World clock

If you use World clock, choose any other entry of the app list: `python3 -I tools/build_tennis.py stock-aza3.bin --list-slots` shows them (Health, Media Controller, Find My Phone,
Weather, Calendar, Timer, Alarm, Stopwatch, World Clock, Camera Remote, Calculator; Settings is refused because it would lock you out of the watch's settings), then for example

```
python3 -I tools/build_tennis.py stock-aza3.bin out.bin --slot "Calculator"        # by name (a prefix is enough) or by window id: --slot 0x8c
python3 -I tools/build_tennis.py stock-aza3.bin out.bin --slot Weather --label "Tennis" --languages all
```

Things to know: only **World clock** has been tried on a real watch; the others are built and tested on the emulator (all eleven, `tools/emu/test_slots.py`). The entry you replace is gone:
Alarm, Timer and Stopwatch may keep timers or alarms running in the background, and Weather, Media Controller and Health get data from the phone. The entry must be **visible** in the app
list (World clock and Camera Remote are shown only when enabled in the phone app). `--languages all` renames the entry in every language file instead of the English ones, so a watch set to
another language shows your name too (untested outside English). `--label` longer than 11 characters wraps onto two lines in the list.

Tests (no watch needed; most need `local/firmware/stock-aza3.bin`): `python3 -I tools/firmware/test_build_package.py`, and the emulator tests of [tools/emu](../tools/emu/README.md).

## Older route: apps for the "light app" loader

The rest of this page is about the loader of Musicalista and its `.f3a` apps, which this project used to start with. The app SDK and simulator (`sdk/`, `apps/`, `sim/`) are in this repository and need nothing else.

## Get the pieces for flashing (none of them is in this repository)

- **Stock firmware** `stock-aza3.bin` (SHA-256 `25e692badec82afe111c517c19c5dbdb1d28c8558c2b027143c43f5c8d05998a`), e.g. from the fit3-flasher project. **Keep a copy.**
- **Patched packages** (`fit3-spp-only.bin`, `fit3-store-base-spp.bin`) and the Android `fit3-manager.apk` from the `1.7` release of `Musicalista/freemyfit3`, which ships a
  `SHA256SUMS.txt`. The author marks the packages as private builds; do not republish them. Put everything in `local/firmware/`.

## Check, then flash

1. `python3 -I tools/firmware/validate_fwd.py local/firmware/<package>.bin` must pass every line.
2. `python3 -I tools/firmware/make_flat_pkg.py local/firmware/fit3-store-base-spp.bin local/firmware/fit3-store-base-spp-flat.bin` (the loader needs a directory the watch does not have, see [firmware.md](firmware.md)); validate the result too.
3. Fit3 Manager (phone): connect, tab *Firmware*, choose the file, accept the warnings, send, then start the installation. It cannot be cancelled; do not switch the watch off.
   According to the loader's author the serial service is only reachable on the setup screen until the spp patch is installed, so the first package may need a factory reset;
   flash `fit3-spp-only.bin` first and the loader package second.
4. Go back to stock with `stock-aza3.bin` the same way. A watch that does not boot cannot be flashed over Bluetooth.

## Apps

```
python3 -I tools/build_app.py tenis
python3 -I tools/device/f3_install.py list                     # first test of the connection (read-only)
python3 -I tools/device/f3_install.py install build/tenis.f3a
```

Close Galaxy Wearable and Fit3 Manager on the phone first. Tell the tools your watch's Bluetooth address (the name is "Galaxy Fit3 (xxxx)"): `--addr AA:BB:CC:DD:EE:FF` or `export F3_ADDR=AA:BB:CC:DD:EE:FF`. On the watch the apps are under
Settings > Extra apps > My apps. Fit3 Manager's own app tab does **not** work with the flat package (it insists on `/user/apps/`); use `f3_install.py`.

## Simulator

```
python3 -I sim/genfont.py sim/kbd_font.h          # once: stand-in 8x12 font (not a copy of anything; see sim/README.md)
sim/run.sh tenis
sim/run.sh styledemo --data local/assets/fonts    # the simulated watch's files; fonts pulled with tools/device/f3_pull.py
```

## Pull fonts and images from your watch (read-only)

```
python3 -I tools/device/f3_pull.py local/assets/fonts /nand/system/font/FONT_ROBOTO_22_GBK_en.bin
```
