# SPDX-License-Identifier: Apache-2.0
"""test_mars.py: the Mars Production app (src/watch/apps/mars.c) as the only app of the window, on the real LVGL code in the emulator.

    python3 -I src/build_tennis.py local/firmware/stock-aza3.bin local/firmware/fit3-mars.bin --app mars
    python3 -I src/firmware/fwx.py local/firmware/fit3-mars.bin main local/re/main-mars.bin
    local/venv/bin/python -I src/emu/test_mars.py

Taps the real buttons and reads the labels back. Limits as in rig.py: no look or layout check (the emulator draws rounded cards with children wrongly: judge the look on the watch)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rig import Rig as _Rig, ROOT, A, BACK
IMG = os.path.join(ROOT, os.environ.get("F3_MARS_IMAGE", "local/re/main-mars.bin"))
PATH = "/user/mars.sav"

class Rig(_Rig):
    def __init__(self): super().__init__(IMG)
    def create(self):
        scr = super().create(); k = self.children(scr); self.rows = k[:6]; self.reset = k[6]
        self.minus = [self.children(r)[1] for r in self.rows]; self.val = [self.children(r)[2] for r in self.rows]; self.plus = [self.children(r)[3] for r in self.rows]
        return scr
    def values(self): return [self.text(v) for v in self.val]

def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-mars.bin (see the docstring)"); return 0
    r = Rig(); e = r.e; res = []; ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    scr = r.create()
    ok("seven children: six rows and the Reset pill", len(r.children(scr)) == 7, len(r.children(scr)))
    ok("each row has the name, a minus button, the value and a plus button", all(len(r.children(x)) == 4 for x in r.rows))
    ok("the names, in the order of the game", [r.text(r.children(x)[0]) for x in r.rows] == ["Credits", "Steel", "Titanium", "Plants", "Energy", "Heat"])
    ok("everything starts at 0", r.values() == ["0"] * 6, r.values())
    for _ in range(3): r.click(r.plus[1])
    ok("three taps on + of Steel give 3, the others stay 0", r.values() == ["0", "3", "0", "0", "0", "0"], r.values())
    r.click(r.minus[1]); ok("- takes one back", r.text(r.val[1]) == "2")
    for _ in range(5): r.click(r.minus[2])
    ok("Titanium cannot go below 0", r.text(r.val[2]) == "0")
    for _ in range(8): r.click(r.minus[0])
    ok("Credits go down to -5 and stop", r.text(r.val[0]) == "-5", r.text(r.val[0]))
    r.click(r.plus[0]); ok("... and come back up (-4)", r.text(r.val[0]) == "-4")
    for _ in range(120): r.click(r.plus[5])
    ok("a track stops at 99", r.text(r.val[5]) == "99", r.text(r.val[5]))
    ok("every tap gave a short vibration", ("motor", 1, 1) in r.calls)
    # saving
    r.tick += 4000; r.timer_cb(); sv = r.files.get(PATH)
    ok("the values are saved 3 s after the last change (one write)", sv is not None and len(r.writes) == 1 and sv[:4] == struct.pack("<I", 0x3152414d) and list(struct.unpack("<6b", sv[4:10])) == [-4, 2, 0, 0, 0, 99], sv and sv.hex())
    r.tick += 4000; r.timer_cb(); ok("no further writes without a change", len(r.writes) == 1)
    # reset asks twice
    r.click(r.reset); ok("Reset asks first (Sure?) and keeps the values", r.text(r.children(r.reset)[0]) == "Sure?" and r.text(r.val[5]) == "99")
    r.tick += 3000; r.timer_cb(); ok("the confirmation expires", r.text(r.children(r.reset)[0]) == "Reset")
    r.click(r.reset); r.click(r.reset); ok("Reset twice zeroes everything", r.values() == ["0"] * 6, r.values())
    for _ in range(4): r.click(r.plus[4])
    # the back gesture leaves the window; closing saves unsaved changes
    r.calls.clear(); r.gesture(2); ok("back gesture leaves the window", ("wm_open", 3, 0xffffffff, 0, BACK) in r.calls, r.calls)
    nw = len(r.writes); st = r.state; r.freed.clear(); e.call(A["obj_del"], scr)
    ok("closing saves the unsaved change and frees the state", len(r.writes) == nw + 1 and st in r.freed and struct.unpack("<6b", r.files[PATH][4:10]) == (0, 0, 0, 0, 4, 0), (len(r.writes) - nw, r.files[PATH].hex()))
    # reopen: the values are back; a damaged save file is ignored
    scr = r.create(); ok("after a restart the saved values are back", r.values() == ["0", "0", "0", "0", "4", "0"], r.values())
    r.files[PATH] = struct.pack("<I6bxx", 0x3152414d, -9, 0, 0, 0, 0, 0); e.call(A["obj_del"], scr); scr = r.create()
    ok("a save file with a value out of range (Credits -9) is ignored", r.values() == ["0"] * 6, r.values())
    r.files[PATH] = struct.pack("<I6bxx", 0x12345678, 1, 1, 1, 1, 1, 1); e.call(A["obj_del"], scr); scr = r.create()
    ok("a save file with another magic is ignored", r.values() == ["0"] * 6, r.values())
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
