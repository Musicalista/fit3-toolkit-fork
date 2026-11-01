# SPDX-License-Identifier: Apache-2.0
"""f3x_install.py: put .f3x apps on the watch (docs/f3x.md), list them, remove them. **The second of two tools that write to the watch** (the other is f3_flash.py); this one can only write the
sixteen files /user/hub/a00.f3x .. /user/hub/a15.f3x, which the Application Hub reads.

    python3 -I src/device/f3x_install.py list                            [--addr AA:BB:CC:DD:EE:FF]   # what is in the sixteen slots (read only)
    python3 -I src/device/f3x_install.py install counter.f3x             [--slot N] [--force]         # first free slot, or the one you name; a slot of another app needs --force
    python3 -I src/device/f3x_install.py remove --slot N                                              # overwrites the slot with a tombstone; the hub ignores it

The file is checked on the PC first (build_f3x.py --check: magic, firmware id, sizes, CRC), written with the same protocol as a firmware upload, then the tool reconnects, reads it back and compares it.
The hub creates /user/hub the first time you open it, so open the hub once before the first install. Needs the Bluetooth patches of build_package.py (the default package has them).
Nothing is installed in the firmware: an app is a file; the hub loads it into RAM when you open it. A log is written to local/logs/f3x_install-<time>.log (protocol events and sizes, never the file's bytes)."""
import argparse, os, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "f3x"))
import f3_link as L, f3_flash as F, f3x

SLOTS = f3x.SLOTS; TOMBSTONE = b"F3X-GONE"
PATH_RE = re.compile(r"/user/hub/a(0[0-9]|1[0-5])\.f3x")


def slot_path(n):
    if not 0 <= n < SLOTS: raise L.Error("the slot must be 0..%d" % (SLOTS - 1))
    return "/user/hub/a%02d.f3x" % n


def write(link, data, path, trace=None):
    """the only write of this tool: refuses every path but the sixteen slots, every content that is not a valid .f3x or the tombstone"""
    if not PATH_RE.fullmatch(path): raise L.Error("refusing to write %r: only /user/hub/a00.f3x .. a15.f3x can be written" % path)
    if data != TOMBSTONE:
        try: f3x.parse(data)
        except f3x.Error as e: raise L.Error("refusing to write: not a valid .f3x (%s)" % e)
    F.write_file(link, data, path, trace=trace)


def read_slot(link, n):
    """-> None (no file), ('free', None) (a tombstone or a file the hub ignores), or ('app', name, size)"""
    data = L.read_raw(link, slot_path(n), limit=64 * 1024)
    if data is None: return None
    try: return ("app", f3x.parse(data)["name"], len(data))
    except f3x.Error: return ("free", None, len(data))


def main(argv=None, connect=None, say=print):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--addr", default=L.ADDR, help="the watch's Bluetooth address (or set F3_ADDR)")
    ap.add_argument("--log"); ap.add_argument("--no-log", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True); sub.add_parser("list")
    i = sub.add_parser("install"); i.add_argument("file"); i.add_argument("--slot", type=int); i.add_argument("--force", action="store_true", help="overwrite a slot that holds another app")
    r = sub.add_parser("remove"); r.add_argument("--slot", type=int, required=True)
    a = ap.parse_args(argv); connect = connect or (lambda: L.open_link(a.addr))
    j = F.Journal(None if a.no_log else (a.log or os.path.join(HERE, "..", "..", "local", "logs", "f3x_install-%s.log" % time.strftime("%Y%m%d-%H%M%S"))), say)
    def session(name, fn):
        j.trace("session %s: connecting to %s" % (name, a.addr)); link = connect(); j.trace("session %s: connected" % name)
        try: return fn(link)
        finally: link.close(); j.trace("session %s: closed" % name)
    def slots(link):
        out = []
        for n in range(SLOTS):
            out.append(read_slot(link, n)); F.pause(0.25)
        return out
    def show(table):
        for n, e in enumerate(table): j("  slot %2d  %s" % (n, "-" if e is None else "free (not an app)" if e[0] == "free" else "%s  (%d bytes)" % (e[1], e[2])))
    try:
        j.trace("arguments: %s" % " ".join(argv if argv is not None else sys.argv[1:]))
        if a.cmd == "list": show(session("list", slots)); return 0
        if a.cmd == "remove":
            path = slot_path(a.slot); j("plan      overwrite %s with a tombstone (the hub ignores it)" % path)
            session("write", lambda link: write(link, TOMBSTONE, path, j.trace)); F.pause(2.2)
            def chk(link):
                got = L.read_raw(link, path, limit=64)
                if got != TOMBSTONE: raise L.Error("the slot does not read back as a tombstone")
            session("check", chk); j("removed   slot %d" % a.slot); return 0
        data = open(a.file, "rb").read()
        try: app = f3x.parse(data)
        except f3x.Error as e: raise L.Error("%s is not a valid .f3x for this firmware: %s" % (a.file, e))
        j("file      %s  %d bytes  app %r  image %d bytes, %d relocations, CRC ok, firmware R390XXU0AZA3" % (a.file, len(data), app["name"], len(app["image"]), len(app["relocs"])))
        table = session("look", slots); show(table)
        if a.slot is None:
            same = [n for n, e in enumerate(table) if e and e[0] == "app" and e[1] == app["name"]]; free = [n for n, e in enumerate(table) if e is None or e[0] == "free"]
            if same: n = same[0]; j("an app named %r is in slot %d: it is updated" % (app["name"], n))
            elif free: n = free[0]
            else: raise L.Error("all %d slots are taken: remove one first" % SLOTS)
        else:
            n = a.slot; slot_path(n); e = table[n]
            if e and e[0] == "app" and e[1] != app["name"] and not a.force: raise L.Error("slot %d holds %r: use --force to overwrite it" % (n, e[1]))
        path = slot_path(n); j("plan      write %s (%d bytes), reconnect, read it back and compare" % (path, len(data)))
        F.pause(2.2); session("write", lambda link: write(link, data, path, j.trace)); F.pause(2.2)
        def verify(link):
            got = L.read_raw(link, path, limit=64 * 1024)
            if got != data: raise L.Error("the file on the watch differs from %s: NOT usable, try again" % a.file)
        session("verify", verify); j("installed %r in slot %d; it appears in the Application Hub the next time you open the hub" % (app["name"], n)); return 0
    except L.Error as e:
        j("ERROR: %s" % e); return 1
    except KeyboardInterrupt:
        j("\ninterrupted. A partly written slot is ignored by the hub (its CRC does not match); run the tool again."); return 130
    finally: j.close()


if __name__ == "__main__": sys.exit(main())
