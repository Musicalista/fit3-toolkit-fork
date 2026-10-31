# SPDX-License-Identifier: Apache-2.0
"""fwd.py: read, edit and rebuild Fit3 FWD firmware packages (see docs/firmware.md for the format).

    p = Package.load("stock-aza3.bin")
    raw = p.raw("/user/ota/app/best1502x_b319_user.bin")       # content of a component
    p.set_raw(path, new_raw)                                   # re-zips it and fixes the CRCs
    p.save("out.bin")                                          # repairs offsets, sizes and every checksum

Unchanged components are copied byte for byte, so load()+save() reproduces a package exactly (tools/firmware/test_fwd.py checks that).
The updater is never touched. Only single-entry deflate ZIPs without a data descriptor are supported, which is what the packages use."""
import io, struct, zipfile, zlib

MAIN = "/user/ota/app/best1502x_b319_user.bin"
u16 = lambda d, o: struct.unpack_from("<H", d, o)[0]
u32 = lambda d, o: struct.unpack_from("<I", d, o)[0]
p32 = lambda v: struct.pack("<I", v)
crc32 = lambda d: zlib.crc32(d) & 0xffffffff


def unzip_single(z):
    """(name, content) of a ZIP that holds one file"""
    zf = zipfile.ZipFile(io.BytesIO(z)); assert len(zf.namelist()) == 1; return zf.namelist()[0], zf.read(zf.namelist()[0])

def rezip_single(z, raw, level=9):
    """the same ZIP (name, timestamps and extra fields included) with `raw` as its content"""
    nl, el = u16(z, 26), u16(z, 28); assert u16(z, 6) & 8 == 0 and u16(z, 8) == 8, "expects deflate and no data descriptor"
    start = 30 + nl + el; cd = z.rfind(b"PK\x01\x02"); eo = z.rfind(b"PK\x05\x06"); assert len(z) == eo + 22 and cd > start
    co = zlib.compressobj(level, zlib.DEFLATED, -15); data = co.compress(raw) + co.flush()
    local, central, eocd = bytearray(z[:start]), bytearray(z[cd:eo]), bytearray(z[eo:eo + 22])
    for hdr, at in ((local, 14), (central, 16)):
        hdr[at:at + 4] = p32(crc32(raw)); hdr[at + 4:at + 8] = p32(len(data)); hdr[at + 8:at + 12] = p32(len(raw))
    eocd[12:16] = p32(len(central)); eocd[16:20] = p32(start + len(data))
    return bytes(local) + data + bytes(central) + bytes(eocd)

def zip_usize(z): return u32(z, z.rfind(b"PK\x01\x02") + 24)

def main_image_crc(raw):
    """the CRC32 kept at 0x1008 of the main image: over the image with bytes 0..3 = 0xff and 0x1000..0x100f = 0"""
    n = bytearray(raw[:u32(raw, 0x100c)]); n[0:4] = b"\xff" * 4; n[0x1000:0x1010] = b"\0" * 16; return crc32(bytes(n))

def fix_main_crc(raw):
    raw = bytearray(raw); raw[0x1008:0x100c] = p32(main_image_crc(raw)); return bytes(raw)


class Package:
    def __init__(self): self.head = b""; self.updater = b""; self.pkt_head = b""; self.entries = []; self.zips = []; self.crcs = []; self.index = {}
    @classmethod
    def load(cls, path):
        b = open(path, "rb").read(); assert u32(b, 0) == 0x7e5a5a60, "not an FWD package"
        p = cls(); off, size = u32(b, 84), u32(b, 88); pk = b[off:off + size]
        assert crc32(pk) == u32(b, off + size), "packet CRC"
        p.head, p.updater, p.pkt_head = b[:92], b[92:off], pk[:80]
        n = pk[70]; end = 80 + n * 128; assert crc32(pk[:end]) == u32(pk, end), "catalogue CRC"
        cur = end + 4
        for i in range(n):
            e = bytearray(pk[80 + i * 128:80 + (i + 1) * 128]); st, sz = u32(e, 4), u32(e, 8); assert st == cur, "components must be contiguous"
            p.entries.append(e); p.zips.append(pk[st:st + sz]); p.crcs.append(pk[st + sz:st + sz + 4]); cur = st + sz + 4
            p.index[bytes(e[12:128]).split(b"\0")[0].decode()] = i
        assert cur == len(pk); return p
    def paths(self): return list(self.index)
    def raw(self, path): return unzip_single(self.zips[self.index[path]])[1]
    def set_raw(self, path, raw, level=9):
        i = self.index[path]; self.zips[i] = rezip_single(self.zips[i], raw, level); self.crcs[i] = p32(crc32(raw))
    def to_bytes(self):
        ents, body, cur = [], b"", 80 + len(self.entries) * 128 + 4; fw = res = 0
        for e, z, c in zip(self.entries, self.zips, self.crcs):
            e = bytearray(e); e[4:8] = p32(cur); e[8:12] = p32(len(z)); ents.append(bytes(e)); body += z + c; cur += len(z) + 4
            if u16(e, 0): fw += zip_usize(z)
            else: res += zip_usize(z)
        ph = bytearray(self.pkt_head); ph[72:76] = p32(fw); ph[76:80] = p32(res)
        cat = bytes(ph) + b"".join(ents); pk = cat + p32(crc32(cat)) + body
        head = bytearray(self.head); head[88:92] = p32(len(pk))
        return bytes(head) + self.updater + pk + p32(crc32(pk))
    def save(self, path): open(path, "wb").write(self.to_bytes())
