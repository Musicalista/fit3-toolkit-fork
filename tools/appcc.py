# SPDX-License-Identifier: Apache-2.0
"""appcc.py: compile one C file into a Fit3 light app (.f3a), see sdk/README.md for the file format.

    python3 -I tools/appcc.py apps/tenis/tenis.c --id tenis --pt "Tenis" --en "Tennis" [--bg RRGGBB --fg RRGGBB] [-I dir] [-o build/tenis.f3a]

Pipeline: arm-none-eabi-gcc (freestanding Cortex-M4 Thumb, absolute word relocations) -> ld with sdk/app.ld (flat image at address 0, bss after it)
-> this script reads the linked ELF itself, collects the words that hold absolute addresses, and writes header + image + relocation table.
Environment: ARM_GNU_BIN = directory of the arm-none-eabi-* tools (default: look them up on PATH). CPATH is honoured by gcc as usual."""
import argparse, os, struct, subprocess, sys, tempfile, zlib

SDK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sdk")
MAX_IMAGE = 40000                         # bytes the loader is willing to take
NAME_LEN = 16
HEADER_LEN = 64

# ELF constants (32-bit little endian, EM_ARM)
SHT_PROGBITS, SHT_SYMTAB, SHT_REL, SHF_ALLOC = 1, 2, 9, 2
ABS_RELOCS = {2: "R_ARM_ABS32", 38: "R_ARM_TARGET1"}                       # words the loader must patch
PCREL_RELOCS = {10: "R_ARM_THM_CALL", 30: "R_ARM_THM_JUMP24", 102: "R_ARM_THM_JUMP11", 103: "R_ARM_THM_JUMP8", 11: "R_ARM_THM_PC8",
                53: "R_ARM_THM_PC12", 3: "R_ARM_REL32", 51: "R_ARM_THM_JUMP19", 40: "R_ARM_V4BX"}   # position independent, nothing to patch

CFLAGS = ["-mcpu=cortex-m4", "-mfpu=fpv4-sp-d16", "-mfloat-abi=hard", "-mthumb", "-Os", "-ffreestanding", "-fno-builtin", "-fno-tree-loop-distribute-patterns",
          "-fno-stack-protector", "-finput-charset=UTF-8", "-fexec-charset=ISO-8859-1", "-mword-relocations", "-fno-pic", "-fno-exceptions",
          "-ffunction-sections", "-fdata-sections"]

def tool(name):
    return os.path.join(os.environ.get("ARM_GNU_BIN", ""), "arm-none-eabi-" + name)

def run(argv):
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode:
        sys.exit("FAILED: %s\n%s%s" % (" ".join(argv[:3]), r.stdout, r.stderr))

