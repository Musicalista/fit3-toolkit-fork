# SPDX-License-Identifier: Apache-2.0
"""test_icon.py: the own app-list icon (build_package.py --icon) on the PATCHED main image of a package built with it.

    python3 -I src/firmware/fwx.py local/firmware/fit3-loader-v2.bin main local/re/main-v2.bin
    local/venv/bin/python -I src/emu/test_icon.py

Route B (docs/roadmap.md): the app-list row of the replaced entry points at an lv_img_dsc_t in the free flash instead of the image ID string "21". Checks, on the real firmware code:
the row and the descriptor are as built; the firmware's own decoder (0x2c210e04, the one that reads ID strings) refuses a non-string source without touching it; lv_img_set_src on
an image object takes the descriptor and the object gets the size 64 x 64; the built-in decoder can open it and returns our pixels. Limits: the real list builder (needs the language
state) and the display are not run, so how the icon looks in the list is only known from the PNG preview."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
from probe_lvgl import Probe, A
IMG = os.path.join(ROOT, "local/re/main-v2.bin"); ICON = os.path.join(ROOT, "build/tennis_icon.bin")

def main():
    if not (os.path.exists(IMG) and os.path.exists(ICON)): print("SKIP: need local/re/main-v2.bin and build/tennis_icon.bin (see the docstring)"); return 0
    p = Probe(IMG); e = p.e; res = []; data = open(ICON, "rb").read()
    ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    row = 0x2c300288 + 4; dsc = e.u32(row)
    ok("the World clock row (index 9, window 0x2b) points at our descriptor", e.u16(0x2c300288 + 2) == 0x2b and 0x2c3a0524 <= dsc < 0x2c3af920, hex(dsc))
    hdr, size, ptr = struct.unpack("<III", e.read(dsc, 12))
    ok("descriptor: cf 5 (true colour + alpha), 64 x 64, 12288 bytes, data follows", (hdr & 31, (hdr >> 10) & 0x7ff, hdr >> 21, size, ptr) == (5, 64, 64, 12288, dsc + 16), (hex(hdr), size, hex(ptr)))
    ok("the pixels in the image are the generated ones", e.read(ptr, 12288) == data)
    other = [e.u32(0x2c30021c + 12 * k + 4) for k in range(12) if k != 9]
    ok("the other 11 rows still point at their stock ID strings", all(0x2c000000 <= o < 0x2c3a0000 for o in other), [hex(o) for o in other][:3])
    # the firmware's own decoder must refuse a source that is not an ID string, without crashing
    hbuf = e.alloc(16, 0xcc); r = e.call(0x2c210e04, 0, dsc, hbuf)
    ok("the stock decoder's info callback rejects a non-string source (returns 0)", r == 0, r)
    # a real image object
    scr = e.call(A["obj_create"], 0); img = e.call(A["img_create"], scr); e.call(0x2c29064c, img, dsc)
    e.call(A["update_layout"], scr)
    w, h = e.call(A["get_width"], img), e.call(A["get_height"], img)
    ok("lv_img_set_src takes the descriptor: the image object is 64 x 64", (w, h) == (64, 64), (w, h))
    src_copy = e.read(img + 0x50, 16)
    ok("the object keeps a copy of the descriptor (the firmware copies 16 bytes)", struct.unpack_from("<III", src_copy)[0] == hdr and struct.unpack_from("<III", src_copy)[2] == ptr, src_copy.hex())
    # the built-in decoder opens it: lv_img_decoder_open(dsc_struct, src, color, frame)
    d = e.alloc(0x28, 0); r = e.call(0x2c27ec28, d, dsc, 0, 0)
    ok("the decoder chain opens the image (lv_img_decoder_open returns OK)", r == 1, r)
    words = [e.u32(d + 4 * i) for i in range(10)]; at = [i * 4 for i, w in enumerate(words) if w == ptr]
    imgdata = ptr if len(at) == 1 else 0                                          # the decoder descriptor holds the data pointer exactly once (at +0x18 in this build)
    ok("... and its pixel data pointer is our array (exactly one field holds it)", r == 1 and imgdata == ptr, "pointer found at offsets %s" % at)
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
