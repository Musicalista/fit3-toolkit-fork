"""mkicon.py: draws our own app-list icon (a tennis ball on a blue disc) in the style of the stock icons, as the raw body of an LVGL image.

    python3 -I tools/assets/mkicon.py build/tennis_icon.bin [build/tennis_icon.png]

Stock icons of the app list (docs/research/T3-resources.md, measured on a watch; nothing of Samsung's is stored here): 64 x 64, a disc that touches the four edges, a
soft vertical gradient (the top is about 16/11/35 steps lighter than the bottom in R/G/B), a flat glyph, anti-aliased. This drawing is original artwork.

Output: 64 * 64 * 3 bytes, per pixel RGB565 little endian then alpha (LVGL's LV_IMG_CF_TRUE_COLOR_ALPHA at 16-bit colour, header cf 5), ready for
`build_package.py --icon`. The optional PNG is a preview. Needs numpy; Pillow only for the preview."""
import struct, sys
import numpy as np

SIZE, SS = 64, 8                                    # 8 x 8 samples per pixel
TOP, BOTTOM = (46, 128, 222), (30, 93, 182)         # disc gradient (court blue)
BALL, SEAM = (214, 232, 66), (255, 255, 255)        # tennis-ball yellow-green and white seams


def draw():
    n = SIZE * SS
    c = (np.arange(n) + 0.5) / SS                   # pixel-centre coordinates in icon units
    x, y = np.meshgrid(c, c)
    disc = ((x - 32) ** 2 + (y - 32) ** 2) <= 32.0 ** 2
    t = (y / SIZE)[..., None]
    rgb = np.array(TOP, float) * (1 - t) + np.array(BOTTOM, float) * t
    ball = ((x - 32) ** 2 + (y - 32) ** 2) <= 21.0 ** 2
    seam = (np.abs(np.hypot(x - (32 - 27), y - 32) - 19.5) <= 1.7) | (np.abs(np.hypot(x - (32 + 27), y - 32) - 19.5) <= 1.7)
    rgb = np.where(ball[..., None], np.array(BALL, float), rgb)
    rgb = np.where((ball & seam)[..., None], np.array(SEAM, float), rgb)
    a = disc.astype(float)
    # box filter down to 64 x 64, colour weighted by alpha
    def down(v): return v.reshape(SIZE, SS, SIZE, SS, *v.shape[2:]).mean(axis=(1, 3))
    A = down(a); C = down(rgb * a[..., None])
    out = np.where(A[..., None] > 0, C / np.maximum(A[..., None], 1e-9), 0)
    return np.clip(np.rint(out), 0, 255).astype(int), np.clip(np.rint(A * 255), 0, 255).astype(int)


def encode(rgb, alpha):
    body = bytearray()
    for yy in range(SIZE):
        for xx in range(SIZE):
            r, g, b = (int(v) for v in rgb[yy, xx])
            v = ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255)
            body += struct.pack("<HB", v, int(alpha[yy, xx]))
    return bytes(body)


def preview(body, path, scale=4):
    from PIL import Image
    im = Image.new("RGBA", (SIZE, SIZE))
    for i in range(SIZE * SIZE):
        v, a = struct.unpack_from("<HB", body, i * 3)
        im.putpixel((i % SIZE, i // SIZE), (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31, a))
    bg = Image.new("RGBA", (SIZE * scale, SIZE * scale), (40, 40, 40, 255)); big = im.resize((SIZE * scale, SIZE * scale), Image.NEAREST); bg.paste(big, (0, 0), big)
    bg.convert("RGB").save(path)


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    body = encode(*draw()); open(sys.argv[1], "wb").write(body)
    print("wrote %s, %d bytes" % (sys.argv[1], len(body)))
    if len(sys.argv) > 2: preview(body, sys.argv[2]); print("preview", sys.argv[2])
