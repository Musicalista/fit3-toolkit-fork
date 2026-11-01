# Firmware notes (R390XXU0AZA3)

Everything here comes from reading packages with `tools/firmware/` and disassembling the main image (`arm-none-eabi-objdump -D -b binary -marm -Mforce-thumb --adjust-vma=0x2c080000`).
Addresses are for the main image of R390XXU0AZA3; **no other version has been looked at**. How the firmware works inside (windows, LVGL, resources, services) is in [details.md](details.md).

## Package format (FWD, `.bin`)

`header(92) | updater | CRC32 | packet | CRC32`. Header: magic `0x7e5a5a60`, source version string at 4, flags at 72 (=2), then header size (92), updater size, packet offset,
packet size. The packet has its own header (magic `0x7e5a5a5a`, target version, component count at byte 70), a table of 128-byte entries (kind, attribute, offset,
stored size, path on the watch) and then each component as a single-file ZIP (deflate) followed by the CRC32 of its content. `tools/firmware/validate_fwd.py`
checks all of it; fit3-flasher refuses a package whose updater differs from the stock one, so the updater is never modified.

Components of the stock package (73): the main image `/user/ota/app/best1502x_b319_user.bin` (3.37 MB), sensor hub, touch panel firmware, `version.ini` and
about 70 `language_*.res`. **Fonts and images are not in the package**; they live on the watch in `/nand/system/`.

## Main image

Code and data are linked at `0x2c080000 + file offset` (the same bytes are also visible at `0x0c...`; function-pointer tables use that alias). Header at `0x1000`
(`0x11223344, 0xdeaddead, CRC32, size`); the CRC32 is over the image with bytes 0..3 set to `0xff` and `0x1000..0x100f` zeroed. It is not encrypted. There is no sign of a signature check on the watch
side (packages with changed main images boot), which we have not proven.

## What `build_package.py` changes

| Where | What |
|---|---|
| `0x2c233820` | `mov r4,r0` -> `movs r4,#3`: Bluetooth access mode always "visible and connectable" |
| `0x2c227f7a` | `mov r1,r2` -> `movs r1,#1`: RFCOMM channel 29 accepts a connection although another client uses it |
| `0x2c3a0524...` | our code, then the icon: the stock image has **62,460 bytes of zeros** here (`0x2c3a0524..0x2c3af920`) |
| the entry of two window functions | `b.w` into our code (create and window event of the replaced app-list entry); the other functions of its window record become `bx lr` (see [details.md](details.md), section 2) |
| the app-list row | the icon pointer of the replaced entry points at our image |
| `language_*.res` | the entry's name (text ID of its row), in the English files or in all 69 |
| `0x1008` and the container | the image CRC and every checksum of the package |

The first two rows are the patches that make the watch's serial service reachable without pairing, which `tools/device/f3_pull.py` and `f3_flash.py` need and Fit3 Manager works with; they were first found by Musicalista
(see [legal.md](legal.md)). With them, **anyone in range can connect to the watch's file service**; `--no-bluetooth-patches` leaves them out (see [howto.md](howto.md)).

## Not known

- Whether the updater verifies anything beyond the CRCs we check.
- The factory command families of the firmware (`AT^...`, `FI^...`); see [protocol.md](protocol.md): **do not experiment, `FORMAT` exists**.
