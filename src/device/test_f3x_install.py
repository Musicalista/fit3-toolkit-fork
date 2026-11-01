# SPDX-License-Identifier: Apache-2.0
"""Tests of f3x_install.py against the mock watch (mock_watch.py). No hardware. python3 -I src/device/test_f3x_install.py   (builds the sample .f3x with arm-none-eabi-gcc, so it needs the toolchain and numpy)"""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "f3x")); sys.path.insert(0, os.path.join(HERE, "..", "assets")); sys.path.insert(0, os.path.join(HERE, "..", "watch"))
import f3_link as L, f3_flash as F, f3x_install as I, f3x, mkicon, gen
from mock_watch import Watch
F.pause = lambda s: None; L.time.sleep = lambda s: None
n_ok = 0
def check(cond, what):
    global n_ok
    if not cond: sys.exit("FAIL: " + what)
    n_ok += 1; print("  ok  ", what)

def build(name):
    wd = tempfile.mkdtemp(); src = os.path.join(HERE, "..", "watch", "apps", name + ".c")
    image, off, rel = f3x.compile_app(src, wd, [gen.generate(list(gen.APPS), False, os.path.join(wd, "gen"))])
    return f3x.pack(f3x.default_name(src), image, off, rel, mkicon.encode_indexed4(*mkicon.draw(name, 64)))
COUNTER, DICE, TENNIS = build("counter"), build("dice"), build("tennis")
tmp = tempfile.mkdtemp(); fc = os.path.join(tmp, "counter.f3x"); fd = os.path.join(tmp, "dice.f3x"); open(fc, "wb").write(COUNTER); open(fd, "wb").write(DICE); ft = os.path.join(tmp, "tennis.f3x"); open(ft, "wb").write(TENNIS)
def run(watch, *args):
    out = []; code = I.main(["--addr", "00:11:22:33:44:55", "--no-log", *args], connect=watch.connect, say=out.append); return code, "\n".join(out)
HUB = "/user/hub/a%02d.f3x"

w = Watch(); w.fs[HUB % 0] = COUNTER; code, text = run(w, "list")
check(code == 0 and "slot  0  Counter" in text and text.count("-") >= 15 and set(w.log) <= {"061", "062"}, "list reads the sixteen slots and writes nothing")
w = Watch(); code, text = run(w, "install", fc)
check(code == 0 and w.fs.get(HUB % 0) == COUNTER and w.paths == {HUB % 0}, "install puts the file byte for byte into the first free slot, and writes only that path")
check("installed 'Counter' in slot 0" in text and w.connections == 3, "it takes a look, a write and a read-back session")
code, text = run(w, "install", fd); check(code == 0 and w.fs.get(HUB % 1) == DICE, "the next app goes to the next free slot")
code, text = run(w, "install", fc); check(code == 0 and "updated" in text and w.fs[HUB % 0] == COUNTER and HUB % 2 not in w.fs, "an app with the same name is updated in place")
code, text = run(w, "install", fd, "--slot", "0"); check(code == 1 and "--force" in text and w.fs[HUB % 0] == COUNTER, "a named slot of another app is not overwritten without --force")
code, text = run(w, "install", fd, "--slot", "0", "--force"); check(code == 0 and w.fs[HUB % 0] == DICE, "--force overwrites it")
code, text = run(w, "remove", "--slot", "0"); check(code == 0 and w.fs[HUB % 0] == I.TOMBSTONE, "remove writes a tombstone")
code, text = run(w, "list"); check("slot  0  free (not an app)" in text, "a tombstone is listed as free")
code, text = run(w, "install", fc); check(code == 0 and w.fs[HUB % 0] == COUNTER, "a tombstone slot is the first free slot")
# refusals
w = Watch(); bad = bytearray(COUNTER); bad[-3] ^= 1; fb = os.path.join(tmp, "bad.f3x"); open(fb, "wb").write(bad)
code, text = run(w, "install", fb); check(code == 1 and "CRC" in text and w.connections == 0, "a damaged file is refused on the PC, the watch is not touched")
fg = os.path.join(tmp, "g.f3x"); open(fg, "wb").write(b"hello"); code, text = run(w, "install", fg); check(code == 1 and w.connections == 0, "a file that is not an .f3x is refused on the PC")
link = w.connect()
refused = 0
for p in ("/user/ota/R390_WEB_FOTA.bin", "/user/tenis.sav", "/user/hub/a16.f3x", "/user/hub/../ota/x", "/user/hub/a1.f3x", "/user/hub/a01.f3x.bak"):
    try: I.write(link, COUNTER, p)
    except L.Error: refused += 1
check(refused == 6 and w.log == [], "every path but a00..a15.f3x is refused before a byte is sent")
try: I.write(link, b"not an app", "/user/hub/a00.f3x"); check(False, "content")
except L.Error: check(w.log == [], "content that is neither a valid .f3x nor the tombstone is refused")
link.close()
w = Watch("refuse"); code, text = run(w, "install", fc); check(code == 1 and "does not accept the file" in text, "when /user/hub does not exist the watch refuses and the tool says so")
w = Watch("corrupt"); code, text = run(w, "install", fc)
check(code == 1 and "differs" in text, "a changed byte on the watch is found by the read-back (the app is reported unusable)")
w = Watch("short"); code, text = run(w, "install", fc); check(code == 1 and "differs" in text, "a file stored with the wrong content is found by the read-back")
w2 = Watch(); w2.fs.update({HUB % k: COUNTER if k % 2 else DICE for k in range(I.SLOTS)})
code, text = run(w2, "install", ft); check(code == 1 and "all 16 slots are taken" in text, "with every slot taken by other apps nothing is overwritten")
code, text = run(w2, "install", fc, "--slot", "99"); check(code == 1 and "0..15" in text, "a slot number out of range is refused")
print("all %d checks passed" % n_ok)
