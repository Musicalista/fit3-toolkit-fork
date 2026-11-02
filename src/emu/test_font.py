# SPDX-License-Identifier: Apache-2.0
"""test_font.py: the fonts made by src/assets/mkfont.py (Roboto Medium, sizes 20 and 24) drawn by the firmware's own LVGL in the emulator, and saved as a PNG.

    local/venv/bin/python -I src/emu/test_font.py [outdir]            # default outdir: build/font; needs local/re/main-stock.bin, the TTF, arm-none-eabi-gcc

A C file that includes ui.h and the generated headers is compiled (flags of src/watch/build_loader.py), linked at 0x20300000 (the headers hold absolute pointers) and loaded into emulator RAM;
its build() puts labels on a screen, and LVGL renders them through lv_font_get_glyph_dsc_fmt_txt / lv_font_get_bitmap_fmt_txt of the firmware. Checks: the glyph metrics the firmware reports
(line_height, adv of 'M' and 'i') match the generator; the picture then has to be looked at (it is written, not compared)."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "src/assets"))
import mkfont
TTF = os.environ.get("F3_KB_TTF") or subprocess.run(["fc-match", "-f", "%{file}", "Roboto:medium"], capture_output=True, text=True).stdout; IMG = os.path.join(ROOT, "local/re/main-stock.bin"); BASE = 0x20300000
TEXT = "Zażółć gęślą jaźń ĄĆĘŁŃÓŚŹŻ 0123 abc"

C = r'''#include "ui.h"
#include "kb20.h"
#include "kb24.h"
__attribute__((section(".text.entry"))) void build(lv_obj_t *scr) {
    set_bg_color(scr, 0); set_bg_opa(scr, 255);
    const char *t = "%s";
    const lv_font_t *fs[2] = { &FONT_KB20, &FONT_KB24 };
    for (int i = 0; i < 2; i++) {
        lv_obj_t *l = lv_label_create(scr); lv_obj_set_pos(l, 4, 6 + i * 120); lv_obj_set_width(l, 248);
        set_text_color(l, 0xffff); lv_label_set_text(l, t); set_text_font(l, fs[i]);
        lv_obj_t *m = lv_label_create(scr); lv_obj_set_pos(m, 4, 90 + i * 120); lv_obj_set_width(m, 248);
        set_text_color(m, 0xffe0); lv_label_set_text(m, "MiMi QWERTY asdf ,.;:!?@#"); set_text_font(m, fs[i]);
    }
}
'''
LD = "MEMORY { R (rwx) : ORIGIN = 0x%x, LENGTH = 0x40000 }\nSECTIONS { .text : { KEEP(*(.text.entry)) *(.text .text.*) *(.rodata .rodata.*) . = ALIGN(4); } > R /DISCARD/ : { *(.ARM.exidx*) *(.comment) *(.ARM.attributes) } }\n" % BASE


def main(argv):
    out = argv[0] if argv else os.path.join(ROOT, "build/font")
    if not (os.path.exists(IMG) and os.path.exists(TTF)): print("SKIP: need local/re/main-stock.bin and", TTF); return 0
    from screenshot import Screen
    from probe_lvgl import A
    d = tempfile.mkdtemp(prefix="f3font_"); os.makedirs(out, exist_ok=True); fonts = {}
    for n in (20, 24):
        f = mkfont.build(TTF, n); open(os.path.join(d, "kb%d.h" % n), "w").write(mkfont.emit(f, "KB%d" % n)); fonts[n] = f
    open(os.path.join(d, "t.c"), "w").write(C % TEXT); open(os.path.join(d, "t.ld"), "w").write(LD)
    sh = lambda *a: subprocess.run(a, check=True, capture_output=True, text=True).stdout
    sh("arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=soft", "-Os", "-Wall", "-Werror", "-ffreestanding", "-fno-builtin", "-fno-pic", "-fno-stack-protector", "-fno-exceptions",
       "-ffunction-sections", "-fdata-sections", "-I" + os.path.join(ROOT, "src/watch"), "-I" + d, "-c", os.path.join(d, "t.c"), "-o", os.path.join(d, "t.o"))
    sh("arm-none-eabi-ld", "--gc-sections", "-T", os.path.join(d, "t.ld"), "-o", os.path.join(d, "t.elf"), os.path.join(d, "t.o"))
    sh("arm-none-eabi-objcopy", "-O", "binary", os.path.join(d, "t.elf"), os.path.join(d, "t.bin"))
    sizes = sh("arm-none-eabi-size", "-A", os.path.join(d, "t.elf")); print(sizes.strip().splitlines()[1])
    blob = open(os.path.join(d, "t.bin"), "rb").read()
    s = Screen(IMG, os.path.join(ROOT, "local/assets/fonts")); e = s.e; s.seed_txt()
    e.write_code(BASE, blob)
    scr = e.call(A["obj_create"], 0); e.call(BASE | 1, scr); s.show(scr)
    e.call(0x2c2782a8, scr); s.tick += 30; e.call(0x2c28a46c, max_insns=4_000_000_000)
    png = os.path.join(out, "kb-font.png"); s.png(png, 3); print("wrote", png)
    res = []
    for n in (20, 24):
        sym = int(sh("arm-none-eabi-nm", os.path.join(d, "t.elf")).split("FONT_KB%d" % n)[0].split()[-2], 16) if False else None
    nm = {l.split()[2]: int(l.split()[0], 16) for l in sh("arm-none-eabi-nm", os.path.join(d, "t.elf")).splitlines() if len(l.split()) == 3}
    dsc = e.alloc(16)
    for n in (20, 24):
        f = fonts[n]; font = nm.get("FONT_KB%d" % n)
        if font is None: font = [v for k, v in nm.items() if k.endswith("FONT_KB%d" % n)][0]
        ok = e.u32(font + 8) == f["ascent"] + f["descent"] and e.u32(font + 12) == f["descent"]
        res.append(ok); print("PASS" if ok else "FAIL", "KB%d line_height/base_line in the linked image: %d/%d" % (n, e.u32(font + 8), e.u32(font + 12)))
        for ch in "Mi":
            r = e.call(0x2c288d70, font, dsc, ord(ch), 0)                              # lv_font_get_glyph_dsc_fmt_txt(font, dsc, unicode, next)
            want = fonts[n]["glyphs"][fonts[n]["cps"].index(ord(ch)) + 1]
            got = e.read(dsc, 14); adv = int.from_bytes(got[4:6], "little"); bw = int.from_bytes(got[6:8], "little")
            ok = r == 1 and adv == (want["adv"] + 8) // 16 and bw == want["w"]; res.append(ok)
            print("PASS" if ok else "FAIL", "KB%d '%s' firmware adv %d px (generator %.2f), box_w %d" % (n, ch, adv, want["adv"] / 16, bw))
    return 0 if all(res) else 1

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
