# SPDX-License-Identifier: Apache-2.0
"""build_tennis.py: one command from *your* stock firmware package to a package that has our watch code in place of World clock (or another app-list entry).

    python3 -I src/build_tennis.py <stock R390XXU0AZA3 package.bin> <out.bin> [--app tennis | --hub tennis,counter,dice] [--slot "World Clock"] [--label "..."] [--languages en|all] [--no-icon] [--no-bluetooth-patches] | --list-slots

`--app NAME` makes the entry that one app (default: tennis); `--hub A,B,C` makes it the Application Hub, a native-style list that opens the apps (src/watch/README.md; apps: tennis, counter, dice).
It compiles src/watch/hub.c with the chosen apps (needs arm-none-eabi-gcc), draws the app-list icon (src/assets/mkicon.py, needs numpy), and builds the package with
src/firmware/build_package.py (Bluetooth serial patches, the take-over of the window, the list label, the icon; every checksum repaired; the result is validated) and prints how much of the free flash it uses.
Nothing of Samsung's or anybody else's is stored in this repository: you bring the stock package. Read docs/legal.md first, and keep the stock package at hand to flash back."""
import argparse, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
for d in ("watch", "assets", "firmware"): sys.path.insert(0, os.path.join(HERE, d))
import build_loader, gen, mkicon, build_package, fwd


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("stock"); ap.add_argument("out", nargs="?")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--app", choices=sorted(gen.APPS), help="one app owns the window (default: tennis)")
    g.add_argument("--hub", help="comma-separated apps, in the order of the list: the window becomes the Application Hub (e.g. tennis,counter,dice)")
    ap.add_argument("--label", help="name in the app list (replaces the entry's name; longer than 11 characters wraps onto two lines). Default: the app's name, or Application Hub")
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
    hub = a.hub is not None; apps = [x.strip() for x in a.hub.split(",")] if hub else [a.app or "tennis"]
    work = tempfile.mkdtemp(prefix="tennis_"); loader = os.path.join(work, "loader.bin")
    syms = build_loader.build(os.path.join(HERE, "watch", "hub.c"), loader, quiet=True, defines=["WINDOW_ID=%#x" % sl["window"]], include_dirs=[gen.generate(apps, hub, os.path.join(work, "gen"))])
    label = a.label or ("Application Hub" if hub else {"tennis": "Tennis Score", "counter": "Counter", "dice": "Dice"}[apps[0]])
    icon = None if a.no_icon else mkicon.encode(*mkicon.draw("hub" if hub else apps[0]))
    build_package.build(a.stock, a.out, open(loader, "rb").read(), label=label, icon=icon, slot=sl["window"], languages=a.languages, force_slot=a.force_slot, bluetooth_patches=not a.no_bluetooth_patches,
                        takeover={"create": syms["world_create"] | 1, "event": syms["world_event"] | 1})
    size = len(open(loader, "rb").read()); free = build_package.FREE_END - build_package.FREE_START; used = size + (16 + len(icon) + 15 if icon else 0)
    print("done:", a.out, "(%s replaces %s)" % ("hub of " + ", ".join(apps) if hub else apps[0], sl["name"]))
    print("free flash: %d of %d bytes used (code and app icons %d, app-list icon %d), %d left" % (used, free, size, used - size, free - used))


if __name__ == "__main__":
    main()
