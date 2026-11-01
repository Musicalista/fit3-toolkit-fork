# SPDX-License-Identifier: Apache-2.0
"""build_tennis.py: one command from *your* stock firmware package to a package that has the tennis score tracker in place of World clock.

    python3 -I tools/build_tennis.py <stock R390XXU0AZA3 package.bin> <out.bin> [--slot "World Clock"] [--label "Tennis Score"] [--languages en|all] [--no-icon] [--no-bluetooth-patches] | --list-slots

It compiles tools/loader/loader_v2.c (needs arm-none-eabi-gcc), draws the app-list icon (tools/assets/mkicon.py, needs numpy), and builds the package with
tools/firmware/build_package.py (Bluetooth serial patches, the take-over of the World clock window, the list label, the icon; every checksum repaired; the result is validated).
Nothing of Samsung's or anybody else's is stored in this repository: you bring the stock package. Read docs/legal.md first, and keep the stock package at hand to flash back."""
import argparse, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
for d in ("loader", "assets", "firmware"): sys.path.insert(0, os.path.join(HERE, d))
import build_loader, mkicon, build_package, fwd


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("stock"); ap.add_argument("out", nargs="?")
    ap.add_argument("--label", default="Tennis Score", help="name in the app list (replaces the entry's name; longer than 11 characters wraps onto two lines)")
    ap.add_argument("--slot", default="World Clock", help="the app-list entry to replace, by name or window id (default World Clock; --list-slots)")
    ap.add_argument("--list-slots", action="store_true", help="show the entries of the app list that can be replaced and exit")
    ap.add_argument("--force-slot", action="store_true", help="allow Settings (it would lock you out of the settings: do not)")
    ap.add_argument("--languages", choices=("en", "all"), default="en", help="rename the entry in the English files only, or in every language file (untested outside English)")
    ap.add_argument("--no-icon", action="store_true", help="keep the stock icon")
    ap.add_argument("--no-bluetooth-patches", action="store_true", help="leave the watch's Bluetooth as stock: nobody in range can connect, and you cannot flash it from here again without a reset (use for the final package)")
    a = ap.parse_args()
    if a.list_slots: sys.exit(subprocess.call([sys.executable, "-I", os.path.join(HERE, "firmware", "build_package.py"), a.stock, "--list-slots"]))
    if not a.out: ap.error("out is required")
    p = fwd.Package.load(a.stock); raw = build_package.check_stock(p); en = next(build_package.lvlang.Lang(p.raw(k)) for k in p.paths() if k.endswith("/language_en.res"))
    sl = build_package.find_slot(build_package.slot_table(raw, en), a.slot)
    work = tempfile.mkdtemp(prefix="tennis_"); loader = os.path.join(work, "loader.bin")
    syms = build_loader.build(os.path.join(HERE, "loader", "loader_v2.c"), loader, quiet=True, defines=["WINDOW_ID=%#x" % sl["window"]])
    icon = None if a.no_icon else mkicon.encode(*mkicon.draw())
    build_package.build(a.stock, a.out, open(loader, "rb").read(), label=a.label, icon=icon, slot=sl["window"], languages=a.languages, force_slot=a.force_slot, bluetooth_patches=not a.no_bluetooth_patches,
                        takeover={"create": syms["world_create"] | 1, "event": syms["world_event"] | 1})
    print("done:", a.out, "(replaces %s)" % sl["name"])


if __name__ == "__main__":
    main()
