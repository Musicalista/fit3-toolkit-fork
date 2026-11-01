# SPDX-License-Identifier: Apache-2.0
"""Tests of the .f3x builder and parser (f3x.py). Needs arm-none-eabi-gcc and numpy. python3 -I src/f3x/test_f3x_format.py"""
import os, struct, sys, tempfile, zlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "assets")); sys.path.insert(0, os.path.join(HERE, "..", "watch"))
import f3x, mkicon, gen
n_ok = 0
def check(cond, what):
    global n_ok
    if not cond: sys.exit("FAIL: " + what)
    n_ok += 1; print("  ok  ", what)
def fails(fn, text=""):
    try: fn()
    except f3x.Error as e: return text in str(e)
    return False
APPS = os.path.join(HERE, "..", "watch", "apps"); wd = tempfile.mkdtemp(); GEN = gen.generate(list(gen.APPS), False, os.path.join(wd, "gen"))
ICON = mkicon.encode_indexed4(*mkicon.draw("counter", 64))
img, off, rel = f3x.compile_app(os.path.join(APPS, "counter.c"), wd, [GEN])
check(len(img) % 4 == 0 and rel and all(o % 4 == 0 for o in rel) and rel == sorted(set(rel)), "the image is word sized; the relocations are distinct, ascending, word aligned")
img2, off2, rel2 = f3x.compile_app(os.path.join(APPS, "counter.c"), tempfile.mkdtemp(), [GEN])
check((img, off, rel) == (img2, off2, rel2), "building twice gives the same image (reproducible)")
words = [struct.unpack_from("<I", img, o)[0] for o in rel]
check(all(f3x.LINK_BASE <= v < f3x.LINK_BASE + len(img) for v in words), "every relocated word is an address inside the image (linked at %#x)" % f3x.LINK_BASE)
app = struct.unpack_from("<5I", img, off)
check(all(f3x.LINK_BASE <= v < f3x.LINK_BASE + len(img) for v in (app[0], app[2], app[3], app[4])) and app[1] == 0, "the App struct: name, create, back, destroy point into the image; no icon")
data = f3x.pack("Counter", img, off, rel, ICON); d = f3x.parse(data)
check(d["name"] == "Counter" and d["image"] == img and d["relocs"] == rel and d["icon"] == ICON and d["app_off"] == off, "pack then parse gives everything back")
check(len(data) == 64 + 2112 + len(img) + len(f3x.varints(rel)) and data[:4] == b"F3X1", "the layout: 64-byte header, icon, image, relocations")
check(f3x.unvarints(f3x.varints([0, 4, 8, 4096, 4100, 1 << 20])) == [0, 4, 8, 4096, 4100, 1 << 20], "delta varints round-trip, also over the 7-bit and 14-bit boundaries")
bad = bytearray(data); bad[100] ^= 1
check(fails(lambda: f3x.parse(bytes(bad)), "CRC"), "a changed byte of the icon is caught by the CRC")
bad = bytearray(data); bad[-1] ^= 1; check(fails(lambda: f3x.parse(bytes(bad)), "CRC"), "a changed byte of the relocations is caught by the CRC")
bad = bytearray(data); struct.pack_into("<I", bad, 8, 0x12345678); check(fails(lambda: f3x.parse(bytes(bad)), "another firmware"), "another firmware id is refused")
check(fails(lambda: f3x.parse(data[:-3]), "bytes"), "a truncated file is refused"); check(fails(lambda: f3x.parse(b"F3X1" + bytes(100))), "an empty header is refused")
check(fails(lambda: f3x.pack("x" * 24, img, off, rel, ICON)) and fails(lambda: f3x.pack("", img, off, rel, ICON)) and fails(lambda: f3x.pack("Café", img, off, rel, ICON)), "names: 1 to 23 printable ASCII characters")
check(fails(lambda: f3x.pack("A", img, off, rel, ICON[:-1])), "the icon must be exactly 2,112 bytes")
# apps the toolchain must refuse
def src(text): p = os.path.join(tempfile.mkdtemp(), "bad.c"); open(p, "w").write('#include "ui.h"\n' + text); return p
GOOD = '__attribute__((unused)) static void *c(lv_obj_t *r) { (void)r; return 0; } __attribute__((unused)) static int b(void *s) { (void)s; return 0; } __attribute__((unused)) static void d(void *s) { (void)s; }\n'
def refuses(code, text): return fails(lambda: f3x.compile_app(src(GOOD + code), tempfile.mkdtemp(), [GEN]), text)
check(refuses('static int st[4]; static void *c2(lv_obj_t *r) { (void)r; st[0]++; return st; } APP_EXPORT(x, "X", 0, c2, b, d)', "must not have"), "a global variable (.bss) is refused")
check(refuses('static int tbl[4] = {1, 2, 3, 4}; static void *c3(lv_obj_t *r) { (void)r; tbl[0]++; return tbl; } APP_EXPORT(x, "X", 0, c3, b, d)', "must not have"), "an initialised writable table (.data) is refused")
check(refuses('extern void *memcpy(void *, const void *, unsigned); static void d2(void *s) { memcpy(s, (char *)s + 64, 32); } APP_EXPORT(x, "X", 0, c, b, d2)', "undefined"), "a call to libc is refused")
check(refuses('static void unused(void) {}', ""), "a source without APP_EXPORT is refused")
ok = f3x.compile_app(src(GOOD + 'APP_EXPORT(x, "X", 0, c, b, d)'), tempfile.mkdtemp(), [GEN]); check(ok[1] % 4 == 0, "a minimal app builds")
for name in gen.APPS:
    i, o, r = f3x.compile_app(os.path.join(APPS, name + ".c"), tempfile.mkdtemp(), [GEN]); check(f3x.parse(f3x.pack(f3x.default_name(os.path.join(APPS, name + ".c")), i, o, r, ICON))["name"], "%s builds as an .f3x (%d bytes image)" % (name, len(i)))
print("all %d checks passed" % n_ok)
