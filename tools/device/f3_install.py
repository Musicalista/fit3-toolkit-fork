# SPDX-License-Identifier: Apache-2.0
"""f3_install.py: install, list and remove light apps (.f3a) on a Galaxy Fit3 from this PC over Bluetooth (RFCOMM), for firmware built by make_flat_pkg.py.
The watch has no /user/apps/ directory, so that firmware keeps everything directly in /user/:  /user/a_index.txt  and  /user/a_<id>.f3a
Protocol (same as Fit3 Manager / fit3-flasher): write "300","33bin,<path>,<len>", blocks of <=39600 B + CRC32 LE (each acked "310"), "32","34";  read "061<path>\\0", "062" per block.

    python3 f3_install.py list
    python3 f3_install.py install hello.f3a            # uses hello.meta next to it for the tile colours / names
    python3 f3_install.py remove hello
Only /user/a_index.txt and /user/a_<id>.f3a can be touched; nothing else on the watch is written or read."""
import argparse, os, re, socket, sys, time, zlib

CHANNEL, MAX_APPS = 29, 12
ADDR = os.environ.get("F3_ADDR", "")                  # your watch's Bluetooth address (the name is "Galaxy Fit3 (xxxx)"): pass --addr or set F3_ADDR
INDEX, PREFIX = "/user/a_index.txt", "/user/a_"
SAFE_PATH = re.compile(r"^/user/a_(index\.txt|[a-z0-9_-]{1,11}\.f3a)$")
ID = re.compile(r"^[a-z0-9_-]{1,11}$")

class Error(Exception): pass

class Link:
    """one RFCOMM session; `sock` is any object with send/recv/settimeout/close (the tests use a socketpair)"""
    def __init__(self, sock): self.s = sock
    def send(self, data): self.s.settimeout(30); self.s.sendall(data if isinstance(data, bytes) else data.encode())
    def read(self, n, timeout=30):
        buf = b""; end = time.monotonic() + timeout
        while len(buf) < n:
            left = end - time.monotonic()
            if left <= 0: raise Error("the watch did not answer in time")
            self.s.settimeout(left)
            try: c = self.s.recv(n - len(buf))
            except socket.timeout: raise Error("the watch did not answer in time")
            if not c: raise Error("the watch closed the connection")
            buf += c
        return buf
    def drain(self):
        self.s.settimeout(0.3)
        try:
            while self.s.recv(4096): pass
        except (socket.timeout, BlockingIOError): pass
    def expect(self, text):
        got = self.read(len(text))
        if got != text.encode():
            self.s.settimeout(1.0)
            try: more = self.s.recv(64)
            except (socket.timeout, BlockingIOError): more = b""
            raise Error("the watch rejected the transfer: expected %r, got %r" % (text, got + more))
    def close(self): self.s.close()

def open_link(addr=ADDR, channel=CHANNEL, attempts=6):
    if not re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", addr or ""): raise Error("no watch address: pass --addr AA:BB:CC:DD:EE:FF or set the environment variable F3_ADDR")
    """the channel needs a few seconds to be released after a session, so a busy/reset answer is retried"""
    for i in range(attempts):
        s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM); s.settimeout(20)
        try: s.connect((addr, channel)); time.sleep(0.5); return Link(s)
        except OSError as e:
            s.close()
            if i == attempts - 1: raise Error("cannot connect to the watch at %s: %s (close Galaxy Wearable and Fit3 Manager, restart the watch)" % (addr, e))
            time.sleep(4)

def check_path(path):
    if not SAFE_PATH.match(path): raise Error("refusing to touch %r" % path)

def read_file(link, path, limit=1 << 20):
    check_path(path); return read_raw(link, path, limit)

def read_raw(link, path, limit=1 << 20, progress=None):
    """reads any path to the end (the watch must see the closing "062", otherwise it keeps an export open until it times out)"""
    link.drain(); link.send("061" + path + "\0"); h = link.read(5, 15)
    if h[0] != 0x40: return None                                 # no such file (the watch answers with an "AT^FI..." text)
    total = int.from_bytes(h[1:5], "big")
    if total > limit: raise Error("%s is %d bytes, over the limit of %d (nothing was read)" % (path, total, limit))
    data = b""
    while len(data) < total:
        link.send("062"); hh = link.read(5, 15); n = int.from_bytes(hh[1:5], "big")
        if hh[0] != 0x40 or n == 0 or n > total - len(data): raise Error("invalid block while reading")
        data += link.read(n, 60); link.read(4, 60)
        if progress: progress(len(data), total)
    link.send("062"); time.sleep(0.1); return data

