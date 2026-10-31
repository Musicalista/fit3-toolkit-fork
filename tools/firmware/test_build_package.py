# SPDX-License-Identifier: Apache-2.0
"""Tests of build_package.py against the packages in local/firmware (skipped when absent). python3 -I tools/firmware/test_build_package.py

The loader is cut out of fit3-store-base-spp-flat.bin (main image bytes 0x2c3a0524..0x2c3a4524, with fwx.py) into local/work/, never into the repository.
The package built from the stock package must equal fit3-worldclock-stage1b.bin except for ZIP container metadata (see the report printed at the end)."""
import io, os, struct, sys, tempfile, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fwd, fwx, build_package as bp, world_clock_takeover as wc
sys.path.insert(0, os.path.join(HERE, "..", "assets"))
ROOT = os.path.join(HERE, "..", ".."); FW = os.path.join(ROOT, "local", "firmware"); WORK = os.path.join(ROOT, "local", "work")
need = ["stock-aza3.bin", "fit3-spp-only.bin", "fit3-store-base-spp-flat.bin", "fit3-worldclock-stage1b.bin"]
if not all(os.path.exists(os.path.join(FW, n)) for n in need): sys.exit("skip: local/firmware lacks " + ", ".join(n for n in need if not os.path.exists(os.path.join(FW, n))))
P = lambda n: os.path.join(FW, n); ok = 0

def payload(z):
    """the raw deflate stream of a single-entry ZIP (independent of its header metadata)"""
    nl, el = fwd.u16(z, 26), fwd.u16(z, 28); cd = z.rfind(b"PK\x01\x02"); return z[30 + nl + el:cd]

# 1. spp patches: stock + the two patches + image CRC == fit3-spp-only (main image, byte for byte)
stock, spp = fwd.Package.load(P("stock-aza3.bin")), fwd.Package.load(P("fit3-spp-only.bin"))
m = bytearray(stock.raw(fwd.MAIN))
for vma, old, new in bp.SPP_PATCHES: assert m[vma - bp.BASE:vma - bp.BASE + len(old)] == old; m[vma - bp.BASE:vma - bp.BASE + len(new)] = new
assert fwd.fix_main_crc(bytes(m)) == spp.raw(fwd.MAIN); print("  ok   SPP_PATCHES reproduce fit3-spp-only's main image byte for byte"); ok += 1

# 2. the stub is the one of world_clock_takeover for the same parameters
assert bp.stub_code(wc.STUB, wc.CALLBACK) == wc.stub_code(); print("  ok   stub_code equals world_clock_takeover.stub_code"); ok += 1

# 3. loader out of flat, build, compare with stage1b
os.makedirs(WORK, exist_ok=True)
flat_main = fwx.components(P("fit3-store-base-spp-flat.bin"))[fwx.MAIN]; LA, LE = 0x2c3a0524, 0x2c3a4525
loader = flat_main[LA - bp.BASE:LE - bp.BASE]; open(os.path.join(WORK, "loader-flat.bin"), "wb").write(loader)
out = os.path.join(tempfile.mkdtemp(prefix="bp_", dir=WORK), "built.bin")
bp.build(P("stock-aza3.bin"), out, loader, hook_a=0x2c3a0524, hook_b=0x2c3a0548, extra_apps=True, quiet=True)   # runs validate_fwd.py
print("  ok   built package passes validate_fwd.py"); ok += 1
a, b = fwd.Package.load(out), fwd.Package.load(P("fit3-worldclock-stage1b.bin"))
assert a.paths() == b.paths() and a.updater == b.updater and all(x[:4] == y[:4] and x[12:] == y[12:] for x, y in zip(a.entries, b.entries))
assert a.raw(fwd.MAIN) == b.raw(fwd.MAIN); print("  ok   main image is identical to stage1b byte for byte (%d bytes)" % len(a.raw(fwd.MAIN))); ok += 1
report = []
for k in a.paths():
    i = a.index[k]
    if a.zips[i] == b.zips[i]: continue
    nested = "language_" in k
    same_content = fwd.unzip_single(a.raw(k))[1] == fwd.unzip_single(b.raw(k))[1] if nested else a.raw(k) == b.raw(k)
    assert same_content, "decompressed content differs: " + k
    same_stream = payload(a.raw(k) if nested else a.zips[i]) == payload(b.raw(k) if nested else b.zips[i])    # for language files: the stream of the inner .res ZIP
    report.append((k.rsplit("/", 1)[1], len(a.zips[i]), len(b.zips[i]), same_stream))
