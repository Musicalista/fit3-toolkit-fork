# SPDX-License-Identifier: Apache-2.0
"""test_f3x.py: installed apps (.f3x files in /user/hub) in the Application Hub (fallback mode, apps in the hub's own window; test_host.py covers the default), on the real firmware code in the emulator.

    python3 -I src/build_tennis.py local/firmware/stock-aza3.bin local/firmware/fit3-hubtest.bin --hub counter --no-native-transitions
    python3 -I src/firmware/fwx.py local/firmware/fit3-hubtest.bin main local/re/main-hubtest.bin
    local/venv/bin/python -I src/emu/test_f3x.py

Builds the three apps as .f3x files (src/f3x), puts them into the rig's fake file system (a good one, a damaged one, one for another firmware, one with a bad magic), opens the hub and checks: the
directory is created, only valid headers get a row, the list is ordered bundled apps first then slots, an installed app is loaded and relocated exactly as the PC predicts and RUNS from the heap
(the emulator executes the relocated code), the CRC is checked at launch, the block is freed after the app's own destroy. Limits as in rig.py; whether the real watch lets code run from its heap
is a question for the watch."""
import os, struct, sys, tempfile, zlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src", "f3x"))
from rig import Rig as _Rig, ROOT, A, WIN, EVENT, BACK
import f3x, mkicon, gen
IMG = os.path.join(ROOT, os.environ.get("F3_FITIMAGE", "local/re/main-hubtest.bin"))

class Rig(_Rig):
    def __init__(self): super().__init__(IMG)
    def create(self):
        scr = super().create(); self.title, self.list = self.children(scr)[:2]; self.rows = self.children(self.list); return scr
    def root(self): k = self.children(self.scr); return k[2] if len(k) > 2 else None
    def app_state(self): return self.e.u32(self.win + 16)

class Rig2(Rig):
    def __init__(self): _Rig.__init__(self, os.path.join(ROOT, "local/re/main-hubempty.bin"))

def build(name, kind):
    wd = tempfile.mkdtemp(prefix="t_f3x_"); src = os.path.join(ROOT, "src/watch/apps/%s.c" % name)
    image, off, rel = f3x.compile_app(src, wd, [gen.generate(list(gen.APPS), False, os.path.join(wd, "gen"))])
    return f3x.pack(f3x.default_name(src), image, off, rel, mkicon.encode_indexed4(*mkicon.draw(kind, 64))), image, rel