def write_file(link, path, data, progress=None):
    check_path(path); link.drain(); link.send("300"); link.expect("300"); link.send("33bin,%s,%d" % (path, len(data))); link.expect("330")
    for off in range(0, len(data), 39600):
        blk = data[off:off + 39600]; link.send(blk + (zlib.crc32(blk) & 0xffffffff).to_bytes(4, "little")); link.expect("310")
        if progress: progress(off + len(blk), len(data))
    link.send("32"); link.expect("320"); time.sleep(0.25); link.send("34"); link.expect("340")

def parse_index(data):
    return [l.strip() for l in (data or b"").decode("latin-1").replace("\r", "").split("\n") if l.strip() and ";" in l]
def index_bytes(lines): return ("".join(l + "\n" for l in lines) or "\n").encode("latin-1")

def is_f3a(b): return len(b) >= 64 and len(b) <= 60000 and b[:4] == b"F3A1"
def meta_line(f3a_path, app_id):
    meta = os.path.splitext(f3a_path)[0] + ".meta"
    if not os.path.exists(meta): raise Error("no %s next to the .f3a (it holds the tile colours and names)" % os.path.basename(meta))
    line = open(meta, encoding="utf-8").read().strip()
    if not line.startswith(app_id + ";"): raise Error("%s does not describe app %r" % (os.path.basename(meta), app_id))
    line.encode("latin-1"); return line

def session(fn, connect):
    link = connect()
    try: return fn(link)
    finally: link.close()

def cmd_list(connect):
    lines = session(lambda l: parse_index(read_file(l, INDEX)), connect)
    print("%d app(s) on the watch" % len(lines)); [print("  " + l.split(";")[0], "-", l.split(";")[4] if l.count(";") >= 4 else l) for l in lines]; return lines

def cmd_install(connect, f3a_path, say=print):
    app_id = os.path.splitext(os.path.basename(f3a_path))[0]
    if not ID.match(app_id): raise Error("the file name must be an app id: 1-11 characters from a-z 0-9 _ -")
    data = open(f3a_path, "rb").read()
    if not is_f3a(data): raise Error("not a valid .f3a file")
    line = meta_line(f3a_path, app_id)
    lines = session(lambda l: parse_index(read_file(l, INDEX)), connect); at = [i for i, x in enumerate(lines) if x.startswith(app_id + ";")]
    if not at and len(lines) >= MAX_APPS: raise Error("the watch's app list is full (max %d)" % MAX_APPS)
    time.sleep(1.5); say("writing %s%s.f3a (%d bytes)" % (PREFIX, app_id, len(data)))
    session(lambda l: write_file(l, PREFIX + app_id + ".f3a", data), connect); time.sleep(1.5)
    got = session(lambda l: read_file(l, PREFIX + app_id + ".f3a"), connect)
    if got != data: raise Error("the file on the watch does not match what was sent; the app list was NOT changed")
    say("file verified on the watch, updating the app list")
    if at: lines[at[0]] = line
    else: lines.append(line)
    session(lambda l: write_file(l, INDEX, index_bytes(lines)), connect); time.sleep(1.5)
    back = session(lambda l: parse_index(read_file(l, INDEX)), connect)
    if back != lines: raise Error("the app list on the watch does not match")
    say("installed %r; apps on the watch: %s" % (app_id, ", ".join(x.split(";")[0] for x in back)))

def cmd_remove(connect, app_id, say=print):
    if not ID.match(app_id): raise Error("invalid app id")
    lines = session(lambda l: parse_index(read_file(l, INDEX)), connect); keep = [x for x in lines if not x.startswith(app_id + ";")]
    if len(keep) == len(lines): say("%r is not in the app list" % app_id); return
    time.sleep(1.5); session(lambda l: write_file(l, INDEX, index_bytes(keep)), connect); say("removed %r from the app list (the file stays on the watch)" % app_id)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--addr", default=ADDR); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list"); sub.add_parser("install").add_argument("f3a"); sub.add_parser("remove").add_argument("id"); a = ap.parse_args()
    connect = lambda: open_link(a.addr)
    try:
        if a.cmd == "list": cmd_list(connect)
        elif a.cmd == "install": cmd_install(connect, a.f3a)
        else: cmd_remove(connect, a.id)
    except Error as e: sys.exit("ERROR: %s" % e)
