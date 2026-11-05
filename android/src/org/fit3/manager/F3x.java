// SPDX-License-Identifier: Apache-2.0
package org.fit3.manager;

import android.graphics.Bitmap;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.zip.CRC32;

/** An .f3x app file (docs/f3x.md): the same checks as src/f3x/f3x.py parse() and the hub. */
final class F3x {
    static final int MAGIC = 0x31583346, VERSION = 1, FW_ID = 0xdf60a3cc, HEADER = 64, ICON_SIZE = 2112, MAX_IMAGE = 0x8000, MAX_RELOC = 0x2000, SLOTS = 16;
    static final byte[] TOMBSTONE = "F3X-GONE".getBytes(StandardCharsets.US_ASCII);

    final String name; final int size, imageSize; final byte[] icon;

    private F3x(String name, int size, int imageSize, byte[] icon) { this.name = name; this.size = size; this.imageSize = imageSize; this.icon = icon; }

    static final class Invalid extends Exception { Invalid(String m) { super(m); } }

    static F3x parse(byte[] d) throws Invalid {
        if (d == null || d.length < HEADER) throw new Invalid("too short");
        ByteBuffer b = ByteBuffer.wrap(d).order(ByteOrder.LITTLE_ENDIAN);
        int magic = b.getInt(0), ver = b.getShort(4) & 0xffff, flags = b.getShort(6) & 0xffff, fw = b.getInt(8), isz = b.getInt(12), aoff = b.getInt(16), rlen = b.getInt(20), crc = b.getInt(24);
        if (magic != MAGIC || ver != VERSION || flags != 0) throw new Invalid("not an .f3x file of version 1");
        if (fw != FW_ID) throw new Invalid("built for another firmware (only R390XXU0AZA3 is supported)");
        if (isz < 16 || isz > MAX_IMAGE || (isz & 3) != 0 || rlen < 0 || rlen > MAX_RELOC || (aoff & 3) != 0 || aoff < 0 || aoff + 20 > isz) throw new Invalid("sizes out of range");
        if (d.length != HEADER + ICON_SIZE + isz + rlen) throw new Invalid("the file size does not match its header");
        CRC32 c = new CRC32(); c.update(d, HEADER, d.length - HEADER);
        if ((int) c.getValue() != crc) throw new Invalid("CRC mismatch: the file is damaged");
        if (d[28 + 23] != 0 || d[28] == 0) throw new Invalid("bad name");
        int n = 0; while (n < 24 && d[28 + n] != 0) n++;
        String name = new String(d, 28, n, StandardCharsets.US_ASCII);
        long pos = 0; int i = HEADER + ICON_SIZE + isz, end = d.length;        // relocation list: LEB128 gaps in words
        while (i < end) {
            long v = 0; int sh = 0;
            while (true) { if (i >= end || sh > 28) throw new Invalid("bad relocation list"); int x = d[i++] & 0xff; v |= (long) (x & 0x7f) << sh; sh += 7; if ((x & 0x80) == 0) break; }
            pos += v * 4; if (pos + 4 > isz) throw new Invalid("a relocation points outside the image");
        }
        return new F3x(name, d.length, isz, Arrays.copyOfRange(d, HEADER, HEADER + ICON_SIZE));
    }

    /** the 64 x 64 four-bit indexed icon: 16 palette entries of B, G, R, A, then 4 bits per pixel, left pixel in the high nibble */
    Bitmap iconBitmap() {
        int[] pal = new int[16];
        for (int k = 0; k < 16; k++) { int B = icon[k * 4] & 0xff, G = icon[k * 4 + 1] & 0xff, R = icon[k * 4 + 2] & 0xff, A = icon[k * 4 + 3] & 0xff; pal[k] = (A << 24) | (R << 16) | (G << 8) | B; }
        int[] px = new int[64 * 64];
        for (int y = 0; y < 64; y++) for (int x = 0; x < 64; x++) { int v = icon[64 + y * 32 + x / 2] & 0xff; px[y * 64 + x] = pal[(x & 1) == 0 ? v >> 4 : v & 15]; }
        return Bitmap.createBitmap(px, 64, 64, Bitmap.Config.ARGB_8888);
    }

    static String slotPath(int n) {
        if (n < 0 || n >= SLOTS) throw new IllegalArgumentException("slot");
        return String.format("/user/hub/a%02d.f3x", n);
    }
}
