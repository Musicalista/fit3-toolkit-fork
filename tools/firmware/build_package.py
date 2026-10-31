# SPDX-License-Identifier: Apache-2.0
"""build_package.py: roadmap stage 3. Builds a Fit3 firmware package from *your own* stock package (R390XXU0AZA3) and a loader binary.

    python3 -I build_package.py <stock.bin> <out.bin> --loader <loader.bin> [options]

What it changes (every old byte is checked first; nothing is written when something is not as expected):
  1. spp patches (same as fit3-spp-only): 0x2c233820 `mov r4,r0` -> `movs r4,#3` (Bluetooth always visible and connectable),
     0x2c227f7a `mov r1,r2` -> `movs r1,#1` (RFCOMM channel 29 accepts a second client).
  2. the loader: the bytes of --loader go to --loader-addr (default 0x2c3a0524) in the free flash. Stock has zeros from 0x2c3a0524 to 0x2c3af920 (62460 bytes);
     the range is checked, so is overlap with the stub.
  3. (v1 takeover instead of the hook: `b.w` at the entry of the stock World clock create (0x2c1ecc64) and window-event (0x2c1ecd68) functions, no stub)
  3. the World clock hook: `bl 0x2c1ebfdc` at 0x2c1ecd30 becomes `bl stub`; the stub (28 bytes at --stub-addr, default: 16-aligned end of the loader) runs the original
     builder and then lv_timer_create(--menu-callback, 80 ms, root). See world_clock_takeover.py for the reasoning.
  3b. --icon: our own 64 x 64 image after the loader in the free flash, and the app-list row of the replaced entry points at it instead of the stock image ID "21" (a pointer to an
     lv_img_dsc_t is a "variable" source for LVGL; the firmware's own decoder rejects it and the built-in one draws it)
  4. labels: every "World Clock" in language_en*.res becomes --label (default Tennis) when it fits in 11 characters; a longer label replaces only the app-list string (ID 181),
     which wraps onto two lines like the longer stock names
  5. optional loader hooks of the old (Musicalista) loader: --hook-a / --hook-b retarget the `bl` at 0x2c1d0802 / 0x2c1b76a0; --extra-apps renames "Tips and tutorials"
     to "Extra apps" (en, en_rUS) and "Dicas e tutoriais" to "Apps extras" (pt_rPT, pt_rBR), which is how that loader's Settings entry is labelled.
  6. all checksums: main image CRC, ZIP CRCs, component CRC32s, catalogue, sizes, packet and header (via fwd.py). The updater is never touched.
The result is run through validate_fwd.py. Addresses are those of R390XXU0AZA3 only. No Samsung or third-party bytes are stored in this repository: you bring the stock package and the loader."""
import argparse, os, re, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets"))
import fwd, world_clock_takeover as wc, lvlang

