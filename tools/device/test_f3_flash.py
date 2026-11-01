# SPDX-License-Identifier: Apache-2.0
"""Tests of f3_flash.py against a mock watch that speaks the real protocol and can fail in the ways a real transfer can. No hardware. python3 -I tools/device/test_f3_flash.py"""
import hashlib, os, random, re, socket, sys, tempfile, threading, zlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import f3_link as L, f3_flash as F
pauses = []; F.pause = lambda s: pauses.append(s); L.time.sleep = lambda s: None            # no real waiting in the tests


class Watch:
    """an in-memory watch with a file system; `mode` injects failures; every message it receives is logged by kind"""
    def __init__(self, mode=None): self.fs = {}; self.mode = mode; self.log = []; self.connections = 0; self.paths = set()
    def connect(self):
        self.connections += 1; a, b = socket.socketpair(); threading.Thread(target=self.serve, args=(b,), daemon=True).start(); return L.Link(a)
    def serve(self, s):
        wr = None; buf = b""; rd = None; blocks = 0
        try:
            while True:
                data = s.recv(1 << 20)
                if not data: return
                if wr is not None and len(wr["data"]) < wr["len"]:                       # receiving blocks of a file
                    buf += data
                    while wr is not None and len(wr["data"]) < wr["len"]:
                        need = min(F.BLOCK, wr["len"] - len(wr["data"])) + 4
                        if len(buf) < need: break
                        blk, crc = buf[:need - 4], int.from_bytes(buf[need - 4:need], "little"); buf = buf[need:]
                        if crc != zlib.crc32(blk) & 0xffffffff: self.log.append("BAD-CRC"); s.sendall(b"311"); wr = None; break
                        wr["data"] += blk; blocks += 1; self.log.append("block"); s.sendall(b"310")
                        if self.mode == "drop-after-2" and blocks == 2: s.close(); return
                    continue
                if data.startswith(b"300"): self.log.append("300"); s.sendall(b"300")
                elif data.startswith(b"33bin,"):
                    path, n = data[6:].decode().rsplit(",", 1); self.paths.add(path); self.log.append("33bin")
                    if self.mode == "refuse": s.sendall(b"open error:-2, 331"); continue
                    wr = {"path": path, "len": int(n), "data": b""}; buf = b""; s.sendall(b"330")
                elif data.startswith(b"32"): self.log.append("32"); s.sendall(b"320")
                elif data.startswith(b"34"):
                    self.log.append("34"); d = wr["data"]
                    if self.mode == "corrupt": d = d[:1000] + bytes([d[1000] ^ 0xff]) + d[1001:]
                    if self.mode == "short": d = d[:-1]
                    self.fs[wr["path"]] = d; wr = None; s.sendall(b"340")
                elif data.startswith(b"061"):
                    self.log.append("061"); p = data[3:].split(b"\0")[0].decode(); rd = {"p": p, "pos": 0}
                    if p not in self.fs: s.sendall(b"AT^FILE_ERR"); rd = None
                    else: s.sendall(b"\x40" + len(self.fs[p]).to_bytes(4, "big"))
                elif data.startswith(b"062"):
                    self.log.append("062")
                    if rd and rd["pos"] < len(self.fs[rd["p"]]):
                        blk = self.fs[rd["p"]][rd["pos"]:rd["pos"] + 20000]; rd["pos"] += len(blk)
                        s.sendall(b"\x40" + len(blk).to_bytes(4, "big") + blk + (sum(blk) & 0xffffffff).to_bytes(4, "big"))
                    else: rd = None
                elif data.startswith(b"00AT^OTA_UPDATE"):
                    self.log.append("OTA")
                    if self.mode != "no-reply": s.sendall(b"0000")
                    s.close(); return
                else: self.log.append("UNKNOWN %r" % data[:20])
        except OSError: pass
        finally:
            try: s.close()
            except OSError: pass


n_ok = 0
def check(cond, what):
    global n_ok
    if not cond: sys.exit("FAIL: " + what)
    n_ok += 1; print("  ok  ", what)
