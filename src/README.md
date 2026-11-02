# src/

Python 3 (numpy for the icons, Pillow for some tools), `arm-none-eabi-gcc` for the code that runs on the watch. Run everything with `python3 -I`.

**The one command you need most:** [`build_firmware.py`](build_firmware.py) compiles the code for the watch with the apps you choose and builds a firmware package from *your* stock package.
It takes `--hub A,B,C` or `--hub none` (the Application Hub), `--app NAME` (one app), `--slot`, `--label`, `--languages`, `--no-install`, `--no-native-transitions`, `--no-bluetooth-patches`, `--reply-keyboard` with `--kb-lang` (the reply keyboard, [docs/replies.md](../docs/replies.md)), `--list-slots`,
and prints how much of the free flash it used. Steps: [docs/howto.md](../docs/howto.md).

| Directory | What | Writes to the watch? |
|---|---|---|
| [`watch/`](watch/README.md) | the code that runs on the watch: the hub and `ui.h` | no |
| [`watch/apps/`](watch/apps/README.md) | demo apps; how to write your own | no |
| [`f3x/`](f3x/README.md) | the `.f3x` app format and its builder | no |
| [`device/`](device/README.md) | flash, install apps, copy fonts and images | **`f3_flash.py` and `f3x_install.py` only** |
| [`firmware/`](firmware/README.md) | read, patch, validate and rebuild packages | no |
| [`emu/`](emu/README.md) | run the real firmware's functions on the PC; screenshots; most of the tests | no |
| [`assets/`](assets/README.md) | decoders for fonts, images and language packs; icon generator | no |
| [`re/`](re/README.md) | the Ghidra pipeline | no |

Protocol: [docs/protocol.md](../docs/protocol.md). Firmware: [docs/firmware.md](../docs/firmware.md), [docs/details.md](../docs/details.md).
