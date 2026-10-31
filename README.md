# Fit3 lab: custom apps and tooling for the Samsung Galaxy Fit3 (SM-R390)

> **Unofficial and experimental. Not affiliated with Samsung. Flashing firmware can leave a watch unusable.**
> Read [docs/legal.md](docs/legal.md) before you do anything, and keep the stock firmware at hand.

The Galaxy Fit3 runs FreeRTOS with an LVGL user interface on a BES1502x chip. It has no official SDK. This repository collects what we found out while
putting our own native apps on one, plus the tools and apps that came out of it:

- **Tools** to inspect and validate firmware packages, to build a package whose app loader works on a fresh watch, and to install, list and remove apps over
  Bluetooth from a Linux PC (no phone app needed).
- **Apps** written in C for the "light app" loader of [Musicalista/fit3-store-apps-games](https://github.com/Musicalista/fit3-store-apps-games): a tennis
  score tracker and a style demo that draws with the watch's own Roboto fonts.
- A **PC simulator** (a window with the mouse as the finger) so apps can be written and tested without touching the watch.
- **Notes**: the file-transfer protocol, the firmware layout and patch points we identified, and the formats of the watch's fonts and images.

## Status

What is verified on a real watch and what is not: [docs/status.md](docs/status.md). Short version: stock firmware R390XXU0AZA3 plus a patched package
boots, native apps run from RAM, and apps install from a PC; the loader's page still scrolls under the finger, and replacing a stock list entry is analysed but
not built.

## Layout

| Path | What is in it |
|---|---|
| [`docs/`](docs/) | the notes: [status](docs/status.md), [roadmap](docs/roadmap.md), [howto](docs/howto.md), [protocol](docs/protocol.md), [firmware](docs/firmware.md), [assets](docs/assets.md), [apps](docs/apps.md), [legal](docs/legal.md) |
| [`tools/`](tools/README.md) | Python tools: `firmware/` (inspect, validate, patch packages), `device/` (talk to the watch), `assets/` (decode Samsung fonts), `build_app.py` |
| [`apps/`](apps/README.md) | our apps (`tenis`, `styledemo`) and the shared headers `apps/include/` (`f3font.h`, `f3ui.h`) |
| [`sim/`](sim/README.md) | the PC simulator |
| `local/` (not in git) | firmware packages, the phone APK and assets pulled from a watch |
| `fit3-store/` (not in git) | external checkout of the SDK, see [docs/howto.md](docs/howto.md) |

## Quick start

```
python3 -I tools/firmware/validate_fwd.py local/firmware/<package>.bin     # every CRC of a package
python3 -I tools/build_app.py tenis                                         # apps/tenis -> build/tenis.f3a
sim/run.sh styledemo --data local/assets/fonts                              # try an app on the PC
python3 -I tools/device/f3_install.py install build/tenis.f3a               # put it on the watch
```

## Credits

The app loader, the SDK and the firmware patches come from **Musicalista**; the transfer protocol and package checks from **yuriyurin/fit3-flasher**. Details in
[docs/legal.md](docs/legal.md). This repository contains none of their code and no Samsung firmware or assets.
