# tools/

Python 3 only (Pillow for `assets/lvfont.py`). Run with `python3 -I`. They never write to the watch unless the table says so.

| Tool | Does | Touches the watch |
|---|---|---|
| `firmware/fwx.py` | list or extract the components of an FWD package (`list`, `main <out>`, `get <path> <out>`) | no |
| `firmware/validate_fwd.py` | re-implements fit3-flasher's checks: layout, every CRC32, main image header, stock updater SHA-256 | no |
| `firmware/fwd.py` | library: read, edit and rebuild a package; repairs offsets, sizes and every checksum (load+save reproduces a package byte for byte) | no |
| `build_tennis.py` | **one command**: compile `loader/loader_v2.c`, draw the icon, build the package from your stock package | no |
| `firmware/build_package.py` | stock package + spp patches + our loader in the free flash + window take-over (or the older timer hook) + label + icon; every checksum repaired; validated | no |
| `firmware/test_build_package.py` | its tests (needs `local/firmware`) | no |
| `firmware/world_clock_takeover.py` | stage 1 of the [roadmap](../docs/roadmap.md): hook the World clock list entry (its full-page builder) to the loader's menu and rename it | no |
| `firmware/test_fwd.py` | tests of the above against the packages in `local/firmware` (skipped when absent) | no |
| `firmware/make_flat_pkg.py` | builds a package whose loader keeps its files in `/user/a_*` instead of the missing `/user/apps/`, repairing all checksums | no |
| `device/f3_install.py` | `list`, `install <app.f3a>`, `remove <id>` over Bluetooth RFCOMM; only `/user/a_*` paths; verifies by reading back | **writes** `/user/a_*` |
| `device/f3_pull.py` | copy fonts and images (`/nand/system/font`, `/nand/system/image`) to the PC | read-only |
| `device/test_f3_install.py` | tests of the installer against a mock watch (18 checks, no hardware) | no |
| `loader/build_loader.py` | compile a loader source (`loader_v0.c`, `loader_v1.c`, `loader_v2.c`) into a flat binary linked at `0x2c3a0524` | no |
| `emu/` | Unicorn harness: run functions of the real firmware on the PC; tests of the loaders and the icon ([README](emu/README.md)) | no |
| `re/` | the Ghidra pipeline ([README](re/README.md)) | no |
| `assets/lvres.py`, `assets/lvlang.py` | decode the image packs (`.res`) and read or edit the language packs | no |
| `assets/mkicon.py` | draw our app-list icon (64 x 64, RGB565 + alpha) | no |
| `assets/lvfont.py` | decode the watch's LVGL fonts and render text to a PNG | no |
| `build_app.py` | build `apps/<name>` to `build/<id>.f3a` and `.meta` with the SDK's compiler script | no |

Protocol: [../docs/protocol.md](../docs/protocol.md). Firmware: [../docs/firmware.md](../docs/firmware.md).
