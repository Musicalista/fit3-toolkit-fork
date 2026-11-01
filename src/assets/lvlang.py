# SPDX-License-Identifier: Apache-2.0
"""lvlang.py: reader/editor for the Fit3 language packs (language_<lang>.res; layout in docs/details.md).

    python3 -I lvlang.py <language_xx.res> [id ...]       print the strings with the given IDs (or the first 20)
    python3 -I lvlang.py <language_xx.res> --fonts        list the embedded fonts (key, offset, size, lv_font_conv size)

The file on the watch (/nand/system/font/language_xx.res) is a one-entry ZIP; the firmware unzips it to /user/language.res and loads that. Pass either form.
Layout of the unzipped file (all little endian):
  header 0x18: u16 version(=1), u16 0, u32 count, u32 blob_size, u32 header_size(=0x18), u32 nfonts, u32 font_table_offset (= 0x18 + count*8 + blob_size)
  count * {u32 string offset in the blob, u32 font key}   indexed by text ID
  blob: NUL-terminated UTF-8 strings
  nfonts * {u32 file offset, u32 size, u32 key}           each font is a complete lv_font_conv --format bin font (lvfont.py reads it)
  font data
"""
import io, struct, sys, zipfile


class Lang:
    def __init__(self, data):
        if data[:4] == b"PK\x03\x04":
            z = zipfile.ZipFile(io.BytesIO(data)); data = z.read(z.namelist()[0])
        self.d = data
        self.version, self.count, self.blob_size, self.hdr_size, self.nfonts, self.font_off = struct.unpack_from("<I5I", data, 0)
        self.version &= 0xffff
        self.idt = [list(struct.unpack_from("<II", data, 0x18 + 8 * i)) for i in range(self.count)]
        self.blob_off = 0x18 + 8 * self.count
        assert self.font_off == self.blob_off + self.blob_size, "unexpected layout"
        self.fonts = [list(struct.unpack_from("<III", data, self.font_off + 12 * i)) for i in range(self.nfonts)]

    def string(self, i):
        o = self.blob_off + self.idt[i][0]; return self.d[o:self.d.index(b"\0", o)].decode("utf-8")

    def font_key(self, i): return self.idt[i][1]

    def set_string(self, i, text):
        """new file bytes where string `i` is `text`: appended to the blob, so every later offset (font table, fonts) shifts; the old text stays unused"""
        add = text.encode("utf-8") + b"\0"; d = self.d
        head = bytearray(d[:0x18 + 8 * self.count]); idt_end = len(head)
        blob = d[self.blob_off:self.blob_off + self.blob_size]
        struct.pack_into("<I", head, 0x18 + 8 * i, len(blob))
        struct.pack_into("<I", head, 8, len(blob) + len(add)); struct.pack_into("<I", head, 20, self.font_off + len(add))
        rest = bytearray(d[self.font_off:])
        for k in range(self.nfonts): struct.pack_into("<I", rest, 12 * k, self.fonts[k][0] + len(add))
        return bytes(head) + blob + add + bytes(rest)


def main(a):
    if not a: print(__doc__); return 1
    L = Lang(open(a[0], "rb").read())
    if "--fonts" in a:
        sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
        import lvfont
        for o, s, k in sorted(L.fonts, key=lambda f: f[2]):
            print(k, o, s, "size", lvfont.Font(L.d[o:o + s]).size)
        return 0
    ids = [int(x, 0) for x in a[1:]] or range(20)
    for i in ids: print(i, L.font_key(i), repr(L.string(i)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
