# SPDX-License-Identifier: Apache-2.0
"""gbtest_rom.py: a 32 KB Game Boy ROM written by hand for the tests of src/watch/apps/gameboy.c (our own bytes, no game). It draws vertical stripes: a background of
tiles 0 and 1 alternating, tile 1 having its left four columns in shade 3, then loops. Tile 2 (all shade 3) is drawn at map column 0 while the A button is held."""

def rom(save=False):
    """save: an MBC1 cartridge with 8 KB of RAM (types 0x03, RAM code 2) whose code writes 0x42 to the first byte of that RAM before the loop"""
    r = bytearray(0x8000)
    r[0x100:0x104] = bytes.fromhex("00c35001")                                  # nop; jp 0x0150
    r[0x134:0x13c] = b"F3XTEST\0"
    code = bytes.fromhex(
        "f3" "af" "e040"                                                         # di; xor a; ldh (LCDC),a: LCD off
        "211080" "0610" "3ef0" "22" "05" "20fa"                                  # tile 1: 16 bytes of 0xf0 (left half shade 3)
        "2120800610" "3eff" "22" "05" "20fa"                                     # tile 2: 16 bytes of 0xff (shade 3)
        "210098" "010004" "7d" "e601" "22" "0b" "78" "b1" "20f7"                 # map 0x9800: tile (l & 1)
        "3ee4" "e047" "3e91" "e040"                                              # BGP = 0xe4; LCDC = 0x91 (on, BG, tiles at 0x8000)
        + ("3e0a" "ea0000" "3e42" "ea00a0" if save else "") +                   # save: enable the cartridge RAM, write 0x42 at 0xa000
        # loop: read the buttons (P1 = 0x10 selects them), bit 0 = A (0 when pressed): map[0] = pressed ? 2 : 0
        "3e10" "e000" "f000" "e601" "2004" "3e02" "1801" "af" "ea0098" "18ec")
    r[0x150:0x150 + len(code)] = code
    if save: r[0x147], r[0x149] = 0x03, 0x02
    x = 0
    for i in range(0x134, 0x14d): x = (x - r[i] - 1) & 0xff
    r[0x14d] = x
    return bytes(r)

if __name__ == "__main__":
    import sys; open(sys.argv[1], "wb").write(rom())
