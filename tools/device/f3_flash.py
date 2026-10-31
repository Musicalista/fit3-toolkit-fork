# SPDX-License-Identifier: Apache-2.0
"""f3_flash.py: send a firmware package to a Galaxy Fit3 from this PC over Bluetooth, instead of with the phone app (Fit3 Manager). **The only tool of this repository that writes to the watch.**

    python3 -I tools/device/f3_flash.py out.bin --addr AA:BB:CC:DD:EE:FF                       # 1. plan only: checks the package on the PC, does not touch the watch
    python3 -I tools/device/f3_flash.py out.bin --addr AA:BB:CC:DD:EE:FF --upload              # 2. copies the package to the watch and checks its size; installs nothing
    python3 -I tools/device/f3_flash.py out.bin --addr AA:BB:CC:DD:EE:FF --upload --verify     #    the same, and reads the whole file back to compare it (recommended)
    python3 -I tools/device/f3_flash.py out.bin --addr AA:BB:CC:DD:EE:FF --upload --verify --start-update    # 3. then starts the installation (asks you to type FLASH)

What happens, in order (protocol: docs/protocol.md; the order and the pauses are those of the phone app, each stage in a session of its own):
  * the package must pass tools/firmware/validate_fwd.py (every CRC, the stock updater, version R390XXU0AZA3), otherwise nothing is sent;
  * `--upload` writes the package to /user/ota/R390_WEB_FOTA.bin in blocks of 39600 bytes, each with a CRC32 that the watch acknowledges. A partly written file is never installed by itself: only
    `--start-update` does that, so an interrupted upload is harmless, just run it again;
  * then, always, a quick check: after about 2 s the tool reconnects and asks the watch for the size of the file; a different size stops everything before anything is installed;
  * `--verify` (recommended, optional) goes further and reads the whole file back, comparing every block with the package (and the watch's own checksum of each block). It takes as long as the upload and
    is the only check that the content, not just the size, is what you sent;
  * `--start-update` waits about 2 s, reconnects and sends `00AT^OTA_UPDATE`. The watch restarts and installs the package; **this cannot be cancelled** and the watch must not be switched off.
    It needs your explicit confirmation.
Only /user/ota/R390_WEB_FOTA.bin can be written. The watch must be visible, charged to at least 50 %, Galaxy Wearable and Fit3 Manager closed, and it must carry the Bluetooth patches of
build_package.py (without them the serial service is reachable only on the setup screen). Keep the stock package at hand: it is the way back. Status: tested against a mock watch; see docs/status.md
for what has been tried on a real one."""
import argparse, hashlib, os, subprocess, sys, time, zlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import f3_link as L

OTA_PATH = "/user/ota/R390_WEB_FOTA.bin"
BLOCK = 39600
OTA_COMMAND = "00AT^OTA_UPDATE"
VALIDATOR = os.path.join(HERE, "..", "firmware", "validate_fwd.py")
MIN_SIZE, MAX_SIZE = 10 << 20, 40 << 20                  # a package is about 18 MB


def expect(link, text):
    got = link.read(len(text))
    if got != text.encode():
        link.s.settimeout(1.0)
        try: more = link.s.recv(64)
        except Exception: more = b""
        raise L.Error("the watch rejected the transfer: expected %r, got %r" % (text, got + more))


def check_package(path, run=subprocess.run):
    """local checks only (the watch is not touched): size, and every check of validate_fwd.py. Returns (bytes, sha256 hex)"""
    if not os.path.isfile(path): raise L.Error("no such file: " + path)
    data = open(path, "rb").read()
    if not MIN_SIZE <= len(data) <= MAX_SIZE: raise L.Error("%s is %d bytes: not a firmware package (expected %d to %d MB)" % (path, len(data), MIN_SIZE >> 20, MAX_SIZE >> 20))
    r = run([sys.executable, "-I", VALIDATOR, path], capture_output=True, text=True)
    if r.returncode: raise L.Error("validate_fwd.py refused the package, nothing was sent:\n" + (r.stdout + r.stderr).strip())
    return data, hashlib.sha256(data).hexdigest()


def upload(link, data, path=OTA_PATH, progress=None):
    """writes `data` to the OTA path: 300 / 33bin,<path>,<length> / blocks with CRC32 / 32 / 34. Nothing is installed by this."""
    if path != OTA_PATH: raise L.Error("refusing to write %r: only %s can be written" % (path, OTA_PATH))
    link.drain(); link.send("300"); expect(link, "300")
    link.send("33bin,%s,%d" % (path, len(data)))
    try: expect(link, "330")
    except L.Error as e: raise L.Error("the watch does not accept the file (%s); is /user/ota/ missing, or is it not a Fit3 with the Bluetooth patches?" % e)
    for off in range(0, len(data), BLOCK):
        blk = data[off:off + BLOCK]; link.send(blk + (zlib.crc32(blk) & 0xffffffff).to_bytes(4, "little")); expect(link, "310")
        if progress: progress(off + len(blk), len(data))
    link.send("32"); expect(link, "320"); time.sleep(0.25); link.send("34"); expect(link, "340")


