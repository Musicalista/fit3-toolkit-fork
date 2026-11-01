# SPDX-License-Identifier: Apache-2.0
"""test_host.py: the hub with native transitions (docs/details.md section 2): each app is a window of its own, id 0x10, opened with wm_open(2, 0x10, arg, 0xf) so the window manager slides it in
like a stock app. The emulator has no window manager, so this test plays its part: it reads the window record the hub writes into the RAM table, calls its create function with the argument the
hub passed to wm_open, and calls its event function. What it cannot show is the slide itself and what the real manager does with the record: that is for the watch.

    python3 -I src/build_tennis.py local/firmware/stock-aza3.bin local/firmware/fit3-hubhost.bin --hub counter,dice
    python3 -I src/firmware/fwx.py local/firmware/fit3-hubhost.bin main local/re/main-hubhost.bin
    local/venv/bin/python -I src/emu/test_host.py"""
import os, struct, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src", "f3x"))
from rig import Rig as _Rig, ROOT, A, WIN, BACK
import f3x, mkicon, gen
IMG = os.path.join(ROOT, os.environ.get("F3_HOSTIMAGE", "local/re/main-hubhost.bin"))
REC = 0x200fb4e4 + 0x10 * 0x30; LOADER = (0x2c3a0524, 0x2c3b0000)

class Rig(_Rig):
    def __init__(self): super().__init__(IMG)
    def create(self):
        scr = super().create(); self.hub = (scr, self.win); self.rows = self.children(self.children(scr)[1]); return scr
    def use(self, scr, win): self.scr, self.win = scr, win
    def manager_open(self, arg):
        """what wm_open(2, 0x10, arg, ...) makes the manager do: create the window with the record's create function, remember its screen, send the event (0, 0)"""
        create = self.e.u32(REC + 0x1c) & ~1; scr = self.e.call(create, arg); self.e.w32(REC + 0x10, scr)
        self.e.call(self.e.u32(REC + 0x24) & ~1, 0, 0, 0); self.use(scr, self.e.u32(scr + 0x10)); return scr

def build(name, kind):
    wd = tempfile.mkdtemp(prefix="t_host_"); src = os.path.join(ROOT, "src/watch/apps/%s.c" % name)
    image, off, rel = f3x.compile_app(src, wd, [gen.generate(list(gen.APPS), False, os.path.join(wd, "gen"))])
    return f3x.pack(f3x.default_name(src), image, off, rel, mkicon.encode_indexed4(*mkicon.draw(kind, 64)))