def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-hubtest.bin (see the docstring)"); return 0
    res = []; ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    counter, c_img, c_rel = build("counter", "counter"); dice, d_img, d_rel = build("dice", "dice")
    r = Rig(); e = r.e; HUB = "/user/hub/a%02d.f3x"
    scr = r.create(); ok("the hub creates /user/hub on its first visit", ("mkdir_p", "/user/hub") in r.calls, r.calls)
    ok("with no files the list shows only the bundled app", [r.alltext(x) for x in r.rows] == [["Counter"]], [r.alltext(x) for x in r.rows])
    # the files
    bad_crc = bytearray(dice); bad_crc[-5] ^= 0xff                                  # a byte inside the relocation list or image: header fine, CRC wrong
    other_fw = bytearray(dice); struct.pack_into("<I", other_fw, 8, 0x12345678)
    r.files[HUB % 0] = counter; r.files[HUB % 1] = b"garbage" * 20; r.files[HUB % 2] = bytes(bad_crc); r.files[HUB % 3] = dice; r.files[HUB % 4] = bytes(other_fw); r.files[HUB % 7] = b"\0" * 8
    r.freed.clear(); e.call(A["obj_del"], scr); r.calls.clear(); scr = r.create()
    names = [r.alltext(x) for x in r.rows]
    ok("valid headers get a row, in slot order after the bundled app; garbage, other firmware and tombstones get none", names == [["Counter"], ["Counter"], ["Dice"], ["Dice"]], names)
    ok("(slot 0 is the counter, slot 2 the damaged dice, slot 3 the good dice; the damaged one passes the header check only)", True)
    ok("nothing is open and no code has been loaded yet", r.app_state() == 0 and not any(c[0] == "wm_open" for c in r.calls))
    # open the damaged one: CRC fails at launch
    r.calls.clear(); r.click(r.rows[2]); ok("a file with a wrong CRC does not open: strong buzz, no app", r.app_state() == 0 and ("motor", 4, 1) in r.calls and r.root() is None, r.calls)
    # open the good dice
    r.calls.clear(); n0 = len(r.sizes); r.click(r.rows[3]); root = r.root()
    ok("a good installed app opens in its own container", root is not None and r.app_state() != 0, r.calls)
    # the block that holds the image is the allocation of image_size + reloc_len bytes
    cand = [a for a, n in r.sizes.items() if n == ((len(d_img) + len(f3x.varints(d_rel)) + 15) & ~15)]
    blk = cand[-1]; got = e.read(blk, len(d_img)); want = bytearray(d_img)
    for o in d_rel: struct.pack_into("<I", want, o, (struct.unpack_from("<I", want, o)[0] + blk - f3x.LINK_BASE) & 0xffffffff)
    ok("the relocated image in the heap is exactly what the PC predicts (%d words moved)" % len(d_rel), bytes(got) == bytes(want))
    t = r.alltext(root); ok("the app RUNS from the heap: its page is built (title, one die, buttons)", "Dice" in t and "Roll" in t and "1 die" in t, t)
    kids = r.children(root); die = kids[1]; roll = kids[4]
    dots = lambda d: sum(1 for k in r.children(d) if not r.hidden(k))
    ok("it shows its initial face (6 dots)", dots(die) == 6, dots(die))
    r.click(roll); seen = set()
    for _ in range(9): r.tick += 100; r.timer_cb(); seen.add(dots(die))
    ok("its timer callback and event handlers run from the heap (the roll flickers and settles)", len(seen) > 1, seen)
    r.freed.clear(); r.gesture(2)
    ok("back closes it: the app's destroy ran (timer, state freed), then its code block was freed", r.root() is None and blk in r.freed and r.app_state() == 0, [hex(x) for x in r.freed])
    ok("the block was freed after the state (the app's destroy needs its own code)", r.freed.index(blk) > 0 if len(r.freed) > 1 else False, [hex(x) for x in r.freed])
    # the counter from slot 0 saves into its file: the installed app has its own /user/counter.sav
    r.click(r.rows[1]); root = r.root(); card = r.children(root)[1]
    for _ in range(3): r.click(card)
    r.gesture(2); ok("an installed counter counts and saves like the bundled one", r.files.get("/user/counter.sav", b"")[4:] == struct.pack("<i", 3), r.files.get("/user/counter.sav"))
    # delete the window with an installed app open
    r.click(r.rows[3]); blk2 = [a for a, n in r.sizes.items() if n == ((len(d_img) + len(f3x.varints(d_rel)) + 15) & ~15)][-1]; r.freed.clear(); e.call(A["obj_del"], scr)
    ok("deleting the window with an installed app open frees its code block, the list entries and the window", blk2 in r.freed and r.win in r.freed and len(r.freed) >= 5, [hex(x) for x in r.freed])
    # ---- removing an installed app from the hub: a long press (LV_EVENT_LONG_PRESSED = 5) ----
    r = Rig(); e = r.e; r.files[HUB % 0] = counter; r.files[HUB % 1] = dice; scr = r.create(); PRESSED, LONG = 1, 5
    ev = lambda o, code: e.call(A["event_send"], o, code, 0)
    sheet = lambda: r.children(r.scr)[2] if len(r.children(r.scr)) > 2 else None
    tap = lambda o: (ev(o, PRESSED), r.click(o))                                  # a real touch always starts with PRESSED
    ok("a long press on a bundled app does nothing", (ev(r.rows[0], PRESSED), ev(r.rows[0], LONG), sheet() is None)[2])
    ev(r.rows[1], PRESSED); ev(r.rows[1], LONG); sh = sheet()
    ok("a long press on an installed app opens the sheet: question, name, size, two buttons", sh is not None and r.alltext(sh) == ["Remove app?", "Counter", "3.5 kB", "Remove", "Cancel"], sh and r.alltext(sh))
    r.click(r.rows[1]); ok("the release after the long press is not a tap: the app does not open", r.app_state() == 0 and len(r.children(r.scr)) == 3)
    r.click(r.children(sh)[-1]); ok("Cancel closes the sheet and removes nothing", sheet() is None and r.files[HUB % 0] == counter and len(r.rows) == 3)
    ev(r.rows[1], PRESSED); ev(r.rows[1], LONG); r.calls.clear(); r.gesture(2)
    ok("the back gesture closes the sheet first (the hub is not left)", sheet() is None and not any(c[0] == "wm_open" for c in r.calls), r.calls)
    tap(r.rows[1]); ok("a plain tap after that still opens the app", r.app_state() != 0); r.gesture(2)
    ev(r.rows[1], PRESSED); ev(r.rows[1], LONG); sh = sheet(); r.click(r.children(sh)[-2])
    ok("Remove asks first (Sure?) and removes nothing yet", "Sure?" in r.alltext(sh) and r.files[HUB % 0] == counter)
    nw = len(r.writes); r.click(r.children(sh)[-2])
    ok("the second tap writes the tombstone over the slot", r.files[HUB % 0] == b"F3X-GONE" and len(r.writes) == nw + 1 and r.files[HUB % 1] == dice, r.files[HUB % 0])
    r.rows = r.children(r.list)
    ok("the sheet is gone and the list is rebuilt without the app: Counter (bundled) and Dice", sheet() is None and [r.alltext(x) for x in r.rows] == [["Counter"], ["Dice"]], [r.alltext(x) for x in r.rows])
    tap(r.rows[1]); ok("the remaining installed app still opens", r.app_state() != 0 and "Dice" in r.alltext(r.root())); r.gesture(2)
    ev(r.rows[1], PRESSED); ev(r.rows[1], LONG); sh = sheet(); r.click(r.children(sh)[-2]); r.click(r.children(sh)[-2]); r.rows = r.children(r.list)
    ok("removing the last installed app leaves the bundled one", [r.alltext(x) for x in r.rows] == [["Counter"]])
    e.call(A["obj_del"], scr)
    # an empty hub says so, and says so again after the last removal
    r = Rig2(); e = r.e; scr = r.create(); ok("an empty hub shows a hint instead of an empty list", r.alltext(r.list) == ["No apps yet", "Add apps from a PC"], r.alltext(r.list))
    e.call(A["obj_del"], scr); r.files[HUB % 5] = counter; scr = r.create(); rows = r.children(r.list); ok("one installed app: one row, no hint", [r.alltext(x) for x in rows] == [["Counter"]])
    ev(rows[0], PRESSED); ev(rows[0], LONG); sh = r.children(r.scr)[2]; r.click(r.children(sh)[-2]); r.click(r.children(sh)[-2])
    ok("after the last removal the hint is back and slot 5 holds the tombstone", r.alltext(r.list) == ["No apps yet", "Add apps from a PC"] and r.files[HUB % 5] == b"F3X-GONE", r.alltext(r.list))
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
