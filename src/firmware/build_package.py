# SPDX-License-Identifier: Apache-2.0
"""build_package.py: builds a Fit3 firmware package from *your own* stock package (R390XXU0AZA3) and a loader binary that takes over one entry of the app list.

    python3 -I build_package.py <stock.bin> <out.bin> --loader <loader.bin> --takeover-create <addr> --takeover-event <addr> [options]
    python3 -I build_package.py <stock.bin> --list-slots

(`src/build_tennis.py` compiles the loader and calls this: use that unless you write your own loader.)

What it changes (every old byte is checked first; nothing is written when something is not as expected):
  1. Bluetooth patches: 0x2c233820 `mov r4,r0` -> `movs r4,#3` (the watch is always visible and connectable),
     0x2c227f7a `mov r1,r2` -> `movs r1,#1` (RFCOMM channel 29 accepts a second client). They let this PC flash the watch, and let ANYONE in range connect without pairing:
     --no-bluetooth-patches leaves them out (flash such a package last, see docs/howto.md).
  2. the loader: the bytes of --loader go to --loader-addr (default 0x2c3a0524) in the free flash. Stock has zeros from 0x2c3a0524 to 0x2c3af920 (62460 bytes); the range is checked.
  3. the take-over of the app-list entry chosen with --slot (default World Clock): a `b.w` branch at the entry of the stock create function and of the stock window event function of that window
     goes to --takeover-create / --takeover-event (Thumb addresses inside the loader); the other window functions of its record (post-enter, +0x28, destroy) become `bx lr` because they would run
     on stock state that never exists (World clock's destroy is null-safe and stays as shipped). Nothing of the window has other callers (Ghidra call graph, see docs/details.md).
  4. --icon: our own 64 x 64 image after the loader in the free flash; the app-list row of the replaced entry points at it instead of the stock image ID string (a pointer to an lv_img_dsc_t is a
     "variable" source for LVGL; the firmware's own decoder rejects it and the built-in one draws it).
  5. the entry's name: for World Clock and a label of at most 11 characters every "World Clock" of the English language files becomes --label; otherwise (any other entry, or a longer label, which then
     wraps onto two lines like the longer stock names) only the app-list string of that entry is replaced, with lvlang.Lang.set_string, in the English files or with --languages all in every language file.
  6. all checksums: main image CRC, ZIP CRCs, component CRC32s, catalogue, sizes, packet and header (via fwd.py). The updater is never touched.
The result is run through validate_fwd.py. Addresses are those of R390XXU0AZA3 only. No Samsung or third-party bytes are stored in this repository: you bring the stock package."""
import argparse, os, re, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets"))
import fwd, lvlang

BASE = 0x2c080000
at = lambda vma: vma - BASE
FREE_START, FREE_END = 0x2c3a0524, 0x2c3af920          # zeros in the stock image (checked at build time)
SPP_PATCHES = [  # (vma, stock bytes, new bytes)
    (0x2c227f7a, bytes.fromhex("1146"), bytes.fromhex("0121")),
    (0x2c233820, bytes.fromhex("0446"), bytes.fromhex("0324")),
]
ICON_SIZE = 64 * 64 * 3                                       # body of a 64 x 64 LV_IMG_CF_TRUE_COLOR_ALPHA image, 16-bit colour: RGB565 LE + alpha (src/assets/mkicon.py)
APPLIST_TABLE, APPLIST_ROWS = 0x2c30021c, 12                 # flash template of the app-list rows, 12 bytes each: u8 kind, pad, s16 window id, char* icon id string, u16 text id, pad
WINDOW_TABLE, WINDOW_COUNT = 0x2c3b4200, 166                 # flash image of the window records, 0x30 bytes each (docs/details.md): +0x1c create, +0x20 post-enter, +0x24 event, +0x28 ?, +0x2c destroy
WINDOW_FNS = (("create", 0x1c), ("post", 0x20), ("event", 0x24), ("x28", 0x28), ("destroy", 0x2c))
FORBIDDEN = {0x36: "Settings: replacing it would lock you out of the watch's settings"}     # only with force_slot
WARNED = {0x08: "Health", 0x4d: "Stopwatch", 0x1d: "Timer", 0x90: "Alarm"}                    # apps with state outside their window: a stock app stops working
KEEP_STOCK = {0x2b: ("destroy",)}                            # World clock: its stock destroy is null-safe without stock state (seen on a watch), so it stays as it was shipped
BX_LR = bytes.fromhex("7047")
LANG_EN = re.compile(r"^/nand/system/font/language_en(_r[A-Z]{2})?\.res$")
ALL_LANG = re.compile(r"^/nand/system/font/language_[A-Za-z_]+\.res$")


