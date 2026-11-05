// SPDX-License-Identifier: Apache-2.0
package org.fit3.manager;

import java.nio.charset.StandardCharsets;

/** A Game Boy ROM for the watch's Game Boy app (src/watch/apps/gameboy.c): the checks that app makes when it loads /user/gb/rom.gb. */
final class GbRom {
    static final String PATH = "/user/gb/rom.gb";
    static final int MAX = 1024 * 1024;                                  // the watch app reads the whole ROM into memory

    final String title; final int size;
    private GbRom(String title, int size) { this.title = title; this.size = size; }

    static GbRom parse(byte[] d) throws F3x.Invalid {
        if (d == null || d.length < 0x150) throw new F3x.Invalid("too short for a Game Boy ROM");
        int code = d[0x148] & 0xff;
        if (code > 5) throw new F3x.Invalid("ROM size code " + code + " is not supported (at most 1 MB)");
        int size = 0x8000 << code;
        if (d.length != size) throw new F3x.Invalid("the file is " + d.length + " bytes, its header says " + size);
        int x = 0; for (int i = 0x134; i <= 0x14c; i++) x = (x - (d[i] & 0xff) - 1) & 0xff;
        if (x != (d[0x14d] & 0xff)) throw new F3x.Invalid("bad header checksum: not a Game Boy ROM");
        if ((d[0x143] & 0xff) == 0xc0) throw new F3x.Invalid("a Game Boy Color-only game (the watch app emulates the original Game Boy)");
        int n = 0; while (n < 16 && d[0x134 + n] >= 0x20 && d[0x134 + n] < 0x7f) n++;
        String t = new String(d, 0x134, n, StandardCharsets.US_ASCII).trim();
        return new GbRom(t.isEmpty() ? "Game Boy ROM" : t, size);
    }
}
