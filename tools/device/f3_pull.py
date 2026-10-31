# SPDX-License-Identifier: Apache-2.0
"""f3_pull.py: copy read-only assets (fonts, images) from the watch to this PC for inspection. Nothing is written to the watch.
    python3 f3_pull.py <out_dir> /nand/system/image/app_worldclock.res [more paths] [--limit BYTES]
Only paths under /nand/system/font/ and /nand/system/image/ are accepted. The files are Samsung's: keep them local, do not redistribute."""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))     # python3 -I does not add the script's folder
import f3_link as F

ALLOWED = ("/nand/system/font/", "/nand/system/image/")
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("paths", nargs="+"); ap.add_argument("--limit", type=int, default=2 << 20); ap.add_argument("--addr", default=F.ADDR); a = ap.parse_args()
for p in a.paths:
    if not p.startswith(ALLOWED) or ".." in p or p.endswith("/"): sys.exit("refusing %r (only %s)" % (p, ", ".join(ALLOWED)))
os.makedirs(a.out, exist_ok=True)
for p in a.paths:
    t0 = time.time(); last = [0]
    def prog(done, total):
        if done == total or time.time() - last[0] > 3: last[0] = time.time(); print("  %s %d/%d B (%.0f%%)" % (os.path.basename(p), done, total, 100 * done / total), flush=True)
    try:
        link = F.open_link(a.addr)
        try: data = F.read_raw(link, p, a.limit, prog)
        finally: link.close()
    except F.Error as e: print("SKIP %s: %s" % (p, e)); continue
    if data is None: print("MISSING", p); continue
    open(os.path.join(a.out, os.path.basename(p)), "wb").write(data); print("OK %s %d bytes in %.1f s" % (p, len(data), time.time() - t0)); time.sleep(3)
