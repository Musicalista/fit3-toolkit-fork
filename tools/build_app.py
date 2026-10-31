# SPDX-License-Identifier: Apache-2.0
"""build_app.py <app>: build apps/<app>/ into build/<id>.f3a and build/<id>.meta with the SDK's appcc.py.
The SDK (Musicalista/fit3-store-apps-games) is an external checkout, by default ./fit3-store; override with F3_SDK=/path/to/its/apps.
apps/<app>/meta holds the launcher line "id;BGRRGGBB;FGRRGGBB;Name PT;Name EN" (the icon field is optional); apps/include is on the include path.
Needs arm-none-eabi-gcc (ARM_GNU_BIN, default /usr/bin)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SDK = os.environ.get("F3_SDK", os.path.join(ROOT, "fit3-store", "apps"))
os.environ.setdefault("ARM_GNU_BIN", "/usr/bin")
os.environ["CPATH"] = os.pathsep.join(filter(None, [os.path.join(ROOT, "apps", "include"), os.environ.get("CPATH", "")]))   # gcc picks this up from appcc's subprocess
sys.path.insert(0, SDK)
import appcc

def build(app):
    d = os.path.join(ROOT, "apps", app); fields = open(os.path.join(d, "meta"), encoding="utf-8").read().strip().split(";")
    app_id, bg, fg, pt, en = fields[:5]; out = os.path.join(ROOT, "build", app_id + ".f3a")
    n = appcc.build(os.path.join(d, app + ".c"), app_id, pt, en, out)
    open(out[:-4] + ".meta", "w", encoding="utf-8").write(";".join(fields) + "\n")
    print("%s: image %d B, bss %d B, %d relocations, file %d B" % (out, *n))

if __name__ == "__main__":
    for a in sys.argv[1:] or sys.exit(__doc__): build(a)
