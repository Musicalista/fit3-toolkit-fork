# SPDX-License-Identifier: Apache-2.0
"""test_gameboy.py: the Game Boy app (src/watch/apps/gameboy.c, Peanut-GB inside) as the only app of the window, on the real firmware code in the emulator.

    python3 -I src/build_firmware.py local/firmware/stock-aza3.bin local/firmware/fit3-gb.bin --app gameboy
    python3 -I src/firmware/fwx.py local/firmware/fit3-gb.bin main local/re/main-gb.bin
    local/venv/bin/python -I src/emu/test_gameboy.py

Runs our hand-written test ROM (gbtest_rom.py) for a few frames through the app's timer and checks the 240 x 216 picture pixel by pixel against the 1.5x scaling of the expected
stripes, the A button (the ROM draws a block while A is held), the save-less cartridge, the messages without a ROM and with a bad checksum, and the double swipe to leave.
Speed is not measured here (the emulator is far slower than the watch)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rig import Rig as _Rig, ROOT, A
import gbtest_rom
IMG = os.path.join(ROOT, os.environ.get("F3_GB_IMAGE", "local/re/main-gb.bin"))
FB = 16 + 240 * 216 // 4
PRESSED, RELEASED = 1, 8

class Rig(_Rig):
    def __init__(self):
        super().__init__(IMG); self.e.hook(0x2c224f2c, lambda em: 0)          # keep the screen on: nothing to do here
    def st(self): return self.e.u32(self.win + 16)
    def timer(self):
        st = self.st()
        for off in range(0, self.sizes[st], 4):
            v = self.e.u32(st + off)
            if 0x20000000 <= v < 0x20800000 and v % 4 == 0 and self.e.u32(v + 12) == st: return v
    def run(self, frames):
        t = self.timer()
        for _ in range(frames): self.tick += 17; self.e.call(self.e.u32(t + 8), t)
    def fb(self):
        a = [x for x, n in self.sizes.items() if n == (FB + 15) & ~15][-1]; return self.e.read(a, FB)
    def press(self, o, code): self.e.call(A["event_send"], o, code, 0)

def pixel(fb, x, y): b = fb[16 + y * 60 + x // 4]; return (b >> (6 - 2 * (x % 4))) & 3

def expected(xd, a_held, yd=0):
    xs = xd // 3 * 2 + (1 if xd % 3 == 2 else 0)                                 # the source column (and line) of a scaled one
    ys = yd // 3 * 2 + (1 if yd % 3 == 2 else 0)
    tile = 2 if a_held and xs < 8 and ys < 8 else (xs // 8) & 1                 # the block is map entry 0: the first tile of the first row
    return 3 if tile == 2 or (tile == 1 and xs % 8 < 4) else 0

def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-gb.bin (see the docstring)"); return 0
    res = []; ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    r = Rig(); r.files["/user/gb/rom.gb"] = gbtest_rom.rom(); scr = r.create()
    k = r.children(scr); btn_a = k[8]
    ok("the directory /user/gb is created", ("mkdir_p", "/user/gb") in r.calls)
    ok("no message: the game runs", r.hidden(k[-1]), r.alltext(scr))
    r.run(6); fb = r.fb()
    rows = [0, 1, 2, 100, 215]
    bad = [(x, y) for y in rows for x in range(240) if pixel(fb, x, y) != expected(x, False, y)]
    ok("the picture: stripes scaled 1.5x, rows %s" % rows, not bad, bad[:6])
    r.press(btn_a, PRESSED); r.run(6); fb = r.fb()
    bad = [(x, y) for y in rows for x in range(240) if pixel(fb, x, y) != expected(x, True, y)]
    ok("A held: the ROM sees it and draws its block", not bad, bad[:6])
    r.press(btn_a, RELEASED); r.run(6); fb = r.fb()
    ok("A released: the block is gone", all(pixel(fb, x, 0) == expected(x, False) for x in range(240)))
    r.gesture(2); ok("first swipe: a hint, the game stays", "Swipe again to exit" in r.alltext(scr) and not any(c[0] == "wm_open" for c in r.calls), r.alltext(scr)[-1])
    r.gesture(2); ok("second swipe: the window is left", any(c[0] == "wm_open" and c[1] == 3 for c in r.calls), r.calls[-3:])
    r.freed.clear(); r.e.call(A["obj_del"], scr)
    ok("closing frees the ROM, the picture and the state; no save is written for a cartridge without RAM", len(r.freed) >= 3 and "/user/gb/rom.sav" not in r.files, len(r.freed))
    # a cartridge with RAM: the save is written when the app closes, with the game's header, and read back on the next start; another game's save is not loaded
    r4 = Rig(); r4.files["/user/gb/rom.gb"] = gbtest_rom.rom(save=True); s4 = r4.create(); r4.run(4); r4.e.call(A["obj_del"], s4)
    sav = r4.files.get("/user/gb/rom.sav", b"")
    ok("the save: header (GBS1, title) + 8 KB, the byte the game wrote", len(sav) == 24 + 8192 and sav[:4] == b"GBS1" and sav[4:11] == b"F3XTEST" and sav[24] == 0x42, (len(sav), sav[:12]))
    def cram_after_create(files):
        r5 = Rig(); r5.files.update(files); r5.create()
        a = [x for x, n in r5.sizes.items() if n == 8192][-1]; return r5.e.read(a, 1)[0]
    ok("the save is loaded on the next start", cram_after_create({"/user/gb/rom.gb": gbtest_rom.rom(save=True), "/user/gb/rom.sav": sav}) == 0x42)
    other = bytearray(sav); other[4] ^= 0x20
    ok("a save of another game is not loaded", cram_after_create({"/user/gb/rom.gb": gbtest_rom.rom(save=True), "/user/gb/rom.sav": bytes(other)}) == 0xff)
    r2 = Rig(); s2 = r2.create(); ok("no ROM: the message", "No game" in r2.alltext(s2), r2.alltext(s2))
    rom = bytearray(gbtest_rom.rom()); rom[0x14d] ^= 1
    r3 = Rig(); r3.files["/user/gb/rom.gb"] = bytes(rom); s3 = r3.create(); ok("bad header checksum: the message", "Bad ROM checksum" in r3.alltext(s3), r3.alltext(s3))
    r3.gesture(2); ok("without a game one swipe leaves", any(c[0] == "wm_open" for c in r3.calls))
    n = len(res); f = n - sum(res); print("%d checks, %d failed" % (n, f)); return 1 if f else 0

if __name__ == "__main__": sys.exit(main())
