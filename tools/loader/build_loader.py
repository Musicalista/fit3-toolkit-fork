# SPDX-License-Identifier: Apache-2.0
"""build_loader.py: compile loader_vN.c into a flat binary for build_package.py (--loader), linked at 0x2c3a0524.

    python3 -I tools/loader/build_loader.py tools/loader/loader_v2.c local/loader/loader_v2.bin

The first function of the image is the entry (section .text.entry); the addresses of world_create and world_event (--takeover-create / --takeover-event of build_package.py) are printed. Refuses libc/libgcc calls, data and bss."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
def run(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    if r.returncode: sys.exit("FAILED: %s\n%s%s" % (" ".join(a[:2]), r.stdout, r.stderr))
    return r.stdout
def build(src, out, quiet=False, defines=()):
    d = tempfile.mkdtemp(prefix="f3loader_"); o, elf = os.path.join(d, "l.o"), os.path.join(d, "l.elf")
    run("arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=soft", "-Os", "-Wall", "-Werror", "-ffreestanding", "-fno-builtin", "-fno-pic", "-fno-stack-protector", "-fno-exceptions",
        "-fno-tree-loop-distribute-patterns", "-ffunction-sections", "-fdata-sections", *("-D" + d for d in defines), "-c", src, "-o", o)
    run("arm-none-eabi-ld", "--gc-sections", "-T", os.path.join(HERE, "loader.ld"), "-o", elf, o)
    und = run("arm-none-eabi-nm", "-u", elf).strip()
    if und: sys.exit("undefined symbols: " + und.replace("\n", " "))
    sizes = run("arm-none-eabi-size", "-A", elf)
    for ln in sizes.splitlines():
        p = ln.split()
        if len(p) >= 2 and p[0] in (".data", ".bss") and int(p[1]): sys.exit("the loader must not have %s (%s bytes): keep state in the heap" % (p[0], p[1]))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    run("arm-none-eabi-objcopy", "-O", "binary", elf, out)
    syms = {l.split()[2]: int(l.split()[0], 16) for l in run("arm-none-eabi-nm", elf).splitlines() if len(l.split()) == 3}
    if not quiet:
        print("wrote %s, %d bytes" % (out, os.path.getsize(out)))
        for name in ("world_create", "world_event"):
            if name in syms: print("  %s at %#x (Thumb address %#x)" % (name, syms[name] & ~1, syms[name] | 1))
    return syms
if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
