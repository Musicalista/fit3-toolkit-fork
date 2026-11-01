# SPDX-License-Identifier: Apache-2.0
"""test_slots.py: build the tennis package for every replaceable app-list entry and test each result in the emulator.

    python3 -I src/emu/test_slots.py [slot ...]        # all slots except Settings, or the given names / window ids

For each slot: the package is built (build_package.py, window id compiled into the loader), the main image gets exactly the expected patches (a `b.w` at the entry of the
stock create and event functions, `bx lr` in the other window functions that are not already no-ops, the icon pointer of the slot's own row, nothing else), and the full
window test of test_tennis.py (run with the emulator's venv, local/venv) runs against the stock addresses of that slot. Takes a few minutes. Needs local/firmware/stock-aza3.bin and local/re/main-stock.bin."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
for d in ("firmware", "watch", "assets"): sys.path.insert(0, os.path.join(ROOT, "src", d))
import fwd, build_package as bp, build_loader, gen, mkicon, lvlang

STOCK = os.path.join(ROOT, "local/firmware/stock-aza3.bin")
EMU_PY = os.path.join(ROOT, "local/venv/bin/python")                  # Unicorn lives there; this script itself only needs numpy (the icon)

def main(argv):
    if not os.path.exists(STOCK): print("SKIP: need local/firmware/stock-aza3.bin"); return 0
    p = fwd.Package.load(STOCK); orig = p.raw(fwd.MAIN); en = next(lvlang.Lang(p.raw(k)) for k in p.paths() if k.endswith("/language_en.res"))
    table = bp.slot_table(orig, en); chosen = [bp.find_slot(table, a) for a in argv] or [r for r in table if r["window"] not in bp.FORBIDDEN]
    work = tempfile.mkdtemp(prefix="slots_", dir=os.path.join(ROOT, "local")) if os.path.isdir(os.path.join(ROOT, "local")) else tempfile.mkdtemp()
    icon = mkicon.encode(*mkicon.draw()); bad = 0
    for sl in chosen:
        name = "%s (window %#x, row %d)" % (sl["name"], sl["window"], sl["row"]); print("== " + name)
        lo = os.path.join(work, "loader_%x.bin" % sl["window"]); syms = build_loader.build(os.path.join(ROOT, "src/watch/hub.c"), lo, quiet=True, defines=["WINDOW_ID=%#x" % sl["window"]], include_dirs=[gen.generate(["tennis"], False, os.path.join(work, "gen"))])
        out = os.path.join(work, "slot_%x.bin" % sl["window"])
        bp.build(STOCK, out, open(lo, "rb").read(), label="Tennis Score", icon=icon, slot=sl["window"], quiet=True, validate=False,
                 takeover={"create": syms["world_create"] | 1, "event": syms["world_event"] | 1})
        new = fwd.Package.load(out).raw(fwd.MAIN); ok = True
        diff = [i for i in range(len(orig)) if orig[i] != new[i]]
        def covered(i):                                                    # every changed byte must be one we meant to change
            a = bp.BASE + i
            if 0x2c081008 <= a < 0x2c08100c or a in (0x2c227f7a, 0x2c227f7b, 0x2c233820, 0x2c233821): return True        # image CRC, spp patches
            if 0x2c3a0524 <= a < 0x2c3af920: return True                                                                # loader and icon
            if sl["icon_field"] <= a < sl["icon_field"] + 4: return True
            return any(f <= a < f + (4 if k in ("create", "event") else 2) for k in ("create", "event", "post", "x28", "destroy") for f in [sl[k]] if f)
        stray = [hex(bp.BASE + i) for i in diff if not covered(i)]
        if stray: ok = False; print("FAIL unexpected changes in the main image:", stray[:8])
        for k in ("create", "event"):
            h = struct.unpack_from("<HH", new, sl[k] - bp.BASE)
            if (h[0] & 0xf800) != 0xf000: ok = False; print("FAIL no b.w at the %s function %#x" % (k, sl[k]))
        for k in ("post", "x28", "destroy"):
            f = sl[k]
            if f and k not in bp.KEEP_STOCK.get(sl["window"], ()) and new[f - bp.BASE:f - bp.BASE + 2] != bp.BX_LR: ok = False; print("FAIL the %s function %#x is not a no-op" % (k, f))
        icon_ptr = struct.unpack_from("<I", new, sl["icon_field"] - bp.BASE)[0]
        others = all(struct.unpack_from("<I", new, bp.APPLIST_TABLE + 12 * r["row"] + 4 - bp.BASE)[0] == r["icon_ptr"] for r in table if r["row"] != sl["row"])
        if not (0x2c3a0524 <= icon_ptr < 0x2c3af920 and others): ok = False; print("FAIL the icon pointers are wrong")
        img = os.path.join(work, "main_%x.bin" % sl["window"]); open(img, "wb").write(new)
        env = dict(os.environ, F3_IMAGE=os.path.relpath(img, ROOT), F3_WINDOW=hex(sl["window"]), F3_CREATE=hex(sl["create"]), F3_EVENT=hex(sl["event"]))
        r = subprocess.run([EMU_PY if os.path.exists(EMU_PY) else sys.executable, "-I", os.path.join(HERE, "test_tennis.py")], capture_output=True, text=True, env=env, cwd=ROOT)
        last = [l for l in r.stdout.splitlines() if "passed" in l or "FAIL" in l]
        if r.returncode: ok = False; print("\n".join(last[:6]) or r.stderr[-400:])
        print("   %s: %s" % ("ok" if ok else "FAILED", last[-1] if last else "no output")); bad += not ok
    print("%d of %d slots ok" % (len(chosen) - bad, len(chosen))); return 1 if bad else 0

sys.exit(main(sys.argv[1:]))
