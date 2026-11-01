# SPDX-License-Identifier: Apache-2.0
"""f3_link.py: a read-only link to a Galaxy Fit3 over Bluetooth (RFCOMM channel 29) for tools that copy files from the watch to this PC (f3_pull.py). Nothing here can write to the watch.

Protocol (see docs/protocol.md): send "061<path>\\0"; the watch answers 0x40 + a 4-byte big-endian length (or an "AT^FI..." text when the file
does not exist); then "062" asks for the next block (0x40, 4-byte length, data, 4 bytes of checksum); a last "062" closes the export. The watch must be visible, Samsung's Galaxy Wearable app
closed on the phone (one client at a time), and the Bluetooth patches of build_package.py installed (they make the serial service reachable without pairing)."""
import os, re, socket, time

CHANNEL = 29
ADDR = os.environ.get("F3_ADDR", "")                  # your watch's Bluetooth address (the name is "Galaxy Fit3 (xxxx)"): pass --addr or set F3_ADDR


class Error(Exception): pass


class Link:
    """one RFCOMM session; `sock` is any object with send/recv/settimeout/close (the tests use a socketpair)"""
    def __init__(self, sock): self.s = sock
    def send(self, data):
        self.s.settimeout(30)
        try: self.s.sendall(data if isinstance(data, bytes) else data.encode())
        except socket.timeout: raise Error("the watch did not take the data in time")
        except OSError as e: raise Error("the watch closed the connection (%s)" % e.__class__.__name__)
    def read(self, n, timeout=30):
        buf = b""; end = time.monotonic() + timeout
        while len(buf) < n:
            left = end - time.monotonic()
            if left <= 0: raise Error("the watch did not answer in time")
            self.s.settimeout(left)
            try: c = self.s.recv(n - len(buf))
            except socket.timeout: raise Error("the watch did not answer in time")
            except OSError as e: raise Error("the watch closed the connection (%s)" % e.__class__.__name__)
            if not c: raise Error("the watch closed the connection")
            buf += c
        return buf
    def drain(self):
        self.s.settimeout(0.3)
        try:
            while self.s.recv(4096): pass
        except (socket.timeout, BlockingIOError): pass
    def close(self): self.s.close()


def open_link(addr=ADDR, channel=CHANNEL, attempts=6):
    """the channel needs a few seconds to be released after a session, so a busy/reset answer is retried"""
    if not re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", addr or ""): raise Error("no watch address: pass --addr AA:BB:CC:DD:EE:FF or set the environment variable F3_ADDR")
    for i in range(attempts):
        s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM); s.settimeout(20)
        try: s.connect((addr, channel)); time.sleep(0.5); return Link(s)
        except OSError as e:
            s.close()
            if i == attempts - 1: raise Error("cannot connect to the watch at %s: %s (close Samsung's Galaxy Wearable app on the phone, restart the watch)" % (addr, e))
            time.sleep(4)


def read_raw(link, path, limit=1 << 20, progress=None):
    """reads a file to the end (the watch must see the closing "062", otherwise it keeps an export open until it times out); None when the file does not exist"""
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
