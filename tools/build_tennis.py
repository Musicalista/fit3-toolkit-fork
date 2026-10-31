"""build_tennis.py: one command from *your* stock firmware package to a package that has the tennis score tracker in place of World clock.

    python3 -I tools/build_tennis.py <stock R390XXU0AZA3 package.bin> <out.bin> [--label "Tennis Score"] [--no-icon]

It compiles tools/loader/loader_v2.c (needs arm-none-eabi-gcc), draws the app-list icon (tools/assets/mkicon.py, needs numpy), and builds the package with
tools/firmware/build_package.py (Bluetooth serial patches, the take-over of the World clock window, the list label, the icon; every checksum repaired; the result is validated).
Nothing of Samsung's or anybody else's is stored in this repository: you bring the stock package. Read docs/legal.md first, and keep the stock package at hand to flash back."""
import argparse, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
for d in ("loader", "assets", "firmware"): sys.path.insert(0, os.path.join(HERE, d))
import build_loader, mkicon, build_package


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("stock"); ap.add_argument("out")
    ap.add_argument("--label", default="Tennis Score", help="name in the app list (replaces 'World Clock'; longer than 11 characters wraps onto two lines)")
    ap.add_argument("--no-icon", action="store_true", help="keep the stock globe icon")
    a = ap.parse_args()
    work = tempfile.mkdtemp(prefix="tennis_"); loader = os.path.join(work, "loader.bin")
    syms = build_loader.build(os.path.join(HERE, "loader", "loader_v2.c"), loader, quiet=True)
    icon = None if a.no_icon else mkicon.encode(*mkicon.draw())
    build_package.build(a.stock, a.out, open(loader, "rb").read(), label=a.label, icon=icon, takeover={"create": syms["world_create"] | 1, "event": syms["world_event"] | 1})
    print("done:", a.out)


if __name__ == "__main__":
    main()
