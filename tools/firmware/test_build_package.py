# SPDX-License-Identifier: Apache-2.0
"""Tests of build_package.py. They need only your stock package, local/firmware/stock-aza3.bin (skipped without it), and a made-up loader: python3 -I tools/firmware/test_build_package.py

What is checked: exactly the intended bytes of the main image change (Bluetooth patches, two branches into the loader, the other window functions made no-ops, the loader, the icon, the row pointer),
the entry's name in the language files, every slot of the app list, and what must be refused."""
import os, random, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "assets"))
import fwd, build_package as bp, lvlang
ROOT = os.path.join(HERE, "..", ".."); STOCK = os.path.join(ROOT, "local", "firmware", "stock-aza3.bin"); WORK = os.path.join(ROOT, "local", "work")
if not os.path.exists(STOCK): print("skip: local/firmware/stock-aza3.bin is not there"); sys.exit(0)
os.makedirs(WORK, exist_ok=True); ok = 0
def good(what):
    global ok; ok += 1; print("  ok  ", what)

def decode_b(raw, vma):
    """the target of the B.W at vma (inverse of build_package.encode_b)"""
    h1, h2 = struct.unpack_from("<HH", raw, vma - bp.BASE)
    assert (h1 & 0xF800) == 0xF000 and (h2 & 0xD000) == 0x9000, "not a B.W"
    s = (h1 >> 10) & 1; i1 = ~((h2 >> 13) ^ s) & 1; i2 = ~((h2 >> 11) ^ s) & 1
    off = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3FF) << 12) | ((h2 & 0x7FF) << 1)
    return vma + 4 + (off - (1 << 25) if s else off)

for _ in range(2000):
    src = random.randrange(0x2c080000, 0x2c3b0000, 2); dst = random.randrange(0x2c080000, 0x2c3b0000, 2); buf = bytearray(0x400000); buf[src - bp.BASE:src - bp.BASE + 4] = bp.encode_b(src, dst)
    assert decode_b(buf, src) == dst
good("encode_b round-trips 2000 random branches")

stock = fwd.Package.load(STOCK); sm = stock.raw(fwd.MAIN)
en = next(lvlang.Lang(stock.raw(k)) for k in stock.paths() if k.endswith("/language_en.res")); table = bp.slot_table(sm, en)
loader = bytes(range(256)) * 4; CREATE, EVENT = 0x2c3a0525, 0x2c3a0565; TK = {"create": CREATE, "event": EVENT}        # a made-up loader: only its position matters here
def build(name, **kw):
    out = os.path.join(WORK, name); args = dict(loader=loader, takeover=TK, quiet=True, validate=False); args.update(kw)
    bp.build(STOCK, out, args.pop("loader"), args.pop("takeover"), **args); return fwd.Package.load(out)
def refuses(what, **kw):
    try: build("refused.bin", **kw)
    except AssertionError: good("refused: " + what); return
    sys.exit("FAIL: not refused: " + what)

# 1. the main image: exactly the intended bytes change
icon = bytes(range(256)) * 48; assert len(icon) == bp.ICON_SIZE
q = build("default.bin", icon=icon, validate=True); mq = q.raw(fwd.MAIN); wc = bp.find_slot(table, "World Clock")        # validate_fwd.py runs inside this build
diff = [i for i in range(len(sm)) if sm[i] != mq[i]]
def intended(i):
    a = bp.BASE + i
    if 0x2c081008 <= a < 0x2c08100c or a in (0x2c227f7a, 0x2c227f7b, 0x2c233820, 0x2c233821): return True        # the image CRC, the two Bluetooth patches
    if 0x2c3a0524 <= a < 0x2c3af920: return True                                                                # the loader and the icon
    if wc["icon_field"] <= a < wc["icon_field"] + 4: return True                                                 # the row's icon pointer
    return any(f <= a < f + (4 if k in ("create", "event") else 2) for k in ("create", "event", "post", "x28", "destroy") for f in [wc[k]] if f)
assert not [hex(bp.BASE + i) for i in diff if not intended(i)], "unexpected changes"
good("only intended bytes of the main image change (%d bytes in total)" % len(diff))
assert decode_b(mq, wc["create"]) == CREATE & ~1 and decode_b(mq, wc["event"]) == EVENT & ~1
good("the stock create and event functions of World clock branch into the loader")
assert mq[0x2c3a0524 - bp.BASE:0x2c3a0524 - bp.BASE + len(loader)] == loader
good("the loader sits at the start of the free flash")
assert mq[wc["destroy"] - bp.BASE:wc["destroy"] - bp.BASE + 4] == sm[wc["destroy"] - bp.BASE:wc["destroy"] - bp.BASE + 4]
good("World clock's destroy function stays as shipped (verified on a watch), the rest are no-ops")
ptr = struct.unpack_from("<I", mq, wc["icon_field"] - bp.BASE)[0]; hdr, size, data, pad = struct.unpack_from("<IIII", mq, ptr - bp.BASE)
assert ptr % 16 == 0 and ptr >= 0x2c3a0524 + len(loader) and (hdr, size, data) == (5 | 64 << 10 | 64 << 21, bp.ICON_SIZE, ptr + 16) and mq[data - bp.BASE:data - bp.BASE + bp.ICON_SIZE] == icon
assert all(struct.unpack_from("<I", mq, r["icon_field"] - bp.BASE)[0] == r["icon_ptr"] for r in table if r is not wc)
good("the icon sits after the loader and only the row of the replaced entry points at it")
assert fwd.main_image_crc(mq) == fwd.u32(mq, 0x1008)
good("the main image CRC is repaired")

