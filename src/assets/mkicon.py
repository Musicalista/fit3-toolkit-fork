# SPDX-License-Identifier: Apache-2.0
"""mkicon.py: draws our own icons (tennis ball, app grid, plus, die; each on a coloured disc) in the style of the stock icons, as the raw body of an LVGL image.

    python3 -I src/assets/mkicon.py build/tennis_icon.bin [build/tennis_icon.png] [--kind tennis|hub|counter|dice]

`draw(kind, size)` + `encode` give the 64 x 64 app-list icon; `draw(kind, 64)` + `encode_indexed4` give the 64 x 64 four-bit icons of the hub list (2,112 bytes each).

Stock icons of the app list (docs/details.md, measured on a watch; nothing of Samsung's is stored here): 64 x 64, a disc that touches the four edges, a
soft vertical gradient (the top is about 16/11/35 steps lighter than the bottom in R/G/B), a flat glyph, anti-aliased. This drawing is original artwork.

Output: 64 * 64 * 3 bytes, per pixel RGB565 little endian then alpha (LVGL's LV_IMG_CF_TRUE_COLOR_ALPHA at 16-bit colour, header cf 5), ready for
`build_package.py --icon`. The optional PNG is a preview. Needs numpy; Pillow only for the preview."""
import struct, sys
import numpy as np

SIZE, SS = 64, 8                                    # the app-list icon: 64 x 64; 8 x 8 samples per pixel
# kind -> disc gradient (top, bottom); the glyph is drawn by GLYPHS[kind] in 64-unit coordinates
KINDS = {"tennis": ((46, 128, 222), (30, 93, 182)),     # court blue
         "hub": ((64, 196, 150), (28, 140, 108)),       # green
         "counter": ((250, 168, 44), (226, 118, 22)),   # orange
         "dice": ((154, 104, 232), (104, 60, 190)),     # purple
         "mars": ((214, 96, 52), (150, 52, 30))}        # rust red
WHITE = (255, 255, 255)


def _rr(x, y, cx, cy, hw, hh, r):
    """rounded rectangle mask: centre (cx, cy), half sizes hw, hh, corner radius r"""
    dx = np.maximum(np.abs(x - cx) - (hw - r), 0); dy = np.maximum(np.abs(y - cy) - (hh - r), 0)
    return dx * dx + dy * dy <= r * r


def _glyph_tennis(x, y, rgb):
    ball = ((x - 32) ** 2 + (y - 32) ** 2) <= 21.0 ** 2                       # yellow-green ball with two white seams
    seam = (np.abs(np.hypot(x - (32 - 27), y - 32) - 19.5) <= 1.7) | (np.abs(np.hypot(x - (32 + 27), y - 32) - 19.5) <= 1.7)
    rgb = np.where(ball[..., None], np.array((214, 232, 66), float), rgb)
    return np.where((ball & seam)[..., None], np.array(WHITE, float), rgb)


def _glyph_hub(x, y, rgb):
    m = np.zeros(x.shape, bool)
    for cx in (23.0, 41.0):
        for cy in (23.0, 41.0): m |= _rr(x, y, cx, cy, 7.0, 7.0, 3.5)           # four white tiles, the shape of an app grid
    return np.where(m[..., None], np.array(WHITE, float), rgb)


def _glyph_counter(x, y, rgb):
    m = _rr(x, y, 32, 32, 5.0, 19.0, 2.5) | _rr(x, y, 32, 32, 19.0, 5.0, 2.5)    # a bold plus
    return np.where(m[..., None], np.array(WHITE, float), rgb)


def _glyph_dice(x, y, rgb):
    rgb = np.where(_rr(x, y, 32, 32, 19.0, 19.0, 7.0)[..., None], np.array(WHITE, float), rgb)   # a white die with the five-face pattern
    dots = np.zeros(x.shape, bool)
    for dx, dy in ((-10, -10), (10, -10), (0, 0), (-10, 10), (10, 10)): dots |= ((x - 32 - dx) ** 2 + (y - 32 - dy) ** 2) <= 3.6 ** 2
    return np.where(dots[..., None], np.array(KINDS["dice"][1], float), rgb)


def _glyph_mars(x, y, rgb):
    planet = ((x - 32) ** 2 + (y - 32) ** 2) <= 20.0 ** 2                      # a pale planet with two craters and a green patch (terraforming)
    rgb = np.where(planet[..., None], np.array((255, 214, 178), float), rgb)
    for cx, cy, r in ((24, 26, 4.5), (40, 40, 3.5)):
        rgb = np.where((planet & (((x - cx) ** 2 + (y - cy) ** 2) <= r * r))[..., None], np.array((222, 160, 120), float), rgb)
    patch = planet & (((x - 38) ** 2 + (y - 25) ** 2) <= 6.5 ** 2)
    return np.where(patch[..., None], np.array((86, 190, 98), float), rgb)