BASE = 0x2c080000
FREE_START, FREE_END = 0x2c3a0524, 0x2c3af920          # zeros in the stock image (checked at build time)
SPP_PATCHES = [  # (vma, stock bytes, new bytes): the whole difference between stock-aza3.bin and fit3-spp-only.bin apart from the image CRC
    (0x2c227f7a, bytes.fromhex("1146"), bytes.fromhex("0121")),
    (0x2c233820, bytes.fromhex("0446"), bytes.fromhex("0324")),
]
HOOK_A = (0x2c1d0802, 0x2c112f58)                      # (site of a `bl`, its stock target): loader hook A of the old loader
HOOK_B = (0x2c1b76a0, 0x2c2974f8)                      # hook B (a log call in the sub-page opener)
WC_SITE, WC_STOCK_TARGET = wc.HOOK, wc.ORIG_CALLEE     # 0x2c1ecd30 -> 0x2c1ebfdc
TIMER_CREATE = wc.TIMER_CREATE                         # lv_timer_create | 1 (stock function)
DELAY_MS = wc.DELAY_MS
EXTRA_APPS = [  # (language file, old string, new string); the new string is padded with spaces to the old length
    (re.compile(r"language_en(_rUS)?\.res$"), b"Tips and tutorials", b"Extra apps"),
    (re.compile(r"language_pt_r(PT|BR)\.res$"), b"Dicas e tutoriais", b"Apps extras"),
]
at = lambda vma: vma - BASE
ICON_ROW_PTR, ICON_STOCK_PTR = 0x2c30028c, 0x2c2e4390        # app-list template row 9 (World clock): 0x2c30021c + 9*12 + 4 = the char* "21", the image ID string of the stock icon
ICON_SIZE = 64 * 64 * 3                                       # body of a 64 x 64 LV_IMG_CF_TRUE_COLOR_ALPHA image, 16-bit colour: RGB565 LE + alpha (tools/assets/mkicon.py)
APPLIST_TABLE, APPLIST_ROWS = 0x2c30021c, 12                 # flash template of the app-list rows, 12 bytes each: u8 kind, pad, s16 window id, char* icon id string, u16 text id, pad
WINDOW_TABLE, WINDOW_COUNT = 0x2c3b4200, 166                 # flash image of the window records, 0x30 bytes each (T4): +0x1c create, +0x20 post-enter, +0x24 event, +0x28 ?, +0x2c destroy
WINDOW_FNS = (("create", 0x1c), ("post", 0x20), ("event", 0x24), ("x28", 0x28), ("destroy", 0x2c))
FORBIDDEN = {0x36: "Settings: replacing it would lock you out of the watch's settings"}     # only with force_slot
WARNED = {0x08: "Health", 0x4d: "Stopwatch", 0x1d: "Timer", 0x90: "Alarm"}                    # apps with state outside their window: a stock app stops working
KEEP_STOCK = {0x2b: ("destroy",)}                            # World clock: its stock destroy is null-safe without stock state (seen on a watch), so it stays as it was shipped
BX_LR = bytes.fromhex("7047")
ALL_LANG = re.compile(r"^/nand/system/font/language_[A-Za-z_]+\.res$")
APPLIST_TEXT_ID = 181                                   # "World Clock" in the app list (T3/T4); the same words under other IDs (page titles, complications) stay as they are
TAKEOVER = {  # stage 2 (loader v1): `b.w ours` at the entry of the stock World clock window functions: (entry, the stock bytes there, what the function is)
    "create": (0x2c1ecc64, bytes.fromhex("2de9f341"), "window create fn (record 0x2b +0x1c)"),
    "event": (0x2c1ecd68, bytes.fromhex("70b58eb0"), "window event fn (record 0x2b +0x24)"),
}


def encode_b(src, dst):
    """Thumb-2 B.W (T4 encoding), same immediate layout as BL with bit 14 clear"""
    return struct.pack("<HH", *[a & ~b for a, b in zip(struct.unpack("<HH", wc.encode_bl(src, dst)), (0, 0x4000))])


def _fn(v): return (v & 0x00ffffff) + 0x2c000000 & ~1 if v else 0     # a record field -> the function's address (the 0x0c.. flash alias removed, Thumb bit cleared)


def slot_table(raw, english=None):
    """the 12 entries of the app list with their windows, read from the stock main image: what can be replaced (english: a lvlang.Lang of language_en for the names)"""
    rd = lambda a, fmt: struct.unpack_from(fmt, raw, a - BASE)
    rows = []
    for k in range(APPLIST_ROWS):
        a = APPLIST_TABLE + 12 * k; kind, _, win = rd(a, "<BBh"); ptr, text = rd(a + 4, "<IH"); rec = WINDOW_TABLE + win * 0x30
        row = dict(row=k, kind=kind, window=win, text_id=text, icon_field=a + 4, icon_ptr=ptr, name=english.string(text) if english else "text %d" % text)
        for nm, off in WINDOW_FNS: row[nm] = _fn(rd(rec + off, "<I")[0])
        rows.append(row)
    return rows


def find_slot(table, spec):
    """spec: a window id (int or '0x2b') or a name ('World Clock', 'worldclock', 'calc')"""
    if isinstance(spec, str) and not spec.strip().lower().startswith("0x") and not spec.strip().isdigit():
        key = "".join(ch for ch in spec.lower() if ch.isalnum())
        hits = [r for r in table if "".join(ch for ch in r["name"].lower() if ch.isalnum()).startswith(key)] if key else []
        if len(hits) != 1: raise AssertionError("slot %r: %s" % (spec, "no such entry in the app list" if not hits else "ambiguous: " + ", ".join(h["name"] for h in hits)))
        return hits[0]
    win = int(spec, 0) if isinstance(spec, str) else spec
    hits = [r for r in table if r["window"] == win]
    if not hits: raise AssertionError("window %#x is not an entry of the app list (replaceable: %s)" % (win, ", ".join("%#x %s" % (r["window"], r["name"]) for r in table)))
    return hits[0]