def read_elf(path):
    """returns (sections, symbols): sections = list of dicts, symbols = {name: (value, shndx)}"""
    d = open(path, "rb").read()
    if d[:4] != b"\x7fELF" or d[4] != 1 or d[5] != 1:
        sys.exit("linker output is not a 32-bit little-endian ELF")
    shoff, = struct.unpack_from("<I", d, 32); shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 46)
    raw = [struct.unpack_from("<10I", d, shoff + i * shentsize) for i in range(shnum)]
    secs = [dict(name_off=r[0], type=r[1], flags=r[2], addr=r[3], off=r[4], size=r[5], link=r[6], info=r[7], entsize=r[9]) for r in raw]
    def cstr(tab, o):
        e = d.index(b"\0", tab + o); return d[tab + o:e].decode("latin-1")
    names_at = secs[shstrndx]["off"]
    for s in secs:
        s["name"] = cstr(names_at, s["name_off"]); s["data"] = d[s["off"]:s["off"] + s["size"]] if s["type"] != 8 else b""
    syms = {}
    for s in secs:
        if s["type"] != SHT_SYMTAB: continue
        strtab = secs[s["link"]]["off"]
        for i in range(1, s["size"] // 16):
            nm, val, _sz, _info, _oth, shndx = struct.unpack_from("<IIIBBH", d, s["off"] + i * 16)
            if nm: syms[cstr(strtab, nm)] = (val, shndx)
    return secs, syms

def build(src, app_id, name_pt, name_en, out, includes=()):
    work = tempfile.mkdtemp(prefix="f3a_"); obj = os.path.join(work, "app.o"); elf = os.path.join(work, "app.elf")
    inc = [a for d in (SDK,) + tuple(includes) for a in ("-I", d)]
    run([tool("gcc")] + CFLAGS + inc + ["-c", src, "-o", obj])
    run([tool("ld"), "-q", "--gc-sections", "-T", os.path.join(SDK, "app.ld"), "-o", elf, obj])
    secs, syms = read_elf(elf)

    missing = sorted(n for n, (_, shndx) in syms.items() if shndx == 0)
    if missing:
        sys.exit("undefined symbols (no libc on the watch: avoid memset/memcpy/division helpers; use F3Api): " + " ".join(missing))
    for need in ("f3app_main", "__image_end", "__bss_end"):
        if need not in syms: sys.exit("the app must define f3app_main()" if need == "f3app_main" else "linker script lacks " + need)
    image_end, bss_end = syms["__image_end"][0], syms["__bss_end"][0]
    entry = syms["f3app_main"][0] & ~1                                      # drop the Thumb bit

    image = bytearray(image_end)                                            # code, rodata and data laid out at their link addresses; gaps stay zero
    for s in secs:
        if s["name"] in (".text", ".data") and s["type"] == SHT_PROGBITS and s["flags"] & SHF_ALLOC:
            image[s["addr"]:s["addr"] + s["size"]] = s["data"]

    relocs = []
    for s in secs:
        if s["type"] != SHT_REL: continue
        target = secs[s["info"]]["name"]
        if target not in (".text", ".data"): continue
        for i in range(s["size"] // 8):
            off, info = struct.unpack_from("<II", s["data"], i * 8); kind = info & 0xff
            if kind in ABS_RELOCS: relocs.append(off)
            elif kind not in PCREL_RELOCS:
                sys.exit("unsupported relocation type %d at 0x%x in %s (call only functions of this file or of F3Api; avoid libc/libgcc helpers)" % (kind, off, target))
    relocs.sort()
    for r in relocs:
        if r % 4 or r + 4 > len(image): sys.exit("misaligned or out-of-range relocation at 0x%x" % r)
    if len(image) > MAX_IMAGE: sys.exit("app too big (%d bytes, max %d)" % (len(image), MAX_IMAGE))

    def name(s): return s.encode("latin-1", "replace")[:NAME_LEN - 1].ljust(NAME_LEN, b"\0")
    image = bytes(image)
    header = struct.pack("<4sHHIIIIII", b"F3A1", 1, 0, len(image), bss_end - image_end, entry, zlib.crc32(image) & 0xffffffff, len(relocs), 0) + name(name_pt) + name(name_en)
    assert len(header) == HEADER_LEN
    blob = header + image + b"".join(struct.pack("<I", r) for r in relocs)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "wb") as f: f.write(blob)
    return len(image), bss_end - image_end, len(relocs), len(blob)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src"); ap.add_argument("--id", required=True); ap.add_argument("--pt", required=True); ap.add_argument("--en", required=True)
    ap.add_argument("--bg", default="B0D4F8"); ap.add_argument("--fg", default="305AAC"); ap.add_argument("-I", action="append", default=[], dest="inc"); ap.add_argument("-o")
    a = ap.parse_args(); out = a.o or os.path.join("build", a.id + ".f3a")
    n = build(a.src, a.id, a.pt, a.en, out, a.inc)
    with open(os.path.splitext(out)[0] + ".meta", "w", encoding="utf-8") as f: f.write("%s;%s;%s;%s;%s\n" % (a.id, a.bg.upper(), a.fg.upper(), a.pt, a.en))
    print("%s: image %d B, bss %d B, %d relocations, file %d B" % (out, *n))
