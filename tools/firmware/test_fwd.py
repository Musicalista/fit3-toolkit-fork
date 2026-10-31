"""Tests of fwd.py against the packages in local/firmware (skipped when absent): load+save must reproduce a package exactly. python3 -I tools/firmware/test_fwd.py"""
import hashlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fwd
FW = os.path.join(HERE, "..", "..", "local", "firmware"); ok = skipped = 0
for name in ("stock-aza3.bin", "fit3-spp-only.bin", "fit3-store-base-spp.bin", "fit3-store-base-spp-flat.bin"):
    path = os.path.join(FW, name)
    if not os.path.exists(path): print("  skip", name); skipped += 1; continue
    a = open(path, "rb").read(); b = fwd.Package.load(path).to_bytes()
    if a != b: sys.exit("FAIL: %s is not reproduced (%d vs %d bytes, first difference at %d)" % (name, len(a), len(b), next(i for i in range(min(len(a), len(b))) if a[i] != b[i])))
    print("  ok   load+save reproduces", name, hashlib.sha256(a).hexdigest()[:12]); ok += 1
# rewriting a component with identical content keeps the package valid (sizes may change with the compressor)
p = fwd.Package.load(os.path.join(FW, "stock-aza3.bin")) if os.path.exists(os.path.join(FW, "stock-aza3.bin")) else None
if p:
    raw = p.raw(fwd.MAIN); assert fwd.main_image_crc(raw) == fwd.u32(raw, 0x1008); print("  ok   main image CRC rule matches the stock image")
    p.set_raw("/nand/system/version/version.ini", p.raw("/nand/system/version/version.ini")); q = p.to_bytes()
    assert fwd.u32(q, 0) == 0x7e5a5a60 and len(q) > 18_000_000; print("  ok   a rewritten small component still builds"); ok += 2
# world_clock_takeover: branch encoding, and the whole build on the flat package
import random, tempfile, world_clock_takeover as w
for _ in range(2000):
    src = random.randrange(0x2c080000, 0x2c3b0000, 2); dst = random.randrange(0x2c080000, 0x2c3b0000, 2); buf = bytearray(0x400000); buf[src - w.BASE:src - w.BASE + 4] = w.encode_bl(src, dst)
    assert w.decode_bl(buf, src) == dst
print("  ok   encode_bl/decode_bl round-trip on 2000 random branches"); ok += 1
flat = os.path.join(FW, "fit3-store-base-spp-flat.bin")
if os.path.exists(flat):
    out = os.path.join(tempfile.mkdtemp(prefix="wc_"), "out.bin"); w.build(flat, out, "Tennis"); q = fwd.Package.load(out); old = fwd.Package.load(flat)
    changed = [k for k in q.paths() if q.raw(k) != old.raw(k)]
    assert fwd.MAIN in changed and len(changed) == 5 and all("language_en" in k for k in changed if k != fwd.MAIN), changed
    m = q.raw(fwd.MAIN); assert fwd.main_image_crc(m) == fwd.u32(m, 0x1008) and w.decode_bl(m, 0x2c1ecd30) == w.STUB and w.decode_bl(m, w.STUB + 2) == w.ORIG_CALLEE and m[0x324530:0x324532] == bytes.fromhex("08b5") and m[0x324544:0x32454c] == bytes.fromhex("b91a3a2cf1a3282c")
    assert all(b"World Clock" not in fwd.unzip_single(q.raw(k))[1] for k in changed if k != fwd.MAIN)
    print("  ok   the stage-1 package changes the main image and four English language files only"); ok += 1
    try: w.build(out, os.path.join(os.path.dirname(out), "twice.bin"), "Tennis"); sys.exit("FAIL: patching an already patched package was not refused")
    except AssertionError: print("  ok   an already patched package is refused"); ok += 1
print("%d checks passed, %d skipped" % (ok, skipped))