def stub_code(stub, callback, timer_create=TIMER_CREATE, delay=DELAY_MS):
    """push {r3,lr}; bl 0x2c1ebfdc; ldr r3,[r4]; ldr r2,[r3]; ldr r0,=callback; movs r1,#delay; ldr r3,=timer_create; blx r3; pop {r3,pc}; .word callback, timer_create"""
    assert callback & 1 and timer_create & 1 and 0 < delay < 256 and stub % 4 == 0
    code = struct.pack("<H", 0xB508) + wc.encode_bl(stub + 2, WC_STOCK_TARGET) + struct.pack("<6H", 0x6823, 0x681A, 0x4802, 0x2100 | delay, 0x4B02, 0x4798) + struct.pack("<H", 0xBD08)
    assert len(code) == 20; return code + struct.pack("<II", callback, timer_create)


def check_stock(p):
    need = lambda ok, what: ok or sys.exit("not the expected stock package: " + what)
    need(fwd.MAIN in p.index, "no main image")
    need(p.pkt_head[4:68].split(b"\0")[0] == b"R390XXU0AZA3", "version is not R390XXU0AZA3")
    raw = p.raw(fwd.MAIN); need(len(raw) == 3371348 and fwd.main_image_crc(raw) == fwd.u32(raw, 0x1008), "main image size/CRC")
    return raw


