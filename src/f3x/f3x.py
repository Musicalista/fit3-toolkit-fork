# SPDX-License-Identifier: Apache-2.0
"""f3x.py: the .f3x installable app format (docs/f3x.md): build an app from C source, pack it, read it back, validate it.

An app is one C file (see src/watch/apps/counter.c) compiled freestanding for the watch's Cortex-M4 and linked twice, at F3X_LINK_BASE and at another base. The words that differ by exactly the
difference of the bases are the addresses that point inside the image: they are the relocation list. The hub on the watch adds the real address of the image to each of them. Calls into the
firmware are absolute constants (the same in both links) and need nothing. Needs arm-none-eabi-gcc/ld/objcopy/nm/size on the PATH; numpy for the icon."""
import os, re, struct, subprocess, sys, tempfile, zlib
HERE = os.path.dirname(os.path.abspath(__file__)); WATCH = os.path.join(os.path.dirname(HERE), "watch"); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "assets")); sys.path.insert(0, WATCH)

MAGIC = b"F3X1"; VERSION = 1
FW_ID = zlib.crc32(b"R390XXU0AZA3") & 0xffffffff                       # the firmware whose addresses the image calls (ui.h F3X_FW)
LINK_BASE, OTHER_BASE = 0x40000000, 0x50000000
ICON_SIZE = 64 * 32 + 64                                               # four-bit 64 x 64 with its 16-entry palette: 2,112 bytes
HEADER = struct.Struct("<4sHHIIIII24s12s")                             # magic, version, flags, fw_id, image_size, app_off, reloc_len, crc, name, reserved: 64 bytes
MAX_IMAGE, MAX_RELOC, SLOTS = 0x8000, 0x2000, 16
assert HEADER.size == 64


class Error(Exception): pass


