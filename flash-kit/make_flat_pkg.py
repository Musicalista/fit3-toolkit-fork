"""make_flat_pkg.py: derive a firmware package whose app loader keeps its files directly in /user/ (the watch has no /user/apps/ directory and nothing creates it).

Reads fit3-store-base-spp.bin (FWD package), changes exactly two NUL-terminated strings in the main image, repairs every checksum and writes a new package:
    /user/apps/index.txt -> /user/a_index.txt       (app list)
    /user/apps/          -> /user/a_                (prefix of /user/apps/<id>.f3a)
The loader copies both strings until the NUL, so a shorter string is fine. Nothing else in the main image changes except the image CRC in its header.
usage: python3 -I make_flat_pkg.py <in.bin> <out.bin>      then run validate_fwd.py on the result."""
import io, struct, sys, zipfile, zlib

u32 = lambda d, o: struct.unpack_from("<I", d, o)[0]
p32 = lambda v: struct.pack("<I", v)
crc = lambda d: zlib.crc32(d) & 0xffffffff
MAIN_PATH = "/user/ota/app/best1502x_b319_user.bin"
EDITS = [  # (offset in the main image, old bytes, new bytes of the same length)
    (0x32393c, b"/user/apps/index.txt\0", b"/user/a_index.txt".ljust(21, b"\0")),
    (0x32395a, b"/user/apps/\0",          b"/user/a_".ljust(12, b"\0")),
]

def build(src, dst):
    b = open(src, "rb").read()
    assert u32(b, 0) == 0x7e5a5a60
    upd_len, off, size = u32(b, 80), u32(b, 84), u32(b, 88)
    head, updater_blk = b[:92], b[92:off]                     # updater + its CRC are copied untouched
    pk = b[off:off + size]; assert crc(pk) == u32(b, off + size)
    n = pk[70]; end = 80 + n * 128; assert crc(pk[:end]) == u32(pk, end)
    entries = [bytearray(pk[80 + i * 128:80 + (i + 1) * 128]) for i in range(n)]
    comps = []                                                 # (zip bytes, raw CRC bytes) per component, catalogue order
    cur = end + 4
    for e in entries:
        st, sz = u32(e, 4), u32(e, 8); assert st == cur
        comps.append([pk[st:st + sz], pk[st + sz:st + sz + 4]]); cur = st + sz + 4
    assert cur == len(pk)
    mains = [i for i, e in enumerate(entries) if bytes(e[12:128]).split(b"\0")[0].decode() == MAIN_PATH]
    assert len(mains) == 1; mi = mains[0]
    z = comps[mi][0]; nl = struct.unpack_from("<H", z, 26)[0]
    raw = bytearray(zipfile.ZipFile(io.BytesIO(z)).read(z[30:30 + nl].decode()))
    for o, old, new in EDITS:
        assert len(old) == len(new) and bytes(raw[o:o + len(old)]) == old, "unexpected bytes at %#x" % o
        raw[o:o + len(new)] = new
    size_img = u32(raw, 0x100c); norm = bytearray(raw[:size_img]); norm[0:4] = b"\xff" * 4; norm[0x1000:0x1010] = b"\0" * 16
    raw[0x1008:0x100c] = p32(crc(bytes(norm)))                 # image CRC in the main header
    raw = bytes(raw)
    co = zlib.compressobj(9, zlib.DEFLATED, -15); data = co.compress(raw) + co.flush()
    cd = z.rfind(b"PK\x01\x02"); eo = z.rfind(b"PK\x05\x06")
    lh = bytearray(z[:30 + nl]); cdr = bytearray(z[cd:eo]); eocd = bytearray(z[eo:eo + 22]); assert len(z) == eo + 22
    for hdr, base in ((lh, 14), (cdr, 16)):
        hdr[base:base + 4] = p32(crc(raw)); hdr[base + 4:base + 8] = p32(len(data)); hdr[base + 8:base + 12] = p32(len(raw))
    eocd[12:16] = p32(len(cdr)); eocd[16:20] = p32(30 + nl + len(data))
    comps[mi] = [bytes(lh) + data + bytes(cdr) + bytes(eocd), p32(crc(raw))]
    body, cur = b"", end + 4
    for e, (zz, c4) in zip(entries, comps):
        e[4:8] = p32(cur); e[8:12] = p32(len(zz)); body += zz + c4; cur += len(zz) + 4
    cat = pk[:80] + b"".join(bytes(e) for e in entries)
    new_pk = cat + p32(crc(cat)) + body
    new_head = bytearray(head); new_head[88:92] = p32(len(new_pk))
    out = bytes(new_head) + updater_blk + new_pk + p32(crc(new_pk))
    open(dst, "wb").write(out)
    print("wrote", dst, len(out), "bytes; main component", len(z), "->", len(comps[mi][0]), "bytes")

if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
