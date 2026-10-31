# SPDX-License-Identifier: Apache-2.0
"""Tests of f3_link.py and the path guard of f3_pull.py against a mock watch that speaks the read protocol. python3 -I test_f3_link.py"""
import os, socket, subprocess, sys, tempfile, threading
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import f3_link as F
F.time.sleep = lambda s: None                                      # no real waiting in the tests


class Watch:
    """an in-memory watch that can only be read; `mode` injects failures"""
    def __init__(self): self.fs = {}; self.mode = None; self.opened = 0; self.closed = 0
    def connect(self):
        a, b = socket.socketpair(); threading.Thread(target=self.serve, args=(b,), daemon=True).start(); return F.Link(a)
    def serve(self, s):
        rd = None
        try:
            while True:
                data = s.recv(65536)
                if not data: return
                if data.startswith(b"061"):
                    p = data[3:].split(b"\0")[0].decode(); rd = {"p": p, "pos": 0}
                    if p not in self.fs: s.sendall(b"AT^FILE_ERR"); rd = None
                    else: s.sendall(b"\x40" + len(self.fs[p]).to_bytes(4, "big")); self.opened += 1
                elif data.startswith(b"062"):
                    if rd and rd["pos"] < len(self.fs[rd["p"]]):
                        blk = self.fs[rd["p"]][rd["pos"]:rd["pos"] + 1000]; rd["pos"] += len(blk)
                        if self.mode == "bad-block": s.sendall(b"\x00" + len(blk).to_bytes(4, "big")); continue
                        s.sendall(b"\x40" + len(blk).to_bytes(4, "big") + blk + (sum(blk) & 0xffffffff).to_bytes(4, "big"))
                    elif rd: self.closed += 1; rd = None
        except OSError: pass
        finally: s.close()


n_ok = 0
def check(cond, what):
    global n_ok
    if not cond: sys.exit("FAIL: " + what)
    n_ok += 1; print("  ok  ", what)
def raises(fn, text=""):
    try: fn()
    except F.Error as e: return text in str(e)
    return False


w = Watch(); path = "/nand/system/font/FONT_X.bin"; w.fs[path] = bytes(range(256)) * 20          # 5120 bytes, read in 6 blocks
link = w.connect(); data = F.read_raw(link, path); link.close()
check(data == w.fs[path], "a file of 5120 bytes is read completely through several blocks")
check(w.opened == 1, "one read session was opened")
link = w.connect(); check(F.read_raw(link, "/nand/system/font/NOPE.bin") is None, "a missing file gives None (no exception)"); link.close()
link = w.connect(); check(raises(lambda: F.read_raw(link, path, limit=1000), "over the limit"), "a file over the limit is refused before reading"); link.close()
seen = []; link = w.connect(); F.read_raw(link, path, progress=lambda d, t: seen.append((d, t))); link.close()
check(seen[-1] == (5120, 5120) and len(seen) == 6, "progress is reported per block")
b = Watch(); b.fs[path] = bytes(3000); b.mode = "bad-block"; link = b.connect()
check(raises(lambda: F.read_raw(link, path), "invalid block"), "a block with a wrong header is detected"); link.close()
check(raises(lambda: F.open_link(""), "no watch address") and raises(lambda: F.open_link("not-a-mac"), "no watch address") and raises(lambda: F.open_link("00:11:22:33:44"), "no watch address"), "a missing or malformed address is refused before any connection")
a_, b_ = socket.socketpair(); lk = F.Link(a_); b_.close()
check(raises(lambda: lk.send(b"x" * 100000), "closed the connection") and raises(lambda: lk.read(5, 2), "closed the connection"), "a connection that is gone raises a clear Error on send and on read, not a raw socket exception")
src = open(os.path.join(HERE, "f3_link.py"), encoding="utf-8").read()
check("sendall" in src and "33bin" not in src and '"300"' not in src and "def write" not in src, "the module has no write command of the transfer protocol")
for bad in ("/user/tenis.sav", "/nand/system/font/../../../etc/passwd", "/nand/user/health/hr-last.rec", "/nand/system/image/"):
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "f3_pull.py"), tempfile.mkdtemp(), bad, "--addr", "00:11:22:33:44:55"], capture_output=True, text=True)
    check(r.returncode != 0 and "refusing" in (r.stdout + r.stderr), "f3_pull refuses %s" % bad)
print("all %d checks passed" % n_ok)