def _run(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    if r.returncode: raise Error("%s failed:\n%s%s" % (" ".join(a[:2]), r.stdout, r.stderr))
    return r.stdout


def varints(offsets):
    """word offsets (bytes, multiples of 4, ascending) -> delta varints in words"""
    out = bytearray(); prev = 0
    for o in offsets:
        assert o % 4 == 0 and o >= prev, o
        v = (o - prev) // 4; prev = o
        while True:
            b = v & 0x7f; v >>= 7
            out.append(b | (0x80 if v else 0))
            if not v: break
    return bytes(out)


def unvarints(data):
    out = []; pos = 0; i = 0
    while i < len(data):
        v = sh = 0
        while True:
            if i >= len(data) or sh > 28: raise Error("damaged relocation list")
            b = data[i]; i += 1; v |= (b & 0x7f) << sh; sh += 7
            if not b & 0x80: break
        pos += v * 4; out.append(pos)
    return out


def _link(obj, base, workdir, tag):
    ld = os.path.join(workdir, "app_%s.ld" % tag); elf = os.path.join(workdir, "app_%s.elf" % tag); binf = os.path.join(workdir, "app_%s.bin" % tag)
    open(ld, "w").write("SECTIONS { . = %#x; .text : { *(.text .text.* .rodata .rodata.*) . = ALIGN(4); } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) *(.ARM.attributes) } }\n" % base)
    _run("arm-none-eabi-ld", "--gc-sections", "-u", "f3x_app", "-T", ld, "-o", elf, obj)
    und = _run("arm-none-eabi-nm", "-u", elf).strip()
    if und: raise Error("undefined symbols (the app may not call libc or libgcc; use the firmware's functions through ui.h): " + und.replace("\n", " "))
    for ln in _run("arm-none-eabi-size", "-A", elf).splitlines():
        p = ln.split()
        if len(p) >= 2 and p[0].startswith((".data", ".bss", ".noinit")) and int(p[1]): raise Error("the app must not have %s (%s bytes): keep state in the block you allocate" % (p[0], p[1]))
    _run("arm-none-eabi-objcopy", "-O", "binary", elf, binf)
    syms = {l.split()[2]: int(l.split()[0], 16) for l in _run("arm-none-eabi-nm", elf).splitlines() if len(l.split()) == 3}
    return open(binf, "rb").read(), syms


def compile_app(source, workdir=None, include_dirs=()):
    """C source -> (image linked at LINK_BASE, offset of f3x_app, relocation word offsets)"""
    wd = workdir or tempfile.mkdtemp(prefix="f3x_"); obj = os.path.join(wd, "app.o")
    _run("arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=soft", "-Os", "-Wall", "-Werror", "-ffreestanding", "-fno-builtin", "-fno-pic", "-fno-stack-protector", "-fno-exceptions",
         "-fno-tree-loop-distribute-patterns", "-ffunction-sections", "-fdata-sections", "-DF3X_BUILD", "-I" + WATCH, *("-I" + d for d in include_dirs), "-c", source, "-o", obj)
    a, sa = _link(obj, LINK_BASE, wd, "a"); b, sb = _link(obj, OTHER_BASE, wd, "b")
    if len(a) != len(b) or "f3x_app" not in sa: raise Error("the two links differ in size, or f3x_app is missing (the app must define it with APP_EXPORT)")
    if len(a) % 4 or len(a) > MAX_IMAGE: raise Error("the image is %d bytes (a multiple of 4, at most %d)" % (len(a), MAX_IMAGE))
    delta = OTHER_BASE - LINK_BASE; rel = []
    for i in range(0, len(a), 4):                                       # the image is a multiple of 4 bytes and every section is word aligned
        if a[i:i + 4] != b[i:i + 4]:
            if struct.unpack_from("<I", b, i)[0] - struct.unpack_from("<I", a, i)[0] != delta: raise Error("the word at offset %#x differs between the links by something other than the base: cannot relocate" % i)
            rel.append(i)
    if any(a[j] != b[j] for j in range(len(a)) if j // 4 * 4 not in set(rel)): raise Error("bytes differ between the links outside whole words")
    off = sa["f3x_app"] - LINK_BASE
    return a, off, rel


def pack(name, image, app_off, reloc_offsets, icon):
    """-> the bytes of the .f3x file. `icon` is the 2,112 bytes of mkicon.encode_indexed4(..., 64)"""
    try: nb = name.encode("ascii")
    except UnicodeEncodeError: raise Error("the name must be 1 to 23 printable ASCII characters")
    if not 1 <= len(nb) <= 23 or not all(32 <= c < 127 for c in nb): raise Error("the name must be 1 to 23 printable ASCII characters")
    if len(icon) != ICON_SIZE: raise Error("the icon must be %d bytes (64 x 64, four bits, 16-entry palette)" % ICON_SIZE)
    rel = varints(reloc_offsets)
    if len(rel) > MAX_RELOC or len(image) > MAX_IMAGE: raise Error("too large")
    body = icon + image + rel
    return HEADER.pack(MAGIC, VERSION, 0, FW_ID, len(image), app_off, len(rel), zlib.crc32(body) & 0xffffffff, nb.ljust(24, b"\0"), bytes(12)) + body


def parse(data):
    """-> dict(name, image, app_off, relocs, icon); raises Error when the file is not a valid .f3x for this firmware (the same checks the hub makes)"""
    if len(data) < HEADER.size: raise Error("too short")
    magic, ver, flags, fw, isz, aoff, rlen, crc, name, resv = HEADER.unpack_from(data)
    if magic != MAGIC or ver != VERSION or flags: raise Error("not an .f3x of version %d" % VERSION)
    if fw != FW_ID: raise Error("built for another firmware (id %08x, this tool: %08x = R390XXU0AZA3)" % (fw, FW_ID))
    if not (16 <= isz <= MAX_IMAGE and isz % 4 == 0 and rlen <= MAX_RELOC and aoff % 4 == 0 and aoff + 20 <= isz): raise Error("sizes out of range")
    if len(data) != HEADER.size + ICON_SIZE + isz + rlen: raise Error("the file is %d bytes, the header says %d" % (len(data), HEADER.size + ICON_SIZE + isz + rlen))
    body = data[HEADER.size:]
    if zlib.crc32(body) & 0xffffffff != crc: raise Error("CRC mismatch: the file is damaged")
    if name[23:24] != b"\0" or not name[:1].strip(b"\0"): raise Error("bad name")
    relocs = unvarints(body[ICON_SIZE + isz:])
    if any(o + 4 > isz for o in relocs): raise Error("a relocation points outside the image")
    return dict(name=name.rstrip(b"\0").decode("ascii"), icon=body[:ICON_SIZE], image=body[ICON_SIZE:ICON_SIZE + isz], app_off=aoff, relocs=relocs)


def default_name(source):
    m = re.search(r'APP_EXPORT\(\s*\w+\s*,\s*"([^"]+)"', open(source).read())
    return m.group(1) if m else None
