# SPDX-License-Identifier: Apache-2.0
"""test_hub.py: the Application Hub (src/watch/hub.c with the apps tennis, counter, dice) on the PATCHED main image of a package built with `build_tennis.py --hub tennis,counter,dice`.

    python3 -I src/build_tennis.py local/firmware/stock-aza3.bin local/firmware/fit3-hub.bin --hub tennis,counter,dice
    python3 -I src/firmware/fwx.py local/firmware/fit3-hub.bin main local/re/main-hub.bin
    local/venv/bin/python -I src/emu/test_hub.py

Opens each app from the list by clicking its row, plays with it through the real LVGL objects, uses the back gesture, and checks the cleanup (widgets deleted, timers deleted, states freed,
files saved). Limits as in rig.py: no display, so no layout or look check (src/emu/screenshot.py renders the pages)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rig import Rig as _Rig, ROOT, A, WIN, EVENT, BACK
IMG = os.path.join(ROOT, os.environ.get("F3_HUB_IMAGE", "local/re/main-hub.bin"))

class Rig(_Rig):
    def __init__(self): super().__init__(IMG)
    def create(self):
        scr = super().create(); self.title, self.list = self.children(scr)[:2]; self.rows = self.children(self.list); return scr
    def root(self): k = self.children(self.scr); return k[2] if len(k) > 2 else None
    def app_state(self): return self.e.u32(self.win + 16)
    def shown(self, o): return [k for k in self.children(o) if not self.hidden(k)]

def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-hub.bin (see the docstring)"); return 0
    r = Rig(); e = r.e; res = []
    ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    scr = r.create()
    ok("the window has a title and a list, nothing else", len(r.children(scr)) == 2 and r.alltext(r.title) == [] and r.text(r.children(scr)[0]) == "Applications", [len(r.children(scr))])
    ok("the list has one row per app, in order, each with the app's name", [r.alltext(x) for x in r.rows] == [["Tennis Score"], ["Counter"], ["Dice"]], [r.alltext(x) for x in r.rows])
    ok("no app is open yet (state 0)", r.app_state() == 0)
    # the icons: each row has an image object that took our 40 x 40 four-bit descriptor
    e.call(A["update_layout"], scr); box = lambda o: [e.i32(o + 0x14 + 4 * k) for k in range(4)]
    imgs = [[k for k in r.children(x) if k not in r.labels(x)] for x in r.rows]
    ok("every row has exactly one image child", all(len(i) == 1 for i in imgs), imgs)
    sizes = [(box(i[0])[2] - box(i[0])[0] + 1, box(i[0])[3] - box(i[0])[1] + 1) for i in imgs]
    ok("the images are 40 x 40", all(s == (40, 40) for s in sizes), sizes)
    cf = [struct.unpack_from("<I", e.read(i[0] + 0x50, 4))[0] & 31 for i in imgs]
    ok("the images took four-bit indexed descriptors (cf 9)", cf == [9, 9, 9], cf)
    rb = [box(x) for x in r.rows]; ok("rows are cards one below the other, 64 px high", all(b[3] - b[1] + 1 == 64 for b in rb) and rb[0][3] < rb[1][1] < rb[2][1], rb)
    # --- counter
    r.click(r.rows[1]); root = r.root(); ok("a click on the Counter row opens the app in its own container", root is not None and r.app_state() != 0 and ("motor", 1, 1) in r.calls, r.calls)
    st = r.app_state(); t = r.alltext(root); ok("the counter starts at 0", "0" in t and "Counter" in t, t)
    card = r.children(root)[1]
    for _ in range(3): r.click(card)
    ok("three taps give 3", "3" in r.alltext(root), r.alltext(root))
    minus, reset = r.children(root)[2:4]
    r.click(minus); ok("-1 gives 2", "2" in r.alltext(root), r.alltext(root))
    r.click(reset); ok("Reset asks first (Sure?) and keeps the count", "Sure?" in r.alltext(root) and "2" in r.alltext(root), r.alltext(root))
    r.tick += 3000; r.timer_cb(); ok("the confirmation expires", "Reset" in r.alltext(root), r.alltext(root))
    r.click(card); r.click(card); r.tick += 4000; r.timer_cb()
    ok("the count is saved 3 s after the last change", r.files.get("/user/counter.sav") == struct.pack("<Ii", 0x434e5431, 4), r.files.get("/user/counter.sav"))
    r.click(reset); r.click(reset); ok("Reset twice zeroes it", "0" in r.alltext(root), r.alltext(root))
    r.click(card); r.click(card); r.click(card); r.click(card); r.click(card)
    r.calls.clear(); r.freed.clear(); nw = len(r.writes); r.gesture(2)
    ok("the back gesture closes the app (not the window): root deleted, list shown again", r.root() is None and not any(c[0] == "wm_open" for c in r.calls) and r.app_state() == 0, r.calls)
    ok("... the state is freed and the unsaved count is written", st in r.freed and len(r.writes) == nw + 1 and r.files["/user/counter.sav"] == struct.pack("<Ii", 0x434e5431, 5), (st in r.freed, len(r.writes) - nw))
    ok("... and the gesture was consumed", ("consume",) in r.calls)
    r.click(r.rows[1]); root = r.root(); ok("reopened: the saved count (5) is back", "5" in r.alltext(root), r.alltext(root)); r.gesture(2)
    # --- dice
    r.click(r.rows[2]); root = r.root(); kids = r.children(root); die = kids[1:3]; l_sum = kids[3]; b_roll, b_n = kids[4:6]
    t = r.alltext(root); ok("dice opens with one die showing 6, the title and the '1 die' pill", t[0] == "Dice" and "1 die" in t and r.text(l_sum) == "", t)
    dots = lambda d: sum(1 for k in r.children(d) if not r.hidden(k))
    ok("a die shows as many dots as its value (6)", dots(die[0]) == 6 and not r.hidden(die[0]) and r.hidden(die[1]), (dots(die[0]), r.hidden(die[0]), r.hidden(die[1])))
    r.click(b_roll); seen = set()
    for _ in range(9): r.tick += 100; r.timer_cb(); seen.add(dots(die[0]))
    ok("rolling flickers through faces and ends on a value 1..6", len(seen) > 1 and all(1 <= v <= 6 for v in seen), seen)
    v = dots(die[0]); r.tick += 100; r.timer_cb(); ok("after the roll nothing changes any more", dots(die[0]) == v and ("motor", 4, 1) in r.calls, (v, dots(die[0])))
    r.click(b_n); t = r.alltext(root); ok("the second pill switches to two dice: both shown, a sum", "2 dice" in t and not r.hidden(die[1]) and r.text(l_sum).startswith("Sum "), t)
    r.click(die[1])
    for _ in range(9): r.tick += 100; r.timer_cb()
    total = dots(die[0]) + dots(die[1]); ok("the sum is the sum of the dots", r.text(l_sum) == "Sum %d" % total and 2 <= total <= 12, (r.text(l_sum), total))
    rolls = set()
    for _ in range(40):
        r.click(b_roll)
        for _ in range(9): r.tick += 37; r.timer_cb()
        rolls.add(dots(die[0]))
    ok("40 rolls give all six faces (the generator is not stuck)", rolls == {1, 2, 3, 4, 5, 6}, sorted(rolls))
    st = r.app_state(); r.freed.clear(); log = []; e.hook(0x2c28a448, lambda em: log.append(em.arg(0)) or 0); r.gesture(2)
    ok("back closes the dice app: timer deleted, state freed", log and st in r.freed and r.root() is None, (log, [hex(x) for x in r.freed]))
    # --- tennis in the hub
    r.click(r.rows[0]); root = r.root(); kids = r.children(root); cardA, undo, stats, ov = kids[1], kids[6], kids[7], kids[8]
    ok("tennis opens as an app of the hub: 9 children", len(kids) == 9, len(kids)); r.click(cardA); ok("a tap on card A gives 15", "15" in r.alltext(cardA), r.alltext(cardA))
    r.click(stats); ok("Stats shows the overlay", not r.hidden(ov)); r.calls.clear(); r.gesture(2)
    ok("back closes the overlay first and the app stays open", r.hidden(ov) and r.root() is not None and not any(c[0] == "wm_open" for c in r.calls), r.calls)
    r.tick += 4000; r.timer_cb(); ok("the match is saved (one write to tenis.sav)", "/user/tenis.sav" in r.files)
    r.gesture(2); ok("the next back closes tennis and shows the list", r.root() is None and r.app_state() == 0)
    r.calls.clear(); r.gesture(2); ok("back on the list leaves the window (wm_open 3,-1,0,BACK)", ("wm_open", 3, 0xffffffff, 0, BACK) in r.calls, r.calls)
    r.calls.clear(); r.gesture(3); ok("a left gesture does nothing", not r.calls)
    # --- window deleted while an app is open
    r.click(r.rows[1]); st = r.app_state(); r.freed.clear(); r.click(r.children(r.root())[1]); nw = len(r.writes); e.call(A["obj_del"], scr)
    ok("deleting the window with an app open destroys the app (saves, frees its state) and frees the window block", len(r.writes) == nw + 1 and st in r.freed and r.win in r.freed, (len(r.writes) - nw, [hex(x) for x in r.freed]))
    # --- the window manager side is the same as for the single-app window
    ok("key policy (0,8) = 0x2c4; queries 6, 7, 9 answer 0; entering sets the window id", e.call(EVENT, 0, 8, 0) == 0x2c4 and all(e.call(EVENT, 0, k, 0) == 0 for k in (6, 7, 9)))
    ok("every window event answers a defined value", all(e.call(EVENT, c, k, 0) == (0x2c4 if (c, k) == (0, 8) else 0) for c in (0, 1, 2) for k in range(12)))
    r.calls.clear(); e.call(EVENT, 0, 0, 0); ok("entering the window sets its own id", ("set_current", WIN) in r.calls, r.calls)
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
