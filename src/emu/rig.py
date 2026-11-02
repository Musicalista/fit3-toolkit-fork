# SPDX-License-Identifier: Apache-2.0
"""rig.py: the common test rig of the watch code (hub.c and its apps) on the real firmware in the emulator.

A Python replacement for the tick, the heap, the file functions and the window-manager calls (recorded in `calls`), the real LVGL objects for everything else. Used by test_tennis.py and test_hub.py
(and screenshot.py has its own, with a display). The window it creates is the one the image replaces: World clock (0x2b) by default; F3_WINDOW, F3_CREATE, F3_EVENT select another slot."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
from probe_lvgl import Probe, A
# the window this image replaces; the defaults are World clock (window 0x2b). For another slot: F3_WINDOW, F3_CREATE, F3_EVENT, F3_DESTROY (the stock addresses, see build_package.py --list-slots)
WIN = int(os.environ.get("F3_WINDOW", "0x2b"), 0); CREATE = int(os.environ.get("F3_CREATE", "0x2c1ecc64"), 0); EVENT = int(os.environ.get("F3_EVENT", "0x2c1ecd68"), 0)
CLICKED, GESTURE, HIDDEN = 7, 12, 1
BACK = 0x14                                                                   # BACK_ANIM of ui.h

def bl_target(raw, addr):
    """the target of the Thumb-2 BL or B.W at `addr` in a main image (to find where a patched site now goes)"""
    h1, h2 = struct.unpack_from("<HH", raw, addr - 0x2c080000)
    assert h1 & 0xf800 == 0xf000 and h2 & 0xd000 in (0xd000, 0x9000), "not a BL or B.W at %#x" % addr
    s = (h1 >> 10) & 1; i1 = ~((h2 >> 13) ^ s) & 1; i2 = ~((h2 >> 11) ^ s) & 1
    off = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3ff) << 12) | ((h2 & 0x7ff) << 1)
    if s: off -= 1 << 25
    return addr + 4 + off


class Rig:
    def __init__(self, image):
        self.p = Probe(image); self.e = e = self.p.e
        self.tick = 1000; self.writes = []; self.calls = []; self.freed = []; self.sizes = {}; self.heap_next = 0x20600000
        e.hook(0x2c288ef4, lambda em: self.tick)
        e.hook(0x2c0eb00c, self._malloc); e.hook(0x2c0eb018, lambda em: self.freed.append(em.arg(0)) or 0)
        e.hook(0x2c0c575c, self._fopen); e.hook(0x2c142dcc, self._fread); e.hook(0x2c142ee0, self._fwrite); e.hook(0x2c142c24, self._fclose)
        e.hook(0x2c1423f8, lambda em: self.calls.append(("motor", em.arg(0), em.arg(1))) or 1)
        e.hook(0x2c224f04, lambda em: self.calls.append(("consume",)) or 0)
        e.hook(0x2c225ddc, lambda em: self.calls.append(("wm_open", em.arg(0), em.arg(1) & 0xffffffff, em.arg(2), em.arg(3))) or 0)
        e.hook(0x2c224d30, lambda em: self.calls.append(("set_current", em.arg(0))) or 0)
        e.hook(0x2c1435e0, lambda em: self.calls.append(("mkdir_p", self.e.cstr(em.arg(0)))) or 0)
        self.gest = 0; e.hook(0x2c279240, lambda em: 0x20000400); e.hook(0x2c279336, lambda em: self.gest)
        self.mode = None; self.buf = b""; self.pos = 0; self.files = {}; self.path = None
    def _malloc(self, em):
        a = self.heap_next; n = (em.arg(0) + 15) & ~15; self.sizes[a] = n; self.heap_next += n; self.e.write(a, bytes(n)); return a
    def _fopen(self, em):
        path, mode = self.e.cstr(em.arg(0)), self.e.cstr(em.arg(1)); self.path = path
        if mode == "r":
            if path not in self.files: return 0xfffffffe
            self.mode, self.buf, self.pos = "r", self.files[path], 0; return 7
        self.mode, self.buf = "w", b""; return 7
    def _fread(self, em):
        n = min(em.arg(2), len(self.buf) - self.pos); self.e.write(em.arg(1), self.buf[self.pos:self.pos + n]); self.pos += n; return n
    def _fwrite(self, em): self.buf += self.e.read(em.arg(1), em.arg(2)); return em.arg(2)
    def _fclose(self, em):
        if self.mode == "w": self.files[self.path] = self.buf; self.writes.append(self.buf)
        return 0
    def create(self):
        scr = self.e.call(CREATE, 0, 0); self.scr = scr
        self.win = self.e.u32(scr + 0x10); self.state = self.e.u32(self.win + 16)        # the window block (Win in hub.c); its offset 16 holds the open app's state
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
        st = self.e.u32(self.win + 16)                                        # the open app's state block
        for off in range(0, self.sizes[st], 4):                                           # State is ~2.6 KB; the timer pointer is the only one whose callback is in the loader
            v = self.e.u32(st + off)
            if 0x20000000 <= v < 0x20800000 and v % 4 == 0:
                try:
                    cb = self.e.u32(v + 8)
                    if (0x2c3a0524 <= (cb & ~1) < 0x2c3b0000 or 0x20000000 <= cb < 0x20800000) and self.e.u32(v + 12) == st: return v
                except Exception: pass
        raise AssertionError("timer not found")

