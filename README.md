# Fit3 lab: a native tennis score tracker for the Samsung Galaxy Fit3

> **Unofficial and experimental. Not affiliated with Samsung. Flashing firmware can leave a watch unusable.**
> Read [docs/legal.md](docs/legal.md) before you do anything, and keep the stock firmware at hand.

The Galaxy Fit3 has no SDK and no way to install apps. This project puts **your own native app on it**: a tennis match score tracker that takes the place of an entry of the stock app list (World clock by
default) and looks and behaves like a stock app. You build the package from your own stock firmware with one command and flash it with the phone app; nothing of Samsung's is in this repository.

<!-- screenshots: docs/images/ (photos of the watch): the app list with the new entry, the score page, the stats page -->

## What it does

- **Score:** tap a player's card for a point. Games, sets (best of 3), tie-break at 6-6 and who serves are tracked; **Undo** takes back up to 16 points; **Stats** shows the match and set times; **New** asks twice.
- **Looks stock:** LVGL cards and pill buttons in the stock colours, the watch's own Roboto fonts, the stock back swipe and back transition, the side key goes to the watch face.
- **Survives:** the page stays when the screen sleeps and wakes; the match is saved (132 bytes, a few seconds after a change) and restored when the window opens again.
- **Your choice of entry:** it replaces World clock unless you pick another (`--slot`), with your own name and icon (`--label`).

Tested on one SM-R390 with firmware **R390XXU0AZA3** only; the build refuses anything else. Details and what was verified where: [docs/status.md](docs/status.md).

## Quick start

```
python3 -I tools/build_tennis.py <your R390XXU0AZA3 package>.bin out.bin                      # builds, checks every CRC
python3 -I tools/build_tennis.py <your package>.bin --list-slots                              # which entries can be replaced
python3 -I tools/build_tennis.py <your package>.bin out.bin --slot Calculator --label "Tennis Score"
```

Then flash `out.bin` with Fit3 Manager (phone) and open the app list. Full steps, requirements and how to go back to stock: [docs/howto.md](docs/howto.md). You need `arm-none-eabi-gcc`, Python 3 with
numpy, and **your own stock package**; keep a copy of it.

## How it works, in short

The firmware calls two functions of each window of its app list through a table. The build puts a branch at the start of those two functions of the chosen entry, into our code in an empty area of the firmware
image (62 KB of zeros). Our code calls the firmware's own LVGL functions, answers the window manager's questions (side key, swipe, transition) and keeps its state in one heap block. Nothing runs at boot, so a mistake
shows only when the entry is opened, and the watch still boots and can be flashed again. The internals, with addresses: [docs/details.md](docs/details.md).

## What is in the repository

| Path | What |
|---|---|
| [`tools/build_tennis.py`](tools/README.md) | one command from your stock package to the tennis package |
| [`tools/loader/`](tools/loader/README.md) | the code that runs on the watch: `loader_v2.c` is the tracker; `loader_v0.c` and `loader_v1.c` are the steps that led to it |
| [`tools/firmware/`](tools/README.md) | read, validate and rebuild firmware packages (`build_package.py`, `validate_fwd.py`) |
| [`tools/emu/`](tools/emu/README.md) | a Unicorn harness that runs functions of the real firmware on the PC; the tests of the loader run on it |
| [`tools/assets/`](tools/README.md), [`tools/re/`](tools/re/README.md), [`tools/device/`](tools/README.md) | decoders for fonts, images and language packs, the icon generator, the Ghidra pipeline, tools that talk to the watch |
| [`docs/`](docs/) | [howto](docs/howto.md), [status](docs/status.md), [details](docs/details.md), [roadmap](docs/roadmap.md), [legal](docs/legal.md), [symbols.csv](docs/symbols.csv) (named firmware addresses) |
| [`sdk/`](sdk/README.md), [`apps/`](apps/README.md), [`sim/`](sim/README.md) | the older route: apps for Musicalista's loader, an SDK and a PC simulator for them |
| `local/`, `build/` (not in git) | your firmware packages and assets pulled from your watch; build output |

## Credits and acknowledgements

This project would not exist without **[Musicalista](https://github.com/Musicalista)**. Their [fit3-store-apps-games](https://github.com/Musicalista/fit3-store-apps-games) and
[freemyfit3](https://github.com/Musicalista/freemyfit3) were the first to get native code running on the Galaxy Fit3: they found the firmware patches that make the watch's Bluetooth
file service reachable, defined the `.f3a` "light app" format and wrote the app loader and the store. Our first experiments started from their hook points, and the idea of running
our own code from the free flash behind an entry of the app list is theirs. We later replaced the loader with our own code (the firmware's window manager calls it directly), but we
started from what they showed was possible. Thank you.

The transfer protocol and the package checks come from **[yuriyurin/fit3-flasher](https://github.com/yuriyurin/fit3-flasher)**. The analysis used the public sources of
[LVGL](https://lvgl.io), [Ghidra](https://ghidra-sre.org) and [Unicorn](https://www.unicorn-engine.org).
This repository contains none of their code and no Samsung firmware or assets; details in [docs/legal.md](docs/legal.md).

## Licence

[Apache License 2.0](LICENSE) for everything in this repository (code, notes and the icon). It covers only what we wrote. It gives you no rights to Samsung's
firmware, fonts or images, which you must bring from your own watch, and it does not change the terms of the projects credited above.
