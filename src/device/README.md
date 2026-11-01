# device: talk to the watch

Over Bluetooth (RFCOMM, the watch's file service, [docs/protocol.md](../../docs/protocol.md)). Set your watch's address once: `export F3_ADDR=AA:BB:CC:DD:EE:FF` (or pass `--addr`).

> [!CAUTION]
> Two tools **write** to the watch. **`f3_flash.py`** sends a firmware package and can brick the watch if you send a bad one; it checks the package first and asks you to type `FLASH`.
> **`f3x_install.py`** can only write the sixteen files `/user/hub/a00.f3x` … `a15.f3x`. Everything else here only reads.

| Tool | Does | Writes? |
|---|---|---|
| [`f3_flash.py`](f3_flash.py) | validate a package, upload it, verify it, start the update, in stages | **yes: the firmware package** |
| [`f3x_install.py`](f3x_install.py) | `list`, `install`, `remove` apps (`.f3x`) | **yes: the 16 app slots** |
| [`f3_pull.py`](f3_pull.py) | copy fonts and images from `/nand/system/` to the PC (for the emulator and for study) | no |
| [`f3_link.py`](f3_link.py) | the link itself: connect, commands, the file transfer; used by the tools above | (library) |
| [`mock_watch.py`](mock_watch.py) | a fake watch for the tests, also able to fail mid-transfer | |

```sh
python3 -I src/device/f3_flash.py hub.bin                                    # 1. plan: checks the package on the PC, touches nothing
python3 -I src/device/f3_flash.py hub.bin --upload --verify                  # 2. copy it to the watch and read it back
python3 -I src/device/f3_flash.py hub.bin --upload --verify --start-update   # 3. install it (cannot be cancelled; watch ≥ 50 % charged, do not touch it)

python3 -I src/device/f3x_install.py list
python3 -I src/device/f3x_install.py install counter.f3x [--slot N] [--force]
python3 -I src/device/f3x_install.py remove --slot N

python3 -I src/device/f3_pull.py local/assets/fonts /nand/system/font/FONT_ROBOTO_22_GBK_en.bin
```

Close the Galaxy Wearable app first (only one client can be connected). The stages, the pauses and the checks are explained at the top of each script, and the whole procedure in
[docs/howto.md](../../docs/howto.md). Tests need no watch: `test_f3_flash.py`, `test_f3_link.py` and `test_f3x_install.py` run against `mock_watch.py`.