def pause(seconds): time.sleep(seconds)


def check_size(link, size, path=OTA_PATH):
    """the quick check: asks the watch for the length of the file and compares it with `size`; returns the open read (so --verify can go on) """
    link.drain(); link.send("061" + path + "\0"); h = link.read(5, 30)
    if h[0] != 0x40: raise L.Error("could not check the file on the watch: it does not answer for %s" % path)
    total = int.from_bytes(h[1:5], "big")
    if total != size: raise L.Error("the file on the watch is %d bytes, the package %d: NOT installing" % (total, size))
    return total


def read_back(link, data, total, progress=None):
    """after check_size: reads the file block by block, comparing it with `data` and the watch's checksum of each block (their sum of bytes, big endian); pauses 0.25 s between blocks"""
    pause(0.25); off = 0
    while off < total:
        link.send("062"); hh = link.read(5, 30); n = int.from_bytes(hh[1:5], "big")
        if hh[0] != 0x40 or n <= 0 or n > (1 << 20) or n > total - off: raise L.Error("invalid block while reading the file back: NOT installing")
        blk = link.read(n, 180); chk = int.from_bytes(link.read(4, 180), "big")
        if (sum(blk) & 0xffffffff) != chk: raise L.Error("checksum error while reading the file back (bluetooth): try again")
        if blk != data[off:off + n]: raise L.Error("the content on the watch differs from the package at byte %d: NOT installing" % off)
        off += n
        if progress: progress(off, total)
        pause(0.25)
    link.send("062"); pause(0.1)                                   # the last "062" ends the export


def start_update(link):
    """sends the OTA command and returns the watch's 4-byte answer, or None (it may restart before answering)"""
    link.drain(); link.send(OTA_COMMAND)
    try: return link.read(4, 6)
    except L.Error: return None


def main(argv=None, connect=None, confirm=None, say=print):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("package"); ap.add_argument("--addr", default=L.ADDR, help="the watch's Bluetooth address (or set F3_ADDR)")
    ap.add_argument("--upload", action="store_true", help="copy the package to the watch and check its size (installs nothing)")
    ap.add_argument("--verify", action="store_true", help="also read the whole file back and compare it (recommended, optional; takes as long as the upload)")
    ap.add_argument("--start-update", action="store_true", help="after the upload, start the installation (cannot be cancelled); asks you to type FLASH")
    ap.add_argument("--yes-flash", action="store_true", help="do not ask for the confirmation (for scripts)")
    a = ap.parse_args(argv)
    connect = connect or (lambda: L.open_link(a.addr)); confirm = confirm or (lambda prompt: input(prompt))
    def session(fn):
        link = connect()
        try: return fn(link)
        finally: link.close()
    try:
        data, digest = check_package(a.package)
        say("package   %s  %d bytes  sha256 %s" % (a.package, len(data), digest[:16] + "..."))
        say("checks    validate_fwd.py passed: every CRC, the stock updater, version R390XXU0AZA3")
        say("plan      write %s in %d blocks, check its size%s%s" % (OTA_PATH, -(-len(data) // BLOCK), ", read it all back and compare" if a.verify else " (add --verify to read it back: recommended)",
                                                                  ", then START THE UPDATE" if a.start_update else ", install nothing"))
        if a.start_update: a.upload = True
        if not a.upload: say("nothing was sent. Add --upload to copy the package to the watch."); return 0
        if a.start_update and not a.yes_flash:
            say("\nThe update cannot be cancelled once it starts. Keep the watch charged (50 % or more) and leave it alone until it is back, several minutes.")
            if confirm("Type FLASH to continue: ").strip() != "FLASH": raise L.Error("not confirmed, nothing was sent")
        last = [0]
        def prog(label):
            def p(done, total):
                if done == total or time.monotonic() - last[0] > 5: last[0] = time.monotonic(); say("  %s %d/%d B (%.0f%%)" % (label, done, total, 100 * done / total))
            return p
        t0 = time.monotonic(); session(lambda link: upload(link, data, progress=prog("upload")))
        say("uploaded %d bytes in %.0f s; the watch acknowledged every block (nothing is installed yet)" % (len(data), time.monotonic() - t0))
        pause(2.2)
        def check(link):
            total = check_size(link, len(data)); say("the file on the watch has the right size (%d bytes)" % total)
            if a.verify: read_back(link, data, total, progress=prog("read-back")); say("read back: the file on the watch is identical to the package")
        session(check)
        if not a.start_update: say("done. The package waits in %s; nothing is installed. Start the installation with --start-update, or with Fit3 Manager." % OTA_PATH); return 0
        pause(2.2)
        reply = session(start_update)
        say("OTA command sent; the watch answered %r. It now restarts and installs: do not touch it until it is back (several minutes)." % (reply,))
        return 0
    except L.Error as e:
        say("ERROR: %s" % e); return 1
    except KeyboardInterrupt:
        say("\ninterrupted. Nothing was installed: a partly written %s is only used by --start-update. Run the tool again." % OTA_PATH); return 130


if __name__ == "__main__":
    sys.exit(main())
