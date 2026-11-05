# SPDX-License-Identifier: Apache-2.0
"""test_manager.py: the App Manager (src/watch/apps/manager.c) as the only app of the window, on the real LVGL code in the emulator.

    python3 -I src/build_firmware.py local/firmware/stock-aza3.bin local/firmware/fit3-manager.bin --app manager
    python3 -I src/firmware/fwx.py local/firmware/fit3-manager.bin main local/re/main-manager.bin
    local/venv/bin/python -I src/emu/test_manager.py

Puts .f3x files into the rig's file system (two good apps, a damaged one, one for another firmware, a tombstone), opens the page and checks the summary, the rows, the detail page with
its CRC check, the two-step Remove that writes the tombstone, and the back gesture. Limits as in rig.py: no look check (judge the look on the watch)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rig import Rig as _Rig, ROOT, A
sys.path.insert(0, os.path.join(ROOT, "src", "f3x")); sys.path.insert(0, os.path.join(ROOT, "src", "assets")); sys.path.insert(0, os.path.join(ROOT, "src", "watch"))
import tempfile, f3x, mkicon, gen

def build(name, kind):
    wd = tempfile.mkdtemp(prefix="t_mgr_"); src = os.path.join(ROOT, "src/watch/apps/%s.c" % name)
    image, off, rel = f3x.compile_app(src, wd, [gen.generate(list(gen.APPS), False, os.path.join(wd, "gen"))])
    return f3x.pack(f3x.default_name(src), image, off, rel, mkicon.encode_indexed4(*mkicon.draw(kind, 64))), image, rel
IMG = os.path.join(ROOT, os.environ.get("F3_MANAGER_IMAGE", "local/re/main-manager.bin"))
HUB = "/user/hub/a%02d.f3x"

class Rig(_Rig):
    def __init__(self): super().__init__(IMG)
    def create(self):
        scr = super().create(); k = self.children(scr); self.title, self.list = k[0], k[1]; return scr
    def rows(self): return self.children(self.list)[1:]
    def page(self): k = self.children(self.scr); return k[2] if len(k) > 2 else None

def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-manager.bin (see the docstring)"); return 0
    r = Rig(); e = r.e; res = []; ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    counter, _, _ = build("counter", "counter"); dice, _, _ = build("dice", "dice")
    damaged = bytearray(dice); damaged[-1] ^= 0xff
    other = bytearray(counter); struct.pack_into("<I", other, 8, 0x12345678)
    r.files[HUB % 0] = counter; r.files[HUB % 2] = bytes(damaged); r.files[HUB % 3] = b"F3X-GONE"; r.files[HUB % 5] = dice; r.files[HUB % 9] = bytes(other)
    scr = r.create()
    ok("the title", r.text(r.title) == "Manage apps", r.text(r.title))
    ok("the directory is created", ("mkdir_p", "/user/hub") in r.calls)
    summary = r.alltext(r.children(r.list)[0]); ok("summary: 3 apps (the damaged dice still has a valid header), 12 of 16 free", summary[:2] == ["3 apps installed", "12 of 16 slots free"], summary)
    rows = [r.alltext(x) for x in r.rows()]
    ok("one row per slot in use, in slot order; the tombstone has none", [[t for t in x if t != "!"][0] for x in rows] == ["Counter", "Dice", "Dice", "Other firmware"], rows)
    ok("the subtitle has the slot and the size", rows[0][1].startswith("Slot 00  ") and rows[0][1].endswith(" kB"), rows[0])
    r.click(r.rows()[0]); pg = r.page(); t = r.alltext(pg) if pg else []
    ok("tap a row: the detail page with name, slot, size, code and File OK", pg is not None and t[0] == "Counter" and "File OK" in t and t[-1] == "Remove", t)
    r.gesture(2); ok("the back gesture closes the page, the app stays", r.page() is None and r.e.u32(r.win + 16) != 0)
    r.click(r.rows()[1]); t = r.alltext(r.page()); ok("the damaged file: CRC check fails", "Damaged: will not open" in t, t); r.gesture(2)
    r.click(r.rows()[0]); pg = r.page(); rm = r.children(pg)[-1]
    r.click(rm); ok("first Remove asks", "Sure?" in r.alltext(pg) and r.files[HUB % 0] == counter)
    r.click(rm); ok("second Remove writes the tombstone and closes the page", r.files[HUB % 0] == b"F3X-GONE" and r.page() is None)
    rows = [[t for t in r.alltext(x) if t != "!"][0] for x in r.rows()]; ok("the list is rebuilt without it", rows == ["Dice", "Dice", "Other firmware"], rows)
    summary = r.alltext(r.children(r.list)[0]); ok("the summary follows", summary[:2] == ["2 apps installed", "13 of 16 slots free"], summary)
    r.click(r.rows()[2]); pg = r.page(); r.click(r.children(pg)[-1]); r.click(r.children(pg)[-1])
    ok("a file for another firmware can be cleared too", r.files[HUB % 9] == b"F3X-GONE")
    r.files.clear(); e.call(A["obj_del"], scr); scr = r.create()
    ok("no files: the hint", r.alltext(r.list)[-2:] == ["No apps yet", "Add apps from a PC"], r.alltext(r.list))
    n = len(res); f = n - sum(res); print("%d checks, %d failed" % (n, f)); return 1 if f else 0

if __name__ == "__main__": sys.exit(main())
