"""test_loader_v2.py: the tennis window of loader v2, run on the PATCHED main image of a loader-v2 package (stock addresses 0x2c1ecc64 / 0x2c1ecd68, as the window manager calls them).

    python3 -I tools/firmware/fwx.py local/firmware/fit3-loader-v2.bin main local/re/main-v2.bin
    local/venv/bin/python -I tools/emu/test_loader_v2.py

Plays matches by sending CLICKED events to the real LVGL objects and reads back the label texts. The file functions and the tick are replaced by Python (a fake /user/tenis.sav,
a settable clock); the vibration, gesture and window-manager calls are recorded. Limits: no real font, so no text width or layout check (the emulator has no display)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
from probe_lvgl import Probe, A
IMG = os.path.join(ROOT, "local/re/main-v2.bin")
CLICKED, GESTURE, HIDDEN = 7, 12, 1
BACK = 0x14                                                                   # BACK_ANIM of loader_v2.c

class Rig:
    def __init__(self):
        self.p = Probe(IMG); self.e = e = self.p.e
        self.tick = 1000; self.file = None; self.writes = []; self.calls = []; self.freed = []; self.heap_next = 0x20600000
        e.hook(0x2c288ef4, lambda em: self.tick)
        e.hook(0x2c0eb00c, self._malloc); e.hook(0x2c0eb018, lambda em: self.freed.append(em.arg(0)) or 0)
        e.hook(0x2c0c575c, self._fopen); e.hook(0x2c142dcc, self._fread); e.hook(0x2c142ee0, self._fwrite); e.hook(0x2c142c24, self._fclose)
        e.hook(0x2c1423f8, lambda em: self.calls.append(("motor", em.arg(0), em.arg(1))) or 1)
        e.hook(0x2c224f04, lambda em: self.calls.append(("consume",)) or 0)
        e.hook(0x2c225ddc, lambda em: self.calls.append(("wm_open", em.arg(0), em.arg(1) & 0xffffffff, em.arg(2), em.arg(3))) or 0)
        e.hook(0x2c224d30, lambda em: self.calls.append(("set_current", em.arg(0))) or 0)
        self.gest = 0; e.hook(0x2c279240, lambda em: 0x20000400); e.hook(0x2c279336, lambda em: self.gest)
        self.mode = None; self.buf = b""; self.pos = 0
    def _malloc(self, em):
        a = self.heap_next; n = (em.arg(0) + 15) & ~15; self.heap_next += n; self.e.write(a, bytes(n)); return a
    def _fopen(self, em):
        path, mode = self.e.cstr(em.arg(0)), self.e.cstr(em.arg(1)); assert path == "/user/tenis.sav", path
        if mode == "r":
            if self.file is None: return 0xfffffffe
            self.mode, self.buf, self.pos = "r", self.file, 0; return 7
        self.mode, self.buf = "w", b""; return 7
    def _fread(self, em):
        n = min(em.arg(2), len(self.buf) - self.pos); self.e.write(em.arg(1), self.buf[self.pos:self.pos + n]); self.pos += n; return n
    def _fwrite(self, em): self.buf += self.e.read(em.arg(1), em.arg(2)); return em.arg(2)
    def _fclose(self, em):
        if self.mode == "w": self.file = self.buf; self.writes.append(self.buf)
        return 0
    def create(self):
        scr = self.e.call(0x2c1ecc64, 0, 0); self.scr = scr; kids = self.children(scr)
        self.hdr, self.cardA, self.cardB, self.info, self.undo, self.stats, self.ov = kids[:7]
        self.state = self.e.u32(self.e.u32(self.e.u32(scr + 8) + 0xc) + 4)
        self.e.w32(0x200fbd04, scr); self.e.write(0x200fbcf7, bytes([4]))        # window record 0x2b in RAM: +0x10 the screen, +3 bit 2 "created" (the window manager does this)
        return scr
    def children(self, o):
        spec = self.e.u32(o + 8)
        if not spec: return []
        return [self.e.u32(self.e.u32(spec) + 4 * i) for i in range(self.e.u32(spec + 4))]
    def labels(self, o):
        out = []
        for c in self.children(o):
            if self.e.u32(c) == 0x2c388a94 | 0: out.append(c)
            out += self.labels(c)
        return out
    def text(self, o): return self.e.cstr(self.e.u32(o + 0x2c))
    def alltext(self, o): return [self.text(l) for l in self.labels(o)]
    def click(self, o): self.e.call(A["event_send"], o, CLICKED, 0)
    def hidden(self, o): return bool(self.e.u32(o + 0x24) & HIDDEN)
    def pill(self, o): return self.labels(o)[0]
    def gesture(self, d): self.gest = d; self.e.call(A["event_send"], self.scr, GESTURE, 0)
    def timer_cb(self):                                                           # the 500 ms timer: find it through the state block's timer pointer (last field before txt)
        t = self.find_timer(); self.e.call(self.e.u32(t + 8), t)
    def find_timer(self):
        st = self.state
        for off in range(0, 0x1200, 4):                                           # State is ~2.6 KB; the timer pointer is the only one whose callback is in the loader
            v = self.e.u32(st + off)
            if 0x20000000 <= v < 0x20800000 and v % 4 == 0:
                try:
                    cb = self.e.u32(v + 8)
                    if 0x2c3a0524 <= (cb & ~1) < 0x2c3a1500 and self.e.u32(v + 12) == st: return v
                except Exception: pass
        raise AssertionError("timer not found")

def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-v2.bin (see the docstring)"); return 0
    r = Rig(); e = r.e; res = []
    ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    scr = r.create()
    ok("create returns a screen; 7 children (header, 2 cards, info, 2 pills, overlay)", scr and len(r.children(scr)) == 7, len(r.children(scr)))
    ok("fresh match: no header and no hint, points 0", (r.text(r.hdr), r.alltext(r.cardA)[1:], r.text(r.info)) == ("", ["0", "0"], ""), (r.text(r.hdr), r.alltext(r.cardA), r.text(r.info)))
    la = r.alltext(r.cardA); lb = r.alltext(r.cardB)
    ok("card A shows letter A, games 0, point 0", la[0] == "A" and "0" in la, la); ok("card B shows letter B", lb[0] == "B", lb)
    ok("overlay starts hidden", r.hidden(r.ov))
    # points: 15, 30, 40, then game
    r.click(r.cardA); ok("1 click = 15", r.alltext(r.cardA)[-1] == "15", r.alltext(r.cardA)); ok("header shows the match clock", r.text(r.hdr).startswith("Match "), r.text(r.hdr))
    r.click(r.cardA); r.click(r.cardA); ok("3 clicks = 40", r.alltext(r.cardA)[-1] == "40")
    r.click(r.cardA); a = r.alltext(r.cardA); ok("4th click wins the game: games 1, points 0", a[-1] == "0" and "1" in a, a)
    ok("a game was won: the strong vibration (id 4)", ("motor", 4, 1) in r.calls, r.calls[-2:])
    r.click(r.undo); ok("undo gives the point back (40)", r.alltext(r.cardA)[-1] == "40", r.alltext(r.cardA))
    # deuce and advantage
    for _ in range(3): r.click(r.cardB)
    ok("40-40 shows 40 / 40", (r.alltext(r.cardA)[-1], r.alltext(r.cardB)[-1]) == ("40", "40"))
    r.click(r.cardA); ok("advantage A shows AD / 40", (r.alltext(r.cardA)[-1], r.alltext(r.cardB)[-1]) == ("AD", "40"), (r.alltext(r.cardA), r.alltext(r.cardB)))
    # serve indicator: exactly one dot visible
    # save: advance the clock past the 3 s debounce, run the tick timer
    r.tick += 4000; r.timer_cb()
    ok("the state is saved 3 s after the last change (one write)", len(r.writes) == 1 and r.writes[0][:4] == struct.pack("<I", 0x54454e33), len(r.writes[0]) if r.writes else 0)
    size = len(r.writes[0]); ok("the save file is small (< 160 bytes)", size < 160, size)
    r.tick += 4000; r.timer_cb(); ok("no further writes without a change", len(r.writes) == 1)
    # stats overlay
    r.click(r.stats); ok("Stats shows the overlay", not r.hidden(r.ov), r.alltext(r.ov))
    ok("overlay lists set 1", any(t.startswith("S1  ") for t in r.alltext(r.ov)), r.alltext(r.ov))
    new_btn, back_btn = r.children(r.ov)[-2:]
    r.click(new_btn); ok("New asks first (Sure?)", "Sure?" in r.alltext(r.ov), r.alltext(r.ov)); ok("...and nothing is reset yet", r.alltext(r.cardA)[-1] == "AD")
    r.tick += 3000; r.timer_cb(); ok("the confirmation expires after 2.5 s", "New" in r.alltext(r.ov), r.alltext(r.ov))
    r.calls.clear(); r.gesture(2); ok("back gesture with the overlay open closes the overlay only", r.hidden(r.ov) and not any(c[0] == "wm_open" for c in r.calls), r.calls)
    r.calls.clear(); r.gesture(3); ok("a left gesture does nothing", not r.calls, r.calls)
    r.gesture(2); ok("back gesture on the score page leaves the window (wm_open 3,-1,0,BACK)", ("wm_open", 3, 0xffffffff, 0, BACK) in r.calls, r.calls)
    # side key (T7): the manager asks (0,8) for the key policy; 0x2c4 (bit 6 set) lets the manager itself send the short press to the watch face, as the stock windows do
    ok("key policy (0,8) = 0x2c4, the stock windows' answer", e.call(0x2c1ecd68, 0, 8, 0) == 0x2c4, hex(e.call(0x2c1ecd68, 0, 8, 0)))
    ok("the garbage-free arguments: upper bytes are masked", e.call(0x2c1ecd68, 0xabcd0000, 0x12340008, 0) == 0x2c4)
    # T8: the manager asks (0, 7) and (0, 9) whether it should run its own swipe-back and which animation; a garbage answer made it animate to the wrong side
    ok("window queries 6, 7 and 9 answer 0, so the manager runs no swipe of its own", all(e.call(0x2c1ecd68, 0, k, 0) == 0 for k in (6, 7, 9)), [e.call(0x2c1ecd68, 0, k, 0) for k in (6, 7, 9)])
    ok("every window event answers a defined value (0 except the policy)", all(e.call(0x2c1ecd68, c, k, 0) == (0x2c4 if (c, k) == (0, 8) else 0) for c in (0, 1, 2) for k in range(12)))
    r.calls.clear(); e.call(0x2c1ecd68, 1, 6, 0); ok("the short press of the side key is left to the manager (we do not call wm)", not r.calls, r.calls)
    # delete the window: flush (nothing dirty) + free the state, timer deleted
    r.click(r.cardB); ok("a new point makes the state dirty", True)
    log = []; e.hook(0x2c28a448, lambda em: log.append(("timer_del", em.arg(0))) or 0)
    nwrites = len(r.writes); e.call(A["obj_del"], scr)
    ok("closing the window saves unsaved points", len(r.writes) == nwrites + 1)
    ok("closing the window deletes the timer and frees the state", any(l[0] == "timer_del" for l in log) and r.state in r.freed, (log, [hex(x) for x in r.freed]))
    # reopen after a "reboot": ticks restart from 0, the saved match is back, the clock continues
    saved = r.file; r.tick = 500; r.freed.clear()
    scr2 = r.create(); a2, b2 = r.alltext(r.cardA), r.alltext(r.cardB)
    ok("after a restart the saved match is shown (advantage A, then a point for B: 40-40)", (a2[-1], b2[-1]) == ("40", "40"), (a2, b2))
    ok("... and its clock continues from the save instead of jumping", r.text(r.hdr).startswith("Match ") and int(r.text(r.hdr).split(" ")[1].split(":")[0]) < 5, r.text(r.hdr))
    # play to the end: A wins two sets 6-0
    r.click(r.stats); nb = r.children(r.ov)[-2]; r.click(nb); r.click(nb); ok("New twice resets the match", r.alltext(r.cardA)[-1] == "0" and r.text(r.hdr) == "", (r.alltext(r.cardA), r.text(r.hdr)))
    ok("...and closes the overlay", r.hidden(r.ov))
    for _ in range(48): r.click(r.cardA)
    ok("two sets 6-0 win the match: WIN on A, 'Match over'", r.alltext(r.cardA)[-1] == "WIN" and r.text(r.info) == "Match over", (r.alltext(r.cardA), r.text(r.info)))
    r.click(r.cardA); ok("clicks after the end change nothing", r.alltext(r.cardB)[-1] == "")
    r.click(r.stats); ok("stats of a finished match list 2 sets", sum(1 for t in r.alltext(r.ov) if t.startswith("S")) >= 2 and "S2  6-0" in " ".join(r.alltext(r.ov)).replace("  ", "  "), r.alltext(r.ov))
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
