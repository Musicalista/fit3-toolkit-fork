# SPDX-License-Identifier: Apache-2.0
"""Tests f3_install.py against a mock watch that speaks the real protocol (including "open error:-2, 331" for a missing directory). python3 -I test_f3_install.py"""
import os, socket, sys, threading, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3_install as F
F.time.sleep = lambda s: None                                      # no real waiting in the tests
HERE = os.path.dirname(os.path.abspath(__file__))

class Watch:
    """in-memory watch; flat /user/ only (no /user/apps/ directory); `mode` injects failures"""
    def __init__(self): self.fs = {}; self.mode = None; self.writes = []
    def connect(self):
        a, b = socket.socketpair(); threading.Thread(target=self.serve, args=(b,), daemon=True).start(); return F.Link(a)
    def serve(self, s):
        wr = None; buf = b""
        try:
            while True:
                data = s.recv(65536)
                if not data: return
                if wr is not None and len(wr["data"]) < wr["len"]:   # receiving blocks of a file
                    buf += data
                    need = min(39600, wr["len"] - len(wr["data"])) + 4
                    if len(buf) < need: continue
                    blk, crc = buf[:need - 4], int.from_bytes(buf[need - 4:need], "little"); buf = buf[need:]
                    assert crc == zlib.crc32(blk) & 0xffffffff, "block CRC"
                    wr["data"] += blk; s.sendall(b"310"); continue
                if data.startswith(b"300"): s.sendall(b"300")
                elif data.startswith(b"33bin,"):
                    path, n = data[6:].decode().rsplit(",", 1); parent = path.rsplit("/", 1)[0]
                    if self.mode == "refuse" or parent != "/user": s.sendall(b"open error:-2, 331"); continue
                    wr = {"path": path, "len": int(n), "data": b""}; s.sendall(b"330")
                elif data.startswith(b"32"): s.sendall(b"320")
                elif data.startswith(b"34"):
                    d = wr["data"]
                    if self.mode == "corrupt" and wr["path"].endswith(".f3a"): d = d[:-1] + bytes([d[-1] ^ 0xff])
                    self.fs[wr["path"]] = d; self.writes.append(wr["path"]); wr = None; s.sendall(b"340")
                elif data.startswith(b"061"):
                    p = data[3:].split(b"\0")[0].decode(); rd = {"p": p, "pos": 0}
                    if p not in self.fs: s.sendall(b"AT^FILE_ERR"); rd = None
                    else: s.sendall(b"\x40" + len(self.fs[p]).to_bytes(4, "big"))
                elif data.startswith(b"062"):
                    if rd and rd["pos"] < len(self.fs[rd["p"]]):
                        blk = self.fs[rd["p"]][rd["pos"]:rd["pos"] + 1000]; rd["pos"] += len(blk)
                        s.sendall(b"\x40" + len(blk).to_bytes(4, "big") + blk + (sum(blk) & 0xffffffff).to_bytes(4, "big"))
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

w = Watch(); quiet = lambda *_: None
# synthetic apps (a valid .f3a only needs the "F3A1" magic and at least 64 bytes), so the test needs no third-party files
import tempfile
TMP = tempfile.mkdtemp(prefix="f3test_")
def make_app(app_id, meta):
    path = os.path.join(TMP, app_id + ".f3a"); open(path, "wb").write(b"F3A1" + bytes(range(256)) * 3 + b"\x00")      # ends in 0: the corruption test flips bits
    open(os.path.join(TMP, app_id + ".meta"), "w", encoding="utf-8").write(meta + "\n"); return path
hello = make_app("hello", "hello;F8D8B0;A85A20;Ol\xe1;Hello;" + "0" * 256)
tenis = make_app("tenis", "tenis;C6EFA8;3A7A1E;Tennis;Tennis")
check(len(F.cmd_list(w.connect)) == 0, "list on a fresh watch (no index file) -> 0 apps")
F.cmd_install(w.connect, hello, quiet)
check(w.fs["/user/a_hello.f3a"] == open(hello, "rb").read(), "hello.f3a stored byte for byte as /user/a_hello.f3a")
check(w.fs["/user/a_index.txt"].decode("latin-1").startswith("hello;F8D8B0;A85A20;Ol\xe1;Hello;"), "index line from hello.meta (Latin-1 name)")
check(w.writes == ["/user/a_hello.f3a", "/user/a_index.txt"], "file is written before the index (an interrupted install never lists a missing app)")
F.cmd_install(w.connect, hello, quiet); check(len(F.parse_index(w.fs["/user/a_index.txt"])) == 1, "installing again updates the line instead of duplicating it")
F.cmd_install(w.connect, tenis, quiet); check([l.split(";")[0] for l in F.parse_index(w.fs["/user/a_index.txt"])] == ["hello", "tenis"], "second app is added to the list")
F.cmd_remove(w.connect, "hello", quiet); check([l.split(";")[0] for l in F.parse_index(w.fs["/user/a_index.txt"])] == ["tenis"], "remove takes hello off the list")
check(len(F.cmd_list(w.connect)) == 1, "list after the changes -> 1 app")
big = Watch(); big.fs["/user/a_index.txt"] = F.index_bytes(["app%d;000000;FFFFFF;a;b" % i for i in range(12)])
check(raises(lambda: F.cmd_install(big.connect, hello, quiet), "full"), "a 13th app is refused (list full)")
r = Watch(); r.mode = "refuse"
check(raises(lambda: F.cmd_install(r.connect, hello, quiet), "rejected the transfer") and not r.fs, "watch refuses the write -> clear error, nothing stored")
c = Watch(); c.mode = "corrupt"
check(raises(lambda: F.cmd_install(c.connect, hello, quiet), "does not match") and "/user/a_index.txt" not in c.fs, "corrupted write is detected and the app list is NOT changed")
for bad in ("/user/apps/x.f3a", "/user/a_../x.f3a", "/nand/system/x", "/user/safe.flag", "/user/a_UPPER.f3a", "/user/a_index.txt.bak"):
    check(raises(lambda: F.check_path(bad), "refusing"), "path guard refuses %s" % bad)
notes = os.path.join(TMP, "Notes.txt"); open(notes, "wb").write(b"not an app")
check(raises(lambda: F.cmd_install(w.connect, notes, quiet)), "a file that is not an app id / .f3a is refused")
print("all %d checks passed" % n_ok)
