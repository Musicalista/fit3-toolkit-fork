# SPDX-License-Identifier: Apache-2.0
"""gb_send.py: send a Game Boy ROM to the watch's Game Boy app (src/watch/apps/gameboy.c). Writes only /user/gb/rom.gb, and only a file that passes the checks the app makes
(header checksum, size = 32 KB << byte 0x148, at most 1 MB, not a Color-only game); then reconnects, reads it back and compares. Open the Game Boy app once first (it creates /user/gb).

    python3 -I src/device/gb_send.py game.gb [--addr AA:BB:CC:DD:EE:FF]

Use only ROMs you have the right to use (homebrew, or dumps of your own cartridges)."""
import argparse, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import f3_link as L, f3_flash as F

PATH = "/user/gb/rom.gb"; MAX = 1 << 20


def check(d):
    """-> the title; raises L.Error for anything the watch app would refuse"""
    if len(d) < 0x150: raise L.Error("too short for a Game Boy ROM")
    if d[0x148] > 5: raise L.Error("ROM size code %d is not supported (at most 1 MB)" % d[0x148])
    if len(d) != 0x8000 << d[0x148]: raise L.Error("the file is %d bytes, its header says %d" % (len(d), 0x8000 << d[0x148]))
    x = 0
    for i in range(0x134, 0x14d): x = (x - d[i] - 1) & 0xff
    if x != d[0x14d]: raise L.Error("bad header checksum: not a Game Boy ROM")
    if d[0x143] == 0xc0: raise L.Error("a Game Boy Color-only game (the watch app emulates the original Game Boy)")
    return bytes(c for c in d[0x134:0x144] if 32 <= c < 127).decode().strip() or "Game Boy ROM"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("rom"); ap.add_argument("--addr", default=L.ADDR); a = ap.parse_args(argv)
    try:
        data = open(a.rom, "rb").read(); title = check(data); print("ROM       %s  %r  %d bytes" % (a.rom, title, len(data)))
        link = L.open_link(a.addr)
        try: F.write_file(link, data, PATH, progress=lambda d, t: print("  %d/%d bytes" % (d, t), end="\r", flush=True))
        finally: link.close()
        print(); time.sleep(2.2); link = L.open_link(a.addr)
        try: got = L.read_raw(link, PATH, limit=MAX)
        finally: link.close()
        if got != data: raise L.Error("the file on the watch differs: try again")
        print("sent %r: open the Game Boy app on the watch" % title); return 0
    except L.Error as e: print("ERROR: %s" % e); return 1


if __name__ == "__main__": sys.exit(main())
