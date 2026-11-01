# SPDX-License-Identifier: Apache-2.0
"""test_f3x.py: installed apps (.f3x files in /user/hub) in the Application Hub, on the real firmware code in the emulator.

    python3 -I src/build_tennis.py local/firmware/stock-aza3.bin local/firmware/fit3-hubtest.bin --hub counter
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
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
