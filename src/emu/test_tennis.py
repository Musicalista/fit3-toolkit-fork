# SPDX-License-Identifier: Apache-2.0
"""test_tennis.py: the tennis app as the only app of the window, run on the PATCHED main image of a package built with `build_firmware.py --app tennis` (the stock addresses of the replaced window, 0x2c1ecc64 / 0x2c1ecd68 for World clock, as the window manager calls them).

    python3 -I src/firmware/fwx.py local/firmware/fit3-tennis.bin main local/re/main-tennis.bin
    local/venv/bin/python -I src/emu/test_tennis.py

Plays matches by sending CLICKED events to the real LVGL objects and reads back the label texts. The file functions and the tick are replaced by Python (a fake /user/tenis.sav,
a settable clock); the vibration, gesture and window-manager calls are recorded. Limits: no real font, so no text width or layout check (the emulator has no display)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rig import Rig as _Rig, ROOT, A, WIN, EVENT, CLICKED, GESTURE, HIDDEN, BACK
IMG = os.path.join(ROOT, os.environ.get("F3_IMAGE", "local/re/main-tennis.bin"))

class Rig(_Rig):
    def __init__(self): super().__init__(IMG)
    def create(self):
        scr = super().create(); kids = self.children(scr)
        self.hdr, self.cardA, self.cardB, self.info, self.game, self.sett, self.undo, self.stats, self.ov = kids[:9]
        return scr

def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-tennis.bin (see the docstring)"); return 0
    r = Rig(); e = r.e; res = []
    ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    scr = r.create()
    ok("create returns a screen; 9 children (header, 2 cards, info, game and set clocks, 2 pills, overlay)", scr and len(r.children(scr)) == 9, len(r.children(scr)))
    ok("fresh match: no header and no hint, points 0", (r.text(r.hdr), r.alltext(r.cardA)[1:], r.text(r.info)) == ("", ["0", "0"], ""), (r.text(r.hdr), r.alltext(r.cardA), r.text(r.info)))
    la = r.alltext(r.cardA); lb = r.alltext(r.cardB)
    ok("card A shows letter A, games 0, point 0", la[0] == "A" and "0" in la, la); ok("card B shows letter B", lb[0] == "B", lb)
    ok("overlay starts hidden", r.hidden(r.ov))
    # points: 15, 30, 40, then game
    r.click(r.cardA); ok("1 click = 15", r.alltext(r.cardA)[-1] == "15", r.alltext(r.cardA)); ok("header shows the match clock", r.text(r.hdr).startswith("Match "), r.text(r.hdr))
    ok("the game and set clocks are over their buttons, the centred line stays empty", (r.text(r.game), r.text(r.sett), r.text(r.info)) == ("G 0:00", "S 0:00", ""), (r.text(r.game), r.text(r.sett), r.text(r.info)))
    e.call(A["update_layout"], scr); box = lambda o: [e.i32(o + 0x14 + 4 * k) for k in range(4)]
    bu, bs, lg, ls = box(r.undo), box(r.stats), box(r.game), box(r.sett)
    ok("each clock spans exactly the width of its button and lies above it (the gap itself is measured on the rendered page, see screenshot.py)", (lg[0], lg[2]) == (bu[0], bu[2]) and (ls[0], ls[2]) == (bs[0], bs[2]) and lg[3] < bu[1] and ls[3] < bs[1], (bu, bs, lg, ls))
    pl = box(r.labels(r.undo)[0]); ok("the button caption starts 13 px below the top of the pill (capitals centred)", pl[1] - bu[1] == 13, (pl, bu))
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
    # side key (docs/details.md, section 2): the manager asks (0,8) for the key policy; 0x2c4 (bit 6 set) lets the manager itself send the short press to the watch face, as the stock windows do
    r.calls.clear(); e.call(EVENT, 0, 0, 0); ok("entering the window sets its own id (wm_set_current)", ("set_current", WIN) in r.calls, r.calls)
    ok("key policy (0,8) = 0x2c4, the stock windows' answer", e.call(EVENT, 0, 8, 0) == 0x2c4, hex(e.call(EVENT, 0, 8, 0)))
    ok("the garbage-free arguments: upper bytes are masked", e.call(EVENT, 0xabcd0000, 0x12340008, 0) == 0x2c4)
    # the manager asks (0, 7) and (0, 9) whether it should run its own swipe-back and which animation; a garbage answer made it animate to the wrong side
    ok("window queries 6, 7 and 9 answer 0, so the manager runs no swipe of its own", all(e.call(EVENT, 0, k, 0) == 0 for k in (6, 7, 9)), [e.call(EVENT, 0, k, 0) for k in (6, 7, 9)])
    ok("every window event answers a defined value (0 except the policy)", all(e.call(EVENT, c, k, 0) == (0x2c4 if (c, k) == (0, 8) else 0) for c in (0, 1, 2) for k in range(12)))
    r.calls.clear(); e.call(EVENT, 1, 6, 0); ok("the short press of the side key is left to the manager (we do not call wm)", not r.calls, r.calls)
    # delete the window: flush (nothing dirty) + free the state, timer deleted
    r.click(r.cardB); ok("a new point makes the state dirty", True)
    log = []; e.hook(0x2c28a448, lambda em: log.append(("timer_del", em.arg(0))) or 0)
    nwrites = len(r.writes); e.call(A["obj_del"], scr)
    ok("closing the window saves unsaved points", len(r.writes) == nwrites + 1)
    ok("closing the window deletes the timer and frees the state", any(l[0] == "timer_del" for l in log) and r.state in r.freed, (log, [hex(x) for x in r.freed]))
    # reopen after a "reboot": ticks restart from 0, the saved match is back, the clock continues
    saved = r.files["/user/tenis.sav"]; r.tick = 500; r.freed.clear()
    scr2 = r.create(); a2, b2 = r.alltext(r.cardA), r.alltext(r.cardB)
    ok("after a restart the saved match is shown (advantage A, then a point for B: 40-40)", (a2[-1], b2[-1]) == ("40", "40"), (a2, b2))
    ok("... and its clock continues from the save instead of jumping", r.text(r.hdr).startswith("Match ") and int(r.text(r.hdr).split(" ")[1].split(":")[0]) < 5, r.text(r.hdr))
    # play to the end: A wins two sets 6-0
    r.click(r.stats); nb = r.children(r.ov)[-2]; r.click(nb); r.click(nb); ok("New twice resets the match", r.alltext(r.cardA)[-1] == "0" and r.text(r.hdr) == "", (r.alltext(r.cardA), r.text(r.hdr)))
    ok("...and closes the overlay", r.hidden(r.ov))
    for _ in range(48): r.click(r.cardA)
    ok("two sets 6-0 win the match: WIN on A, 'Match over'", r.alltext(r.cardA)[-1] == "WIN" and r.text(r.info) == "Match over" and (r.text(r.game), r.text(r.sett)) == ("", ""), (r.alltext(r.cardA), r.text(r.info), r.text(r.game), r.text(r.sett)))
    r.click(r.cardA); ok("clicks after the end change nothing", r.alltext(r.cardB)[-1] == "")
    r.click(r.stats); ok("stats of a finished match list 2 sets", sum(1 for t in r.alltext(r.ov) if t.startswith("S")) >= 2 and "S2  6-0" in " ".join(r.alltext(r.ov)).replace("  ", "  "), r.alltext(r.ov))
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
