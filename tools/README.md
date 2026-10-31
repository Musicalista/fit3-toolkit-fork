# tools/

Python 3 only (Pillow for `assets/lvfont.py`). Run with `python3 -I`. They never write to the watch unless the table says so.

| Tool | Does | Touches the watch |
|---|---|---|
| `firmware/fwx.py` | list or extract the components of an FWD package (`list`, `main <out>`, `get <path> <out>`) | no |
| `firmware/validate_fwd.py` | re-implements fit3-flasher's checks: layout, every CRC32, main image header, stock updater SHA-256 | no |
| `firmware/make_flat_pkg.py` | builds a package whose loader keeps its files in `/user/a_*` instead of the missing `/user/apps/`, repairing all checksums | no |
| `device/f3_install.py` | `list`, `install <app.f3a>`, `remove <id>` over Bluetooth RFCOMM; only `/user/a_*` paths; verifies by reading back | **writes** `/user/a_*` |
| `device/f3_pull.py` | copy fonts and images (`/nand/system/font`, `/nand/system/image`) to the PC | read-only |
| `device/test_f3_install.py` | tests of the installer against a mock watch (18 checks, no hardware) | no |
| `assets/lvfont.py` | decode the watch's LVGL fonts and render text to a PNG | no |
| `build_app.py` | build `apps/<name>` to `build/<id>.f3a` and `.meta` with the SDK's compiler script | no |

Protocol: [../docs/protocol.md](../docs/protocol.md). Firmware: [../docs/firmware.md](../docs/firmware.md).
