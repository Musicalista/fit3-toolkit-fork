# SPDX-License-Identifier: Apache-2.0
"""screenshot.py: render the tennis window with the firmware's own LVGL code on the PC, and save PNG screenshots.

    python3 -I tools/firmware/fwx.py local/firmware/fit3-tennis.bin main local/re/main-v2.bin
    local/venv/bin/python -I tools/emu/screenshot.py <outdir> [--fonts local/assets/fonts]

The real firmware code runs in the emulator: `fonts_init` loads the Roboto fonts from the files you pulled from your watch (tools/device/f3_pull.py), our window is created by the
patched stock address, and LVGL's software renderer draws it into a 256 x 402 RGB565 buffer through the display driver's flush callback. Screens: the empty score page, a match in progress,
the stats overlay, a finished match. Needs the unicorn venv (tools/emu/README.md), local/re/main-v2.bin and the fonts. Not modelled: the real display, touch, the status of other windows.
The fonts are Samsung's files, but a rendered picture contains no font file; the layout, colours and drawing are what the watch does (the text is the loader's own)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
from probe_lvgl import Probe, A

W, H = 256, 402
FONT_DIR = os.path.join(ROOT, "local/assets/fonts")


class Screen:
    def __init__(self, image, fonts):
        self.p = Probe(image); self.e = e = self.p.e
        self.tick = 1000; self.fb = bytearray(W * H * 2); self.flushes = 0; self.files = {}; self.nextfd = 1
        e.hook(0x2c288ef4, lambda em: self.tick)                                       # lv_tick_get
        self.heap = 0x20600000
        e.hook(0x2c0eb00c, self._malloc); e.hook(0x2c0eb018, lambda em: 0)             # app_malloc / app_free
        e.hook(0x2c0c575c, lambda em: 0xfffffffe)                                      # fopen: no save file
        e.hook(0x2c1423f8, lambda em: 1)                                               # motor_once
        e.hook(0x2c224d30, lambda em: 0); e.hook(0x2c224f04, lambda em: 0); e.hook(0x2c225ddc, lambda em: 0)
        self.fonts = fonts; self.handles = {}
        e.hook(0x2c28c544, self._fs_open); e.hook(0x2c28c274, self._fs_read); e.hook(0x2c28c424, self._fs_seek); e.hook(0x2c28c234, lambda em: 0)
        # replace the display's flush callback (the Probe installed a no-op one) by one that keeps the pixels
        self.flush_addr = 0x20000200; e.hook(self.flush_addr, self._flush)
    def _malloc(self, em):
        a = self.heap; n = (em.arg(0) + 15) & ~15; self.heap += n; self.e.write(a, bytes(n)); return a
    # --- a tiny file system for lv_font_load: P:/nand/system/font/<name> -> files in the fonts folder
    def _fs_open(self, em):
        path = self.e.cstr(em.arg(1)); name = os.path.basename(path); f = os.path.join(self.fonts, name)
        if not os.path.isfile(f): return 2                                              # LV_FS_RES_NOT_EX
        fd = self.nextfd; self.nextfd += 1; self.handles[fd] = [open(f, "rb").read(), 0]
        self.e.w32(em.arg(0), fd); self.e.w32(em.arg(0) + 4, 1); return 0
    def _fs_read(self, em):
        h = self.handles[self.e.u32(em.arg(0))]; n = min(em.arg(2), len(h[0]) - h[1]); self.e.write(em.arg(1), h[0][h[1]:h[1] + n]); h[1] += n
        if em.arg(3): self.e.w32(em.arg(3), n)
        return 0
    def _fs_seek(self, em):
        h = self.handles[self.e.u32(em.arg(0))]; pos, wh = em.arg(1), em.arg(2)
        h[1] = pos if wh == 0 else h[1] + pos if wh == 1 else len(h[0]) + pos; return 0
    def _flush(self, em):
        # lv_disp_drv.flush_cb(drv, area, color_p); with LV_USE_LARGE_COORD an lv_area_t is four int32 (T1)
        x1, y1, x2, y2 = struct.unpack("<iiii", self.e.read(em.arg(1), 16)); w = x2 - x1 + 1
        px = self.e.read(em.arg(2), w * (y2 - y1 + 1) * 2)
        for r in range(y2 - y1 + 1): self.fb[((y1 + r) * W + x1) * 2:((y1 + r) * W + x1 + w) * 2] = px[r * w * 2:(r + 1) * w * 2]
        self.flushes += 1; self.last_area = (x1, y1, x2, y2)
        # lv_disp_flush_ready: in this build the draw buffer is {buf1, buf2, buf_act, size, flushing, flushing_last, ...}; the refresh waits while the word at +0x10 is set
        dsc = self.e.u32(em.arg(0) + 0x18); self.e.w32(dsc + 0x10, 0); self.e.w32(dsc + 0x14, 0)
        return 0
    def seed_txt(self):
        """The firmware's UTF-8 helpers of lv_txt live in a table of function pointers in .data (0x200fd848..0x200fd868) that the C start-up fills on the watch and the emulator does not run.
        We install Python versions; read from how the firmware calls them: 0x858 next(text, &i), 0x85c prev(text, &i), 0x860 size(text) (compared with 1), 0x864 length(text), 0x850/0x854 conversions of a code point; 0x868 is used by two rarely used functions and gets the length as well. self.txt_log counts the calls."""
        e = self.e; self.txt_log = {}
        def dec(txt, i):                                    # the character that starts at byte i and its length
            b = e.u8(txt + i); n = 1 if b < 0x80 else 2 if b >> 5 == 6 else 3 if b >> 4 == 14 else 4
            return ord(e.read(txt + i, n).decode("utf-8", "replace")[0]), n
        def start_of_prev(txt, i):
            i -= 1
            while i > 0 and (e.u8(txt + i) & 0xC0) == 0x80: i -= 1
            return i
        def f_next(em):                                     # (txt, &i): the character at i, i advances
            txt, ip = em.arg(0), em.arg(1); i = e.u32(ip) if ip else 0; ch, n = dec(txt, i)
            if ip: e.w32(ip, i + n)
            return ch
        def f_prev(em):                                     # (txt, &i): the character before i, i moves back
            txt, ip = em.arg(0), em.arg(1); j = start_of_prev(txt, e.u32(ip)); e.w32(ip, j); return dec(txt, j)[0]
        def f_size(em):                                     # (txt): bytes of the character at txt
            b = e.u8(em.arg(0)); return 1 if b < 0x80 else 2 if b >> 5 == 6 else 3 if b >> 4 == 14 else 4
        def f_len(em): return len(e.cstr(em.arg(0), 4096).encode("latin1").decode("utf-8", "replace"))
        def f_byte_id(em):                                  # (txt, char index) -> byte offset
            txt, k = em.arg(0), em.arg(1); i = 0
            for _ in range(k): i += dec(txt, i)[1]
            return i
        def f_char_id(em):                                  # (txt, byte offset) -> char index
            txt, off = em.arg(0), em.arg(1); i = k = 0
            while i < off: i += dec(txt, i)[1]; k += 1
            return k
        def ident(em): return em.arg(0)                     # unicode <-> encoded: UTF-8 is its own encoding for ASCII, which is all our screens use
        table = {0x850: ident, 0x854: ident, 0x858: f_next, 0x85c: f_prev, 0x860: f_size, 0x864: f_len, 0x868: f_len}
        for off, fn in table.items():
            slot = 0x200fd000 + off; addr = 0x20000600 + (off - 0x848) * 0x10
            def wrap(fn, off): 
                def g(em): self.txt_log[off] = self.txt_log.get(off, 0) + 1; return fn(em)
                return g
            e.hook(addr, wrap(fn, off)); e.w32(slot, addr | 1)
    def load_fonts(self):
        self.e.call(0x2c1006b0, max_insns=2_000_000_000)                                                       # fonts_init: the firmware loads its Roboto files
        slots = [self.e.u32(0x2010b0e0 + 4 * i) for i in range(11)]
        return slots
    def show(self, scr):
        self.e.call(0x2c275b16, scr); self.settle()
    def settle(self, rounds=12):
        for _ in range(rounds): self.tick += 60; self.e.call(0x2c28a46c, max_insns=4_000_000_000)             # lv_timer_handler: runs the refresh timer
    def png(self, path, scale=2):
        from PIL import Image
        im = Image.new("RGB", (W, H))
        px = im.load()
        for y in range(H):
            for x in range(W):
                v = self.fb[(y * W + x) * 2] | self.fb[(y * W + x) * 2 + 1] << 8
                px[x, y] = (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)
        if scale != 1: im = im.resize((W * scale, H * scale), Image.NEAREST)
        im.save(path); return im


def children(e, o):
    spec = e.u32(o + 8)
    return [e.u32(e.u32(spec) + 4 * i) for i in range(e.u32(spec + 4))] if spec else []


def main(argv):
    out = argv[0] if argv else "build/shots"; fonts = argv[argv.index("--fonts") + 1] if "--fonts" in argv else FONT_DIR
    image = os.path.join(ROOT, os.environ.get("F3_IMAGE", "local/re/main-v2.bin"))
    s = Screen(image, fonts); e = s.e; os.makedirs(out, exist_ok=True)
    s.seed_txt(); slots = s.load_fonts(); print("font slots loaded:", sum(1 for v in slots if v), "of", len(slots))
    create = int(os.environ.get("F3_CREATE", "0x2c1ecc64"), 0)
    scr = e.call(create, 0, 0); s.show(scr)
    hdr, card_a, card_b, info, undo, stats, ov = children(e, scr)[:7]
    click = lambda o: e.call(A["event_send"], o, 7, 0)                                 # LV_EVENT_CLICKED, as a tap does
    def shot(name):                                                                    # a whole new frame: the drawing is invalidated first, so the double buffer is complete
        e.call(0x2c2782a8, scr); s.tick += 30; e.call(0x2c28a46c, max_insns=4_000_000_000); s.png(os.path.join(out, name + ".png")); print("wrote", name, "(flushes: %d)" % s.flushes)
    shot("score-empty")
    for _ in range(4): click(card_a)                                                   # A wins the first game (serve passes to B)
    click(card_b); click(card_b); click(card_a)                                        # B 30, A 15
    s.tick += 65000; shot("score-playing")
    click(stats); shot("stats")
    back = children(e, ov)[-1]; click(back)
    for _ in range(4 * 11 + 3): click(card_a)                                          # A takes the rest of set 1 and set 2
    shot("score-finished")
    return 0

sys.exit(main(sys.argv[1:]))
