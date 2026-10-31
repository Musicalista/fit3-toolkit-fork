# How to

**Read [legal.md](legal.md) first.** You need: a Galaxy Fit3 (SM-R390) on exactly `R390XXU0AZA3` (Settings > About > Software information), Linux with Bluetooth and Python 3,
`arm-none-eabi-gcc` for apps, a phone for flashing (Fit3 Manager, Android), and a watch charged to 50 % or more.

## Get the pieces (none of them is in this repository)

- **SDK and loader sources:** `git clone https://github.com/Musicalista/fit3-store-apps-games fit3-store` in the repository root.
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

Close Galaxy Wearable and Fit3 Manager on the phone first. The watch's address is set in `tools/device/f3_install.py` (`ADDR`) or with `--addr`. On the watch the apps are under
Settings > Extra apps > My apps. Fit3 Manager's own app tab does **not** work with the flat package (it insists on `/user/apps/`); use `f3_install.py`.

## Simulator

```
python3 -I sim/genfont.py sim/kbd_font.h          # once: stand-in 8x12 font (the SDK's kbd_font.h is not published)
sim/run.sh tenis
sim/run.sh styledemo --data local/assets/fonts    # the simulated watch's files; fonts pulled with tools/device/f3_pull.py
```

## Pull fonts and images from your watch (read-only)

```
python3 -I tools/device/f3_pull.py local/assets/fonts /nand/system/font/FONT_ROBOTO_22_GBK_en.bin
```
