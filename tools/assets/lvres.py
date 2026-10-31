# SPDX-License-Identifier: Apache-2.0
"""lvres.py: decoder for the Fit3 image packs (/nand/system/image/*.res) and helper for the firmware's image-ID tables (docs/details.md).

    python3 -I lvres.py info  <pack.res> [--fw main.bin --first-id N]     list the records (id, offset, size, format, w x h)
    python3 -I lvres.py png   <pack.res> <outdir> [--fw main.bin --first-id N]   write one PNG per record (needs Pillow)
    python3 -I lvres.py ids   <main.bin> [<id>]                           print the pack table / the pack and record of one ID (reads the firmware image you give it)
    python3 -I lvres.py icons <main.bin>                                  print the app-list rows: key, app id, icon ID, text ID

A pack is a plain concatenation of records, with no directory. Every record is `lv_img_header_t (4 bytes, little endian) | body`, and the header is
`cf:5 | zero:3 | reserved:2 | w:11 | h:11`. The firmware loads the body as is and lets the draw code interpret it. Formats seen in app_worldclock.res:
  cf 0x1b (27)  Samsung "IDX8":  b"IDX8" b"IDX8" | w u16 BE | h u16 BE | palette bytes u16 BE | 0 u16 | w*h palette indices | palette (B,G,R,A per colour)
  cf 5          TRUE_COLOR_CHROMA_KEYED/ALPHA flavour, 3 bytes per pixel: RGB565 little endian, then alpha (the firmware also accepts cf 4 and 6 and 0x15..0x1a: not seen)
Both are self-sizing, so a pack can be walked without any table. For other cf values give the firmware's {offset,size} table (--fw): record boundaries then come from it.
Nothing of Samsung's is stored here: the tables are read from the firmware image you pass in."""
import struct, sys, os

FW_BASE = 0x2c080000
PACK_TABLE, PACK_COUNT = 0x2c300a84, 52          # {path ptr, first id, last id}, 12 bytes each, sorted by id
ID_TABLE, ID_COUNT = 0x2c300cf4, 0x116a          # per ID {offset in its pack, record size incl. 4-byte header}, 8 bytes each
APPLIST_TABLE, APPLIST_ROWS = 0x2c30021c, 12     # flash template of the app-list rows, 12 bytes each

CF_IDX8 = 0x1b
CF_RGB565A = (4, 5)


def parse_header(h):
    return dict(cf=h & 31, w=(h >> 10) & 0x7ff, h=h >> 21)


def record_size(data, pos, hdr):
    """total size of the record starting at `pos` (header included), or None when the format's size is unknown"""
    cf, w, h = hdr["cf"], hdr["w"], hdr["h"]
    if cf == CF_IDX8:
        if data[pos + 4:pos + 12] != b"IDX8IDX8": raise ValueError("bad IDX8 tag at %d" % pos)
        w2, h2, pal = struct.unpack_from(">HHH", data, pos + 12)
        if (w2, h2) != (w, h): raise ValueError("IDX8 size mismatch at %d" % pos)
        return 4 + 16 + w * h + pal
    if cf in CF_RGB565A: return 4 + w * h * 3
    return None


def walk(data, table=None):
    """records of a pack as dicts {pos, size, cf, w, h}; `table` = [(offset, size)] from the firmware overrides the self-sizing walk"""
    out = []
    if table is not None:
        for off, size in table:
            hdr = parse_header(struct.unpack_from("<I", data, off)[0]); hdr.update(pos=off, size=size); out.append(hdr)
        return out
    pos = 0
    while pos + 4 <= len(data):
        hdr = parse_header(struct.unpack_from("<I", data, pos)[0]); size = record_size(data, pos, hdr)
        if size is None: raise ValueError("unknown format cf=%d at offset %d: pass the firmware table (--fw)" % (hdr["cf"], pos))
        hdr.update(pos=pos, size=size); out.append(hdr); pos += size
    if pos != len(data): raise ValueError("pack does not tile exactly (%d != %d)" % (pos, len(data)))
    return out


