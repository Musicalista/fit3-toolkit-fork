# Status

Legend: **verified** = seen working on a real watch (SM-R390, R390XXU0AZA3); **analysis** = from reading the firmware, not tried; **open** = unknown.

| Area | State | Notes |
|---|---|---|
| Flash a package over Bluetooth (Fit3 Manager) | verified | `fit3-spp-only` (2 one-instruction patches) and `fit3-store-base-spp` (loader) both boot |
| Serial service reachable without pairing, from Linux | verified | RFCOMM channel 29 with plain BlueZ sockets, after the spp patch |
| Native apps (`.f3a`) run from RAM | verified | `hello`, `tenis` |
| Loader needs `/user/apps/` | verified, **bug upstream** | the directory does not exist and nothing creates it (`open error:-2, 331`); `tools/firmware/make_flat_pkg.py` moves the files to `/user/a_*` |
| Install / list / remove apps from a PC | verified | `tools/device/f3_install.py`, reads the file back before touching the app list |
| `tenis` (score tracker) | verified | after cutting its saves from 2 KB per tap to 128 B 3 s after the last change, undo and exit no longer restart the watch (cause not proven) |
| Read `/nand/system/{font,image}` from a PC | verified | `tools/device/f3_pull.py`, read-only |
| Samsung fonts decoded | verified (PC) | LVGL binary fonts, `tools/assets/lvfont.py`; drawn in the simulator |
| Samsung images (`app_*.res`) | partial | first record type (indexed 8 bit) decodes; other record types not yet |
| An app reads `/nand/...` itself (`styledemo`) | **open** | being tested: the footer of the app says how many fonts opened |
| Loader page scrolls under the finger | open | taps become drags; a stock list entry with a fresh full-screen root may avoid it |
| Replace the stock *World clock* entry by our menu | analysis | hook site, helper addresses and free space found, nothing built or flashed ([docs/firmware.md](firmware.md)) |
| Start an app directly from a list entry (no menu) | open | needs changes to the loader itself |
| Factory file commands (`FI^MKDIR`, `FI^LS`, ...) | open | exist in the firmware, syntax unknown; the same set has `FORMAT`, **do not guess** |
| Galaxy Wearable after our experiments | observed | once stuck on "Updating info" after aborted transfers; a watch restart cleared it |
