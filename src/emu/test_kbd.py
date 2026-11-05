# SPDX-License-Identifier: Apache-2.0
"""test_kbd.py: the reply keyboard (src/watch/kbd.c) on the real firmware in the emulator: the patched call site, the extra row on the page of quick replies, the keyboard window (QWERTY and
multi-tap, Polish letters, shift, delete, the 100-byte limit) and what it hands to the firmware's reply sender.

    python3 -I src/build_firmware.py local/firmware/stock-aza3.bin local/firmware/fit3-hub-reply.bin --hub counter,dice --reply-keyboard --kb-lang pl,en,pt,de,fr,tr
    python3 -I src/firmware/fwx.py local/firmware/fit3-hub-reply.bin main local/re/main-reply.bin
    local/venv/bin/python -I src/emu/test_kbd.py

What it cannot show: the real window manager, the phone, and the stock functions that need their own state (the page builder runs on stubs for the font proxy and the text-id lookup)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rig import Rig as _Rig, ROOT, A, BACK, bl_target
IMG = os.path.join(ROOT, os.environ.get("F3_REPLY_IMAGE", "local/re/main-reply.bin"))
SITE_MAIN, SITE_REFRESH, STOCK_MAIN, STOCK_REFRESH, KB_ID = 0x2c1d0f92, 0x2c1d2598, 0x2c1d09d0, 0x2c1d0b94, 0x9c
REC = 0x200fb4e4 + KB_ID * 0x30
SCREEN_PTR, COUNT_PTR = 0x201160a0, 0x2011609c


class Rig(_Rig):
    def __init__(self):
        super().__init__(IMG); e = self.e; self.heap_next = 0x207c0000; e.max_insns = 300_000_000          # above the firmware heap of the emulator (0x20400000..0x207c0000): this test builds several pages and the two would meet
        self.sent = []; self.linked = 1; self.seq = 0x1234abcd; self.replies = ["Yes", "No thanks", "On my way"]
        e.hook(0x2c112f58, lambda em: self.sent.append((em.arg(0), em.cstr(em.arg(1), 300).encode("latin1"), em.arg(2))) or 1)
        e.hook(0x2c0e6ef4, lambda em: self.linked)
        e.hook(0x2c0ed1f8, lambda em: (em.w32(em.arg(0) + 0x124, self.seq), self.fetches.append((em.arg(2), em.arg(3)))) and 0); self.fetches = []
        e.hook(0x2c0ec1bc, lambda em: len(self.replies)); e.hook(0x2c0ec194, self._reply_text)
        self.font = e.u32(0x2010b0e0 + 4 * 8)
        e.hook(0x2c213a90, lambda em: self.font); e.hook(0x2c2138cc, lambda em: e.put_cstr("No quick replies")); e.hook(0x2c27b610, lambda em: 0); e.hook(0x2c1cfc08, lambda em: 0)
        self.timers_deleted = []; e.hook(0x2c28a448, lambda em: self.timers_deleted.append(em.arg(0)) or 0)
    def _reply_text(self, em):
        b = self.replies[em.arg(2)].encode(); em.write(em.arg(0) + 1, b + b"\0"); return 1
    def pad(self, kb): return self.children(kb)[5] if len(self.children(kb)) > 5 else None
    def keys(self, kb):
        pad = [c for c in self.children(kb) if len(self.children(c)) > 3 and all(self.labels(g) for g in self.children(c)[:2])][-1]
        return pad, {self.alltext(k)[0]: k for k in self.children(pad) if self.alltext(k)}
    def state(self, kb): return self.e.u32(kb + 0x10)
    def timer_run(self, kb):                                           # the 100 ms timer of the window: Kb.timer is the thirteenth pointer of the state block
        t = self.e.u32(self.state(kb) + 48); self.e.call(self.e.u32(t + 8), t)
    def cnt(self, kb): return self.alltext(self.children(kb)[-2])[-1]              # the text field is the second last child of the window; the count is its last label
    def used(self, kb): return int(self.cnt(kb).split("/")[0])
    def lang(self, kb): return self.alltext(self.children(kb)[1])[0]                # with a choice of languages the button after the layout switch names the layout
    def text(self, o): return self.e.cstr(self.e.u32(o + 0x2c), 512).encode("latin1").decode("utf-8", "replace")


def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-reply.bin (see the docstring)"); return 0
    res = []; ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    r = Rig(); e = r.e; cnt = r.cnt; raw = open(IMG, "rb").read(); stock = open(os.path.join(ROOT, "local/re/main-stock.bin"), "rb").read()
    hm, hr = bl_target(raw, SITE_MAIN), bl_target(raw, SITE_REFRESH)
    ok("the two places that build the page of quick replies now go into our code (the tail call of the reply icon's page, the refresh call)", all(0x2c3a0524 <= x < 0x2c3b0000 for x in (hm, hr)) and hm != hr and (bl_target(stock, SITE_MAIN), bl_target(stock, SITE_REFRESH)) == (STOCK_MAIN, STOCK_REFRESH), (hex(hm), hex(hr)))
    diff = [i for i in range(len(stock)) if stock[i] != raw[i] and not (0x2c3a0524 - 0x2c080000 <= i < 0x2c3b0000 - 0x2c080000) and i >= 0x1010]
    sites = (SITE_MAIN - 0x2c080000, SITE_REFRESH - 0x2c080000)
    ok("outside the free flash only those two sites differ from stock, besides the entry's name, icon pointer and take-over branches", sum(1 for i in diff if any(x <= i < x + 4 for x in sites)) == 8 and len(diff) < 40, len(diff))
    box = lambda o: [e.i32(o + 0x14 + 4 * k) for k in range(4)]
    def page(kind, n):
        """the page as the stock builder and our hook make it: kind 'main' = the page of the reply icon (hook called as the tail call is), 'refresh' = the page rebuilt on event 0x42"""
        r.replies = ["Yes", "No thanks", "On my way"][:n]; scr = e.call(A["obj_create"], 0); e.w32(SCREEN_PTR, scr)
        if kind == "main": e.call(hm, scr, 4, 0x55)
        else: e.call(hr)
        e.call(A["update_layout"], scr); return scr
    for kind in ("main", "refresh"):
        scr = page(kind, 3); cont = r.children(scr)[0]; kids = r.children(cont); texts = [r.alltext(k) for k in kids]
        ok("[%s] the page has our row plus the stock ones: three replies, our row, the stock button" % kind, ["Write reply"] in texts and all([t] in texts for t in ("Yes", "No thanks", "On my way")), texts)
        ours = kids[texts.index(["Write reply"])]; yo = box(ours); ys = [box(kids[texts.index([t])]) for t in ("Yes", "No thanks", "On my way")]
        ok("[%s] our row is above the first stock row, stock rows keep their order and spacing" % kind, yo[3] < ys[0][1] < ys[1][1] < ys[2][1] and 8 <= ys[0][1] - yo[3] <= 14 and ys[1][1] - ys[0][3] == ys[2][1] - ys[1][3], (yo, ys))
        ok("[%s] our row is as wide and as high as the stock rows (their height follows their text)" % kind, yo[2] - yo[0] == ys[0][2] - ys[0][0] and yo[3] - yo[1] == ys[0][3] - ys[0][1] == ys[1][3] - ys[1][1], (yo, ys[0]))
        if kind == "main": ok("[main] the stock builder stored the notice ids the stock rows (and our row) use: 0x201160a8 = 0x55, 0x201160a4 = 4", (e.u32(0x201160a8), e.u32(0x201160a4)) == (0x55, 4), (hex(e.u32(0x201160a8)), e.u32(0x201160a4)))
        e.call(A["obj_del"], scr)
        scr = page(kind, 0); kids = r.children(r.children(scr)[0]); texts = [r.alltext(k) for k in kids]
        ours = kids[texts.index(["Write reply"])]; yo = box(ours); first = box(kids[0])
        ok("[%s] with no stored replies the page keeps its text and our row is below it, once" % kind, len(kids) == 2 and first[3] < yo[1] and yo[3] - yo[1] + 1 >= 24 and sum(1 for t in texts if t == ["Write reply"]) == 1, (first, yo, texts))
        e.call(A["obj_del"], scr)
    # the phone sends new replies while the page is open: the stock code rebuilds the same screen (the old row goes with the old content), and the row is there once
    scr = page("main", 3); e.call(hr); e.call(A["update_layout"], scr)
    cont = r.children(scr)[0]; texts = [r.alltext(k) for k in r.children(cont)]
    ok("a refresh after the page of the reply icon leaves exactly one row of ours (no duplicate, no loss)", len(r.children(scr)) == 1 and sum(1 for t in texts if t == ["Write reply"]) == 1 and ["Yes"] in texts, texts)
    r.replies = ["Yes", "No thanks", "On my way"]
    kids = r.children(cont); ours = kids[texts.index(["Write reply"])]
    # ---- a tap on our row
    r.calls.clear(); n0 = len(r.sizes); r.click(ours); wo = [c for c in r.calls if c[0] == "wm_open"]
    ok("a tap on the row asks the window manager for our keyboard window (wm_open 2, 0x9c, block, 0xf)", len(wo) == 1 and wo[0][:3] == ("wm_open", 2, KB_ID) and wo[0][4] == 0xf, wo)
    blk = wo[0][3]; ok("the block holds the magic and the notice's seq_id from the stock lookup", e.u32(blk) == 0x3159424b and e.u32(blk + 4) == r.seq, (hex(e.u32(blk)), hex(e.u32(blk + 4))))
    ok("the lookup used the stock arguments: the two ids the page builder stored (0x55, 4)", r.fetches == [(0x55, 4)], r.fetches)
    word = lambda k: e.u32(REC + 4 * k)
    ok("the record of window 0x9c is filled like the hub's: id and flags 0x01d3009c, create and event are our Thumb code", word(0) == 0x01d3009c and all(0x2c3a0524 <= word(k) < 0x2c3b0000 and word(k) & 1 for k in (7, 9, 10, 11)), [hex(word(k)) for k in (0, 7, 9)])
    # ---- the keyboard window (what the manager does: create(param), then event (0, 0))
    CREATE, EV = word(7) & ~1, word(9) & ~1
    kb = e.call(CREATE, blk)
    e.w32(REC + 0x10, kb); e.call(EV, 0, 0, 0)
    ok("the block was freed by the window (the manager passes it once)", blk in r.freed)
    ok("the window sets itself as current (0, 0) and answers the key policy (0, 8) with 0x2c4, the queries 6, 7, 9 with 0", ("set_current", KB_ID) in r.calls and e.call(EV, 0, 8, 0) == 0x2c4 and all(e.call(EV, 0, q, 0) == 0 for q in (6, 7, 9)))
    st = r.state(kb); all_text = r.alltext(kb); ok("it shows the layout switch (QWE), the language and the count, Send and the text field", "QWE" in all_text and "Send" in all_text and r.lang(kb) == "PL" and r.used(kb) == 0 and cnt(kb) == "0/100", all_text)
    pad, keys = r.keys(kb); e.call(A["update_layout"], kb)
    ok("QWERTY has 26 letters, shift, delete, 123, the Polish layer key and space (a capital first: a new text starts a sentence)", all(c in keys for c in "QWERTYUIOPASDFGHJKLZXCVBNM") and "<" in keys and "123" in keys, sorted(keys))
    typ = lambda s: [r.click(r.keys(kb)[1][c]) for c in s]
    def shown(): return [t for t in r.alltext(kb) if t.endswith("_")][0]
    typ("H"); ok("the first letter is a capital (auto-capital at the start); the next ones are lower case", shown() == "H_", shown())
    typ("ello"); k = r.keys(kb)[1]; ok("the keys went lower case after the first letter", "q" in k and "Q" not in k, sorted(k)[:5])
    r.click(r.keys(kb)[1][" "]); typ("w"); typ("orld"); ok("typing: Hello world", shown() == "Hello world_", shown())
    r.click(r.keys(kb)[1]["<"]); r.click(r.keys(kb)[1]["<"]); ok("delete removes one character at a time", shown() == "Hello wor_", shown())
    # Polish layer
    key = lambda c: r.keys(kb)[1][c]
    r.click(key("ąć")); k = r.keys(kb)[1]; ok("the Polish layer has all nine letters", all(c in k for c in "ąćęłńóśźż"), sorted(k))
    r.click(key("ł")); r.click(key("ś")); ok("a Polish letter is two UTF-8 bytes in the text", shown() == "Hello worłś_", shown())
    r.click(key("<")); ok("delete removes a whole two-byte letter, not half of it", shown() == "Hello worł_", shown())
    r.click(key("ab")); k = r.keys(kb)[1]; ok("shift on the Polish layer gives capitals", "Ł" in k and "Ą" in k, sorted(k))
    r.click(key("Ż")); ok("one tap on shift is one capital: Ż is inserted and the layer is lower case again", shown() == "Hello worłŻ_" and "ż" in r.keys(kb)[1], shown())
    r.click(key("abc")); r.click(key("123")); k = r.keys(kb)[1]; ok("the symbol layer has digits and punctuation", all(c in k for c in "1234567890") and "!" in k and "?" in k, sorted(k))
    r.click(key("!")); ok("a symbol is inserted as is", shown() == "Hello worłŻ!_", shown()); r.click(key("abc"))
    # ---- the counter and the limit
    ok("the counter shows the length in bytes", r.used(kb) == 14, r.alltext(kb))
    # ---- send
    sn = len(r.sent); r.calls.clear(); b_send = [c for c in r.children(kb) if r.alltext(c) == ["Send"]][0]; r.click(b_send)
    want = "Hello worłŻ!".encode()
    ok("Send hands the seq_id and the UTF-8 text to the firmware's reply sender", r.sent[sn:] == [(r.seq, want, len(want))], r.sent[sn:])
    ok("... and shows 'Sent', with a buzz", "Sent" in r.alltext(kb) and ("motor", 1, 1) in r.calls, r.alltext(kb))
    n = len(r.sent); r.click(b_send); ok("a second tap while 'Sent' is shown sends nothing", len(r.sent) == n)
    r.calls.clear(); r.tick += 900; r.timer_run(kb); ok("a moment later the window leaves (wm_open 3, -1, 0, back)", ("wm_open", 3, 0xffffffff, 0, BACK) in r.calls, r.calls)
    r.freed.clear(); e.call(A["obj_del"], kb); ok("deleting the window frees the keyboard's state", len(r.freed) >= 1 and r.timers_deleted, [hex(x) for x in r.freed])
    # ---- multi-tap
    blk = e.alloc(8); e.w32(blk, 0x3159424b); e.w32(blk + 4, 7); r.files["/user/kbd.sav"] = struct.pack("<I", 1)
    kb = e.call(CREATE, blk); e.w32(REC + 0x10, kb); e.call(EV, 0, 0, 0)
    ok("the saved mode (multi-tap) is restored: the switch says T9 and the pad has digits' letter groups", "T9" in r.alltext(kb) and any(t == "abcąć" for t in r.alltext(kb)), r.alltext(kb))
    key = lambda c: r.keys(kb)[1][c]; labels = sorted(r.keys(kb)[1])
    tap = lambda c, dt=100: (setattr(r, "tick", r.tick + dt), r.click(key(c)))
    tap("abcąć"); ok("first letter: a capital (sentence start), the first character of the group", shown() == "A_", shown())
    seq = []
    for _ in range(6): tap("abcąć"); seq.append(shown()[:-1])
    ok("the same key again soon cycles the group, replacing the last character: b c ą ć 2 and back to a (one capital, from the first tap)", seq == ["B", "C", "Ą", "Ć", "2", "A"], seq)
    tap("abcąć", 1000); ok("after a pause the same key adds a new character", shown() == "Aa_", shown())
    tap("def\u0119", 100); tap("defę", 1000)
    ok("another key adds its first character; a pause then the same key adds again", shown() == "Aadd_" or shown() == "Aadd_", shown())
    tap("_", 1000); tap("_", 100); ok("the space key gives a space, and quickly again a zero", shown() == "Aadd0_", shown())
    r.click(key("<")); r.click(key("<")); ok("delete works in multi-tap too", shown() == "Aad_", shown())
    # ---- the limit: 100 bytes
    for _ in range(120): tap("ghi", 1000)
    ok("the text stops at 100 bytes and the counter says so", r.used(kb) == 100, [t for t in r.alltext(kb) if "/" in t])
    r.calls.clear(); tap("ghi", 1000); ok("a key past the limit buzzes strongly and adds nothing", ("motor", 4, 1) in r.calls and r.used(kb) == 100, r.calls[:3])
    # ---- the mode switch is saved
    b_mode = [c for c in r.children(kb) if r.alltext(c) == ["T9"]][0]; r.click(b_mode)
    ok("the switch toggles to QWERTY and remembers it (4 bytes to /user/kbd.sav)", "QWE" in r.alltext(kb) and r.files.get("/user/kbd.sav") == struct.pack("<I", 0) and "q" in r.keys(kb)[1], r.files.get("/user/kbd.sav"))
    # ---- no phone: nothing is sent, the text stays
    r.linked = 0; sn = len(r.sent); b_send = [c for c in r.children(kb) if r.alltext(c) == ["Send"]][0]; r.click(b_send)
    ok("without the phone link nothing is sent and the user is told", len(r.sent) == sn and "Phone not connected" in r.alltext(kb), r.alltext(kb)[-1])
    r.calls.clear(); r.tick += 2000; r.timer_run(kb); ok("the message goes away by itself and the window stays (the text is kept)", "Phone not connected" not in r.alltext(kb) and not any(c[0] == "wm_open" for c in r.calls) and r.used(kb) == 100, r.alltext(kb)[-2:])
    r.linked = 1; r.click(b_send); ok("with the phone back, Send sends the 100 bytes", len(r.sent) == sn + 1 and r.sent[-1][2] == 100, r.sent[-1][2:])
    r.freed.clear(); e.call(A["obj_del"], kb)
    # ---- an empty text is not sent; the back gesture leaves
    blk = e.alloc(8); e.w32(blk, 0x3159424b); e.w32(blk + 4, 9); r.files.pop("/user/kbd.sav")
    kb = e.call(CREATE, blk); e.w32(REC + 0x10, kb); e.call(EV, 0, 0, 0); sn = len(r.sent)
    b_send = [c for c in r.children(kb) if r.alltext(c) == ["Send"]][0]; r.click(b_send); r.click(r.keys(kb)[1]["<"])
    ok("an empty text is not sent and delete on an empty text is harmless", len(r.sent) == sn and r.used(kb) == 0)
    r.scr = kb; r.calls.clear(); r.gesture(2); ok("the back gesture leaves with the stock back slide and is consumed", ("wm_open", 3, 0xffffffff, 0, BACK) in r.calls and ("consume",) in r.calls, r.calls)
    e.call(A["obj_del"], kb)
    # ---- languages: the layout follows the system language (a byte of the firmware), a tap on the count switches it
    def open_kb(lang_id=None, saved=None):
        if lang_id is not None: e.write(0x200fafe0, bytes([lang_id]))
        if saved is None: r.files.pop("/user/kbd.sav", None)
        else: r.files["/user/kbd.sav"] = saved
        b = e.alloc(8); e.w32(b, 0x3159424b); e.w32(b + 4, 7); k = e.call(CREATE, b); e.w32(REC + 0x10, k); e.call(EV, 0, 0, 0); return k
    def keyset(k): return set(r.keys(k)[1])
    for lang_id, name, first, probe in ((16, "PL", "q", "ąć"), (45, "PT", "q", "áà"), (46, "PT", "q", "áà"), (54, "TR", "q", "çğ"), (22, "FR", "a", "àâ"), (23, "FR", "a", "àâ"), (20, "DE", "q", "äö"), (1, "EN", "q", None), (0, "PL", "q", "ąć")):
        k = open_kb(lang_id); ks = keyset(k); first_row = [r.alltext(c)[0] for c in r.children(r.keys(k)[0])][:4]
        ok("system language %d gives the %s layout (button '%s'; unknown languages fall back to the first of the build)" % (lang_id, name, name), r.lang(k) == name and r.used(k) == 0 and (probe is None or probe in ks or probe.upper() in ks), (r.lang(k), first_row, sorted(ks)[:6]))
        e.call(A["obj_del"], k)
    k = open_kb(22); letters = [r.alltext(c)[0] for c in r.children(r.keys(k)[0]) if len(r.alltext(c)[0]) == 1][:10]; e.call(A["obj_del"], k)
    ok("French is AZERTY: the first row starts a z e r t y", "".join(letters).lower().startswith("azerty"), letters)
    k = open_kb(20); letters = [r.alltext(c)[0] for c in r.children(r.keys(k)[0]) if len(r.alltext(c)[0]) == 1][:10]; e.call(A["obj_del"], k)
    ok("German is QWERTZ: q w e r t z", "".join(letters).lower().startswith("qwertz"), letters)
    # the extra-letters layer: Portuguese has twelve extras (two rows), French sixteen
    k = open_kb(45); r.click(r.keys(k)[1]["áà"]); ks = keyset(k)
    ok("Portuguese: all twelve extra letters (two rows, capitals while a sentence starts) and punctuation on their layer", all(c.upper() in ks for c in "áàâãçéêíóôõú") and "," in ks and "abc" in ks, sorted(ks))
    r.click(r.keys(k)[1]["Ã"]); ok("a Portuguese letter is typed (a capital at the start of a text)", [t for t in r.alltext(k) if t.endswith("_")][0] == "Ã_", [t for t in r.alltext(k) if t.endswith("_")]); e.call(A["obj_del"], k)
    k = open_kb(22); r.click(r.keys(k)[1]["àâ"]); ks = keyset(k); ok("French: sixteen extra letters on the layer, all reachable", all(c.upper() in ks for c in "àâæçéèêëîïôœùûüÿ"), sorted(ks)); e.call(A["obj_del"], k)
    # capitals of other languages' letters; Turkish i
    k = open_kb(54); r.click(r.keys(k)[1]["çğ"]); r.click(r.keys(k)[1]["Ğ"]); typed = [t for t in r.alltext(k) if t.endswith("_")][0]
    ok("Turkish: a capital at the start gives Ğ; then the layer is lower case: ı is there", typed == "Ğ_" and "ı" in keyset(k), typed); r.click(r.keys(k)[1]["ı"]); typed = [t for t in r.alltext(k) if t.endswith("_")][0]
    ok("Turkish: ı is typed as ı", typed == "Ğı_", typed); e.call(A["obj_del"], k)
    k = open_kb(54, saved=struct.pack("<I", 0)); r.click(r.keys(k)[1]["İ"]); typed = [t for t in r.alltext(k) if t.endswith("_")][0]
    ok("Turkish: the first letter of a new text is a capital and 'i' becomes İ", typed == "İ_", typed); e.call(A["obj_del"], k)
    # multi-tap in French: the groups come from the language, the caption has at most six glyphs
    k = open_kb(22, saved=struct.pack("<I", 1)); caps = sorted(set(r.keys(k)[1]) - {"ab", "AB", "_", "<"})
    ok("French multi-tap: the 2 key holds abc and its accents (caption cut to six glyphs), 3 holds é è ê ë", "abcàâæ" in caps and any(c.startswith("def") for c in caps), caps)
    kk = r.keys(k)[1]; seq = []
    for _ in range(8): r.tick += 100; r.click(r.keys(k)[1]["abcàâæ"]); seq.append([t for t in r.alltext(k) if t.endswith("_")][0][:-1])
    ok("... and the cycle includes the letters beyond the caption: A B C À Â Æ Ç 2", seq[:8] == ["A", "B", "C", "À", "Â", "Æ", "Ç", "2"], seq); e.call(A["obj_del"], k)
    # switching and remembering
    k = open_kb(16); b_cnt = r.children(k)[1]; r.click(b_cnt)
    ok("a tap on the language button switches to the next language of the build (EN after PL) and saves the choice", r.lang(k) == "EN" and r.files.get("/user/kbd.sav") == bytes([0, 2, 0, 0]), (r.lang(k), r.files.get("/user/kbd.sav"))); e.call(A["obj_del"], k)
    k = open_kb(16, saved=bytes([0, 2, 0, 0])); ok("a saved choice beats the system language", r.lang(k) == "EN", r.lang(k)); e.call(A["obj_del"], k)
    k = open_kb(16, saved=struct.pack("<I", 1)); ok("an old save file (the layout switch only, 4 bytes) follows the system language", r.lang(k) == "PL" and "T9" in r.alltext(k), r.alltext(k)[:3]); e.call(A["obj_del"], k)
    k = open_kb(16, saved=bytes([0, 99, 0, 0])); ok("a damaged save file is ignored", r.lang(k) == "PL", r.lang(k)); e.call(A["obj_del"], k)
    # ---- the emoji layer (only in a build with --kb-emoji-font): a key in both modes, 24 emoji of four UTF-8 bytes each, sent as they are
    EMO = "\U0001F60A"
    k = open_kb(45, saved=bytes([0, 0, 0, 0]))
    if EMO in keyset(k):
        typed = lambda: [t for t in r.alltext(k) if t.endswith("_")][0]
        r.click(r.keys(k)[1][EMO]); ks = keyset(k); emo = [c for c in ks if len(c) == 1 and ord(c) > 0xffff]
        ok("emoji: the key opens a layer of 24 emoji with abc, space and delete", len(emo) == 24 and {"abc", " ", "<"} <= ks, sorted(ks))
        r.click(r.keys(k)[1]["\U0001F602"]); r.click(r.keys(k)[1]["\U0001F44D"]); ok("an emoji is four bytes of UTF-8 in the text", typed() == "\U0001F602\U0001F44D_" and r.used(k) == 8, (typed(), r.used(k)))
        r.click(r.keys(k)[1]["<"]); ok("delete removes a whole emoji", typed() == "\U0001F602_" and r.used(k) == 4, typed())
        for _ in range(30): r.click(r.keys(k)[1]["\U0001F525"])
        ok("the 100-byte limit: 25 emoji at most, no half emoji", r.used(k) == 100 and typed().endswith("\U0001F525_"), r.used(k))
        sn = len(r.sent); r.click([c for c in r.children(k) if r.alltext(c) == ["Send"]][0])
        ok("Send hands the emoji to the reply sender as UTF-8", r.sent[sn:] and r.sent[-1][1] == ("\U0001F602" + "\U0001F525" * 24).encode(), r.sent[sn:][:1])
        e.call(A["obj_del"], k)
        k = open_kb(45, saved=bytes([0, 0, 0, 0])); r.click(r.keys(k)[1][EMO]); r.click(r.keys(k)[1]["abc"]); ok("abc goes back to the letters", "Q" in keyset(k) or "q" in keyset(k), sorted(keyset(k))[:5]); e.call(A["obj_del"], k)
        k = open_kb(45, saved=bytes([1, 0, 0, 0])); ok("multi-tap has the emoji key too", EMO in keyset(k) and "_" in keyset(k) and "<" in keyset(k), sorted(keyset(k)))
        r.click(r.keys(k)[1][EMO]); r.click(r.keys(k)[1]["\U0001F64F"]); ok("... and types an emoji", [t for t in r.alltext(k) if t.endswith("_")][0] == "\U0001F64F_"); e.call(A["obj_del"], k)
    else: e.call(A["obj_del"], k)
    # ---- the block can be anywhere in RAM: the watch's heap is not the emulator's (a first version accepted only 0x20000000..0x20800000 and showed the error screen on the watch)
    for addr in (0x28000010, 0x2a123450):
        e.uc.mem_map(addr & ~0xfff, 0x1000); e.w32(addr, 0x3159424b); e.w32(addr + 4, 0x77); r.freed.clear()
        kb = e.call(CREATE, addr); ok("a block at %#x (outside the emulator's heap) opens the keyboard and is freed" % addr, [c for c in r.children(kb) if r.alltext(c) == ["Send"]] and addr in r.freed, r.alltext(kb)[:3]); e.call(A["obj_del"], kb)
    # ---- what can go wrong with the argument: a screen that names the value it got
    for arg in (0, 5, 0x20000001, 0x207c0000, 0x40000000):
        kb = e.call(CREATE, arg); ok("a bad argument (%#x) gives a screen that says so and shows the value, nothing is sent" % arg, r.alltext(kb) == ["Open this from a message", "0x%08x" % arg] and not [c for c in r.children(kb) if r.alltext(c) == ["Send"]], r.alltext(kb)); e.call(A["obj_del"], kb)
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