def build(stock, out, loader, loader_addr=FREE_START, label="Tennis", stub_addr=None, menu_callback=0x2c3a1ab9, hook_a=None, hook_b=None, extra_apps=False, validate=True, quiet=False, takeover=None, icon=None, slot=0x2b, languages="en", force_slot=False):
    log = (lambda *a: None) if quiet else print
    new_label = label.encode("ascii") + b"\0"; old_label = b"World Clock\0"
    long_label = len(new_label) > len(old_label)            # longer than "World Clock": only the app-list string (text ID 181) is replaced, via lvlang.Lang.set_string
    p = fwd.Package.load(stock); raw = bytearray(check_stock(p)); orig = bytes(raw)
    english = next(lvlang.Lang(p.raw(k)) for k in p.paths() if k.endswith("/language_en.res"))
    sl = find_slot(slot_table(orig, english), slot)
    assert force_slot or sl["window"] not in FORBIDDEN, "slot %s refused: %s (force_slot=True / --force-slot overrides)" % (sl["name"], FORBIDDEN[sl["window"]])
    is_wc = sl["window"] == 0x2b
    # --- loader and stub placement
    lend = loader_addr + len(loader)
    assert loader_addr % 2 == 0 and FREE_START <= loader_addr and lend <= FREE_END, "loader %#x..%#x is outside the free flash %#x..%#x" % (loader_addr, lend, FREE_START, FREE_END)
    if stub_addr is None: stub_addr = (lend + 15) & ~15
    stub = b"" if takeover else stub_code(stub_addr, menu_callback); send = stub_addr + len(stub)    # takeover = {"create": addr, "event": addr}: no stub, no timer hook
    assert FREE_START <= stub_addr and send <= FREE_END, "stub %#x..%#x is outside the free flash" % (stub_addr, send)
    assert send <= loader_addr or stub_addr >= lend, "the stub overlaps the loader"
    assert takeover or loader_addr <= menu_callback & ~1 < lend, "--menu-callback %#x is not inside the loader" % menu_callback
    for k, t in (takeover or {}).items(): assert loader_addr <= t & ~1 < lend and t & 1, "--takeover-%s %#x is not a Thumb address inside the loader" % (k, t)
    if icon is not None:
        assert len(icon) == ICON_SIZE, "the icon must be %d bytes (64 x 64, RGB565 + alpha), see tools/assets/mkicon.py" % ICON_SIZE
        icon_addr = (max(lend, send) + 15) & ~15; icon_end = icon_addr + 16 + len(icon)
        assert icon_end <= FREE_END, "the icon (%#x..%#x) is outside the free flash" % (icon_addr, icon_end)
        assert not any(orig[at(icon_addr):at(icon_end)]), "stock flash %#x..%#x is not empty" % (icon_addr, icon_end)
        assert struct.unpack_from("<I", orig, at(sl["icon_field"]))[0] == sl["icon_ptr"] and re.fullmatch(rb"\d{1,4}", bytes(orig[at(sl["icon_ptr"]):at(sl["icon_ptr"]) + 4]).split(b"\0")[0] or b"x"), "the icon of row %d of the app list is not an image ID string" % sl["row"]
    for a, b in ((loader_addr, lend), (stub_addr, send)):
        assert not any(orig[at(a):at(b)]), "stock flash %#x..%#x is not empty" % (a, b)
    # --- spp patches
    for vma, old, new in SPP_PATCHES:
        assert orig[at(vma):at(vma) + len(old)] == old, "spp patch site %#x does not hold %s (another version?)" % (vma, old.hex())
        raw[at(vma):at(vma) + len(new)] = new
    # --- loader, stub, World clock hook
    raw[at(loader_addr):at(lend)] = loader; raw[at(stub_addr):at(send)] = stub
    if takeover:
        assert set(takeover) == {"create", "event"}, "takeover needs both create and event"
        for k in ("create", "event"):
            entry = sl[k]; h = struct.unpack_from("<H", orig, at(entry))[0]
            assert entry and ((h & 0xfe00) == 0xb400 or h == 0xe92d), "the window %s function %#x does not start like a function (push): another version?" % (k, entry)
            raw[at(entry):at(entry) + 4] = encode_b(entry, takeover[k] & ~1)
        # the other window functions would run on the stock state that we never create: make them no-ops (a function nobody else points at, checked against all 166 records)
        refs = {}
        for w in range(WINDOW_COUNT):
            for nm, off in WINDOW_FNS:
                f = _fn(struct.unpack_from("<I", orig, at(WINDOW_TABLE + w * 0x30 + off))[0]); refs[f] = refs.get(f, 0) + 1
        for k, _ in WINDOW_FNS:
            f = sl[k]
            if k in ("create", "event") or not f or k in KEEP_STOCK.get(sl["window"], ()) or orig[at(f):at(f) + 2] == BX_LR: continue
            assert refs[f] == 1, "the window %s function %#x is used by another window: cannot make it a no-op" % (k, f)
            raw[at(f):at(f) + 2] = BX_LR
    else:
        assert wc.decode_bl(orig, WC_SITE) == WC_STOCK_TARGET, "no `bl 0x2c1ebfdc` at the World clock hook site"
        raw[at(WC_SITE):at(WC_SITE) + 4] = wc.encode_bl(WC_SITE, stub_addr)
    if icon is not None:    # lv_img_dsc_t (header cf 5 | w << 10 | h << 21, data size, data pointer, 4 bytes of padding: the firmware copies 16) + the pixels; the row's icon pointer now points at it
        raw[at(icon_addr):at(icon_addr) + 16] = struct.pack("<IIII", 5 | 64 << 10 | 64 << 21, len(icon), icon_addr + 16, 0)
        raw[at(icon_addr) + 16:at(icon_end)] = icon
        raw[at(sl["icon_field"]):at(sl["icon_field"]) + 4] = struct.pack("<I", icon_addr)
    # --- optional hooks of the old loader
    for (site, stock_target), target in ((HOOK_A, hook_a), (HOOK_B, hook_b)):
        if target is None: continue
        assert wc.decode_bl(orig, site) == stock_target, "no `bl %#x` at %#x" % (stock_target, site)
        assert loader_addr <= target < lend, "hook target %#x is not inside the loader" % target
        raw[at(site):at(site) + 4] = wc.encode_bl(site, target)
    p.set_raw(fwd.MAIN, fwd.fix_main_crc(bytes(raw)))
    # --- language files: the label (every English file) and, optionally, the old loader's Settings entry (en, en_rUS, pt_rPT, pt_rBR)
    changed = []
    for path in p.paths():
        english, other = wc.LANG.match(path), re.search(r"language_pt_r(PT|BR)\.res$", path)
        chosen = english or (languages == "all" and ALL_LANG.match(path))
        if not (chosen or other): continue
        zbytes = p.raw(path); inner = fwd.unzip_single(zbytes)[1]; new = inner; n = m = 0
        if chosen and is_wc and not long_label: n = new.count(old_label); new = new.replace(old_label, new_label.ljust(len(old_label), b"\0"))     # the verified way for World clock and a short label: every "World Clock" of the file
        elif chosen:                                                                                                                                  # any other slot, or a long label: only the string of the app-list row
            L = lvlang.Lang(new); assert sl["text_id"] < L.count, "%s has no text %d" % (path, sl["text_id"])
            if english: assert L.string(sl["text_id"]) == sl["name"], "text %d of %s is %r, not %r" % (sl["text_id"], path, L.string(sl["text_id"]), sl["name"])
            new = L.set_string(sl["text_id"], label); n = 1
        if extra_apps:
            for rx, old, repl in EXTRA_APPS:
                if rx.search(path): m += new.count(old + b"\0"); new = new.replace(old + b"\0", repl.ljust(len(old)) + b"\0")
        if new != inner: p.set_raw(path, fwd.rezip_single(zbytes, new)); changed.append((path.rsplit("/", 1)[1], n, m))
    assert any(c[1] for c in changed), "found no label to replace for %s" % sl["name"]
    p.save(out)
    log("spp patches: %d; loader %d bytes at %#x..%#x; %s" % (len(SPP_PATCHES), len(loader), loader_addr, lend,
        "takeover of %s (window %#x, list row %d): " % (sl["name"], sl["window"], sl["row"]) + ", ".join("%s %#x -> b.w %#x" % (k, sl[k], v & ~1) for k, v in takeover.items()) if takeover else
        "stub %d bytes at %#x; hook %#x -> bl %#x" % (len(stub), stub_addr, WC_SITE, stub_addr)))
    log("labels -> %r; changed language files: %s" % (label, ", ".join("%s (label x%d, extra-apps x%d)" % c for c in changed)))
    log("wrote", out, os.path.getsize(out), "bytes")
    if validate:
        r = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate_fwd.py"), out], capture_output=True, text=True)
        log(r.stdout.rstrip())
        if r.returncode: sys.exit("validate_fwd.py FAILED:\n" + r.stdout + r.stderr)
    return out


