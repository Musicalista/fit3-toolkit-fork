# SPDX-License-Identifier: Apache-2.0
"""Tests for mkfont.py: the generated header is parsed back and looked up the way the firmware's LVGL does (cmap search of 0x2c288aac), then compared with the glyph tables.
Needs PIL and /usr/share/fonts/google-roboto/Roboto-Medium.ttf (skips without it). Run: python3 -I src/assets/test_mkfont.py"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mkfont

TTF = "/usr/share/fonts/google-roboto/Roboto-Medium.ttf"


def parse(h, name):
    p = "F3F_%s_" % name
    bmp = bytes(int(x, 16) for x in re.search(p + r"bmp\[\d+\] = \{(.*?)\};", h, re.S).group(1).replace("\n", "").replace(" ", "").strip(",").split(","))
    body = re.search(p + r"glyph\[\d+\] = \{(.*?)\n\};", h, re.S).group(1)
    glyph = [tuple(int(x) for x in m.split(",")) for m in re.findall(r"\{ ([-\d, ]+) \}", body)]
    ul = {int(i): [int(x) for x in v.split(",")] for i, v in re.findall(p + r"ul(\d+)\[\d+\] = \{ ([\d, ]+) \};", h)}
    cmaps = []
    for m in re.finditer(r"\{ (0x[0-9a-f]+), (\d+), (\d+), (\S+), 0, (\d+), (\d+), 0 \},", re.search(p + r"cmap\[\d+\] = \{(.*?)\n\};", h, re.S).group(1)):
        rs, rl, gs, ulp, n, t = m.groups(); cmaps.append(dict(start=int(rs, 16), length=int(rl), gid=int(gs), ul=ul[int(re.search(r"ul(\d+)", ulp).group(1))] if ulp != "0" else None, n=int(n), type=int(t)))
    return bmp, glyph, cmaps


def get_gid(cmaps, cp):                                  # lv_font_fmt_txt get_glyph_id as in the firmware: first cmap with (cp - start) <= range_length (unsigned)
    for c in cmaps:
        k = (cp - c["start"]) & 0xffffffff
        if k > c["length"]: continue
        if c["type"] == 2: return c["gid"] + k
        if c["type"] == 3: return c["gid"] + c["ul"].index(k) if k in c["ul"] else 0
        raise AssertionError("type")
    return 0


def unpack(bmp, off, w, h, bpp):
    out, k = [], off * 8
    for _ in range(w * h):
        v = 0
        for _ in range(bpp): v = v << 1 | (bmp[k >> 3] >> (7 - (k & 7))) & 1; k += 1
        out.append(v)
    return out


def check(bpp, size, extra=""):
    f = mkfont.build(TTF, size, extra, bpp); h = mkfont.emit(f, "T"); bmp, glyph, cmaps = parse(h, "T")
    assert bmp == f["bitmap"] and len(glyph) == len(f["glyphs"]) == len(f["cps"]) + 1
    assert glyph[0] == (0, 0, 0, 0, 0, 0)
    for cp in f["cps"]:
        g = get_gid(cmaps, cp); assert g > 0, hex(cp); src = f["glyphs"][g]
        assert src["cp"] == cp, (hex(cp), g)
        idx, adv, w, hh, x, y = glyph[g]; assert (adv, w, hh, x, y) == (src["adv"], src["w"], src["h"], src["x"], src["y"]) and idx == f["bitmap_index"][g]
        if w * hh: assert unpack(bmp, idx, w, hh, bpp) == src["px"], hex(cp)
    for cp in [0, 0x1f, 0x7f, 0xd2, 0xd4, 0xf2, 0xf4, 0x103, 0x108, 0x117, 0x11a, 0x140, 0x145, 0x159, 0x15c, 0x178, 0x17d, 0x4000, 0xffff, 0x10000]:
        if cp not in f["cps"]: assert get_gid(cmaps, cp) == 0, hex(cp)
    return f, h


def test_required_chars():
    f, h = check(2, 24)
    for c in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ" + "".join(chr(i) for i in range(0x20, 0x7f)): assert ord(c) in f["cps"]
    assert "const lv_font_t FONT_T" in h and "0x2c288d71u" in h and "0x2c288b9du" in h
    g = {c: f["glyphs"][i + 1] for i, c in enumerate(f["cps"])}
    assert g[0x20]["w"] == 0 and g[ord("M")]["adv"] > g[ord("i")]["adv"] > 0
    assert any(any(g[ord(c)]["px"]) for c in "ąĄ") and f["ascent"] + f["descent"] > 24 and f["descent"] > 0


def test_extra_and_bpp4():
    f, h = check(4, 20, "€§")
    assert 0x20ac in f["cps"] and 0xa7 in f["cps"] and max(max(g["px"] or [0]) for g in f["glyphs"]) == 15


def test_plan():
    cm = mkfont.plan_cmaps([1, 2, 3, 4, 5, 9, 12, 13, 20, 21, 22, 23, 24])
    assert [(t, a, len(l), g) for t, a, l, g in cm] == [(2, 1, 5, 1), (3, 9, 3, 6), (2, 20, 5, 9)]


if __name__ == "__main__":
    if not os.path.exists(TTF): print("SKIP: no", TTF); sys.exit(0)
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"): v(); n += 1; print("PASS", k)
    print("%d tests passed" % n)