# 2. the name of the entry
short = build("short.bin", label="Tennis"); long_ = build("long.bin", label="Tennis match score"); nonen = [k for k in stock.paths() if k.endswith("language_pl_rPL.res")]
for k in stock.paths():
    if not bp.LANG_EN.match(k): continue
    old, new_s, new_l = stock.raw(k), short.raw(k), long_.raw(k)
    io_, in_ = fwd.unzip_single(old)[1], fwd.unzip_single(new_s)[1]                                  # the stock files already have 3 "Tennis" strings (the sport), so compare the increase
    assert in_.count(b"World Clock\0") == 0 and in_.count(b"Tennis\0") == io_.count(b"Tennis\0") + io_.count(b"World Clock\0")
    Lo, Ln = lvlang.Lang(old), lvlang.Lang(new_l)
    assert Ln.string(wc["text_id"]) == "Tennis match score" and all(Ln.string(i) == Lo.string(i) for i in range(Lo.count) if i != wc["text_id"])
good("a short label replaces every \"World Clock\" of the English files; a long one only the app-list string (text %d)" % wc["text_id"])
assert all(short.raw(k) == stock.raw(k) for k in stock.paths() if not bp.LANG_EN.match(k) and k != fwd.MAIN)
good("without --languages all the other language files are untouched")

# 3. every slot, another slot in every language
assert [r["name"] for r in table] == ["Health", "Media Controller", "Find My Phone", "Weather", "Calendar", "Settings", "Timer", "Alarm", "Stopwatch", "World Clock", "Camera Remote", "Calculator"], [r["name"] for r in table]
assert all(r["create"] and r["event"] for r in table) and len({r["create"] for r in table}) == 12 and len({r["event"] for r in table}) == 12
good("the app list has 12 entries, each with its own create and event function")
assert bp.find_slot(table, "world clock")["window"] == bp.find_slot(table, "WorldClock")["window"] == bp.find_slot(table, "0x2b")["window"] == bp.find_slot(table, 43)["window"] == 0x2b and bp.find_slot(table, "calc")["window"] == 0x8c
good("a slot is found by name (case, spaces, a prefix) or by window id")
for bad, why in (("ca", "ambiguous prefix"), ("nothing", "unknown name"), (0x02, "a window that is not in the app list")):
    try: bp.find_slot(table, bad); sys.exit("FAIL: not refused: slot " + why)
    except AssertionError: good("refused: slot " + why)
refuses("Settings without force_slot", slot="Settings")
calc = bp.find_slot(table, "Calculator"); pc = build("calc.bin", label="Tennis Score", slot="Calculator", languages="all", validate=True); n_changed = 0       # validate_fwd.py runs inside
for k in stock.paths():
    if not bp.ALL_LANG.match(k): continue
    Lo, Ln = lvlang.Lang(stock.raw(k)), lvlang.Lang(pc.raw(k))
    assert Ln.string(calc["text_id"]) == "Tennis Score" and Ln.count == Lo.count and all(Ln.string(i) == Lo.string(i) for i in range(Lo.count) if i != calc["text_id"]), k
    assert [f[2] for f in Ln.fonts] == [f[2] for f in Lo.fonts] and all(Ln.d[o:o + sz] == Lo.d[o0:o0 + sz] for (o, sz, _), (o0, _, _) in zip(Ln.fonts, Lo.fonts)), "fonts of " + k
    n_changed += 1
assert n_changed > 50
good("slot Calculator, languages=all: the entry is renamed in %d language files, no other string and no font changes; the package validates" % n_changed)

# 4. what must be refused
refuses("loader past the end of the free flash", loader=bytes(3000), loader_addr=0x2c3af000, takeover={"create": 0x2c3af001, "event": 0x2c3af021})
refuses("loader below the free flash", loader_addr=0x2c3a0000, takeover={"create": 0x2c3a0001, "event": 0x2c3a0041})
refuses("loader over used flash", loader_addr=0x2c300000, takeover={"create": 0x2c300001, "event": 0x2c300041})
refuses("a take-over address outside the loader", takeover={"create": 0x2c3a8001, "event": EVENT})
refuses("a take-over address that is not Thumb", takeover={"create": CREATE & ~1, "event": EVENT})
refuses("a take-over without the event function", takeover={"create": CREATE})
refuses("an icon of the wrong size", icon=bytes(100))
try: bp.build(os.path.join(WORK, "default.bin"), os.path.join(WORK, "refused.bin"), loader, TK, quiet=True, validate=False); sys.exit("FAIL: a patched package was accepted as stock")
except AssertionError: good("refused: an already patched package as the stock input")
print("%d checks passed" % ok)
