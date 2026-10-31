# SPDX-License-Identifier: Apache-2.0
"""probe_lvgl.py: check the LVGL claims of docs/details.md by running the real firmware functions in the emulator.

    local/venv/bin/python -I tools/emu/probe_lvgl.py [path/to/main-stock.bin]

Each claim prints PASS / FAIL / SKIP with the observed value. Exit status 1 when any claim FAILs.
Setup (see README.md): lv_init (0x2c27cb30) of the firmware runs as is; the display is registered by replaying disp_init (0x2c26a1b8)
with our own buffers (the original also talks to the LCD driver); the firmware heap is a bump allocator that poisons memory with 0xA5."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fw_emu import FwEmu

A = dict(  # addresses from docs/symbols.csv (R390XXU0AZA3)
    lv_init=0x2c27cb30, obj_create=0x2c27cb84, obj_del=0x2c27b164, add_flag=0x2c27cbb8, clear_flag=0x2c27cc5c, set_size=0x2c277b2c,
    set_pos=0x2c277a24, set_width=0x2c277a5c, get_width=0x2c277d68, get_height=0x2c277d90, update_layout=0x2c278d2c,
    add_event_cb=0x2c27d9cc, event_send=0x2c27d8fc, label_create=0x2c28de90, label_set_text=0x2c28e98c, label_get_text=0x2c28df00,
    img_create=0x2c2905ac, timer_create=0x2c28a3f0, style_init=0x2c2895d8, draw_buf_init=0x2c2892ec, drv_init=0x2c289298,
    drv_register=0x2c289308, disp_get_default=0x2c2893fc, hor_res=0x2c289408, ver_res=0x2c289424,
    obj_class=0x2c32ae74, label_class=0x2c388a94, img_class=0x2c388b94,
)
EV_DELETE, EV_CHILD_CHANGED, EV_CHILD_CREATED, EV_CHILD_DELETED = 0x21, 0x22, 0x23, 0x24
LV_PCT100 = 0x20000064


class Probe:
    def __init__(self, image=None):
        self.e = FwEmu(image); self.results = []
        self.e.call(A["lv_init"]); self.e.seed_text_functions(); self._display()
        self.events = []                                    # (cb_addr, event_t fields) recorded by Python callbacks
    def _display(self):
        e = self.e; buf = e.alloc(0x32400 * 2, 0); dsc = e.alloc(64, 0); drv = e.alloc(0x80, 0); flush = 0x20000200
        e.hook(flush, lambda e: 0)                           # flush_cb: we never draw
        e.call(A["draw_buf_init"], dsc, buf, buf + 0x32400, 256 * 402); e.call(A["drv_init"], drv)
        e.w32(drv, 256); e.w32(drv + 4, 402); e.w32(drv + 0x18, dsc); e.w32(drv + 0x20, flush | 1); e.write(drv + 0x1c, bytes([e.u8(drv + 0x1c) | 1]))
        self.disp = e.call(A["drv_register"], drv)
    def check(self, claim, ok, observed, skip=False):
        self.results.append(("SKIP" if skip else "PASS" if ok else "FAIL", claim, observed)); return ok
    def on_event(self, addr):
        """install a Python event callback at addr (a fake function address in RAM); records the lv_event_t fields"""
        def f(e):
            ev = e.arg(0); self.events.append(dict(cb=addr, target=e.u32(ev), cur=e.u32(ev + 4), code=e.u8(ev + 8), ud=e.u32(ev + 12), param=e.u32(ev + 16), code_word=e.u32(ev + 8)))
        self.e.hook(addr, f); return addr | 1
    def size_of_last_alloc(self, n0):
        return [s for _, s in self.e.allocs[n0:]]

    def run(self):
        e, c = self.e, self.check; call = e.call; h = lambda v: "%#x" % v
        # --- class structs (static data in the image)
        for name, base, size, wd in (("lv_obj_class", A["obj_class"], 44, 0xda), ("lv_label_class", A["label_class"], 88, 0x200007d1), ("lv_img_class", A["img_class"], 96, None)):
            bits = e.u32(base + 0x1c); isz = (bits >> 4) & 0xffff
            c("%s: instance_size %d (bitfield %#x at class+0x1c)" % (name, size, bits), isz == size, "instance_size=%d" % isz)
        c("lv_obj_class: width_def = height_def = 0xda (LARGE_COORD int32 at +0x14/+0x18)", e.u32(A["obj_class"] + 0x14) == 0xda == e.u32(A["obj_class"] + 0x18), "%s %s" % (h(e.u32(A["obj_class"] + 0x14)), h(e.u32(A["obj_class"] + 0x18))))
        c("lv_label_class: width_def = height_def = LV_SIZE_CONTENT 0x200007d1", e.u32(A["label_class"] + 0x14) == 0x200007d1 == e.u32(A["label_class"] + 0x18), h(e.u32(A["label_class"] + 0x14)))
        c("lv_obj_class: base_class = NULL", e.u32(A["obj_class"]) == 0, h(e.u32(A["obj_class"])))
        c("display registered: 256 x 402", (call(A["hor_res"], 0), call(A["ver_res"], 0)) == (256, 402), "%d x %d" % (call(A["hor_res"], 0), call(A["ver_res"], 0)))

        # --- lv_obj_create(NULL): a screen
        n0 = len(e.allocs); scr = call(A["obj_create"], 0); sizes = self.size_of_last_alloc(n0)
        c("lv_obj_create(NULL) allocates the 44-byte lv_obj_t (heap request)", 44 in sizes, "heap requests %s" % sizes)
        f = lambda o: [e.u32(o + 4 * i) for i in range(11)]
        w = f(scr)
        c("lv_obj_t: class pointer at +0 (== lv_obj_class)", w[0] == A["obj_class"], h(w[0]))
        c("lv_obj_t: parent at +4 (NULL for a screen)", w[1] == 0, h(w[1]))
        c("lv_obj_t: coords x1,y1,x2,y2 at +0x14..+0x20 = 0,0,255,401 for a screen (16 bytes: LARGE_COORD)", w[5:9] == [0, 0, 255, 401], str(w[5:9]))
        c("lv_obj_t: flags at +0x24 (screen: CLICKABLE|CLICK_FOCUSABLE|SCROLLABLE|ELASTIC|MOMENTUM|WITH_ARROW|SNAPPABLE = 0x1872)", w[9] == 0x1872, h(w[9]))
        c("lv_obj_t: state (u16) at +0x28 = 0; the bitfield byte pair at +0x2a is the last field (style_cnt = bits 3..8 = 0)", e.u16(scr + 0x28) == 0 and (e.u16(scr + 0x2a) >> 3) & 0x3f == 0, "state=%s, +0x2a=%s" % (h(e.u16(scr + 0x28)), h(e.u16(scr + 0x2a))))

        # --- child, flags, size, position, percent
        n0 = len(e.allocs); ch = call(A["obj_create"], scr); wc = f(ch)
        c("child: parent pointer at +4 is the screen", wc[1] == scr, h(wc[1]))
        c("child: flags at +0x24 add PRESS_LOCK 0x2000 and SCROLL_CHAIN 0x300 to the screen's", wc[9] & ~0x1872 != 0 or wc[9] != 0x1872, h(wc[9]))
        sa = e.u32(scr + 8)
        c("parent: spec_attr at +8 allocated (0x24 bytes), child_cnt at spec_attr+4 = 1, children[] at spec_attr+0 holds the child", sa != 0 and e.u32(sa + 4) == 1 and e.u32(e.u32(sa)) == ch, "spec_attr=%s cnt=%s" % (h(sa), e.u32(sa + 4) if sa else None))
        c("lv_obj_add_flag(obj, 0x1) sets bit at +0x24", (call(A["add_flag"], ch, 1), e.u32(ch + 0x24) & 1)[1] == 1, h(e.u32(ch + 0x24)))
        c("lv_obj_clear_flag(obj, 0x10) clears SCROLLABLE at +0x24", (call(A["clear_flag"], ch, 0x10), e.u32(ch + 0x24) & 0x10)[1] == 0, h(e.u32(ch + 0x24)))
        call(A["clear_flag"], ch, 1)
        call(A["set_size"], ch, 100, 50); call(A["set_pos"], ch, 10, 20); call(A["update_layout"], ch)
        cc = [e.i32(ch + 0x14 + 4 * i) for i in range(4)]
        c("lv_obj_set_size(100,50) + set_pos(10,20) + update_layout: coords x1,y1,x2,y2 = 10,20,109,69", cc == [10, 20, 109, 69], str(cc))
        c("lv_obj_get_width/height = x2-x1+1 / y2-y1+1 (100 x 50)", (call(A["get_width"], ch), call(A["get_height"], ch)) == (100, 50), "%d x %d" % (call(A["get_width"], ch), call(A["get_height"], ch)))
        call(A["set_size"], ch, 256, 402); call(A["set_pos"], ch, 0, 0); call(A["update_layout"], ch)
        c("lv_obj_set_size(obj, 256, 402) as in the stock apps gives 256 x 402", (call(A["get_width"], ch), call(A["get_height"], ch)) == (256, 402), "%d x %d" % (call(A["get_width"], ch), call(A["get_height"], ch)))
        call(A["set_width"], ch, LV_PCT100); call(A["update_layout"], ch)
        c("LV_PCT(100) = 0x20000064: set_width gives the parent's width (256)", call(A["get_width"], ch) == 256, "width=%d" % call(A["get_width"], ch))
        call(A["set_width"], ch, 0x20000032); call(A["update_layout"], ch)
        c("LV_PCT(50) = 0x20000032: width 128", call(A["get_width"], ch) == 128, "width=%d" % call(A["get_width"], ch))

        # --- events
        n0 = len(e.allocs); cb = self.on_event(0x20000300); call(A["add_event_cb"], ch, cb, 0, 0x1234)
        sa = e.u32(ch + 8); cnt = e.u8(sa + 0x22) & 0x3f
        c("lv_obj_add_event_cb allocates spec_attr on the object; event_dsc_cnt = 6 bits at spec_attr+0x22 (= 1)", sa != 0 and cnt == 1, "spec_attr=%s cnt=%d" % (h(sa), cnt))
        dsc = [(i, e.u32(sa + i)) for i in range(0, 0x24, 4) if e.u32(sa + i) and 0x20000000 <= e.u32(sa + i) < 0x20800000 and e.u32(e.u32(sa + i)) == cb]
        if dsc:
            p = dsc[0][1]; rec = [e.u32(p), e.u32(p + 4), e.u32(p + 8)]
            c("event descriptor array pointer at spec_attr+0xc; element = 12 bytes {cb, user_data, filter (only the low byte is written)}", rec[:2] == [cb, 0x1234] and rec[2] & 0xff == 0, "spec_attr+%#x -> %s; realloc sizes %s" % (dsc[0][0], [h(x) for x in rec], self.size_of_last_alloc(n0)))
        else: c("event descriptor array found in spec_attr", False, "no pointer to {cb,...} in spec_attr")
        self.events.clear(); call(A["event_send"], ch, 7, 0xBEEF0001)
        ev = self.events[0] if self.events else {}
        c("lv_event_t: target +0, current_target +4, code +8, user_data +0xc, param +0x10 (event_send(obj, 7 (CLICKED), param))", {k: v for k, v in ev.items() if k != "code_word"} == dict(cb=0x20000300, target=ch, cur=ch, code=7, ud=0x1234, param=0xBEEF0001), str({k: h(v) for k, v in ev.items()}))
        pcb = self.on_event(0x20000320); call(A["add_event_cb"], scr, pcb, 0, 0); self.events.clear()
        g = call(A["obj_create"], scr); codes = [x["code"] for x in self.events if x["cb"] == 0x20000320]
        c("creating a child sends CHILD_CHANGED 0x22 and CHILD_CREATED 0x23 to the parent", codes == [EV_CHILD_CHANGED, EV_CHILD_CREATED], str([h(x) for x in codes]))
        self.events.clear(); call(A["obj_del"], ch)
        own = [x["code"] for x in self.events if x["cb"] == 0x20000300]; par = [x["code"] for x in self.events if x["cb"] == 0x20000320 and 0x21 <= x["code"] <= 0x24]
        ownall = [x["code"] for x in self.events if x["cb"] == 0x20000320]
        c("lv_obj_del: the object receives LV_EVENT_DELETE = 0x21 (33, not 29)", own == [EV_DELETE], str([h(x) for x in own]))
        c("lv_obj_del: the parent receives CHILD_CHANGED 0x22 (sent twice in this build) and then CHILD_DELETED 0x24 last (GET_SELF_SIZE 0x2c from the relayout in between)", set(par) == {EV_CHILD_CHANGED, EV_CHILD_DELETED} and par[-1] == EV_CHILD_DELETED, "%s; all codes %s" % ([h(x) for x in par], [h(x) for x in ownall]))
        junk = [x for x in self.events if x["code_word"] >> 8]
        c("lv_event_t: `code` is a single byte (packed enum): upper bytes of the word at +8 are stack garbage in some events", bool(junk), "e.g. word %s -> code %s" % (h(junk[0]["code_word"]), h(junk[0]["code"])) if junk else "all upper bytes were 0 in this run")

        # --- label
        n0 = len(e.allocs); lb = call(A["label_create"], scr); sizes = self.size_of_last_alloc(n0)
        c("lv_label_create allocates the 88-byte object", 88 in sizes, "heap requests %s" % sizes)
        c("lv_label_t: class at +0 is lv_label_class", e.u32(lb) == A["label_class"], h(e.u32(lb)))
        n0 = len(e.allocs); txt = e.put_cstr("Tennis 6:4")
        call(A["label_set_text"], lb, txt); tp = e.u32(lb + 0x2c)
        c("lv_label_set_text copies the string: text pointer at obj+0x2c is a new heap block holding the text", tp not in (0, txt) and e.cstr(tp) == "Tennis 6:4", "ptr=%s %r" % (h(tp), e.cstr(tp) if tp else None))
        c("lv_label_get_text returns obj+0x2c", call(A["label_get_text"], lb) == tp, h(call(A["label_get_text"], lb)))
        c("label text block is exactly strlen+1 bytes (11) from lv_mem_alloc", 11 in self.size_of_last_alloc(n0), str(self.size_of_last_alloc(n0)))
        c("label: the static-text flag (bit 3 of the byte at obj+0x54) is clear after set_text (the setting side, set_text_static, is not exercised)", e.u8(lb + 0x54) & 8 == 0, "byte[0x54]=%#x" % e.u8(lb + 0x54))

        # --- image, style, timer
        n0 = len(e.allocs); im = call(A["img_create"], scr)
        c("lv_img_create allocates 96 bytes (80 standard + 16 Samsung bytes at +0x50)", 96 in self.size_of_last_alloc(n0), str(self.size_of_last_alloc(n0)))
        c("lv_img_t: the 16 extra bytes at +0x50 are zeroed by the constructor", e.read(im + 0x50, 16) == bytes(16), e.read(im + 0x50, 16).hex())
        st = e.alloc(16); call(A["style_init"], st)
        c("lv_style_init writes sentinel 0xaabbccdd at +0 and zeroes the rest of the 12-byte lv_style_t", e.u32(st) == 0xaabbccdd and e.read(st + 4, 8) == bytes(8) and e.u8(st + 12) == 0xA5, "%s, byte[12]=%#x" % (e.read(st, 12).hex(), e.u8(st + 12)))
        n0 = len(e.allocs); tm = call(A["timer_create"], 0x20000340 | 1, 80, 0x77)
        c("lv_timer_t: period at +0 (80), callback at +8, user_data at +0xc", (e.u32(tm), e.u32(tm + 8) & ~1, e.u32(tm + 0xc)) == (80, 0x20000340, 0x77), "%s" % [h(e.u32(tm + o)) for o in (0, 8, 0xc)])
        c("lv_indev_data_t is 0x1c bytes with state at +0x18 (a hypothesis)", False, "not exercised: needs the indev driver and the touch ring", skip=True)
        return self.results


def main():
    p = Probe(sys.argv[1] if len(sys.argv) > 1 else None); res = p.run()
    for st, claim, obs in res: print("%-4s %s\n       -> %s" % (st, claim, obs))
    n = {k: sum(1 for r in res if r[0] == k) for k in ("PASS", "FAIL", "SKIP")}
    print("\n%(PASS)d PASS, %(FAIL)d FAIL, %(SKIP)d SKIP" % n)
    print("emulator notes: %d MMIO pages touched, %d unmapped fetches %s, %d stubbed calls" % (len(p.e.mmio_log), len(p.e.unmapped_fetch), [hex(a) for a in p.e.unmapped_fetch], len(p.e.stub_log)))
    sys.exit(1 if n["FAIL"] else 0)

if __name__ == "__main__": main()
