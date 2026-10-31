# Firmware notes (R390XXU0AZA3)

Everything here comes from reading packages with `tools/firmware/` and disassembling the main image (`arm-none-eabi-objdump -D -b binary -marm -Mforce-thumb
--adjust-vma=0x2c080000`). Addresses are for the main image of R390XXU0AZA3; **no other version has been looked at**.

## Package format (FWD, `.bin`)

`header(92) | updater | CRC32 | packet | CRC32`. Header: magic `0x7e5a5a60`, source version string at 4, flags at 72 (=2), then header size (92), updater size, packet offset,
packet size. The packet has its own header (magic `0x7e5a5a5a`, target version, component count at byte 70), a table of 128-byte entries (kind, attribute, offset,
stored size, path on the watch) and then each component as a single-file ZIP (deflate) followed by the CRC32 of its content. `tools/firmware/validate_fwd.py`
checks all of it; fit3-flasher refuses a package whose updater differs from the stock one, so the updater is never modified.

Components of the stock package (73): the main image `/user/ota/app/best1502x_b319_user.bin` (3.37 MB), sensor hub, touch panel firmware, `version.ini` and
about 70 `language_*.res`. **Fonts and images are not in the package**; they live on the watch in `/nand/system/`.

## Main image

Code and data are linked at `0x2c080000 + file offset` (the same bytes are also visible at `0x0c...`; function-pointer tables use that alias). Header at `0x1000`
(`0x11223344, 0xdeaddead, CRC32, size`); the CRC32 is over the image with bytes 0..3 set to `0xff` and `0x1000..0x100f` zeroed. It is not encrypted; there is no
sign of a signature check on the watch side (the two modified packages above boot), which we have not proven.

## What the known patches change (`fit3-spp-only`: 8 bytes, `fit3-store-base-spp`: about 14.8 KB)

| Where | What |
|---|---|
| `0x2c233820` | `mov r4,r0` -> `movs r4,#3`: Bluetooth access mode always "visible and connectable" |
| `0x2c227f7a` | `mov r1,r2` -> `movs r1,#1`: RFCOMM channel 29 accepts a connection although another client uses it |
| `0x2c1d0802` | `bl 0x2c112f58` -> `bl 0x2c3a0524` (loader hook A) |
| `0x2c1b76a0` | `bl 0x2c2974f8` (a log call in the sub-page opener) -> `bl 0x2c3a0548` (loader hook B) |
| `0x2c3a0524..0x2c3a4524` | 16 KB of loader code and strings in formerly empty flash; **the block is full** |
| `.res` | the string "Tips and tutorials" is renamed "Extra apps" in four language files (same length, 36 bytes) |

Free space for more code: `0x2c3a4525..0x2c3af920` (about 46 KB of zeros in the stock image).

Hook B calls `lv_timer_create(cb=0x2c3a1ab9, 80 ms, user_data=root)` (`0x2c28a3f0`); `cb` deletes the timer (`0x2c28a448`) and calls `menu_open(root)` at `0x2c3a1a54`,
which allocates a state block, builds the menu image on `root` and returns. `lv_timer` keeps its user data at `+12`.

`tools/firmware/make_flat_pkg.py` changes two strings in the block (`/user/apps/index.txt` -> `/user/a_index.txt`, `/user/apps/` -> `/user/a_`) and rebuilds every checksum:
the loader copies those strings to the NUL, so shorter ones are fine, and the watch has no `/user/apps/` directory.

## App registry and the World clock entry (analysis only)

Apps are described by 48-byte records starting at file offset `0x334a10` (word 0: flags and id; word 7 at `+0x1c`: the `init` function, stored as `0x0c......|1`).
World clock is id `0x2b`, `app_worldclock_init` at `0x2c1ecc64`: it creates a fresh screen with `lv_obj_create(NULL)` (`0x2c27cb84`), registers an event callback, and for the
main page (`param & 0xff == 0x67`) calls `app_worldclock_tile_init(root)` (`0x2c1ecbac`) at **`0x2c1ecd1c`**, its only call site. Replacing that one `bl` with a stub in the free space
that creates the same 80 ms timer would open our menu on the World clock page. The label "World Clock" appears four times in the English language resource
(inner offsets `0xa8d2 0x11504 0x115c0 0x1d83f`). The list icon is not located yet. None of this has been built or flashed.

## Stage 1 (built by `tools/firmware/world_clock_takeover.py`, not flashed)

The stub at `0x2c3a4530` (16 bytes of code and two literals) is `push {r0-r3,lr}; mov r2,r0; ldr r0,=0x2c3a1ab9; movs r1,#80; ldr r3,=0x2c28a3f1; blx r3; pop {r0-r3,pc}`:
it passes `root` (still in `r0` at the hook site) as the timer's user data, so the loader's callback opens its menu on that page. Together with the label change ("World Clock" -> "Tennis",
same length, in `language_en`, `_rUS`, `_rCA` and `_rPH`) that is 31 changed bytes in the main image and four rewritten language files. The packet header's resource size is recomputed
(it is the sum of the unpacked sizes of the non-firmware components and changes with the language files).

## Not known

- Which of the loader's hooks run when the list entry of an app is tapped (we only know the registry).
- How to start one app directly instead of showing the menu (needs a changed loader).
- Whether the updater verifies anything beyond the CRCs we check.
