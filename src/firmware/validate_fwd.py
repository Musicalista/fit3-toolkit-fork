# SPDX-License-Identifier: Apache-2.0
"""Independent re-implementation of fit3-flasher's validatePackage (structure + every CRC32 + updater SHA-256). usage: validate_fwd.py file..."""
import hashlib, io, struct, sys, zipfile, zlib
STOCK_VER = b"R390XXU0AZA3"; UPD_SHA = "122d0946e0776e9e6b01b300da3be077f47fa97acd44ddf501c302518eb069e4"
u32 = lambda d, o: struct.unpack_from("<I", d, o)[0]
u16 = lambda d, o: struct.unpack_from("<H", d, o)[0]
crc = lambda d: zlib.crc32(d) & 0xffffffff
def need(ok, what):
    if not ok: raise SystemExit("  FAIL: " + what)
    print("  ok   " + what)
def validate(path):
    b = open(path, "rb").read(); print(path.split("/")[-1], len(b), "bytes, sha256", hashlib.sha256(b).hexdigest()[:16])
    need(u32(b, 0) == 0x7e5a5a60, "FWD magic")
    need(b[4:68].split(b"\0")[0] == STOCK_VER and u32(b, 72) == 2, "source version R390XXU0AZA3, flags 2")
    hdr, upd, off, size = u32(b, 76), u32(b, 80), u32(b, 84), u32(b, 88)
    need(hdr == 92 and 0 < upd <= 0x38000 and off == hdr + upd + 4 and size >= 80 and off + size + 4 == len(b), "container layout (header/updater/packet offsets)")
    updater, packet = b[hdr:off - 4], b[off:off + size]
    need(crc(updater) == u32(b, off - 4), "updater CRC32")
    need(crc(packet) == u32(b, off + size), "packet CRC32")
    need(hashlib.sha256(updater).hexdigest() == UPD_SHA, "updater is the stock updater (SHA-256)")
    need(u32(packet, 0) == 0x7e5a5a5a and packet[69] == 0x18, "packet magic / format byte")
    need(packet[4:68].split(b"\0")[0] == STOCK_VER, "target version R390XXU0AZA3")
    n = packet[70]; end = 80 + n * 128
    need(crc(packet[:end]) == u32(packet, end), "component catalogue CRC32 (%d components)" % n)
    cur, fw, res, mains, bad, seen = end + 4, 0, 0, 0, 0, set()
    for i in range(n):
        o = 80 + i * 128; kind, attr = u16(packet, o), u16(packet, o + 2); start, stored = u32(packet, o + 4), u32(packet, o + 8)
        p = packet[o + 12:o + 128].split(b"\0")[0].decode()
        ok = start == cur and stored > 0 and start + stored + 4 <= len(packet) and p.lower() not in seen and ((kind == 0 and attr == 0x34) or (kind in (1, 4, 7) and attr == 0x74))
        z = zipfile.ZipFile(io.BytesIO(packet[start:start + stored])); raw = z.read(z.namelist()[0])     # zipfile verifies the member CRC
        ok = ok and crc(raw) == u32(packet, start + stored); seen.add(p.lower())
        if kind == 1:
            mains += 1; sz = u32(raw, 0x100c); nm = bytearray(raw[:sz]); nm[0:4] = b"\xff" * 4; nm[0x1000:0x1010] = b"\0" * 16
            mok = u32(raw, 0x1000) == 0x11223344 and u32(raw, 0x1004) == 0xdeaddead and crc(bytes(nm)) == u32(raw, 0x1008)
            print("  %s main image header + CRC32 (%s)" % ("ok  " if mok else "FAIL", p)); ok = ok and mok
        if kind: fw += len(raw)
        else: res += len(raw)
        bad += not ok; cur = start + stored + 4
        if not ok: print("  FAIL component", i, p)
    need(bad == 0, "all %d components: ZIP CRC + stored CRC32 + layout" % n)
    need(cur == len(packet) and mains == 1 and fw == u32(packet, 72) and res == u32(packet, 76), "no gaps; one main image; sizes match header")
for f in sys.argv[1:]: validate(f); print()
