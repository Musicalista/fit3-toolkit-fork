# SPDX-License-Identifier: Apache-2.0
"""Tests for lvres.py / lvlang.py. Synthetic data always; with local/assets/images/app_worldclock.res and local/re/main-stock.bin
(your own copies, git-ignored) it also checks the real pack. Run: python3 -I src/assets/test_lvres.py"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
import lvres, lvlang


def hdr(cf, w, h): return struct.pack("<I", cf | w << 10 | h << 21)

def idx8(w, h, pal):                                   # pal: list of (r, g, b, a); pixels count up
    pb = b"".join(bytes((b, g, r, a)) for r, g, b, a in pal)
    return hdr(0x1b, w, h) + b"IDX8IDX8" + struct.pack(">HHHH", w, h, len(pb), 0) + bytes(i % len(pal) for i in range(w * h)) + pb

def rgb565a(w, h): return hdr(5, w, h) + b"".join(struct.pack("<HB", 0xf800, 0x80) for _ in range(w * h))


def test_synthetic_pack():
    a, b = idx8(4, 3, [(1, 2, 3, 255), (255, 0, 0, 0)]), rgb565a(2, 2)
    recs = lvres.walk(a + b + a)
    assert [(r["cf"], r["w"], r["h"], r["size"]) for r in recs] == [(27, 4, 3, len(a)), (5, 2, 2, len(b)), (27, 4, 3, len(a))]
    w, h, px = lvres.to_rgba(a + b, recs[0]); assert (w, h) == (4, 3) and px[:8] == bytes((1, 2, 3, 255, 255, 0, 0, 0))
    w, h, px = lvres.to_rgba(a + b, recs[1]); assert px[:4] == bytes((255, 0, 0, 0x80))
    assert [r["pos"] for r in lvres.walk(a + b, [(0, len(a)), (len(a), len(b))])] == [0, len(a)]
    try: lvres.walk(hdr(9, 2, 2) + bytes(8)); assert False
    except ValueError: pass


def test_synthetic_lang():
    strings = [b"alpha", b"beta", b"gamma"]; blob = b"".join(s + b"\0" for s in strings); offs = [0, 6, 11]
    n = len(strings); font_off = 0x18 + 8 * n + len(blob); fdata = b"FONTDATA"
    d = struct.pack("<HHIIIII", 1, 0, n, len(blob), 0x18, 1, font_off) + b"".join(struct.pack("<II", o, 7) for o in offs) + blob \
        + struct.pack("<III", font_off + 12, len(fdata), 7) + fdata
    L = lvlang.Lang(d); assert [L.string(i) for i in range(3)] == ["alpha", "beta", "gamma"] and L.font_key(1) == 7
    L2 = lvlang.Lang(L.set_string(1, "Tennis")); assert [L2.string(i) for i in range(3)] == ["alpha", "Tennis", "gamma"]
    o, s, k = L2.fonts[0]; assert L2.d[o:o + s] == fdata and k == 7


def test_real_pack():
    p = os.path.join(ROOT, "local/assets/images/app_worldclock.res"); fw = os.path.join(ROOT, "local/re/main-stock.bin")
    if not os.path.exists(p): print("  (no local app_worldclock.res: skipped)"); return
    data = open(p, "rb").read(); recs = lvres.walk(data)
    assert len(recs) == 7 and sum(r["size"] for r in recs) == len(data)
    assert [(r["cf"], r["w"], r["h"]) for r in recs][:2] == [(27, 256, 189), (5, 178, 132)]
    for r in recs: w, h, px = lvres.to_rgba(data, r); assert len(px) == w * h * 4
    if os.path.exists(fw):
        F = lvres.Firmware(open(fw, "rb").read())
        assert F.locate(1264)[0].endswith("app_worldclock.res") and F.locate(21)[0].endswith("app_applist.res")
        assert [(r["pos"], r["size"]) for r in recs] == F.pack_table(1264, 1270)         # the firmware table and the self-sizing walk agree
        wc = [r for r in F.applist() if r["key"] == 10][0]; assert wc["icon_id"] == 21 and wc["app_id"] == 0x2b and wc["text_id"] == 181


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
