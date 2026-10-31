# Disclaimer, credits and licensing

## Disclaimer

This is an independent, unofficial hobby project. It is **not affiliated with, endorsed by or supported by Samsung** (or by the authors credited below). Galaxy Fit3 and Samsung
are trademarks of their owners.

**Flashing firmware can make a watch unusable, and recovery may be impossible.** A package that boots on one watch may not boot on another: everything here was tried on one watch,
one firmware version (R390XXU0AZA3), one model (SM-R390). Apps are native code with no sandbox; a faulty app can restart the watch, and an app can read and write the watch's files.
The Bluetooth patch used here leaves the watch visible and its file service open to anyone in range. Flashing may void your warranty. You use all of this at your own risk; there is no warranty.

## What this repository does not contain

- no Samsung firmware, no firmware package of any kind, no firmware-derived binary;
- none of the code of the SDK and loader (an external checkout, see [howto.md](howto.md));
- no Samsung fonts or images (the notes describe the formats; `local/` is git-ignored).

What it does contain: our own code (the loader in `tools/loader/`, the tools, the apps), our own icon artwork (`tools/assets/mkicon.py` draws it), and notes on how the firmware works with the
addresses and function names we found (`docs/research/`, `docs/symbols.csv`). Those are our analysis for interoperability; they quote no Samsung code. `tools/build_tennis.py` builds a package
from the stock package *you* provide; do not redistribute its output, which contains Samsung's firmware.

`tools/firmware/make_flat_pkg.py` *produces* a modified package from one you already have; do not redistribute its output.

## Credits and third-party terms

| What | From | Terms as far as we know |
|---|---|---|
| App SDK, `.f3a` format, loader, Fit3 Manager, firmware patches | **Musicalista**, [fit3-store-apps-games](https://github.com/Musicalista/fit3-store-apps-games), [freemyfit3](https://github.com/Musicalista/freemyfit3) | no licence file in either repository; the packages are marked "private builds ... do not publish the .bin files" |
| Transfer protocol, package validation rules | **yuriyurin**, [fit3-flasher](https://github.com/yuriyurin/fit3-flasher) | the Fit3 store project notes that it carried no licence |
| Roboto (the shape of the fonts on the watch) | Google | Apache 2.0 for Roboto itself; Samsung's compiled font files are theirs |
| Fonts and images on the watch | Samsung | proprietary; for inspection on your own watch only |

The two Bluetooth patches that `build_package.py` applies (two one-instruction changes, addresses in its source) were first made by Musicalista; we found them again by comparing the stock
package with `fit3-spp-only.bin`, and we reproduce them without copying that package.

Before publishing anything derived from the loader, ask its author. Our reading of the loader (addresses, hook points) is analysis for interoperability, and it is documented, not copied.

## Licence of this repository

[Apache License 2.0](../LICENSE) for everything in the repository: the code (`tools/`, `apps/`, `sim/`), the notes (`docs/`, `docs/research/`, `docs/symbols.csv`) and our icon
(`tools/assets/mkicon.py`). One licence on purpose, with the patent grant that Apache-2.0 includes. Source files carry an `SPDX-License-Identifier: Apache-2.0` line.

What the licence does **not** do: it covers what we wrote, nothing else. It does not licence Samsung's firmware, fonts or images (you bring them), the SDK and loader of Musicalista
(an external checkout, which has no licence of its own; `apps/` and `sim/` are our code but compile against its headers) or the package your build produces (it contains Samsung's firmware).
Copyright of contributions stays with their authors, who grant the licence by contributing. This is not legal advice.
