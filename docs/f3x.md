# .f3x: apps you install on the watch over Bluetooth

An `.f3x` file is one app: compiled code, its icon and a list of the addresses inside it that must be moved. You put it on the watch with `src/device/f3x_install.py`, **without flashing the firmware**;
the Application Hub (`--hub`, [src/watch/README.md](../src/watch/README.md)) lists it next to the apps built into the firmware and loads it into RAM when you open it.

Status and what was seen on the watch: [status.md](status.md). The format is our own, unrelated to Musicalista's `.f3a`.

## Using it

Commands: [howto.md](howto.md), section 3 (`build_f3x.py`, `f3x_install.py list | install | remove`; a long press on an installed app's row in the hub removes it too). Writing an app:
[src/watch/apps/README.md](../src/watch/apps/README.md). Two things concern the format itself: the hub needs the loader (default for `--hub`, `--no-install` leaves it out), and the installer needs the
Bluetooth patches, so **a package built with `--no-bluetooth-patches` cannot receive apps** (apps already installed keep working). The installer checks the file on the PC, writes it, reconnects, reads it back
and compares; the app appears the next time you open the hub.

## The file

All numbers little endian. `src/f3x/f3x.py` builds and parses it; `src/watch/hub.c` loads it.

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | magic `F3X1` |
| 4 | 2 | format version, 1 |
| 6 | 2 | flags, 0 (a file with a flag set is refused) |
| 8 | 4 | firmware id: `crc32("R390XXU0AZA3")` = `0xdf60a3cc`. The image calls firmware functions at absolute addresses, so a file is good for one firmware build only; the hub refuses another |
| 12 | 4 | image size in bytes (multiple of 4, 16 to 32768) |
| 16 | 4 | offset of the `App` struct in the image (multiple of 4) |
| 20 | 4 | size of the relocation list in bytes (at most 8192) |
| 24 | 4 | CRC-32 (zlib) of everything after the header |
| 28 | 24 | the name in the list: 1 to 23 printable ASCII characters, zero padded |
| 52 | 12 | reserved, zero |
| 64 | 2112 | the icon: LVGL `LV_IMG_CF_INDEXED_4BIT`, 64 x 64: 16 palette entries of 4 bytes (B, G, R, A; entry 0 transparent), then 4 bits per pixel, the left pixel in the high nibble, 32 bytes per row |
| 2176 | image size | the image, linked at `0x40000000` |
| | relocation size | the relocation list |

**The image** is the app's `.text` and `.rodata` as one block, no `.data` and no `.bss`: all state lives in memory the app allocates (`app_malloc`). Its entry is the global `f3x_app`, a
`const App { name, icon, create, back, destroy }` (the hub reads the name and icon from the header, so `icon` is 0). The code is Thumb-2 for the Cortex-M4, position independent except for the
words that hold addresses of the image itself: function pointers in `f3x_app`, string and table pointers, literal pools.

**The relocation list** names those words. `build_f3x.py` links the app twice, at `0x40000000` and `0x50000000`; the words that differ by exactly `0x10000000` are the relocations (every other difference
is an error). The list is the ascending word offsets as LEB128 varints of the gap in words from the previous one (the first from offset 0). The hub adds `address_of_the_image - 0x40000000` to each word.
Calls into the firmware are absolute constants in both links and are not touched; calls inside the image are PC-relative.

**Loading** (`inst_load` in `hub.c`): open the file, check the header again, read the icon and the image and the list through the CRC, `app_malloc` a block of image + list (8-byte aligned or refused),
relocate, call `create`. On close the hub calls `destroy`, deletes the widgets, **then** frees the block (`destroy` is code in that block). A file that fails any check does not open: a strong buzz.

## Where the files live

`/user/hub/aNN.f3x`, NN = 00..15. Sixteen fixed names instead of a directory listing: the hub tries to open each one, so it never needs `readdir` (we have never run it). The hub creates `/user/hub` with the
firmware's `mkdir_p` when it opens; the protocol's file write fails with `open error:-2` if the directory does not exist, so open the hub once before the first install. The list shows bundled apps first, then
the installed ones in slot order. Removing an app (`f3x_install.py remove`, or a **long press on its row in the hub**, then Remove twice) writes an 8-byte tombstone (`F3X-GONE`) over its slot: the Bluetooth protocol we know has no delete, and the hub ignores anything that is not a valid header.
For the icons the hub keeps 2.1 kB per installed app in RAM while the hub window is open; the code is loaded only when you open the app.

## Limits and unknowns

- **Code from the heap runs on the real watch**, with no cache maintenance (verified with blocks of 1.4 to 4 kB, including the 6 kB tennis file; not tried with the largest allowed image of 32 kB: `app_malloc` may refuse it,
  then the app does not open and the hub buzzes).
- One format version, one firmware: R390XXU0AZA3. A new firmware needs a new `FW_ID` and a rebuild of every app (and a new hub).
- At most 16 installed apps, an image of at most 32 kB, 8-byte aligned load address required.
- An installed app can do anything the firmware's functions can, as the code the hub is made of can; there is no sandbox. Install only apps whose source you have read. The only way onto the watch is the
  Bluetooth service, which (with the patches) anyone in range can reach: see the heads-up in the README about `--no-bluetooth-patches`.
- LVGL's image cache may keep a decoded-icon entry keyed by the address of an installed app's icon descriptor after the hub window closes; the next hub window allocates the same size again, so a stale entry
  would show the same bytes. Not seen in the emulator; watch for a wrong icon after removing an app and installing another.
