# SPDX-License-Identifier: Apache-2.0
"""screenshot_kbd.py: render the page of quick replies with our extra row and the reply keyboard (src/watch/kbd.c) with the firmware's own LVGL, to PNG files.

    python3 -I src/build_firmware.py local/firmware/stock-aza3.bin local/firmware/fit3-hub-reply.bin --hub counter,dice --reply-keyboard --kb-lang pl,en,pt,de,fr,tr
    python3 -I src/firmware/fwx.py local/firmware/fit3-hub-reply.bin main local/re/main-reply.bin
    local/venv/bin/python -I src/emu/screenshot_kbd.py <outdir> [--fonts local/assets/fonts]

Same limits as screenshot.py: no real display or touch; the stock page builder runs with stand-ins for the text-id lookup and the font proxy. The Samsung fonts come from your own pulled files."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
from probe_lvgl import A
from rig import bl_target, CLICKED
from screenshot import Screen, children, FONT_DIR

SITE, KB_ID = 0x2c1d2598, 0x9c
REC = 0x200fb4e4 + KB_ID * 0x30


def label_text(e, o):
    for c in children(e, o):
        if e.u32(c) == 0x2c388a94: return e.cstr(e.u32(c + 0x2c), 64).encode("latin1").decode("utf-8", "replace")
    return ""


def main(argv):
    out = argv[0] if argv and not argv[0].startswith("--") else "build/shots"; fonts = argv[argv.index("--fonts") + 1] if "--fonts" in argv else FONT_DIR
    image = os.path.join(ROOT, os.environ.get("F3_REPLY_IMAGE", "local/re/main-reply.bin")); os.makedirs(out, exist_ok=True)
    s = Screen(image, fonts); e = s.e; s.seed_txt(); font = s.load_fonts()[8]
    replies = ["Yes", "No thanks", "On my way"]
    e.hook(0x2c0ec1bc, lambda em: len(replies)); e.hook(0x2c0ec194, lambda em: (em.write(em.arg(0) + 1, replies[em.arg(2)].encode() + b"\0"), 1)[1])
    e.hook(0x2c213a90, lambda em: font); e.hook(0x2c2138cc, lambda em: e.put_cstr("No quick replies")); 
    e.hook(0x2c0ed1f8, lambda em: e.w32(em.arg(0) + 0x124, 0x1234) and 0); e.hook(0x2c112f58, lambda em: 1); e.hook(0x2c0e6ef4, lambda em: 1)
    hook = bl_target(open(image, "rb").read(), SITE)
    def shot(scr, name):                                                              # a whole new frame: the drawing is invalidated first, so the double buffer is complete
        e.call(0x2c2782a8, scr); s.tick += 30; e.call(0x2c28a46c, max_insns=4_000_000_000); s.png(os.path.join(out, name + ".png")); print("wrote", name)
    click = lambda o: e.call(A["event_send"], o, CLICKED, 0, max_insns=900_000_000)
    # the page of quick replies as the stock builder and our hook make it
    page = e.call(A["obj_create"], 0); e.w32(0x201160a0, page); e.w32(0x2011609c, len(replies)); e.call(hook)
    # the emulator has no theme: a plain lv_obj would be transparent, on the watch the theme gives it an opaque background and no border. Do the same for the stock rows (ours set them themselves).
    for row in children(e, children(e, page)[0]):
        if e.u32(row) == 0x2c32ae74 and e.u32(row + 8): e.call(0x2c27d55c, row, 255, 0); e.call(0x2c27d5ae, row, 0, 0)
    s.show(page); shot(page, "reply-page")
    click(children(e, children(e, page)[0])[-1])                                      # a tap on our row registers the window record (the hooked wm_open does nothing here)
    blk = e.alloc(8); e.w32(blk, 0x3159424b); e.w32(blk + 4, 0x1234)
    kb = e.call(e.u32(REC + 0x1c) & ~1, blk, max_insns=2_000_000_000); s.show(kb)
    pad = children(e, kb)[4]; keys = lambda: {label_text(e, k): k for k in children(e, pad)}
    shot(kb, "kbd-empty")
    for c in "Hello wlasnie": click(keys()[c] if c in keys() else keys()[c.lower()])
    shot(kb, "kbd-typing")
    click(keys()["ąć"]); shot(kb, "kbd-polish")
    click(keys()["ab"]); shot(kb, "kbd-polish-caps"); click(keys()["abc"]); click(keys()["123"]); shot(kb, "kbd-symbols"); click(keys()["abc"])
    click([c for c in children(e, kb) if label_text(e, c) == "QWE"][0]); shot(kb, "kbd-multitap")
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