def num(s): return int(s, 0)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stock"); ap.add_argument("out", nargs="?"); ap.add_argument("--loader", help="binary placed at --loader-addr (position dependent!)")
    ap.add_argument("--loader-addr", type=num, default=FREE_START); ap.add_argument("--stub-addr", type=num, help="default: end of the loader rounded up to 16")
    ap.add_argument("--menu-callback", type=num, default=0x2c3a1ab9, help="Thumb address (bit 0 set) of the loader's timer callback that opens its UI; user data = root object")
    ap.add_argument("--label", default="Tennis"); ap.add_argument("--hook-a", type=num); ap.add_argument("--hook-b", type=num); ap.add_argument("--extra-apps", action="store_true")
    ap.add_argument("--icon", help="raw 64 x 64 RGB565+alpha body from tools/assets/mkicon.py: the app-list icon of the replaced entry (placed after the loader in the free flash)")
    ap.add_argument("--takeover-create", type=num, help="loader v1: Thumb address of world_create; replaces the stock window create function (needs --takeover-event)")
    ap.add_argument("--takeover-event", type=num, help="loader v1: Thumb address of world_event")
    ap.add_argument("--slot", default="World Clock", help="which entry of the app list to take over (name or window id; --list-slots shows them)")
    ap.add_argument("--list-slots", action="store_true", help="print the replaceable entries of the stock package and exit")
    ap.add_argument("--force-slot", action="store_true", help="allow a slot that is refused by default (Settings)")
    ap.add_argument("--languages", choices=("en", "all"), default="en", help="language files whose entry name is replaced (all: untested outside English)")
    a = ap.parse_args()
    if a.list_slots:
        p = fwd.Package.load(a.stock); raw = check_stock(p); en = next(lvlang.Lang(p.raw(k)) for k in p.paths() if k.endswith("/language_en.res"))
        print("row  window  entry                      note")
        for r in slot_table(raw, en): print("%3d  %#6x  %-26s %s" % (r["row"], r["window"], r["name"], ("refused without --force-slot: " + FORBIDDEN[r["window"]]) if r["window"] in FORBIDDEN else ("replaces the stock app" + ("; it may keep timers, alarms or data running in the background" if r["window"] in WARNED else "") if r["window"] != 0x2b else "default: rarely used, nothing runs in the background")))
        sys.exit(0)
    if not a.out or not a.loader: ap.error("out and --loader are required")
    tk = {"create": a.takeover_create, "event": a.takeover_event} if (a.takeover_create or a.takeover_event) else None
    build(a.stock, a.out, open(a.loader, "rb").read(), a.loader_addr, a.label, a.stub_addr, a.menu_callback, a.hook_a, a.hook_b, a.extra_apps, takeover=tk, icon=open(a.icon, "rb").read() if a.icon else None, slot=a.slot, languages=a.languages, force_slot=a.force_slot)
