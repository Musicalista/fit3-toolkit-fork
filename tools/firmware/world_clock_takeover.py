# SPDX-License-Identifier: Apache-2.0
"""world_clock_takeover.py: stage 1 of docs/roadmap.md. Makes the stock *World clock* list entry open the loader's menu on top of its own page, and renames the entry.

    python3 -I world_clock_takeover.py <fit3-store-base-spp-flat.bin> <out.bin> [--label Tennis]

1. app_worldclock_init has two ways to build its page: for `param & 0xff == 0x67` it calls app_worldclock_tile_init (the tile; left alone), otherwise `bl 0x2c1ebfdc`
   (0x2c1ecd30), the full page that the app list opens. That second call is replaced by `bl stub`.
2. The stub (32 bytes in free flash at 0x2c3a4530) calls the original builder, so the stock page and its state stay intact, then does what the loader's own hook does:
   lv_timer_create(callback 0x2c3a1ab9, 80 ms, root), with root = **r4 (the context the caller keeps in r4). The callback deletes the timer and calls the loader's menu_open(root),
   which draws its menu on top.
3. Every "World Clock" label in the English language files becomes the label (default "Tennis"), padded with NULs to the same length.
The first try hooked the tile call instead; the app list never reaches it (docs/status.md). Addresses are those of R390XXU0AZA3 and the loader of fit3-store-base-spp; every
assumption is checked before anything is written. See docs/firmware.md."""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fwd

BASE = 0x2c080000
HOOK, ORIG_CALLEE = 0x2c1ecd30, 0x2c1ebfdc
STUB = 0x2c3a4530
CALLBACK, TIMER_CREATE, MENU_OPEN = 0x2c3a1ab9, 0x2c28a3f1, 0x2c3a1a54
DELAY_MS = 80
LANG = re.compile(r"^/nand/system/font/language_en(_r[A-Z]{2})?\.res$")

def decode_bl(raw, vma):
    h1, h2 = struct.unpack_from("<HH", raw, vma - BASE)
    if (h1 & 0xF800) != 0xF000 or (h2 & 0xD000) != 0xD000: return None
    s = (h1 >> 10) & 1; i1 = ~((h2 >> 13) ^ s) & 1; i2 = ~((h2 >> 11) ^ s) & 1
    off = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3FF) << 12) | ((h2 & 0x7FF) << 1)
    return vma + 4 + (off - (1 << 25) if s else off)

def encode_bl(src, dst):
    off = dst - (src + 4); assert off % 2 == 0 and -(1 << 24) <= off < (1 << 24)
    s = 1 if off < 0 else 0; off &= 0x1FFFFFF; i1, i2 = (off >> 23) & 1, (off >> 22) & 1
    j1, j2 = ~(i1 ^ s) & 1, ~(i2 ^ s) & 1
    return struct.pack("<HH", 0xF000 | (s << 10) | ((off >> 12) & 0x3FF), 0xD000 | (j1 << 13) | (j2 << 11) | ((off >> 1) & 0x7FF))

def stub_code():
    """push {r3,lr}; bl ORIG_CALLEE; ldr r3,[r4]; ldr r2,[r3]; ldr r0,=CALLBACK; movs r1,#DELAY; ldr r3,=TIMER_CREATE; blx r3; pop {r3,pc}; .word CALLBACK, TIMER_CREATE
    (the pc-relative loads at +10 and +14 reach the words at +20 and +24)"""
    code = struct.pack("<H", 0xB508) + encode_bl(STUB + 2, ORIG_CALLEE) + struct.pack("<6H", 0x6823, 0x681A, 0x4802, 0x2100 | DELAY_MS, 0x4B02, 0x4798) + struct.pack("<H", 0xBD08)
    assert len(code) == 20; return code + struct.pack("<II", CALLBACK, TIMER_CREATE)

def build(src, dst, label):
    old, new = b"World Clock\0", label.encode("ascii") + b"\0"
    assert len(new) <= len(old), "the label must be at most 11 characters"
    p = fwd.Package.load(src); raw = bytearray(p.raw(fwd.MAIN)); at = lambda vma: vma - BASE
    # --- checks: this is the package we analysed
    assert decode_bl(raw, HOOK) == ORIG_CALLEE, "no `bl app_worldclock_tile_init` at the hook site (already patched, or another version?)"
    assert struct.unpack_from("<H", raw, at(MENU_OPEN))[0] == 0xB573 and struct.unpack_from("<H", raw, at(CALLBACK & ~1))[0] == 0xB510, "the loader's menu_open / callback are not where expected"
    assert struct.unpack_from("<H", raw, at(TIMER_CREATE & ~1))[0] == 0xB5F8, "lv_timer_create is not where expected"
    code = stub_code(); assert raw[at(STUB):at(STUB) + len(code) + 16] == bytes(len(code) + 16), "the stub area is not free (already patched?)"
    # --- main image: stub, hook, image CRC
    raw[at(STUB):at(STUB) + len(code)] = code; raw[at(HOOK):at(HOOK) + 4] = encode_bl(HOOK, STUB)
    assert decode_bl(raw, HOOK) == STUB
    p.set_raw(fwd.MAIN, fwd.fix_main_crc(raw))
    # --- labels
    changed = []
    for path in p.paths():
        if not LANG.match(path): continue
        zbytes = p.raw(path); name, inner = fwd.unzip_single(zbytes); n = inner.count(old)
        if not n: continue
        p.set_raw(path, fwd.rezip_single(zbytes, inner.replace(old, new.ljust(len(old), b"\0")))); changed.append((path.rsplit("/", 1)[1], n))
    assert changed, "found no World Clock label"
    p.save(dst)
    print("hook %#x: bl %#x -> bl %#x (stub, %d bytes, calls the original first)" % (HOOK, ORIG_CALLEE, STUB, len(code)))
    print("labels -> %r: %s" % (label, ", ".join("%s x%d" % c for c in changed))); print("wrote", dst, os.path.getsize(dst), "bytes")

if __name__ == "__main__":
    a = sys.argv[1:]; label = a[a.index("--label") + 1] if "--label" in a else "Tennis"
    build(a[0], a[1], label)
