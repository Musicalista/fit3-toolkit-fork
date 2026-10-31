# SPDX-License-Identifier: Apache-2.0
"""lvfont.py: decoder for LVGL binary fonts (lv_font_conv --format bin), the format of /nand/system/font/FONT_ROBOTO_*_GBK_en.bin on the Fit3.
    python3 -I lvfont.py <font.bin> "text" <out.png> [scale]        render text with the font's own glyphs (anti-aliased, light on dark)
Layout: [u32 length]["head"|"cmap"|"loca"|"glyf"|"kern"][table data]; glyphs are bit-packed (advance, x, y, w, h, then w*h pixels of `bpp` bits)."""
import struct, sys

class BitReader:
    def __init__(self, data, pos=0): self.d, self.bit = data, pos * 8
    def u(self, n):
        v = 0
        for _ in range(n): v = (v << 1) | ((self.d[self.bit >> 3] >> (7 - (self.bit & 7))) & 1); self.bit += 1
        return v
    def s(self, n):
        v = self.u(n); return v - (1 << n) if v >> (n - 1) else v

class Font:
    def __init__(self, data):
        self.d = data; self.t = {}; pos = 0
        while pos + 8 <= len(data):
            ln, tag = struct.unpack_from("<I4s", data, pos)
            if ln < 8 or pos + ln > len(data) + 3: break
            self.t[tag.decode("latin-1")] = (pos, ln); pos += ln
        o = self.t["head"][0] + 8
        (self.version, self.ntables, self.size, self.ascent, self.descent, self.typo_asc, self.typo_desc, self.typo_gap, self.min_y, self.max_y,
         self.def_adv, self.kern_scale, self.loc_fmt, self.gid_fmt, self.adv_fmt, self.bpp, self.xy_bits, self.wh_bits, self.adv_bits, self.comp,
         self.subpx, _pad, self.ul_pos, self.ul_thick) = struct.unpack_from("<IHHHhHhHhhHHBBBBBBBBBBhH", data, o)
        assert self.comp == 0, "compressed glyph bitmaps (compression_id=%d) are not supported" % self.comp
        self._cmap(); self._loca()
    def _cmap(self):
        p, ln = self.t["cmap"]; n = struct.unpack_from("<I", self.d, p + 8)[0]; self.maps = []
        for i in range(n):
            off, rs, rl, gs, cnt, fmt, _ = struct.unpack_from("<IIHHHBB", self.d, p + 12 + i * 16)
            self.maps.append((p + off, rs, rl, gs, cnt, fmt))
    def _loca(self):
        p, ln = self.t["loca"]; n = struct.unpack_from("<I", self.d, p + 8)[0]
        f, sz = ("<H", 2) if self.loc_fmt == 0 else ("<I", 4)
        self.loca = [struct.unpack_from(f, self.d, p + 12 + i * sz)[0] for i in range(n)]
        self.glyf = self.t["glyf"][0]                                  # loca offsets count from the start of the glyf table (its first glyph is at 8)
    def gid(self, cp):
        for base, rs, rl, gs, cnt, fmt in self.maps:
            if not (rs <= cp < rs + rl): continue
            k = cp - rs
            if fmt == 0:  return gs + self.d[base + k] if self.d[base + k] else 0                         # format0_full (u8 offsets)
            if fmt == 2:  return gs + k                                                                   # format0_tiny
            lst = struct.unpack_from("<%dH" % cnt, self.d, base)                                          # sparse: u16 code offsets
            if k in lst:
                i = lst.index(k)
                return gs + i if fmt == 3 else struct.unpack_from("<H", self.d, base + 2 * cnt + 2 * i)[0]  # sparse_tiny / sparse_full
        return 0
    def glyph(self, cp):
        g = self.gid(cp)
        if g == 0 or g >= len(self.loca): return None
        r = BitReader(self.d, self.glyf + self.loca[g])
        adv = r.u(self.adv_bits); x = r.s(self.xy_bits); y = r.s(self.xy_bits); w = r.u(self.wh_bits); h = r.u(self.wh_bits)
        px = [r.u(self.bpp) for _ in range(w * h)]
        return {"adv": adv / 16.0 if self.adv_fmt == 1 else adv, "x": x, "y": y, "w": w, "h": h, "px": px}
    def render(self, text, scale=1):
        from PIL import Image
        gl = [self.glyph(ord(c)) for c in text]; width = sum((g["adv"] if g else self.size // 2) for g in gl) + 4
        im = Image.new("L", (int(width) + 4, self.ascent - self.descent + 4), 0); x = 2.0; top = 2 + self.ascent; levels = (1 << self.bpp) - 1
        for g in gl:
            if not g: x += self.size // 2; continue
            for j in range(g["h"]):
                for i in range(g["w"]):
                    v = g["px"][j * g["w"] + i]
                    px, py = int(x) + g["x"] + i, top - g["y"] - g["h"] + j
                    if v and 0 <= px < im.width and 0 <= py < im.height: im.putpixel((px, py), v * 255 // levels)
            x += g["adv"]
        return im.resize((im.width * scale, im.height * scale), Image.NEAREST) if scale > 1 else im

if __name__ == "__main__":
    f = Font(open(sys.argv[1], "rb").read())
    print("size %d ascent %d descent %d bpp %d adv_fmt %d loc_fmt %d cmaps %d glyphs %d" % (f.size, f.ascent, f.descent, f.bpp, f.adv_fmt, f.loc_fmt, len(f.maps), len(f.loca)))
    f.render(sys.argv[2], int(sys.argv[4]) if len(sys.argv) > 4 else 1).save(sys.argv[3])
