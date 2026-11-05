# SPDX-License-Identifier: Apache-2.0
"""mkfont.py: turn a TTF into a C header with a static const LVGL 8.3 bitmap font for the Fit3 firmware's own LVGL (docs/details.md; the watch code is freestanding, no .data/.bss).
    python3 -I mkfont.py <font.ttf> <px size> <out.h> --name KB24 [--chars "extra chars"] [--bpp 2|4]
The header defines `H const lv_font_t FONT_<name>` (H comes from src/watch/ui.h, which must be included first) and covers ASCII 0x20..0x7e, the Polish letters and --chars.
Structure layouts were read from the firmware's own lv_font_load (0x2c288010) and lv_font_get_glyph_dsc_fmt_txt / lv_font_get_bitmap_fmt_txt (0x2c288d70, 0x2c288b9c, helper 0x2c288aac):
  lv_coord_t is int32 here, so lv_font_t is 32 bytes: get_glyph_dsc +0, get_glyph_bitmap +4, line_height +8, base_line +0xc, subpx:2 +0x10, underline_position +0x11, underline_thickness +0x12, dsc +0x14, fallback +0x18, user_data +0x1c.
  lv_font_fmt_txt_dsc_t (24 bytes): glyph_bitmap +0, glyph_dsc +4, cmaps +8, kern_dsc +0xc, kern_scale u16 +0x10, u16 +0x12 = cmap_num:9 | bpp:4 << 9 | kern_classes:1 << 13 | bitmap_format:2 << 14, cache +0x14
  (the firmware writes through `cache` when it is not NULL, so it is NULL: the font stays in flash).
  glyph_dsc (16 bytes): bitmap_index u32, adv_w u32 (1/16 px), box_w u16, box_h u16, ofs_x s16, ofs_y s16.
  cmap (20 bytes): range_start u32, range_length u16 (the last valid offset: the firmware accepts offset <= range_length), glyph_id_start u16, unicode_list ptr, glyph_id_ofs_list ptr, list_length u16, type u8 (+ pad).
  Types used: 2 = FORMAT0_TINY (gid = start + offset), 3 = SPARSE_TINY (gid = start + index in the sorted u16 offset list). Glyph 0 is the empty "no glyph"."""
import os, sys

POLISH = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
TINY, SPARSE = 2, 3
RUN_MIN = 4                                            # a run of consecutive code points this long becomes a FORMAT0_TINY cmap


def charset(extra="", polish=True):
    return sorted({ord(c) for c in (chr(i) for i in range(0x20, 0x7f))} | ({ord(c) for c in POLISH} if polish else set()) | {ord(c) for c in extra})


def ttf_codepoints(path):
    """the code points a TrueType font maps to a glyph (cmap formats 4 and 12), so that a missing letter is refused instead of drawn as an empty box"""
    import struct
    d = open(path, "rb").read(); n = struct.unpack_from(">H", d, 4)[0]; cm = None
    for i in range(n):
        tag, _, off, ln = struct.unpack_from(">4sIII", d, 12 + 16 * i)
        if tag == b"cmap": cm = off
    assert cm is not None, "no cmap table in %s" % path
    out = set(); k = struct.unpack_from(">H", d, cm + 2)[0]
    for i in range(k):
        pid, eid, off = struct.unpack_from(">HHI", d, cm + 4 + 8 * i); t = cm + off; fmt = struct.unpack_from(">H", d, t)[0]
        if fmt == 4:
            sc = struct.unpack_from(">H", d, t + 6)[0] // 2; ends = struct.unpack_from(">%dH" % sc, d, t + 14); starts = struct.unpack_from(">%dH" % sc, d, t + 16 + 2 * sc)
            for a, b in zip(starts, ends):
                if a != 0xffff: out |= set(range(a, b + 1))
        elif fmt == 12:
            ng = struct.unpack_from(">I", d, t + 12)[0]
            for g in range(ng):
                a, b, _ = struct.unpack_from(">III", d, t + 16 + 12 * g); out |= set(range(a, b + 1))
    return out


