# SPDX-License-Identifier: Apache-2.0
"""mock_watch.py: an in-memory watch that speaks the real protocol (docs/protocol.md) for the tests of f3_flash.py and f3x_install.py. No hardware."""
import socket, sys, os, threading, zlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import f3_link as L, f3_flash as F


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
