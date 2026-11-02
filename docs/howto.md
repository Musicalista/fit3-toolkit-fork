# How to

**Read [legal.md](legal.md) first.** You need a Galaxy Fit3 (SM-R390) on exactly `R390XXU0AZA3` (see [Check your firmware version](#check-your-firmware-version)), charged to 50 % or more; Linux with a Bluetooth adapter, Python 3
(numpy, Pillow) and `arm-none-eabi-gcc`; and **the stock package** `stock-aza3.bin` (SHA-256 `25e692badec82afe111c517c19c5dbdb1d28c8558c2b027143c43f5c8d05998a`, e.g. from the fit3-flasher project).
Keep a copy of it: flashing it is the way back.

## Check your firmware version

The build and the flasher work only with **exactly `R390XXU0AZA3`**. The version of a different build has other addresses, so our code would land in the wrong place; the build refuses it, and you should not try to get around that. Check before you do anything:

- **On the band:** Settings > About band > Software information. The line to look for is `R390XXU0AZA3`.
- **In the Galaxy Wearable app (phone):** Band settings > About band > Software information (the band must be connected).

If the version differs, do not flash: other versions are not supported (see [status.md](status.md)).

## 1. Build a package

```
python3 -I src/build_firmware.py stock-aza3.bin out.bin --hub none                          # Application Hub, no apps built in (install them later as .f3x)
python3 -I src/build_firmware.py stock-aza3.bin out.bin --hub tennis,counter,dice,mars      # the hub with these apps built in (order = list order)
python3 -I src/build_firmware.py stock-aza3.bin out.bin --app tennis                        # one app owns the entry, no hub (the default build)
```

Options: `--label "..."` (the name in the app list; more than 11 characters wraps onto two lines), `--slot` (see below), `--languages all` (rename the entry in every language file; untested outside English),
`--no-icon`, `--no-install` (a hub without the loader of `.f3x` apps), `--no-native-transitions` (apps open inside the hub's window, without the slide: the fallback), `--no-bluetooth-patches` (see section 4).
The build compiles the watch code, draws the icons, patches your stock package, repairs every checksum, runs `validate_fwd.py` on the result and prints how much of the free flash it used. It refuses a stock
package that is not exactly R390XXU0AZA3. To see what changed: `python3 -I src/firmware/fwx.py list out.bin`.

**Which entry is replaced:** World Clock unless you pass `--slot`. `--list-slots` shows the choices (Health, Media Controller, Find My Phone, Weather, Calendar, Timer, Alarm, Stopwatch, World Clock, Camera Remote,
Calculator; Settings is refused because it would lock you out of the watch's settings), e.g. `--slot Calculator` or `--slot 0x8c`. Only World Clock was tried on a real watch; the others are built and tested in
the emulator. The entry you replace is gone (Alarm, Timer and Stopwatch may keep timers running; Weather, Media Controller and Health get data from the phone), and it must be visible in the app list (World Clock
and Camera Remote are shown only when enabled in the phone app).

### The reply keyboard (optional)

```
python3 -I src/build_firmware.py stock-aza3.bin out.bin --hub none --reply-keyboard --kb-lang pl,en
```

`--reply-keyboard` adds a *Write reply* row to the page of quick replies of a notification (the page the reply icon opens); it opens a QWERTY or T9 keyboard and sends the text to the phone as the reply.
`--kb-lang` lists the layouts to build in (`en` is the default; `pl pt es fr de it nl cs sk hu hr sl ro sv nb is tr lt lv et ca ga sq`, or `all`). With more than one, the watch's system language
chooses (the first of the list is the fallback), and the language button in the keyboard's header switches it. It needs a Roboto TTF for the font: found with `fc-match`, or pass `--kb-font file.ttf`.
It costs 10 to 25 kB of the free flash depending on the languages, and works with `--app` and `--hub`. To remove it, build and flash again without the option. Details, limits and what was tried on a
watch: [replies.md](replies.md).

## 2. Flash it from the PC: `src/device/f3_flash.py`

No phone app needed. The protocol is in [protocol.md](protocol.md); each stage is a separate command:

```
export F3_ADDR=AA:BB:CC:DD:EE:FF                                              # your watch's Bluetooth address (its name is "Galaxy Fit3 (xxxx)")
python3 -I src/device/f3_flash.py out.bin                                     # plan: checks the package on the PC, touches nothing
python3 -I src/device/f3_flash.py out.bin --upload --verify                   # copies it to the watch, checks the size, reads it all back; installs nothing
python3 -I src/device/f3_flash.py out.bin --upload --verify --start-update    # also starts the installation (you type FLASH); it cannot be cancelled
```

- The package must pass `validate_fwd.py` or nothing is sent. Without `--start-update` nothing is installed, so an interrupted upload is harmless: run it again.
- `--verify` reads the whole file back and compares it: the only check that the *content* arrived intact (without it only the length is checked). It takes about 17 minutes against 2 for the upload.
- The watch must be visible, Samsung's Galaxy Wearable app closed on the phone (one client at a time), and it must already carry our Bluetooth patches (any package built here has them by default). Do not touch the
  watch during the installation.
- A time-stamped log of the protocol events (never the package's bytes) goes to `local/logs/f3_flash-<time>.log`; `--log PATH` and `--no-log` change that.

## 3. Install apps without flashing (the hub)

Open the hub once after flashing (it creates `/user/hub`), then:

```
python3 -I src/f3x/build_f3x.py src/watch/apps/dice.c dice.f3x --icon-kind dice      # build an app as a file (or your own .c file)
python3 -I src/device/f3x_install.py list                                            # the sixteen slots, read only
python3 -I src/device/f3x_install.py install dice.f3x                                # first free slot; the same name updates in place
python3 -I src/device/f3x_install.py remove --slot 3                                 # or: long press the app's row in the hub
```

The format, how to write an app and the limits: [f3x.md](f3x.md).

## 4. The Bluetooth patches, and closing the door when you are done

Every package built here carries two one-instruction **Bluetooth patches** ([firmware.md](firmware.md)). They let this PC flash the watch, and they have a price: the watch is **always visible and
connectable, and its file service accepts a connection without pairing from anyone in range**. It can read files and write `/user` files and a firmware package, and we saw no signature check on the firmware
(only CRCs). Treat a watch with these patches as open to anyone near it.

When you are finished, build the **final package without them** and flash it last: `python3 -I src/build_firmware.py stock-aza3.bin final.bin --hub none --no-bluetooth-patches`. The watch then behaves as from the
factory. The price: **to flash it again you need the serial service, which stock firmware offers only on the setup screen after a factory reset**, and nothing more can be installed from the PC. Apps already
installed keep working. Flashing the genuine `stock-aza3.bin` also removes the patches (and our code). A package without the patches was built and validated but **has not been flashed**.

## 5. The very first flash: expect a factory reset

On a watch that has only ever run Samsung's firmware, the serial service every tool here talks to is reachable only on the **setup screen shown after a factory reset**. So the first package must be flashed from
there (everything on the watch is erased; pair it with the phone again afterwards). Later flashes need no reset as long as the package carries the Bluetooth patches. This comes from the notes of the author of
the first patches (Musicalista); **we have not tried it ourselves**, because our watch was patched before this project began. If you do, please report what you saw.

## 6. Going back, and what can go wrong

Flash `stock-aza3.bin` the same way. A watch that does not boot cannot be flashed over Bluetooth, so never flash a package that did not pass `validate_fwd.py` (the build runs it) and never touch code that runs
at boot: nothing of ours does. A mistake in our code shows only when the entry is opened; the watch still boots and can be flashed again.

## Pull fonts and images from your watch (read-only, optional)

For the emulator screenshots (`src/emu/screenshot.py` needs the Roboto fonts) and for studying the resources:
`python3 -I src/device/f3_pull.py local/assets/fonts /nand/system/font/FONT_ROBOTO_22_GBK_en.bin`. Only files under `/nand/system/font/` and `/nand/system/image/` are accepted, nothing is written to the watch,
and the files are Samsung's: keep them in `local/` and do not redistribute them.

## Tests

No watch needed. `src/firmware/test_build_package.py`, `src/device/test_f3_flash.py`, `src/device/test_f3x_install.py`, `src/f3x/test_f3x_format.py` and the emulator tests of [src/emu](../src/emu/README.md)
(they need `local/firmware/stock-aza3.bin`; the emulator needs its venv).