def raises(fn, text=""):
    try: fn()
    except L.Error as e: return text in str(e)
    return False


random.seed(5); PKG = bytes(random.getrandbits(8) for _ in range(100_000))              # 3 blocks: 39600 + 39600 + 20800
def run(watch, *flags, answer="FLASH", package=PKG):
    out = []; F.check_package = lambda path: (package, hashlib.sha256(package).hexdigest())
    code = F.main(["pkg.bin", "--addr", "00:11:22:33:44:55", *(flags if "--log" in flags else (*flags, "--no-log"))], connect=watch.connect, confirm=lambda prompt: answer, say=out.append)
    return code, "\n".join(out)

# 1. the default does not touch the watch at all
w = Watch(); code, text = run(w)
check(code == 0 and w.connections == 0 and w.log == [] and "nothing was sent" in text, "the default is a plan only: no connection to the watch is made")
check("validate_fwd.py passed" in text and "add --verify" in text, "the plan names the checks and suggests --verify")

# 2. --upload: the file arrives, its size is checked, nothing is installed
w = Watch(); pauses.clear(); code, text = run(w, "--upload")
check(code == 0 and w.fs.get(F.OTA_PATH) == PKG, "--upload stores the package byte for byte at the OTA path")
check(w.paths == {F.OTA_PATH}, "the only path ever written is %s" % F.OTA_PATH)
check("OTA" not in w.log and "installs nothing" in text or "nothing is installed" in text, "--upload alone never sends the OTA command")
check(w.connections == 2 and pauses[:1] == [2.2], "the upload and the size check run in separate sessions, 2.2 s apart (the sequence of the existing flashers)")
check(w.log.count("block") == 3 and w.log[:2] == ["300", "33bin"] and w.log[w.log.index("block") + 3:w.log.index("block") + 5] == ["32", "34"], "the protocol order is 300, 33bin, 3 blocks, 32, 34")
check("062" not in w.log, "without --verify the file is not read back (only the 5-byte header is asked for)")
check(all(not m.startswith("UNKNOWN") and m != "BAD-CRC" for m in w.log), "every message the watch received was a known one, every block CRC correct")

# 3. --verify reads everything back
w = Watch(); code, text = run(w, "--upload", "--verify")
check(code == 0 and "identical to the package" in text and "062" in w.log, "--verify reads the file back and finds it identical")
check(0.25 in pauses, "the read-back pauses between blocks")

# 4. what must stop the process before anything is installed
for mode, flags, needle, label in (("short", ("--upload", "--start-update", "--yes-flash"), "NOT installing", "a file of the wrong size stops the update (the quick check)"),
                                   ("corrupt", ("--upload", "--verify", "--start-update", "--yes-flash"), "differs from the package", "a changed byte is found by --verify and stops the update"),
                                   ("refuse", ("--upload", "--start-update", "--yes-flash"), "does not accept the file", "a refusal to take the file stops everything"),
                                   ("drop-after-2", ("--upload", "--start-update", "--yes-flash"), "closed the connection", "a connection that drops in the middle of the upload stops everything")):
    w = Watch(mode); code, text = run(w, *flags)
    check(code == 1 and needle in text and "OTA" not in w.log, label)
w = Watch("corrupt"); code, text = run(w, "--upload")
check(code == 0 and "OTA" not in w.log, "(documented limit) without --verify a changed byte of the right size is not noticed: that is why --verify is recommended")

# 5. starting the update needs a confirmation, then it is one command in a session of its own
w = Watch(); code, text = run(w, "--upload", "--start-update", answer="no")
check(code == 1 and "not confirmed" in text and w.connections == 0 and w.log == [], "--start-update without the typed confirmation sends nothing at all")
w = Watch(); pauses.clear(); code, text = run(w, "--start-update", "--verify")
check(code == 0 and w.log[-1] == "OTA" and w.log.count("OTA") == 1 and w.connections == 3 and pauses.count(2.2) == 2, "--start-update implies the upload; the OTA command is the last message, sent once, in a third session")
check("answered b'0000'" in text and "do not touch it" in text, "the watch's answer is shown, with the instruction to leave the watch alone")
w = Watch("no-reply"); code, text = run(w, "--start-update", "--yes-flash")
check(code == 0 and "answered None" in text, "no answer to the OTA command (the watch restarts at once) is not an error")

