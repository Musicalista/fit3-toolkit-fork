# SPDX-License-Identifier: Apache-2.0
"""build_f3x.py: C source of an app -> an installable .f3x file.

    python3 -I src/f3x/build_f3x.py src/watch/apps/counter.c local/f3x/counter.f3x [--name "Counter"] [--icon-kind counter | --icon my64x64.png]
    python3 -I src/f3x/build_f3x.py --check local/f3x/counter.f3x          # validate a file and show what is in it

The source must include "ui.h" and export the app with APP_EXPORT (docs/f3x.md). The name defaults to the one in APP_EXPORT; the icon is one of the drawn kinds (src/assets/mkicon.py) or a 64 x 64
PNG with transparency (reduced to 15 colours + transparent). Nothing is sent to a watch: src/device/f3x_install.py does that."""
import argparse, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import f3x, mkicon, gen


def png_icon(path):
    import numpy as np
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    if im.size != (64, 64): raise f3x.Error("the icon must be 64 x 64 pixels, it is %d x %d" % im.size)
    a = np.asarray(im).astype(int); return mkicon.encode_indexed4(a[..., :3], a[..., 3])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("source"); ap.add_argument("out", nargs="?")
    ap.add_argument("--name"); g = ap.add_mutually_exclusive_group(); g.add_argument("--icon-kind", choices=sorted(mkicon.KINDS)); g.add_argument("--icon", help="64 x 64 PNG")
    ap.add_argument("--check", action="store_true", help="source is a .f3x file: validate it and print its content")
    a = ap.parse_args(argv)
    try:
        if a.check:
            d = f3x.parse(open(a.source, "rb").read()); print("%s: name %r, image %d bytes, %d relocations, app struct at +%#x, icon ok" % (a.source, d["name"], len(d["image"]), len(d["relocs"]), d["app_off"])); return 0
        if not a.out: ap.error("out is required")
        name = a.name or f3x.default_name(a.source)
        if not name: ap.error("no --name and no APP_EXPORT with a name found")
        wd = tempfile.mkdtemp(prefix="f3x_")
        image, off, rel = f3x.compile_app(a.source, wd, [gen.generate(list(gen.APPS), False, os.path.join(wd, "gen"))])
        icon = png_icon(a.icon) if a.icon else mkicon.encode_indexed4(*mkicon.draw(a.icon_kind or "hub", 64))
        data = f3x.pack(name, image, off, rel, icon); os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True); open(a.out, "wb").write(data)
        print("wrote %s: %r, %d bytes (image %d, %d relocations)" % (a.out, name, len(data), len(image), len(rel))); return 0
    except f3x.Error as e:
        print("error:", e, file=sys.stderr); return 1


if __name__ == "__main__": sys.exit(main())
