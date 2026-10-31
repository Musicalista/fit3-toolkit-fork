# SPDX-License-Identifier: Apache-2.0
"""make_flat_pkg.py: derive a firmware package whose app loader keeps its files directly in /user/ (the watch has no /user/apps/ directory and nothing creates it).

Changes exactly two NUL-terminated strings in the main image and repairs the checksums (via fwd.py):
    /user/apps/index.txt -> /user/a_index.txt       (app list)
    /user/apps/          -> /user/a_                (prefix of /user/apps/<id>.f3a)
The loader copies both strings until the NUL, so a shorter string is fine. Nothing else in the main image changes except the image CRC in its header.
usage: python3 -I make_flat_pkg.py <in.bin> <out.bin>      then run validate_fwd.py on the result."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fwd

EDITS = [  # (offset in the main image, old bytes, new bytes of the same length)
    (0x32393c, b"/user/apps/index.txt\0", b"/user/a_index.txt".ljust(21, b"\0")),
    (0x32395a, b"/user/apps/\0",          b"/user/a_".ljust(12, b"\0")),
]

def build(src, dst):
    p = fwd.Package.load(src); raw = bytearray(p.raw(fwd.MAIN))
    for o, old, new in EDITS:
        assert len(old) == len(new) and bytes(raw[o:o + len(old)]) == old, "unexpected bytes at %#x (is this fit3-store-base-spp.bin?)" % o
        raw[o:o + len(new)] = new
    p.set_raw(fwd.MAIN, fwd.fix_main_crc(raw)); p.save(dst); print("wrote", dst, os.path.getsize(dst), "bytes")

if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
