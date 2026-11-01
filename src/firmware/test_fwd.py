# SPDX-License-Identifier: Apache-2.0
"""Tests of fwd.py against the packages in local/firmware (skipped when absent): load+save must reproduce a package exactly. python3 -I src/firmware/test_fwd.py"""
import hashlib, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fwd
FW = os.path.join(HERE, "..", "..", "local", "firmware"); ok = skipped = 0
for name in ("stock-aza3.bin",):
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
print("%d checks passed, %d skipped" % (ok, skipped))