def plan_cmaps(cps):
    """cps sorted unique. Glyph ids are 1.. in code point order, so each cmap is a consecutive slice of them: [(type, first_cp, [cps], glyph_id_start)]"""
    segs, i = [], 0
    while i < len(cps):
        j = i
        while j + 1 < len(cps) and cps[j + 1] == cps[j] + 1: j += 1
        segs.append((i, j + 1))                        # slice [i, j+1) is one run of consecutive code points
        i = j + 1
    out, sparse = [], []                               # a sparse cmap stores offsets from its first code point as u16: emoji (U+1Fxxx) start a new one
    def flush():
        if sparse: out.append((SPARSE, sparse[0][0][0], [c for s in sparse for c in s[0]], sparse[0][1])); sparse.clear()
    for a, b in segs:
        if b - a >= RUN_MIN: flush(); out.append((TINY, cps[a], cps[a:b], a + 1))
        else:
            if sparse and cps[b - 1] - sparse[0][0][0] > 0xffff: flush()
            sparse.append((cps[a:b], a + 1))
    flush()
    return out


def render(ttf, size, cps, bpp):
    """-> (ascent, descent, glyphs) with glyphs[0] the empty glyph; each glyph: dict(cp, adv, w, h, x, y, bits (list of pixel levels)), adv in 1/16 px, y = offset of the bottom above the baseline"""
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(ttf, size); asc, desc = f.getmetrics(); mx = (1 << bpp) - 1
    gl = [dict(cp=0, adv=0, w=0, h=0, x=0, y=0, px=[])]
    for cp in cps:
        ch = chr(cp); adv = int(round(f.getlength(ch) * 16)); pad = size; base = asc + size          # PIL's getbbox includes the advance box, so the ink box is measured on a canvas
        cv = Image.new("L", (int(adv / 16) + 2 * pad + 2, base + desc + size), 0); ImageDraw.Draw(cv).text((pad, base), ch, font=f, fill=255, anchor="ls")
        bb = cv.getbbox()
        if bb is None: gl.append(dict(cp=cp, adv=adv, w=0, h=0, x=0, y=0, px=[])); continue
        im = cv.crop(bb); w, h = im.size
        gl.append(dict(cp=cp, adv=adv, w=w, h=h, x=bb[0] - pad, y=base - bb[3], px=[(v * mx + 127) // 255 for v in im.tobytes()]))
    return asc, desc, gl


def pack(px, bpp):
    n = len(px) * bpp; out = bytearray((n + 7) // 8); k = 0
    for v in px:
        for s in range(bpp - 1, -1, -1):
            if (v >> s) & 1: out[k >> 3] |= 0x80 >> (k & 7)
            k += 1
    return bytes(out)


def build(ttf, size, extra="", bpp=2, polish=True, emoji_ttf=None, emoji="", emoji_size=None):
    """emoji: characters drawn from a second font (emoji_ttf, a monochrome one such as Noto Emoji) at emoji_size px, on the same baseline, merged into the one font"""
    cps = charset(extra, polish); missing = [chr(c) for c in cps if c not in ttf_codepoints(ttf)]
    if missing: raise SystemExit("%s has no glyph for: %s" % (os.path.basename(ttf), " ".join(missing)))
    asc, desc, gl = render(ttf, size, cps, bpp)
    ecps = sorted({ord(c) for c in emoji} - set(cps))
    if ecps:
        assert emoji_ttf, "emoji need emoji_ttf"
        em = [chr(c) for c in ecps if c not in ttf_codepoints(emoji_ttf)]
        if em: raise SystemExit("%s has no glyph for: %s" % (os.path.basename(emoji_ttf), " ".join(em)))
        _, _, eg = render(emoji_ttf, emoji_size or size, ecps, bpp)
        merged = sorted(gl[1:] + eg[1:], key=lambda g: g["cp"]); gl = [gl[0]] + merged; cps = [g["cp"] for g in merged]
    bitmap = bytearray(b"\0"); idx = [0]    # byte 0 belongs to glyph 0
    for g in gl[1:]:
        b = pack(g["px"], bpp); idx.append(len(bitmap) if b else 0); bitmap += b
    return dict(size=size, bpp=bpp, ascent=asc, descent=desc, cps=cps, glyphs=gl, bitmap_index=idx, bitmap=bytes(bitmap), cmaps=plan_cmaps(cps))


def emit(font, name):
    gl, cm = font["glyphs"], font["cmaps"]; p = "F3F_%s_" % name; L = []
    L += ["/* generated by src/assets/mkfont.py: %d px, %d bpp, %d glyphs, %d cmaps, %d bitmap bytes. Include after ui.h. */" % (font["size"], font["bpp"], len(gl) - 1, len(cm), len(font["bitmap"])),
          "#ifndef F3_FONT_TYPES", "#define F3_FONT_TYPES",
          "typedef struct { u32 bitmap_index, adv_w; u16 box_w, box_h; short ofs_x, ofs_y; } lv_font_fmt_txt_glyph_dsc_t;",
          "typedef struct { u32 range_start; u16 range_length, glyph_id_start; const u16 *unicode_list; const void *glyph_id_ofs_list; u16 list_length; u8 type, pad; } lv_font_fmt_txt_cmap_t;",
          "typedef struct { const u8 *glyph_bitmap; const lv_font_fmt_txt_glyph_dsc_t *glyph_dsc; const lv_font_fmt_txt_cmap_t *cmaps; const void *kern_dsc; u16 kern_scale, flags; void *cache; } lv_font_fmt_txt_dsc_t;",
          "typedef struct { u32 get_glyph_dsc, get_glyph_bitmap; i32 line_height, base_line; u8 subpx; signed char underline_position; u8 underline_thickness, pad; const void *dsc, *fallback, *user_data; } lv_font_t;",
          "_Static_assert(sizeof(lv_font_fmt_txt_glyph_dsc_t) == 16 && sizeof(lv_font_fmt_txt_cmap_t) == 20 && sizeof(lv_font_fmt_txt_dsc_t) == 24 && sizeof(lv_font_t) == 32, \"firmware LVGL layout\");",
          "#endif", ""]
    L.append("H const u8 %sbmp[%d] = {" % (p, len(font["bitmap"])))
    b = font["bitmap"]; L += ["  " + ",".join("0x%02x" % v for v in b[i:i + 24]) + "," for i in range(0, len(b), 24)]; L.append("};")
    L.append("H const lv_font_fmt_txt_glyph_dsc_t %sglyph[%d] = {" % (p, len(gl)))
    for g, ix, in zip(gl, font["bitmap_index"]):
        L.append("  { %d, %d, %d, %d, %d, %d }, /* %s */" % (ix, g["adv"], g["w"], g["h"], g["x"], g["y"], "none" if not g["cp"] else "U+%04X" % g["cp"]))
    L.append("};")
    for i, (t, first, lst, gid) in enumerate(cm):
        if t == SPARSE: L.append("H const u16 %sul%d[%d] = { %s };" % (p, i, len(lst), ", ".join(str(c - first) for c in lst)))
    L.append("H const lv_font_fmt_txt_cmap_t %scmap[%d] = {" % (p, len(cm)))
    for i, (t, first, lst, gid) in enumerate(cm):
        L.append("  { 0x%x, %d, %d, %s, 0, %d, %d, 0 }," % (first, lst[-1] - first if t == SPARSE else len(lst) - 1, gid, "%sul%d" % (p, i) if t == SPARSE else "0", len(lst) if t == SPARSE else 0, t))
    L.append("};")
    L.append("H const lv_font_fmt_txt_dsc_t %sdsc = { %sbmp, %sglyph, %scmap, 0, 0, %d | (%d << 9), 0 };" % (p, p, p, p, len(cm), font["bpp"]))
    ul = max(1, font["size"] // 16)
    L.append("H const lv_font_t FONT_%s = { 0x2c288d71u, 0x2c288b9du, %d, %d, 0, -%d, %d, 0, &%sdsc, 0, 0 };" % (name, font["ascent"] + font["descent"], font["descent"], ul, ul, p))
    return "\n".join(L) + "\n"


def main(argv):
    if len(argv) < 3 or "--name" not in argv: sys.exit(__doc__)
    ttf, size, out = argv[0], int(argv[1]), argv[2]; name = argv[argv.index("--name") + 1]
    extra = argv[argv.index("--chars") + 1] if "--chars" in argv else ""; bpp = int(argv[argv.index("--bpp") + 1]) if "--bpp" in argv else 2
    assert bpp in (2, 4)
    f = build(ttf, size, extra, bpp); open(out, "w").write(emit(f, name))
    m = {c: g for c, g in zip(f["cps"], f["glyphs"][1:])}
    print("wrote %s: %d glyphs, %d cmaps, bitmap %d bytes, line_height %d base_line %d, adv M %.2f i %.2f px" % (out, len(f["cps"]), len(f["cmaps"]), len(f["bitmap"]), f["ascent"] + f["descent"], f["descent"], m[77]["adv"] / 16, m[105]["adv"] / 16))

if __name__ == "__main__": main(sys.argv[1:])