# 5b. the log file: time-stamped protocol events, counts and sizes, never the package's bytes
logf = os.path.join(tempfile.mkdtemp(), "sub", "flash.log"); w = Watch(); code, text = run(w, "--start-update", "--yes-flash", "--verify", "--log", logf)
log = open(logf, encoding="utf-8").read()
check(code == 0 and os.path.exists(logf) and logf in text.replace("\n", " "), "a log file is written (also in a folder that did not exist) and its name is shown")
check(all(re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}  ", l) for l in log.strip().split("\n")), "every line of the log has a date and a time with milliseconds")
check(hashlib.sha256(PKG).hexdigest() in log and "00:11:22:33:44:55" in log and "arguments:" in log, "the log names the package's SHA-256, the watch's address and the arguments")
for needle in ("session upload: connected", "-> 300", "-> 33bin,/user/ota/R390_WEB_FOTA.bin,100000", "block 1/3: 39600 bytes", "block 3/3", "-> 32", "-> 34", "session check: closed", "<- header: the file is 100000 bytes (the package: 100000)",
               "read-back: 5 blocks, 100000 bytes, all identical", "pause 2.20 s", "-> 00AT^OTA_UPDATE", "<- b'0000'", "uploaded 100000 bytes"):
    check(needle in log, "the log has: " + needle)
check(PKG[5000:5016].hex() not in log and repr(PKG[5000:5016]) not in log, "the log never contains the package's bytes")
w = Watch("refuse"); logf2 = os.path.join(tempfile.mkdtemp(), "f.log"); code, text = run(w, "--upload", "--log", logf2)
check(code == 1 and "ERROR" in open(logf2, encoding="utf-8").read() and "open error" in open(logf2, encoding="utf-8").read(), "a failure is in the log with the watch's own words")
w = Watch(); code, text = run(w, "--upload"); check("log " not in text and not any(f.startswith("f3_flash-") for f in os.listdir(tempfile.gettempdir())), "--no-log writes no file")

# 6. the write path is guarded
w = Watch(); link = w.connect()
check(raises(lambda: F.upload(link, b"x" * 10, path="/user/tenis.sav"), "only /user/ota/R390_WEB_FOTA.bin") and w.log == [], "writing any other path is refused before a byte is sent")
link.close()

# 7. the package checks (these use a real package when there is one)
tmp = tempfile.mkdtemp(); small = os.path.join(tmp, "small.bin"); open(small, "wb").write(b"x" * 1000)
F.check_package = F.__dict__["check_package"] if "check_package" in F.__dict__ else None
import importlib; importlib.reload(F); F.pause = lambda s: None
check(raises(lambda: F.check_package(small), "not a firmware package"), "a file of the wrong size is refused")
check(raises(lambda: F.check_package(os.path.join(tmp, "nope.bin")), "no such file"), "a missing file is refused")
real = os.path.join(HERE, "..", "..", "local", "firmware", "fit3-tennis.bin")
if os.path.exists(real):
    data, digest = F.check_package(real); check(hashlib.sha256(data).hexdigest() == digest, "a real package passes validate_fwd.py")
    bad = bytearray(data); bad[len(bad) // 2] ^= 0xff; bp = os.path.join(tmp, "bad.bin"); open(bp, "wb").write(bad)
    check(raises(lambda: F.check_package(bp), "validate_fwd.py refused"), "a package with one changed byte is refused before the watch is touched")
else: print("  skip a real package (local/firmware/fit3-tennis.bin is not there)")
print("all %d checks passed" % n_ok)
