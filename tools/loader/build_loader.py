"""build_loader.py: compile loader_vN.c into a flat binary for build_package.py (--loader), linked at 0x2c3a0524.

    python3 -I tools/loader/build_loader.py tools/loader/loader_v0.c local/loader/loader_v0.bin

The first function of the image is the entry (section .text.entry), so the callback to pass as --menu-callback is 0x2c3a0525. Refuses libc/libgcc calls, data and bss."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
def run(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    if r.returncode: sys.exit("FAILED: %s\n%s%s" % (" ".join(a[:2]), r.stdout, r.stderr))
    return r.stdout
def build(src, out):
    d = tempfile.mkdtemp(prefix="f3loader_"); o, elf = os.path.join(d, "l.o"), os.path.join(d, "l.elf")
    run("arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=soft", "-Os", "-Wall", "-Werror", "-ffreestanding", "-fno-builtin", "-fno-pic", "-fno-stack-protector", "-fno-exceptions",
        "-fno-tree-loop-distribute-patterns", "-ffunction-sections", "-fdata-sections", "-c", src, "-o", o)
    run("arm-none-eabi-ld", "--gc-sections", "-T", os.path.join(HERE, "loader.ld"), "-o", elf, o)
    und = run("arm-none-eabi-nm", "-u", elf).strip()
    if und: sys.exit("undefined symbols: " + und.replace("\n", " "))
    sizes = run("arm-none-eabi-size", "-A", elf)
    for ln in sizes.splitlines():
        p = ln.split()
        if len(p) >= 2 and p[0] in (".data", ".bss") and int(p[1]): sys.exit("the loader must not have %s (%s bytes): keep state in the heap" % (p[0], p[1]))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    run("arm-none-eabi-objcopy", "-O", "binary", elf, out)
    entry = [int(l.split()[0], 16) for l in run("arm-none-eabi-nm", elf).splitlines() if l.endswith(" loader_entry")][0]
    print("wrote %s, %d bytes; loader_entry at %#x (--menu-callback %#x)" % (out, os.path.getsize(out), entry & ~1, entry | 1))
if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
