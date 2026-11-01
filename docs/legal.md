# Legal notes

What the [README](../README.md) does not say: the details of the disclaimer, the status of the AI-written parts, what the repository does and does not contain, and the terms of the projects we learned from.

## Disclaimer

Galaxy Fit3 and Samsung are trademarks of their owners; the authors credited in the README do not endorse this project either.

A package that boots on one watch may not boot on another: everything here was tried on one watch, one model (SM-R390), one firmware version (R390XXU0AZA3). Recovery from a bad flash may be impossible.
Apps are native code with no sandbox: a faulty app can restart the watch, and an app can read and write the watch's files. The Bluetooth patches leave the watch visible and its file service open to
anyone in range. Flashing may void your warranty. You use all of this at your own risk; there is no warranty.

## AI-written parts

The AI can be wrong in the notes about what the firmware does too. [status.md](status.md) lists what was actually seen on a watch; a statement in a comment or in a note that is not listed there is a
hypothesis. AI-written code has no extra warranty, and the disclaimer above applies in full. The maintainer is responsible for what is published; the AI is not an author in the legal sense, and nothing
here is a statement about the legal status of AI-generated work.

## What this repository contains, and what it does not

**Does not contain:** any Samsung firmware, package or firmware-derived binary; Samsung's fonts or images (the notes describe the formats, `local/` is git-ignored); any code of Musicalista's SDK, loader or
phone app, or of any other project in the README's credits.

**Does contain:** our own code (the code that runs on the watch in `src/watch/`, the tools), our own icon artwork (`src/assets/mkicon.py` draws it), the banner, our photos of the screen, the `.f3x` format
([f3x.md](f3x.md)), and notes on how the firmware works with the addresses and function names we found ([details.md](details.md), [symbols.csv](symbols.csv)). The notes are our analysis for interoperability and
quote no Samsung code. A stock icon or font that is visible in a photo of the watch is still Samsung's.

`src/build_firmware.py` builds a package from the stock package *you* provide. **Do not redistribute its output**: it contains Samsung's firmware.

## Terms of the projects we learned from

As far as we know; check them yourself before you rely on this.

| Project | Terms |
|---|---|
| **Musicalista**: [fit3-store-apps-games](https://github.com/Musicalista/fit3-store-apps-games), [freemyfit3](https://github.com/Musicalista/freemyfit3) (the Fit3 Manager phone app, the app loader, the `.f3a` format, patched packages) | no license file in either repository; the packages are marked "private builds ... do not publish the .bin files". We used facts only |
| **yuriyurin**: [fit3-flasher](https://github.com/yuriyurin/fit3-flasher) | the transfer protocol and package validation rules; the sequence of a flash was also checked against the published source of Fit3 Manager (no license file: read for interoperability, our code is our own) |
| Roboto (the shape of the watch's fonts) | Apache 2.0 for Roboto itself; Samsung's compiled font files are theirs |
| Fonts and images on the watch | Samsung; proprietary, for inspection on your own watch only |

The two Bluetooth patches in `src/firmware/build_package.py` (two one-instruction changes, addresses in its source) are also in Musicalista's package; we found them again by comparing the stock package
with their `fit3-spp-only.bin`, and we reproduce them without copying that package. Their loader is not used: our code is called by the firmware's own window manager ([details.md](details.md)).

## License of this repository

Apache License 2.0 ([LICENSE](../LICENSE)) for everything we wrote: the code, the notes, the icons, the banner and the photos. One license on purpose, with the patent grant that Apache-2.0 includes.
Source files carry an `SPDX-License-Identifier: Apache-2.0` line.

It does **not** cover Samsung's firmware, fonts or images, Musicalista's SDK, loader, Fit3 Manager and `.f3a` format (ours, `.f3x`, is unrelated), or the package your build produces. Copyright of
contributions stays with their authors, who grant the license by contributing. This is not legal advice.