GLYPHS = {"mars": _glyph_mars, "tennis": _glyph_tennis, "hub": _glyph_hub, "counter": _glyph_counter, "dice": _glyph_dice}


def draw(kind="tennis", size=SIZE):
    """RGB (size x size x 3, ints) and alpha (size x size) of the icon `kind`, drawn in 64-unit coordinates and scaled to `size` pixels"""
    top, bottom = KINDS[kind]
    n = size * SS
    c = (np.arange(n) + 0.5) / SS * (SIZE / size)   # sample positions in 64-unit icon coordinates
    x, y = np.meshgrid(c, c)
    disc = ((x - 32) ** 2 + (y - 32) ** 2) <= 32.0 ** 2
    t = (y / SIZE)[..., None]
    rgb = GLYPHS[kind](x, y, np.array(top, float) * (1 - t) + np.array(bottom, float) * t)
    a = disc.astype(float)
    # box filter down to size x size, colour weighted by alpha
    def down(v): return v.reshape(size, SS, size, SS, *v.shape[2:]).mean(axis=(1, 3))
    A = down(a); C = down(rgb * a[..., None])
    out = np.where(A[..., None] > 0, C / np.maximum(A[..., None], 1e-9), 0)
    return np.clip(np.rint(out), 0, 255).astype(int), np.clip(np.rint(A * 255), 0, 255).astype(int)


def encode_indexed4(rgb, alpha):
    """LV_IMG_CF_INDEXED_4BIT body (cf 9): 16 palette entries (B, G, R, A bytes; entry 0 is fully transparent), then 4 bits per pixel, the left pixel in the high nibble, rows padded to bytes.
    The palette is a deterministic k-means of the premultiplied colours, so a flat-coloured icon keeps its colours and the soft edge of the disc gets a few partly transparent entries."""
    h, w = alpha.shape
    px = np.concatenate([rgb * alpha[..., None] / 255.0, alpha[..., None]], axis=2).reshape(-1, 4).astype(float)     # premultiplied r, g, b + alpha
    solid = px[:, 3] >= 8
    pts = px[solid]; k = 15
    rng = np.random.default_rng(1); cent = [pts[rng.integers(len(pts))]]
    for _ in range(k - 1):                                                   # k-means++ seeding
        d = np.min([((pts - c) ** 2).sum(axis=1) for c in cent], axis=0); cent.append(pts[np.argmax(d)])
    cent = np.array(cent)
    for _ in range(40):
        lab = np.argmin(((pts[:, None, :] - cent[None]) ** 2).sum(axis=2), axis=1)
        for i in range(k):
            if (lab == i).any(): cent[i] = pts[lab == i].mean(axis=0)
    pal = bytearray(4 * 16)                                                  # entry 0 stays zero: transparent
    for i, c in enumerate(cent, 1):
        a = max(1.0, c[3]); r, g, b = (np.clip(c[:3] * 255.0 / a, 0, 255) if a > 0 else (0, 0, 0))
        pal[4 * i:4 * i + 4] = bytes((int(round(b)), int(round(g)), int(round(r)), int(round(min(255, a)))))
    idx = np.zeros(len(px), int); idx[solid] = np.argmin(((pts[:, None, :] - cent[None]) ** 2).sum(axis=2), axis=1) + 1
    idx = idx.reshape(h, w); stride = (w + 1) // 2; body = bytearray(h * stride)
    for yy in range(h):
        for xx in range(w): body[yy * stride + xx // 2] |= int(idx[yy, xx]) << (4 if xx % 2 == 0 else 0)
    return bytes(pal) + bytes(body)


def encode(rgb, alpha):
    body = bytearray()
    for yy in range(SIZE):
        for xx in range(SIZE):
            r, g, b = (int(v) for v in rgb[yy, xx])
            v = ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255)
            body += struct.pack("<HB", v, int(alpha[yy, xx]))
    return bytes(body)


def preview(body, path, scale=4):
    SIZE = int((len(body) // 3) ** 0.5)
    from PIL import Image
    im = Image.new("RGBA", (SIZE, SIZE))
    for i in range(SIZE * SIZE):
        v, a = struct.unpack_from("<HB", body, i * 3)
        im.putpixel((i % SIZE, i // SIZE), (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31, a))
    bg = Image.new("RGBA", (SIZE * scale, SIZE * scale), (40, 40, 40, 255)); big = im.resize((SIZE * scale, SIZE * scale), Image.NEAREST); bg.paste(big, (0, 0), big)
    bg.convert("RGB").save(path)


if __name__ == "__main__":
    args = sys.argv[1:]; kind = "tennis"
    if "--kind" in args: i = args.index("--kind"); kind = args[i + 1]; del args[i:i + 2]
    if not args: sys.exit(__doc__)
    body = encode(*draw(kind)); open(args[0], "wb").write(body)
    print("wrote %s, %d bytes" % (args[0], len(body)))
    if len(args) > 1: preview(body, args[1]); print("preview", args[1])
