# src/

Python 3 (numpy for the icon, Pillow for some tools), `arm-none-eabi-gcc` for the code that runs on the watch. Run with `python3 -I`. The tools that talk to the watch: `device/f3_pull.py` only reads; **`device/f3_flash.py` is the only one that writes**, and only the firmware package to `/user/ota/R390_WEB_FOTA.bin`.

| Tool | Does |
|---|---|
| `build_tennis.py` | **one command**: compile `watch/hub.c` with the chosen apps (`--app NAME` or `--hub A,B,C`), draw the icon, build the package from your stock package (`--slot`, `--label`, `--languages`, `--list-slots`) |
| `firmware/build_package.py` | stock package + Bluetooth patches + our code in the free flash + the take-over of an app-list entry + name + icon; every checksum repaired; validated |
| `firmware/validate_fwd.py` | re-implements fit3-flasher's checks: layout, every CRC32, main image header, stock updater SHA-256 |
| `firmware/fwd.py`, `firmware/fwx.py` | read, edit and rebuild a package (load and save reproduce a package byte for byte); list and extract components (`list`, `main <out>`, `get <path> <out>`) |
| `firmware/test_build_package.py`, `firmware/test_fwd.py` | their tests (need `local/firmware/stock-aza3.bin`, skipped without it) |
| `watch/` | the code that runs on the watch (see its README): `hub.c`, `ui.h`, `apps/`; `build_loader.py` compiles it into a flat binary linked at `0x2c3a0524`, `gen.py` writes the generated headers, `test_score.c` tests the scoring logic on the PC |
| `emu/` | Unicorn harness: run functions of the real firmware on the PC; tests of the loaders, the icon and every slot; screenshots ([README](emu/README.md)) |
| `re/` | the Ghidra pipeline ([README](re/README.md)) |
| `assets/lvres.py`, `assets/lvlang.py`, `assets/lvfont.py` | decode the image packs (`.res`), read or edit the language packs, decode the watch's LVGL fonts and render text to a PNG |
| `assets/mkicon.py` | draw our app-list icon (64 x 64, RGB565 + alpha) |
| `device/f3_pull.py`, `device/f3_link.py` | copy fonts and images (`/nand/system/font`, `/nand/system/image`) from the watch to the PC, **read-only**; `test_f3_link.py` tests the link against a mock watch |
| `f3x/build_f3x.py`, `f3x/f3x.py` | C source of an app -> an installable `.f3x` file (docs/f3x.md); `f3x/test_f3x_format.py` tests the format and the refusals |
| `device/f3x_install.py` | list, install and remove `.f3x` apps on the watch (only `/user/hub/a00..a15.f3x`); `test_f3x_install.py` tests it against `mock_watch.py` |
| `device/f3_flash.py` | send a package to the watch from the PC, in stages: plan, `--upload` (+ `--verify`), `--start-update`; `test_f3_flash.py` tests it against a mock watch that can fail mid-transfer |

Protocol: [../docs/protocol.md](../docs/protocol.md). Firmware: [../docs/firmware.md](../docs/firmware.md), [../docs/details.md](../docs/details.md).