unchanged = [k for k in a.paths() if a.zips[a.index[k]] == b.zips[b.index[k]]]
assert len(unchanged) + len(report) == 73 and {r[0] for r in report} == {"best1502x_b319_user.bin", "language_en.res", "language_en_rUS.res", "language_pt_rPT.res", "language_pt_rBR.res"}, report
print("  ok   %d of 73 components are byte-identical to stage1b; the other %d have identical decompressed content" % (len(unchanged), len(report))); ok += 1
assert [r[3] for r in report if r[0].startswith("best") or r[0] in ("language_en.res", "language_en_rUS.res")] == [True] * 3
print("  ok   main image, language_en and language_en_rUS: same deflate stream, only ZIP header metadata differs"); ok += 1

# 4. the checks refuse what they should
def refuses(what, **kw):
    global ok
    args = dict(loader=loader, quiet=True, validate=False); args.update(kw)
    try: bp.build(P("stock-aza3.bin"), os.path.join(WORK, "refused.bin"), **args); sys.exit("FAIL: not refused: " + what)
    except AssertionError: print("  ok   refused:", what); ok += 1
refuses("loader past the end of free flash", loader_addr=0x2c3af000, menu_callback=0x2c3af001)
refuses("loader below the free flash", loader_addr=0x2c3a0000, menu_callback=0x2c3a1ab9)
refuses("loader over used flash", loader_addr=0x2c300000, menu_callback=0x2c3a1ab9)
refuses("callback outside the loader", menu_callback=0x2c3a8001)
refuses("stub overlapping the loader", stub_addr=0x2c3a1000)
# a label longer than "World Clock" is accepted and replaces only the app-list string (ID 181) of the English files
lp = os.path.join(WORK, "long-label.bin"); bp.build(P("stock-aza3.bin"), lp, loader, label="Tennis match score", quiet=True, validate=False)
import lvlang
for k in fwd.Package.load(lp).paths():
    if not bp.wc.LANG.match(k): continue
    Lnew = lvlang.Lang(fwd.Package.load(lp).raw(k)); Lold = lvlang.Lang(stock.raw(k))
    assert Lnew.string(181) == "Tennis match score" and all(Lnew.string(i) == Lold.string(i) for i in range(Lold.count) if i != 181), k
print("  ok   a long label replaces only text ID 181 in every English language file"); ok += 1
refuses("hook target outside the loader", hook_a=0x2c3a8000)

# slots: which entry of the app list is replaced
en = next(lvlang.Lang(stock.raw(k)) for k in stock.paths() if k.endswith("/language_en.res")); table = bp.slot_table(stock.raw(fwd.MAIN), en)
assert [r["name"] for r in table] == ["Health", "Media Controller", "Find My Phone", "Weather", "Calendar", "Settings", "Timer", "Alarm", "Stopwatch", "World Clock", "Camera Remote", "Calculator"], [r["name"] for r in table]
assert all(r["create"] and r["event"] for r in table) and len({r["create"] for r in table}) == 12 and len({r["event"] for r in table}) == 12
print("  ok   the app list has 12 entries, each with its own create and event function"); ok += 1
assert bp.find_slot(table, "world clock")["window"] == bp.find_slot(table, "WorldClock")["window"] == bp.find_slot(table, "0x2b")["window"] == bp.find_slot(table, 43)["window"] == 0x2b and bp.find_slot(table, "calc")["window"] == 0x8c
print("  ok   a slot is found by name (case, spaces, a prefix) or by window id"); ok += 1
for bad, why in (("ca", "ambiguous prefix"), ("nothing", "unknown name"), (0x02, "a window that is not in the app list")):
    try: bp.find_slot(table, bad); sys.exit("FAIL: not refused: slot " + why)
    except AssertionError: print("  ok   refused: slot", why); ok += 1
