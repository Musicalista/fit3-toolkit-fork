# Disclaimer, credits and licensing

## Disclaimer

This is an independent, unofficial hobby project. It is **not affiliated with, endorsed by or supported by Samsung** (or by the authors credited below). Galaxy Fit3 and Samsung
are trademarks of their owners.

**Flashing firmware can make a watch unusable, and recovery may be impossible.** A package that boots on one watch may not boot on another: everything here was tried on one watch,
one firmware version (R390XXU0AZA3), one model (SM-R390). Apps are native code with no sandbox; a faulty app can restart the watch, and an app can read and write the watch's files.
The Bluetooth patch used here leaves the watch visible and its file service open to anyone in range. Flashing may void your warranty. You use all of this at your own risk; there is no warranty.

## What this repository does not contain

- no Samsung firmware, no firmware package of any kind, no firmware-derived binary;
- none of the code of Musicalista's SDK, loader and phone app (we neither contain nor need them: our code on the watch and our flasher are our own);
- no Samsung fonts or images (the notes describe the formats; `local/` is git-ignored).

What it does contain: our own code (the code that runs on the watch in `src/loader/`, the tools), our own icon artwork (`src/assets/mkicon.py` draws it), and notes on how the firmware works with the
addresses and function names we found (`docs/details.md`, `docs/symbols.csv`). Those are our analysis for interoperability; they quote no Samsung code. `src/build_tennis.py` builds a package
from the stock package *you* provide; do not redistribute its output, which contains Samsung's firmware.

## Credits and third-party terms

| What | From | Terms as far as we know |
|---|---|---|
| Fit3 Manager (their phone app), the app loader and `.f3a` format (not used here any more), the first firmware patches | **Musicalista**, [fit3-store-apps-games](https://github.com/Musicalista/fit3-store-apps-games), [freemyfit3](https://github.com/Musicalista/freemyfit3) | no licence file in either repository; the packages are marked "private builds ... do not publish the .bin files" |
| Transfer protocol, package validation rules | **yuriyurin**, [fit3-flasher](https://github.com/yuriyurin/fit3-flasher); the sequence of a flash was also checked against the published source of Fit3 Manager (no licence file: read for interoperability, our code is our own) | the Fit3 store project notes that it carried no licence |
| Roboto (the shape of the fonts on the watch) | Google | Apache 2.0 for Roboto itself; Samsung's compiled font files are theirs |
| Fonts and images on the watch | Samsung | proprietary; for inspection on your own watch only |

The two Bluetooth patches that `build_package.py` applies (two one-instruction changes, addresses in its source) were first made by Musicalista; we found them again by comparing the stock
package with `fit3-spp-only.bin`, and we reproduce them without copying that package.

We do not use or contain their loader any more: our code is called by the firmware's own window manager (see [details.md](details.md)). Their work is credited in the README.

## Licence of this repository

[Apache License 2.0](../LICENSE) for everything in the repository: the code (`src/`), the notes (`docs/`, `docs/symbols.csv`) and our icon
(`src/assets/mkicon.py`). One licence on purpose, with the patent grant that Apache-2.0 includes. Source files carry an `SPDX-License-Identifier: Apache-2.0` line.

What the licence does **not** do: it covers what we wrote, nothing else. It does not licence Samsung's firmware, fonts or images (you bring them), the SDK, loader and Fit3 Manager of Musicalista
(which have no licence of their own; we neither contain nor need their code) or the package your build produces (it contains Samsung's firmware).
Copyright of contributions stays with their authors, who grant the licence by contributing. This is not legal advice.
