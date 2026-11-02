# Status

Tested on **one** Galaxy Fit3 (SM-R390) on firmware **R390XXU0AZA3**. Legend: **watch** = seen working on a real watch (2026-11-01 unless noted); **emulator** = the real firmware code run on the PC
(`src/emu`); **PC** = tools tested without a watch; **open** = not tried.

## Reply keyboard

Writing your own reply to a notification ([replies.md](replies.md)): **works on a watch (2026-11-02)**: the *Write reply* row is the first on every opening of the reply page, the keyboard opens (QWERTY and T9, layouts per language, language button) and replies sent on SMS and Signal reached the phone. Built and tested in the emulator (82 checks) and on the PC. Not yet confirmed: Polish letters arriving intact on the phone, the system language choosing the layout.

## Hub, apps, installable apps

| What | State |
|---|---|
| Application Hub in the World Clock entry: list with rows the size of the stock list, 64 x 64 icons, scrolling with eight apps | watch |
| An app opens as a window of its own (id `0x10`) with the stock slide in, the stock slide back; a quick double tap opens one app; the side key goes to the watch face; the double press of the side key opens the hub | watch |
| Tennis Score (games, sets, tie-break, serve, 16-step undo, stats, save and restore, wake from screen-off), Counter, Dice, Mars Production | watch (tennis since 2026-10-31); the saved match restored after a restart: emulator only |
| `.f3x` apps: build, install over Bluetooth (eight, each read back identical), the hub creates `/user/hub`, opens the files, loads them into the heap and runs them; repeated open and close | watch |
| Removing an installed app: long press, sheet, two-step Remove, list rebuilt | watch |
| `f3x_install.py remove` and `--force`, an update in place, a damaged file refused by the hub, an image near the 32 kB limit | PC and emulator; **open** on a watch |
| Hub built with `--no-native-transitions` (apps inside the hub's window) | emulator |

## Build and flash

| What | State |
|---|---|
| Build a package from your own stock package (`build_firmware.py`) | watch: the packages pass `validate_fwd.py` and were flashed |
| Flash from the PC: upload, size check, read-back (`f3_flash.py --upload --verify`) | watch: 18.3 MB in about 110 s, 462 blocks all acknowledged; read-back 1015 s, identical. 45 checks on a mock watch, incl. failures mid-transfer |
| Flash from the PC: `--start-update` | watch: the watch restarts at once (no answer to the OTA command), installs, and runs the new build |
| Own app-list name and icon (`--label`, `mkicon.py`) | watch |
| Replacing another entry (`--slot`) | emulator: all 11 entries build and pass the window test; **only World Clock tried on a watch** |
| A package without the Bluetooth patches (`--no-bluetooth-patches`) | PC: built and validated; **open on a watch** |
| The first flash on a watch that never had the patches (factory reset, setup screen) | **open** (from Musicalista's notes, not tried by us) |
| Names in all languages (`--languages all`) | PC: the structure of all 69 language files is checked; **open** on a non-English watch |

## Tools

| What | State |
|---|---|
| Validate and rebuild firmware packages (`src/firmware`) | PC: every CRC, byte-identical rebuild of a known package |
| Copy fonts and images from a watch (`src/device/f3_pull.py`) | watch; read-only |
| Decoders for fonts, image packs, language packs (`src/assets`); Ghidra pipeline (`src/re`) | PC (15,478 functions decompiled) |
| Unicorn harness and tests (`src/emu`) | PC: LVGL structures, tennis, hub, host window, installed apps, Mars, icons, all 11 slots |
| The emulator's pictures of rounded cards that have children (serve dot, divider, some rows) are wrong; the watch draws them correctly | known limit: judge the look on the watch |

## Open

- What replacing each other stock app breaks (Alarm, Timer and Stopwatch may keep state outside their window).
- Other watches and firmware versions: the build refuses anything but R390XXU0AZA3.
- Why 2 KB writes after every tap restarted the watch; the apps avoid them (a few bytes, 3 s after a change).
- The factory file commands (`FI^...`) exist in the firmware and include a `FORMAT`; **do not guess their syntax**. The triple press of the side key (message `0x408`) is the emergency SOS: never hook it.
- The RTC call, heart-rate and step counters ([details.md](details.md)).

## Ideas, not planned

- Keep the list's scroll position when returning from an app; more apps; a 13th row in the stock list instead of replacing an entry (needs patches to the row count and the order normaliser).
