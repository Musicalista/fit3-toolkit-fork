# How to

**Read [legal.md](legal.md) first.** You need: a Galaxy Fit3 (SM-R390) on exactly `R390XXU0AZA3` (Settings > About > Software information), Linux with Bluetooth and Python 3
(numpy, Pillow), `arm-none-eabi-gcc`, a Bluetooth adapter on the PC for flashing, and a watch charged to 50 % or more.

## The tennis score tracker (the current route)

1. Get the stock package `stock-aza3.bin` (SHA-256 `25e692badec82afe111c517c19c5dbdb1d28c8558c2b027143c43f5c8d05998a`), e.g. from the fit3-flasher project, and **keep a copy**.
2. Build: `python3 -I tools/build_tennis.py stock-aza3.bin out.bin` (options: `--label "Tennis Score"`, `--slot`, `--languages`, `--no-icon`, see below). It compiles the loader, draws the icon, patches your stock
   package and runs `validate_fwd.py` on the result. It refuses to build when the stock package is not exactly R390XXU0AZA3.
3. Check what changed: `python3 -I tools/firmware/fwx.py list out.bin`, and compare the main image with the stock one (the differences are the image CRC, two spp patches,
   two 4-byte branches at `0x2c1ecc64` and `0x2c1ecd68`, the loader and the icon in the free flash from `0x2c3a0524`, and the label in the English language files).
4. Flash `out.bin` from this PC with `tools/device/f3_flash.py`, see "Flash from the PC" below. The installation cannot be cancelled: do not switch the watch off.
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

## Flash from the PC: `tools/device/f3_flash.py`

No phone app needed. It talks to the watch over Bluetooth with the protocol of [protocol.md](protocol.md), in stages you start one by one:

```
export F3_ADDR=AA:BB:CC:DD:EE:FF                       # your watch's Bluetooth address
python3 -I tools/device/f3_flash.py out.bin                       # 1. plan: checks the package on the PC, touches nothing
python3 -I tools/device/f3_flash.py out.bin --upload --verify     # 2. copies it to the watch, checks the size and reads it all back; installs nothing
python3 -I tools/device/f3_flash.py out.bin --upload --verify --start-update    # 3. also starts the installation (you type FLASH)
```

- The package must pass `validate_fwd.py` or nothing is sent. Without `--start-update` nothing is installed: the file only waits on the watch, so an interrupted upload is harmless, run it again.
- **`--verify` is optional but recommended.** Without it the tool checks only that the file on the watch has the right *length*. With it, the whole file is read back and compared byte by byte:
  the only check that the *content* arrived intact. It is slow, because the watch hands the file back at about 18 kB/s: on a real watch the 18 MB upload took under 2 minutes and the read-back 17 minutes.
  Use it at least the first time and after changing anything in the tool.
- Requirements: the watch visible, charged to 50 % or more, Samsung's Galaxy Wearable app closed on the phone (one client at a time), and **it must already carry our Bluetooth patches** (any package built here has them).
  A watch that never had them is a different case: see "The very first flash" below.
- **Logs:** the tool prints the progress (bytes and percent) and writes a time-stamped log of the protocol events to `local/logs/f3_flash-<time>.log` (every command and answer, every 20th block, sizes, durations, the watch's
  reply to the OTA command; never the package's bytes). `--log PATH` picks the file, `--no-log` writes none.
- Status: tested against a mock watch (45 checks, including failures in the middle of a transfer); see [status.md](status.md) for what has been tried on a real watch.

## The Bluetooth patches, and closing the door when you are done

Every package built here carries two one-instruction **Bluetooth patches** (`build_package.py`, [firmware.md](firmware.md)). They are what lets this PC flash the watch, and they have a price: the watch is
**always visible and connectable, and its file service on RFCOMM channel 29 accepts a connection without pairing from anyone in range**. The protocol behind it can read files (we use it for fonts and images; which other
paths are readable we have not tested) and write `/user` files and a firmware package, and we saw no signature check on the firmware (only CRCs). So treat a watch with these patches as open to anyone near it.

When your work with the watch is finished, build the **final package without them** and flash it last:

```
python3 -I tools/build_tennis.py stock-aza3.bin final.bin --no-bluetooth-patches ...
python3 -I tools/device/f3_flash.py final.bin --upload --verify --start-update
```

The watch then behaves as it did from the factory (Bluetooth visible and connectable only where Samsung's firmware allows it), with your app in it. The price on the other side: **to flash it again you need the serial service, which stock firmware offers only on the setup screen after a reset** (that is a factory reset of the watch). Flashing the genuine `stock-aza3.bin` also removes the patches (and your app).
Keep a patched build for development and make the final one last. Samsung's own phone app is not affected by any of this.

## The very first flash: expect a factory reset

On a watch that has only ever run Samsung's firmware, **the serial service that every tool here talks to is reachable only on the watch's setup screen, the screen it shows after a factory reset**.
So the first time you put any package on such a watch, you have to **reset it to factory settings** (everything on it is erased and it must be paired with the phone again afterwards), connect while it shows the
setup screen, and flash that first package from there with `f3_flash.py` (we have not tried it on a setup screen). If that package carries the Bluetooth patches (the default), later flashes need no reset. If you build the final
package with `--no-bluetooth-patches`, the next flash needs a reset again (see above).

This comes from the notes of the author of the first patches (Musicalista); **we have not tried it ourselves**, because the watch we work with was patched before this project began.
If you reset a watch for this, please report what you saw.

## The pieces you bring (none of them is in this repository)

- **The stock firmware** `stock-aza3.bin` for R390XXU0AZA3 (SHA-256 `25e692badec82afe111c517c19c5dbdb1d28c8558c2b027143c43f5c8d05998a`), e.g. from the fit3-flasher project. **Keep a copy**: it is the way back.
- **A way to send the package**: our `tools/device/f3_flash.py` (above); on Linux it needs BlueZ and a Bluetooth adapter.

## Going back, and what can go wrong

Flash `stock-aza3.bin` the same way to go back to stock. A watch that does not boot cannot be flashed over Bluetooth, so never flash a package that did not pass `validate_fwd.py`
(`build_package.py` runs it for you) and never touch code that runs at boot: nothing of ours does. A mistake in our code shows only when the entry (or, for the icon, the app list) is opened;
the watch still boots and can be flashed again.

## Pull fonts and images from your watch (read-only)

For the emulator screenshots (`tools/emu/screenshot.py` needs the Roboto fonts) and for studying the resources:

```
export F3_ADDR=AA:BB:CC:DD:EE:FF                    # your watch's Bluetooth address (its name is "Galaxy Fit3 (xxxx)")
python3 -I tools/device/f3_pull.py local/assets/fonts /nand/system/font/FONT_ROBOTO_22_GBK_en.bin
```

Close Samsung's Galaxy Wearable app on the phone first (one client at a time); the watch must be visible and carry the Bluetooth patches of `build_package.py`. Only files under `/nand/system/font/`
and `/nand/system/image/` are accepted, nothing is written to the watch, and the files are Samsung's: keep them in `local/` and do not redistribute them.
