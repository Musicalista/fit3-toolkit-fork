# SPDX-License-Identifier: Apache-2.0
import gzip, struct, sys
d = gzip.open("/usr/lib/kbd/consolefonts/lat1-12.psfu.gz").read()
if d[:4] == b"\x72\xb5\x4a\x86":
    hs, fl, n, bpg, h, w = struct.unpack("<6I", d[8:32]); off = hs
else:
    assert d[:2] == b"\x36\x04"; n = 512 if d[2] & 1 else 256; bpg = d[3]; h = bpg; w = 8; off = 4
assert w == 8 and h == 12, (w, h)
rows = []
for cp in range(32, 127):
    g = d[off + cp * bpg: off + (cp + 1) * bpg]; rows.append("{" + ",".join("0x%02x" % b for b in g) + "}")
open(sys.argv[1], "w").write("#include <stdint.h>\n#define KBD_FONT_N_ASCII 95\nstatic const uint8_t kbd_font[95][12] = {\n" + ",\n".join(rows) + "\n};\nstatic const uint16_t kbd_font_extra_cp[1] = {0};\n")
