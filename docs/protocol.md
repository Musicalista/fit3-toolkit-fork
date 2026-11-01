# File service over Bluetooth (RFCOMM)

The watch exposes a serial service (SPP, UUID `db764ac8-4b08-7f25-aafe-59d03c27bae3`, RFCOMM channel 29, 115200 baud nominal). Stock firmware accepts a
connection only on the setup screen after a reset; the "spp" patch ([firmware.md](firmware.md)) makes it always visible and lets a second client connect.
After that patch a Linux PC can open `socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM)` to channel 29 **without pairing**. Anyone in range can, too.

Messages are plain ASCII commands, no terminator. The protocol is that of the community flashers (see the credits in [legal.md](legal.md)); everything below was seen on a real watch unless noted.

## Writing a file

(The protocol that sends a firmware package. `src/device/f3_flash.py` writes only `/user/ota/R390_WEB_FOTA.bin`; `src/device/f3x_install.py` uses the same write sequence for `/user/hub/aNN.f3x` and nothing else; the directory must exist.)

| You send | The watch answers | Meaning |
|---|---|---|
| `300` | `300` | start a transfer |
| `33bin,<path>,<length>` | `330` | announce the file; on failure `open error:-2, 331` (missing parent directory) |
| a block of up to 39600 bytes + CRC32 of the block (little endian) | `310` | repeat for each block; wait for `310` before the next |
| `32` | `320` | end of data |
| `34` (250 ms later) | `340` | close the file |

Writes are only allowed under `/user/` by the clients we know. The firmware package goes to `/user/ota/R390_WEB_FOTA.bin` (about 18 MB, 460 blocks).

**The sequence of a flash** (each stage in a session of its own; the order and the pauses were checked against the published source of an existing flasher, see [legal.md](legal.md), and `f3_flash.py` is our own code; it has flashed our watch this way):
1. Upload the package as above, then close the session.
2. About 2.2 s later, in a new session, ask for the file with `061/user/ota/R390_WEB_FOTA.bin\0` (answer within 30 s) and compare the length in the answer with the package. A different length blocks the installation.
   The optional full read-back then reads the file block by block with `062`, 0.25 s apart, comparing every byte and each block's checksum; a last `062` ends the export.
3. About 2.2 s later, in a new session, send `00AT^OTA_UPDATE`. The watch answers with 4 bytes within about 6 s, or restarts without answering (both happen). The installation cannot be cancelled.

## Reading a file

| You send | The watch answers |
|---|---|
| `061<path>\0` | `0x40` + 32-bit big-endian size, or text starting `AT^FI` when the file does not exist |
| `062` | `0x40` + 32-bit big-endian block length `n`, then `n` bytes, then 4 checksum bytes (sum of the bytes, big endian) |
| `062` once more after the last block | ends the export |

Read to the end. An export left open produces `last export had no end` in the firmware and times out later. Paths under `/nand/system/` can be read.

## Other

- `00AT^OTA_UPDATE` starts the installation of `/user/ota/R390_WEB_FOTA.bin` (see the sequence above). The watch restarts and updates itself; it cannot be cancelled.
- `30...` answers `300` (a transfer session starts), `07...` answers with an echo of the text. Neither is understood further.
- The firmware has factory command families `AT^...` (about 300 names) and `FI^...` (`START END FORMAT FORMATFACT MKDIR LS FS RM RMDIR DF CAT VI LOG SPACE NANDUSE BLOCK
  SPP_RX_BUFF FILE_CHECK`). We did not find their framing; the ones we tried (`00FI^LS=/user` and variants) got no answer. **`FORMAT`, `RM` and `RMDIR` exist: do not experiment.**

## On Linux

- Close Samsung's Galaxy Wearable app first; the watch serves one session at a time in practice.
- Connecting right after closing a session can fail with `EBUSY` or `ECONNRESET` for a few seconds: retry (`src/device/f3_link.py` does).
- Opening a session and dropping it without finishing (a half-written file, an unfinished read) left Galaxy Wearable stuck on "Updating info" once; restarting the watch fixed it.
