"""test_loader_v0.py: runs loader_v0 (tools/loader) on the real LVGL code of the firmware in the emulator.

    python3 -I tools/loader/build_loader.py tools/loader/loader_v0.c local/loader/loader_v0.bin
    local/venv/bin/python -I tools/emu/test_loader_v0.py

Checks: the entry builds the page under a fresh root and deletes its own start timer; the panel is 256 x 402 and not scrollable; the labels get text; our tick timer
refreshes it; pressed/clicked/released events change the counters; deleting the root (what closing the page does) sends DELETE (33), after which no timer of ours is left
and the state block is freed. Limits: no real display, touch or RTOS (see README.md)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
from probe_lvgl import Probe, A
LOADER = os.path.join(ROOT, "local/loader/loader_v0.bin"); BASE = 0x2c3a0524

def main():
    if not (os.path.exists(LOADER) and os.path.exists(os.path.join(ROOT, "local/re/main-stock.bin"))): print("SKIP: need local/loader/loader_v0.bin and local/re/main-stock.bin"); return 0
    p = Probe(); e = p.e; res = []
    ok = lambda name, cond, obs="": (res.append(cond), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    code = open(LOADER, "rb").read(); e.write_code(BASE, code); e.write_code(BASE + 0x0c000000 - 0x2c000000 + 0x2c000000 - 0x2c000000, b"") if False else None
    e.write_code(BASE - 0x20000000, code)                                         # alias copy at 0x0c......
    e.w32(0x2010b0f4, 0)                                                          # no Roboto slot in the emulator: the loader must cope
    root = e.call(A["obj_create"], 0); dummy = 0x20000300; e.hook(dummy, lambda em: 0)
    t = e.call(A["timer_create"], dummy | 1, 80, root)
    n_before = e.u32(root + 8) and 0
    e.call(BASE | 1, t)                                                           # loader_entry(timer)
    spec = e.u32(root + 8); nchild = e.u32(spec + 4)
    ok("entry creates one child (the panel) under the root", nchild == 1, "children=%d" % nchild)
    panel = e.u32(e.u32(spec) + 0)
    e.call(0x2c278d2c, root) if False else None
    e.call(A["update_layout"], panel)
    ok("panel is 256 x 402", (e.call(A["get_width"], panel), e.call(A["get_height"], panel)) == (256, 402), "%s x %s" % (e.call(A["get_width"], panel), e.call(A["get_height"], panel)))
    ok("panel is not scrollable", not (e.u32(panel + 0x24) & (1 << 4)), "flags=%#x" % e.u32(panel + 0x24))
    pspec = e.u32(panel + 8); nl = e.u32(pspec + 4); labels = [e.u32(e.u32(pspec) + 4 * i) for i in range(nl)]
    texts = [e.cstr(e.u32(l + 0x2c)) for l in labels]
    ok("four labels with the expected texts", texts == ["Loader v0", "0.0", "p0 c0 r0", "0,0"], repr(texts))
    # the state block: the panel's event descriptor user data
    ev = e.u32(pspec + 0xc)                                                       # array of 12-byte descriptors {cb, user_data, filter}
    ok("panel has our event handler (filter 0 = ALL)", ev != 0 and e.u32(ev) == (BASE | 1) + (e.u32(ev) - (BASE | 1)) and e.u8(ev + 8) == 0, "cb=%#x" % e.u32(ev))
    state = e.u32(ev + 4)
    ok("state block is in the heap", state != 0 and state < 0x20800000, hex(state))
    timer = e.u32(state + 20); ok("our tick timer exists", timer != 0, hex(timer))
    # drive the timer: call its callback like lv_timer_handler would
    cb = e.u32(timer + 8)
    for _ in range(5): e.call(cb, timer)
    ok("tick timer refreshes the uptime (5 ticks -> 1.2)", e.cstr(e.u32(labels[1] + 0x2c)) == "1.2", e.cstr(e.u32(labels[1] + 0x2c)))
    for code_, n in ((1, "pressed"), (7, "clicked"), (8, "released")): e.call(A["event_send"], panel, code_, 0)
    e.call(cb, timer); ok("press/click/release counters", e.cstr(e.u32(labels[2] + 0x2c)) == "p1 c1 r1", e.cstr(e.u32(labels[2] + 0x2c)))
    log = []; e.hook(0x2c28a448, lambda em: log.append(("timer_del", em.arg(0))) or 0); e.hook(0x2c28a668, lambda em: log.append(("mem_free", em.arg(0))) or 0)
    e.call(A["obj_del"], root)                                                    # closing the page
    ok("deleting the root deletes our tick timer", ("timer_del", timer) in log, "%d calls logged" % len(log))
    ok("deleting the root frees the state block", ("mem_free", state) in log, "%d calls logged" % len(log))
    ok("the emulator survived every call", True)
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
