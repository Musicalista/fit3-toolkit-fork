# Status

Tested on **one** Galaxy Fit3 (SM-R390) on firmware **R390XXU0AZA3**. Legend: **watch** = seen working on a real watch; **emulator** = the real firmware code run on the PC (`tools/emu`); **PC** = tools tested without a watch;
**open** = not known or not tried.

## The tennis score tracker

| What | State | Notes |
|---|---|---|
| Build a package from your own stock package | watch | `tools/build_tennis.py`; the result passes `validate_fwd.py`; flashed with Fit3 Manager |
| The app in the World clock slot | watch | native LVGL window, no menu in front of it, nothing of ours runs at boot |
| Score, Undo, Stats, "New" with a second tap | watch | best of 3 sets, tie-break at 6-6, 16 undo steps |
| Save and restore | emulator | 132 bytes in `/user/tenis.sav`, 3 s after a change and when the window closes; restoring after a restart (with the clock continuing) is tested in the emulator, **not explicitly tried on the watch** |
| Touch | watch | as responsive as the stock apps (LVGL's own input, not the panel driver) |
| Back gesture, with the stock transition | watch | right swipe leaves the window; with the Stats overlay open it closes the overlay first (that case: emulator) |
| Side key | watch | short press goes to the watch face, like the stock apps |
| Wake from screen-off | watch | the page stays, no stock page flashes in or comes back |
| Own app-list name and icon | watch | `--label` (two lines when long), `mkicon.py` draws the icon, `--no-icon` keeps the stock one |
| Replacing another entry (`--slot`) | emulator | all 11 replaceable entries build and pass the window test; **only World clock was tried on a watch** |
| Names in all languages (`--languages all`) | PC | the structure of all 69 language files is checked; not tried on a watch in another language |

## Tools

| What | State |
|---|---|
| Validate and rebuild firmware packages (`tools/firmware`) | PC: every CRC, byte-identical rebuild of a known package |
| Copy fonts and images from a watch (`tools/device/f3_pull.py`) | watch; read-only |
| Flash from the PC (`tools/device/f3_flash.py`) | **mock watch only**: 45 checks incl. failures mid-transfer and the log file; **never run on a real watch** (the upload, the size check and the OTA command are those of the phone app, but we have not sent them ourselves) |
| Decoders for fonts, image packs, language packs (`tools/assets`) | PC |
| Ghidra pipeline (`tools/re`) | PC: 15,478 functions and the decompiled C of the stock main image |
| Unicorn harness, loader and icon tests, screenshots (`tools/emu`) | PC: 40 checks on LVGL structures, 40 on the window, 9 on the icon, all 11 slots |

## Open

- What replacing each other stock app breaks on a watch (Alarm, Timer and Stopwatch may keep state outside their window).
- Other watches and firmware versions: the build refuses anything but R390XXU0AZA3.
- Why 2 KB writes after every tap restarted the watch; the app avoids them.
- The factory file commands (`FI^...`) exist in the firmware and include a `FORMAT`; **do not guess their syntax**.
- The RTC call, heart-rate and step counters (see [details.md](details.md)).