def to_rgba(data, rec):
    """(w, h, RGBA bytes) of one record"""
    p, cf, w, h = rec["pos"], rec["cf"], rec["w"], rec["h"]
    if cf == CF_IDX8:
        pal = struct.unpack_from(">H", data, p + 16)[0]; px = data[p + 20:p + 20 + w * h]; pb = data[p + 20 + w * h:p + 20 + w * h + pal]
        lut = [(pb[i + 2], pb[i + 1], pb[i], pb[i + 3]) for i in range(0, len(pb) - 3, 4)]
        out = bytearray()
        for i in px: out += bytes(lut[i] if i < len(lut) else (0, 0, 0, 0))
        return w, h, bytes(out)
    if cf in CF_RGB565A:
        b = data[p + 4:p + 4 + w * h * 3]; out = bytearray()
        for i in range(0, len(b), 3):
            v = b[i] | b[i + 1] << 8
            out += bytes(((v >> 11 & 31) * 255 // 31, (v >> 5 & 63) * 255 // 63, (v & 31) * 255 // 31, b[i + 2]))
        return w, h, bytes(out)
    raise ValueError("cannot decode cf=%d" % cf)


class Firmware:
    """the image-ID tables of a main firmware image (best1502x_b319_user.bin); pass the file you extracted yourself"""
    def __init__(self, image):
        self.d = image
    def u32(self, a): return struct.unpack_from("<I", self.d, a - FW_BASE)[0]
    def cstr(self, a):
        p = (a & 0x2fffffff) - FW_BASE; return self.d[p:self.d.index(b"\0", p)].decode("latin1")   # 0x0c.. is an alias of 0x2c..
    def packs(self):
        return [(self.cstr(self.u32(PACK_TABLE + 12 * i)), self.u32(PACK_TABLE + 12 * i + 4), self.u32(PACK_TABLE + 12 * i + 8)) for i in range(PACK_COUNT)]
    def locate(self, i):
        """(pack path, offset in pack, record size) of image ID i"""
        if not 0 <= i < ID_COUNT: raise ValueError("ID out of range (decoder rejects >= 0x116a)")
        for path, a, b in self.packs():
            if a <= i <= b: return path, self.u32(ID_TABLE + 8 * i), self.u32(ID_TABLE + 8 * i + 4)
        raise ValueError("ID in no pack")
    def pack_table(self, first, last):
        return [(self.u32(ID_TABLE + 8 * i), self.u32(ID_TABLE + 8 * i + 4)) for i in range(first, last + 1)]
    def applist(self):
        """app-list rows: dicts {key, app_id, icon_id, text_id}; `key` 10 is World clock (the code logs "app_list worldclock key")"""
        rows = []
        for i in range(APPLIST_ROWS):
            a = APPLIST_TABLE + 12 * i; k, _, app = struct.unpack_from("<BBh", self.d, a - FW_BASE)
            rows.append(dict(key=k, app_id=app, icon_id=int(self.cstr(self.u32(a + 4))), text_id=struct.unpack_from("<H", self.d, a + 8 - FW_BASE)[0]))
        return rows


def _png(path, w, h, rgba):
    from PIL import Image
    Image.frombytes("RGBA", (w, h), rgba).save(path)


def main(a):
    if len(a) < 2: print(__doc__); return 1
    cmd = a[0]; opt = lambda n: a[a.index(n) + 1] if n in a else None
    if cmd in ("ids", "icons"):
        fw = Firmware(open(a[1], "rb").read())
        if cmd == "icons":
            for r in fw.applist(): print(r)
        elif len(a) > 2: print(fw.locate(int(a[2], 0)))
        else:
            for p in fw.packs(): print(*p)
        return 0
    data = open(a[1], "rb").read(); table = None
    if opt("--fw"):
        fw = Firmware(open(opt("--fw"), "rb").read()); first = int(opt("--first-id"), 0)
        last = next(l for p, f, l in fw.packs() if f == first); table = fw.pack_table(first, last)
    recs = walk(data, table)
    for n, r in enumerate(recs):
        print("%d\toffset %d\tsize %d\tcf %d\t%dx%d" % (n, r["pos"], r["size"], r["cf"], r["w"], r["h"]))
        if cmd == "png":
            os.makedirs(a[2], exist_ok=True)
            try: _png(os.path.join(a[2], "rec_%04d.png" % n), *to_rgba(data, r))
            except ValueError as e: print("  skipped:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
