# SPDX-License-Identifier: Apache-2.0
"""build_app.py <app>: build apps/<app>/ into build/<id>.f3a and build/<id>.meta with tools/appcc.py and the SDK in sdk/ (nothing outside this repository is read).
apps/<app>/meta holds the launcher line "id;BGRRGGBB;FGRRGGBB;Name PT;Name EN" (the icon field is optional); apps/include is on the include path.
Needs arm-none-eabi-gcc and ld (ARM_GNU_BIN = their directory, default /usr/bin)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ARM_GNU_BIN", "/usr/bin")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import appcc

def build(app):
    d = os.path.join(ROOT, "apps", app); fields = open(os.path.join(d, "meta"), encoding="utf-8").read().strip().split(";")
    app_id = fields[0]; pt, en = fields[3], fields[4]; out = os.path.join(ROOT, "build", app_id + ".f3a")
    n = appcc.build(os.path.join(d, app + ".c"), app_id, pt, en, out, [os.path.join(ROOT, "apps", "include")])
    open(out[:-4] + ".meta", "w", encoding="utf-8").write(";".join(fields) + "\n")
    print("%s: image %d B, bss %d B, %d relocations, file %d B" % (out, *n))

if __name__ == "__main__":
    for a in sys.argv[1:] or sys.exit(__doc__): build(a)