def encode_b(src, dst):
    """Thumb-2 B.W (encoding T4): 4 bytes that branch from src to dst (both even, within +-16 MB)"""
    off = dst - (src + 4); assert off % 2 == 0 and -(1 << 24) <= off < (1 << 24)
    s = 1 if off < 0 else 0; off &= 0x1FFFFFF; i1, i2 = (off >> 23) & 1, (off >> 22) & 1
    j1, j2 = ~(i1 ^ s) & 1, ~(i2 ^ s) & 1
    return struct.pack("<HH", 0xF000 | (s << 10) | ((off >> 12) & 0x3FF), 0x9000 | (j1 << 13) | (j2 << 11) | ((off >> 1) & 0x7FF))


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


def check_stock(p):
    need = lambda ok, what: ok or sys.exit("not the expected stock package: " + what)
    need(fwd.MAIN in p.index, "no main image")
    need(p.pkt_head[4:68].split(b"\0")[0] == b"R390XXU0AZA3", "version is not R390XXU0AZA3")
    raw = p.raw(fwd.MAIN); need(len(raw) == 3371348 and fwd.main_image_crc(raw) == fwd.u32(raw, 0x1008), "main image size/CRC")
    return raw


def build(stock, out, loader, takeover, loader_addr=FREE_START, label="Tennis", validate=True, quiet=False, icon=None, slot=0x2b, languages="en", force_slot=False, bluetooth_patches=True):
    """takeover = {"create": Thumb address, "event": Thumb address} of the two window functions inside `loader`"""
    log = (lambda *a: None) if quiet else print
    new_label = label.encode("ascii") + b"\0"; old_label = b"World Clock\0"
    long_label = len(new_label) > len(old_label)            # longer than "World Clock": only the app-list string is replaced, via lvlang.Lang.set_string
    p = fwd.Package.load(stock); raw = bytearray(check_stock(p)); orig = bytes(raw)
    english = next(lvlang.Lang(p.raw(k)) for k in p.paths() if k.endswith("/language_en.res"))
    sl = find_slot(slot_table(orig, english), slot)
    assert force_slot or sl["window"] not in FORBIDDEN, "slot %s refused: %s (force_slot=True / --force-slot overrides)" % (sl["name"], FORBIDDEN[sl["window"]])
    is_wc = sl["window"] == 0x2b
    # --- placement checks
    lend = loader_addr + len(loader)
    assert loader_addr % 2 == 0 and FREE_START <= loader_addr and lend <= FREE_END, "loader %#x..%#x is outside the free flash %#x..%#x" % (loader_addr, lend, FREE_START, FREE_END)
    assert not any(orig[at(loader_addr):at(lend)]), "stock flash %#x..%#x is not empty" % (loader_addr, lend)
    assert set(takeover) == {"create", "event"}, "takeover needs both create and event"
    for k, t in takeover.items(): assert loader_addr <= t & ~1 < lend and t & 1, "--takeover-%s %#x is not a Thumb address inside the loader" % (k, t)
    if icon is not None:
        assert len(icon) == ICON_SIZE, "the icon must be %d bytes (64 x 64, RGB565 + alpha), see src/assets/mkicon.py" % ICON_SIZE
        icon_addr = (lend + 15) & ~15; icon_end = icon_addr + 16 + len(icon)
        assert icon_end <= FREE_END, "the icon (%#x..%#x) is outside the free flash" % (icon_addr, icon_end)
        assert not any(orig[at(icon_addr):at(icon_end)]), "stock flash %#x..%#x is not empty" % (icon_addr, icon_end)
        ptr = sl["icon_ptr"]
        assert struct.unpack_from("<I", orig, at(sl["icon_field"]))[0] == ptr and re.fullmatch(rb"\d{1,4}", bytes(orig[at(ptr):at(ptr) + 4]).split(b"\0")[0] or b"x"), "the icon of row %d of the app list is not an image ID string" % sl["row"]
    # --- Bluetooth patches (always checked: the sites must hold the stock bytes; applied unless bluetooth_patches is False)
    for vma, old, new in SPP_PATCHES:
        assert orig[at(vma):at(vma) + len(old)] == old, "patch site %#x does not hold %s (another version, or a package that is already patched?)" % (vma, old.hex())
        if bluetooth_patches: raw[at(vma):at(vma) + len(new)] = new
    # --- the loader and the take-over of the window
    raw[at(loader_addr):at(lend)] = loader
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
    if icon is not None:    # lv_img_dsc_t (header cf 5 | w << 10 | h << 21, data size, data pointer, 4 bytes of padding: the firmware copies 16) + the pixels; the row's icon pointer now points at it
        raw[at(icon_addr):at(icon_addr) + 16] = struct.pack("<IIII", 5 | 64 << 10 | 64 << 21, len(icon), icon_addr + 16, 0)
        raw[at(icon_addr) + 16:at(icon_end)] = icon
        raw[at(sl["icon_field"]):at(sl["icon_field"]) + 4] = struct.pack("<I", icon_addr)
    p.set_raw(fwd.MAIN, fwd.fix_main_crc(bytes(raw)))
    # --- language files: the entry's name
    changed = []
    for path in p.paths():
        chosen = LANG_EN.match(path) or (languages == "all" and ALL_LANG.match(path))
        if not chosen: continue
        zbytes = p.raw(path); inner = fwd.unzip_single(zbytes)[1]; new = inner; n = 0
        if is_wc and not long_label: n = new.count(old_label); new = new.replace(old_label, new_label.ljust(len(old_label), b"\0"))     # World clock and a short label: every "World Clock" of the file, as shipped and verified
        else:                                                                                                                              # any other entry, or a long label: only the string of the app-list row
            L = lvlang.Lang(new); assert sl["text_id"] < L.count, "%s has no text %d" % (path, sl["text_id"])
            if LANG_EN.match(path): assert L.string(sl["text_id"]) == sl["name"], "text %d of %s is %r, not %r" % (sl["text_id"], path, L.string(sl["text_id"]), sl["name"])
            new = L.set_string(sl["text_id"], label); n = 1
        if new != inner: p.set_raw(path, fwd.rezip_single(zbytes, new)); changed.append((path.rsplit("/", 1)[1], n))
    assert any(c[1] for c in changed), "found no label to replace for %s" % sl["name"]
    p.save(out)
    log("Bluetooth patches: %s; loader %d bytes at %#x..%#x; take-over of %s (window %#x, list row %d): %s" % ("%d (the watch is open to anyone in range)" % len(SPP_PATCHES) if bluetooth_patches else "none (stock Bluetooth behaviour)", len(loader), loader_addr, lend, sl["name"], sl["window"], sl["row"],
        ", ".join("%s %#x -> b.w %#x" % (k, sl[k], v & ~1) for k, v in takeover.items())))
    log("label -> %r; changed language files: %s" % (label, ", ".join("%s (x%d)" % c for c in changed)))
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
    ap.add_argument("--loader-addr", type=num, default=FREE_START)
    ap.add_argument("--label", default="Tennis")
    ap.add_argument("--icon", help="raw 64 x 64 RGB565+alpha body from src/assets/mkicon.py: the app-list icon of the replaced entry (placed after the loader in the free flash)")
    ap.add_argument("--takeover-create", type=num, help="Thumb address (bit 0 set) inside the loader that replaces the stock window create function")
    ap.add_argument("--takeover-event", type=num, help="Thumb address inside the loader that replaces the stock window event function")
    ap.add_argument("--slot", default="World Clock", help="which entry of the app list to take over (name or window id; --list-slots shows them)")
    ap.add_argument("--list-slots", action="store_true", help="print the replaceable entries of the stock package and exit")
    ap.add_argument("--force-slot", action="store_true", help="allow a slot that is refused by default (Settings)")
    ap.add_argument("--no-bluetooth-patches", action="store_true", help="leave the Bluetooth behaviour as stock (the watch cannot then be flashed again without a reset; see docs/howto.md)")
    ap.add_argument("--languages", choices=("en", "all"), default="en", help="language files whose entry name is replaced (all: untested outside English)")
    a = ap.parse_args()
    if a.list_slots:
        p = fwd.Package.load(a.stock); raw = check_stock(p); en = next(lvlang.Lang(p.raw(k)) for k in p.paths() if k.endswith("/language_en.res"))
        print("row  window  entry                      note")
        for r in slot_table(raw, en):
            note = ("refused without --force-slot: " + FORBIDDEN[r["window"]]) if r["window"] in FORBIDDEN else (
                "default: rarely used, nothing runs in the background" if r["window"] == 0x2b else
                "replaces the stock app" + ("; it may keep timers, alarms or data running in the background" if r["window"] in WARNED else ""))
            print("%3d  %#6x  %-26s %s" % (r["row"], r["window"], r["name"], note))
        sys.exit(0)
    if not (a.out and a.loader and a.takeover_create and a.takeover_event): ap.error("out, --loader, --takeover-create and --takeover-event are required")
    build(a.stock, a.out, open(a.loader, "rb").read(), {"create": a.takeover_create, "event": a.takeover_event}, a.loader_addr, a.label, icon=open(a.icon, "rb").read() if a.icon else None,
          slot=a.slot, languages=a.languages, force_slot=a.force_slot, bluetooth_patches=not a.no_bluetooth_patches)
