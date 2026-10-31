# Fit3 lab: a native tennis score tracker for the Samsung Galaxy Fit3 (SM-R390), and the tools behind it

> **Unofficial and experimental. Not affiliated with Samsung. Flashing firmware can leave a watch unusable.**
> Read [docs/legal.md](docs/legal.md) before you do anything, and keep the stock firmware at hand.

The Galaxy Fit3 runs FreeRTOS with an LVGL 8.3 user interface on a BES1502x chip. It has no official SDK. This repository holds what we found out while putting our own
native app on one, and the tools that came out of it.

## What works (firmware R390XXU0AZA3, one SM-R390)

A **tennis score tracker that replaces the *World clock* entry of the app list** and looks like a stock app: LVGL cards and pill buttons in the stock colours, Roboto from the watch's
own font tables, the stock back transition, the back gesture and side key of the stock apps, its own app-list name and icon. Tap a card for a point; Undo; Stats with a two-step "New";
best of 3 sets with tie-breaks; the match survives a restart of the watch. It is plain C compiled into the free flash of the firmware, started by the window manager like any
other window: no loader menu, no scrolling page, nothing runs at boot.

Everything above has been used on a real watch (one SM-R390). It has not been tried on any other watch or firmware version: the build refuses anything but R390XXU0AZA3.

Build it from **your own** stock package with one command (pick another entry than World clock with `--slot`; see [docs/howto.md](docs/howto.md)):

```
python3 -I tools/build_tennis.py <your R390XXU0AZA3 package>.bin out.bin       # then flash out.bin with Fit3 Manager; see docs/howto.md
```

What is verified and what is not: [docs/status.md](docs/status.md). Where this is going: [docs/roadmap.md](docs/roadmap.md).

## What is in here

| Path | What |
|---|---|
| [`tools/loader/`](tools/loader/README.md) | the loader: `loader_v2.c` is the tennis window; `loader_v0.c`, `loader_v1.c` are the steps that got us there (kept as small, readable examples of the technique) |
| [`tools/firmware/`](tools/README.md) | read, validate and rebuild firmware packages: `build_package.py` (spp patches, window take-over, label, icon, every checksum), `validate_fwd.py` |
| [`tools/emu/`](tools/emu/README.md) | a Unicorn harness that runs functions of the real firmware on the PC; the loader's tests run on it |
| [`tools/assets/`](tools/README.md) | decoders for the watch's fonts, image packs and language packs; `mkicon.py` draws our app-list icon |
| [`tools/re/`](tools/re/README.md) | the Ghidra pipeline (headless) used to analyse the firmware |
| [`tools/device/`](tools/README.md) | talk to the watch over Bluetooth: install apps, copy fonts and images (read-only) |
| [`docs/research/`](docs/research/) | analysis notes T1-T8: LVGL, the stock UI patterns, resources, the window manager, services, the side key, transitions |
| [`docs/symbols.csv`](docs/symbols.csv) | ~500 named firmware addresses with confidence and evidence |
| [`docs/`](docs/) | [status](docs/status.md), [roadmap](docs/roadmap.md), [howto](docs/howto.md), [protocol](docs/protocol.md), [firmware](docs/firmware.md), [assets](docs/assets.md), [apps](docs/apps.md), [legal](docs/legal.md) |
| [`apps/`](apps/README.md), [`sim/`](sim/README.md) | the older route: apps for the "light app" loader of Musicalista (our own SDK in `sdk/`) and a PC simulator for them |
| [`sdk/`](sdk/README.md) | header files, linker script and format description for light apps (compiled by `tools/appcc.py`) |
| `local/`, `build/` (not in git) | your firmware packages and assets pulled from your watch; build output |

## How it works, in short

The stock firmware calls two functions of the World clock window through a table. `build_package.py` puts a `b.w` branch at their entry, into our code in the free flash
(`0x2c3a0524..0x2c3af920`, zeros in stock). Our code calls the firmware's own LVGL functions (addresses in `docs/symbols.csv`), answers the window manager's queries (key policy,
swipe, transition) and keeps its state in one heap block. The research that made this possible is in `docs/research/`; the emulator tests check every claim they rest on
([tools/emu](tools/emu/README.md)). The honest limits are in [docs/status.md](docs/status.md).

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