def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-hubhost.bin (see the docstring)"); return 0
    res = []; ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    dice = build("dice", "dice"); bad = bytearray(dice); bad[-5] ^= 0xff
    r = Rig(); e = r.e; r.files["/user/hub/a02.f3x"] = dice; r.files["/user/hub/a03.f3x"] = bytes(bad); scr = r.create()
    word = lambda k: e.u32(REC + 4 * k)
    ok("opening the hub fills the record of window 0x10: id and flags like World clock's (0x01d30010), words 2 and 3 as in the stock window", word(0) == 0x01d30010 and word(2) == 0x0a and word(3) == 2, [hex(word(k)) for k in range(4)])
    ok("create (+0x1c), event (+0x24) and the two hooks (+0x28, +0x2c) point into our code, Thumb addresses", all(LOADER[0] <= word(k) < LOADER[1] and word(k) & 1 for k in (7, 9, 10, 11)) and word(8) == 0, [hex(word(k)) for k in (7, 8, 9, 10, 11)])
    ok("the record's screen field is untouched (0: no screen yet)", word(4) == 0)
    e.w32(REC, 0x01d30010 | 4 << 24); r.e.call(A["obj_del"], scr); scr = r.create()
    ok("opening the hub again does not rewrite a record that is in use", word(0) == 0x01d30010 | 4 << 24, hex(word(0)))
    names = [r.alltext(x) for x in r.rows]; ok("the list: Counter, Dice (bundled) and the two installed files", names == [["Counter"], ["Dice"], ["Dice"], ["Dice"]], names)
    # ---- a tap asks the window manager; the hub does not build the app itself
    r.calls.clear(); r.click(r.rows[0]); wo = [c for c in r.calls if c[0] == "wm_open"]
    ok("a tap on a bundled app asks for wm_open(2, 0x10, index, 0xf): the stock push slide", wo == [("wm_open", 2, 0x10, 0, 0xf)], wo)
    ok("the hub window itself stays as it is (title and list, no app container)", len(r.children(scr)) == 2)
    r.click(r.rows[1]); ok("a second tap while the push is pending is ignored", len([c for c in r.calls if c[0] == "wm_open"]) == 1)
    # ---- the manager creates the window
    hub = r.hub; hs = r.manager_open(0); k = r.children(hs); st = r.e.u32(r.win + 16)
    ok("the manager's create(0) builds the Counter page as the whole screen of the app window", st != 0 and "Tap to add" in r.alltext(hs) and len(k) >= 4, r.alltext(hs))
    r.click(k[1]); r.click(k[1]); ok("it works: two taps give 2", "2" in r.alltext(hs), r.alltext(hs))
    ok("the window's own events: (0,0) sets id 0x10 as current", ("set_current", 0x10) in r.calls, [c for c in r.calls if c[0] == "set_current"])
    EV = e.u32(REC + 0x24) & ~1
    ok("key policy (0,8) = 0x2c4 and the queries 6, 7, 9 answer 0, as for every window of ours", e.call(EV, 0, 8, 0) == 0x2c4 and all(e.call(EV, 0, q, 0) == 0 for q in (6, 7, 9)) and all(e.call(EV, c, q, 0) == (0x2c4 if (c, q) == (0, 8) else 0) for c in (0, 1, 2) for q in range(12)))
    r.calls.clear(); r.gesture(2); ok("the back gesture in the app window asks the manager for the stock back slide (wm_open 3, -1, 0, 0x14)", ("wm_open", 3, 0xffffffff, 0, BACK) in r.calls and ("consume",) in r.calls, r.calls)
    r.freed.clear(); e.call(A["obj_del"], hs)
    ok("when the manager deletes the window the app is destroyed (state freed) and so is the window block", st in r.freed and len(r.freed) >= 2, [hex(x) for x in r.freed])
    e.w32(REC + 0x10, 0)
    # ---- an installed app through the host window
    r.use(*hub); r.calls.clear(); r.click(r.rows[2]); ok("the hub ignores taps while its push is pending, even after the app window is gone", not [c for c in r.calls if c[0] == "wm_open"])
    e.w32(0x200fb4e4 + WIN * 0x30 + 0x10, hub[0]); e.call(0x2c1ecd68, 0, 0, 0); r.calls.clear(); r.click(r.rows[2]); wo = [c for c in r.calls if c[0] == "wm_open"]
    ok("a tap on an installed app passes 0x100 + its slot as the argument", wo == [("wm_open", 2, 0x10, 0x102, 0xf)], wo)
    n0 = len(r.sizes); hs = r.manager_open(0x102); k = r.children(hs)
    ok("the manager's create(0x102) loads the file, relocates it and builds its page: the dice, running from the heap", "Roll" in r.alltext(hs) and "1 die" in r.alltext(hs), r.alltext(hs))
    r.click(k[4]); seen = set(); dots = lambda d: sum(1 for c in r.children(d) if not r.hidden(c))
    for _ in range(9): r.tick += 100; r.timer_cb(); seen.add(dots(k[1]))
    ok("its timer and handlers run (the roll flickers)", len(seen) > 1, seen)
    blk = [a for a, n in r.sizes.items() if n >= 1600][-1]; r.freed.clear(); e.call(A["obj_del"], hs)
    ok("deleting its window frees its code block after the app's destroy", blk in r.freed and r.freed.index(blk) > 0, [hex(x) for x in r.freed])
    e.w32(REC + 0x10, 0)
    # ---- what can go wrong
    hs = r.manager_open(0x103); ok("a damaged file (wrong CRC) gives a screen that says so, no app, nothing leaks", r.alltext(hs) == ["Cannot open this app"] and r.e.u32(r.win + 16) == 0, r.alltext(hs))
    r.calls.clear(); r.gesture(2); ok("... and the back gesture still leaves it", ("wm_open", 3, 0xffffffff, 0, BACK) in r.calls)
    r.freed.clear(); e.call(A["obj_del"], hs); ok("... and deleting it frees the window block", len(r.freed) == 1, [hex(x) for x in r.freed])
    hs = r.manager_open(0x200); ok("an argument that names nothing (0x200) gives the same screen", r.alltext(hs) == ["Cannot open this app"]); e.call(A["obj_del"], hs)
    hs = r.manager_open(0x105); ok("an empty slot (0x105) gives the same screen", r.alltext(hs) == ["Cannot open this app"]); e.call(A["obj_del"], hs)
    hs = r.manager_open(7); ok("a bundled index out of range (7) gives the same screen", r.alltext(hs) == ["Cannot open this app"]); e.call(A["obj_del"], hs)
    # ---- the hub window in this mode
    r.use(*hub); r.calls.clear(); r.gesture(2); ok("the back gesture on the list leaves the hub (wm_open 3, -1, 0, 0x14)", ("wm_open", 3, 0xffffffff, 0, BACK) in r.calls, r.calls)
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
