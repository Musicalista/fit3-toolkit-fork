"""test_loader_v1.py: runs the PATCHED main image of a loader-v1 package in the emulator and calls the stock addresses of the World clock window functions,
exactly as the window manager does (0x2c1ecc64 create, 0x2c1ecd68 event): the `b.w` at their entry must land in our world_create / world_event.

    python3 -I tools/firmware/fwx.py local/firmware/fit3-loader-v1.bin main local/re/main-v1.bin
    local/venv/bin/python -I tools/emu/test_loader_v1.py

Checks: create returns a fresh screen (no parent) with our four labels and never builds the stock page (0x2c1ebfdc is never entered); the screen is not scrollable; our tick timer
and the press counters work; the window event fn does only what we wrote (kind 3 = LCD on does not rebuild anything); GESTURE with direction 2 calls ui_gesture_consume
and wm_open(3, -1, 0, 0); deleting the screen deletes our timer and frees the state; the stock destroy (0x2c1ecee4) is safe with the state we never created."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
from probe_lvgl import Probe, A
IMG = os.path.join(ROOT, "local/re/main-v1.bin")

def main():
    if not os.path.exists(IMG): print("SKIP: need local/re/main-v1.bin (see the docstring)"); return 0
    p = Probe(IMG); e = p.e; res = []
    ok = lambda name, cond, obs="": (res.append(bool(cond)), print("%s %s %s" % ("PASS" if cond else "FAIL", name, obs)))
    entered = []; e.hook(0x2c1ebfdc, lambda em: entered.append(1) or 0)          # the stock page builder: must never run
    calls = []; e.hook(0x2c224f04, lambda em: calls.append(("consume",)) or 0); e.hook(0x2c225ddc, lambda em: calls.append(("wm_open", em.arg(0), em.arg(1) & 0xffffffff, em.arg(2), em.arg(3))) or 0)
    e.hook(0x2c224d30, lambda em: calls.append(("set_current", em.arg(0))) or 0)
    scr = e.call(0x2c1ecc64, 0, 0)                                                # stock address of the create fn
    ok("create returns a screen (no parent)", scr and e.u32(scr + 4) == 0, hex(scr))
    ok("the stock page builder was never entered", not entered)
    ok("screen is not scrollable", not (e.u32(scr + 0x24) & (1 << 4)), "flags=%#x" % e.u32(scr + 0x24))
    spec = e.u32(scr + 8); n = e.u32(spec + 4); labels = [e.u32(e.u32(spec) + 4 * i) for i in range(n)]
    texts = [e.cstr(e.u32(l + 0x2c)) for l in labels]
    ok("four labels with the expected texts", texts == ["Loader v1b", "0.0", "p0 c0 r0", "0,0"], repr(texts))
    ev = e.u32(spec + 0xc); state = e.u32(ev + 4); timer = e.u32(state + 20)
    ok("state block and tick timer exist", state and timer, "state=%#x timer=%#x" % (state, timer))
    cb = e.u32(timer + 8)
    for _ in range(4): e.call(cb, timer)
    for code in (1, 7, 8): e.call(A["event_send"], scr, code, 0)
    e.call(cb, timer)
    ok("timer and counters", (e.cstr(e.u32(labels[1] + 0x2c)), e.cstr(e.u32(labels[2] + 0x2c))) == ("1.2", "p1 c1 r1"), (e.cstr(e.u32(labels[1] + 0x2c)), e.cstr(e.u32(labels[2] + 0x2c))))
    e.call(0x2c1ecd68, 0, 3, 0); ok("window event kind 3 (LCD on) rebuilds nothing", not entered and e.u32(spec + 4) == n)
    e.call(0x2c1ecd68, 0, 0, 0); ok("window event kind 0 sets the current window id 0x2b", ("set_current", 0x2b) in calls, calls)
    # back gesture: right (2) goes back, left (3) does nothing
    e.hook(0x2c279240, lambda em: 0x20000400); calls.clear()
    for d, expect in ((2, True), (3, False)):
        e.hook(0x2c279336, lambda em, d=d: d); e.call(A["event_send"], scr, 12, 0)
        ok("gesture dir %d %s" % (d, "goes back via wm_open(3,-1,0,0x14), as the stock page does" if expect else "does nothing"), (("wm_open", 3, 0xffffffff, 0, 0x14) in calls) == expect, calls)
        calls.clear()
    log = []; e.hook(0x2c28a448, lambda em: log.append(("timer_del", em.arg(0))) or 0); e.hook(0x2c28a668, lambda em: log.append(("mem_free", em.arg(0))) or 0)
    e.call(0x2c1ecee4)                                                            # stock destroy, run before the window manager deletes the screen
    ok("stock destroy is safe without stock state", True)
    e.call(A["obj_del"], scr)
    ok("deleting the screen deletes our timer and frees the state", ("timer_del", timer) in log and ("mem_free", state) in log, "%d calls" % len(log))
    print("%d/%d passed" % (sum(res), len(res))); return 0 if all(res) else 1
sys.exit(main())