refuses("Settings without force_slot", slot="Settings")
# another slot, every language: the entry's own text is replaced everywhere and nothing else of the language files
ap_ = os.path.join(WORK, "calc.bin"); bp.build(P("stock-aza3.bin"), ap_, loader, label="Tennis Score", slot="Calculator", languages="all", quiet=True)     # validate_fwd runs inside
pc = fwd.Package.load(ap_); calc = bp.find_slot(table, "Calculator"); n_changed = 0
for k in stock.paths():
    if not bp.ALL_LANG.match(k): continue
    Lo, Ln = lvlang.Lang(stock.raw(k)), lvlang.Lang(pc.raw(k))
    assert Ln.string(calc["text_id"]) == "Tennis Score" and Ln.count == Lo.count and all(Ln.string(i) == Lo.string(i) for i in range(Lo.count) if i != calc["text_id"]), k
    assert [f[2] for f in Ln.fonts] == [f[2] for f in Lo.fonts] and all(Ln.d[o:o + sz] == Lo.d[o0:o0 + sz] for (o, sz, _), (o0, _, _) in zip(Ln.fonts, Lo.fonts)), "fonts of " + k
    n_changed += 1
assert n_changed > 50, n_changed
assert pc.raw(fwd.MAIN) != stock.raw(fwd.MAIN)
print("  ok   slot Calculator, languages=all: the entry is renamed in %d language files, no other string and no font changes; the package validates" % n_changed); ok += 1
refuses("an icon of the wrong size", icon=bytes(100))
# an icon: the app-list row of the replaced entry points at a descriptor after the loader, and nothing else of the table changes
ip = os.path.join(WORK, "icon.bin"); fake = bytes(range(256)) * 48; assert len(fake) == bp.ICON_SIZE
bp.build(P("stock-aza3.bin"), ip, loader, icon=fake, quiet=True, validate=False)
mi = fwd.Package.load(ip).raw(fwd.MAIN); ptr = struct.unpack_from("<I", mi, bp.ICON_ROW_PTR - bp.BASE)[0]
hdr, size, data, pad = struct.unpack_from("<IIII", mi, ptr - bp.BASE)
assert ptr % 16 == 0 and ptr >= 0x2c3a0524 + len(loader) and (hdr, size, data) == (5 | 64 << 10 | 64 << 21, bp.ICON_SIZE, ptr + 16) and mi[data - bp.BASE:data - bp.BASE + bp.ICON_SIZE] == fake
sm = stock.raw(fwd.MAIN); rows = [struct.unpack_from("<I", mi, 0x2c30021c - bp.BASE + 12 * k + 4)[0] == struct.unpack_from("<I", sm, 0x2c30021c - bp.BASE + 12 * k + 4)[0] for k in range(12)]
assert rows == [True] * 9 + [False] + [True] * 2, rows
print("  ok   an icon is placed after the loader and only row 9 (the replaced entry) points at it"); ok += 1
try: bp.build(P("fit3-worldclock-stage1b.bin"), os.path.join(WORK, "refused.bin"), loader, quiet=True, validate=False); sys.exit("FAIL: patched package accepted as stock")
except AssertionError: print("  ok   refused: an already patched package as the stock input"); ok += 1
big = bytes(0xf000)                                                       # a loader that fits only at the start; its stub then lands inside the same region
bp.build(P("stock-aza3.bin"), os.path.join(WORK, "big.bin"), big[:-1] + b"\0", menu_callback=0x2c3a0525, quiet=True, validate=True); ok += 1   # near the limit but legal
print("  ok   a 61 KB loader fits (stub placed after it); validate_fwd.py passes")
os.remove(os.path.join(WORK, "big.bin")); os.path.exists(os.path.join(WORK, "refused.bin")) and os.remove(os.path.join(WORK, "refused.bin"))
print("\n%d checks passed" % ok)
print("differences to fit3-worldclock-stage1b.bin (component, size here, size there, same deflate stream):")
for r in report: print("   ", r)
print("package-level fields that follow from them: packet header resource size, component offsets, packet CRC, header packet size")
