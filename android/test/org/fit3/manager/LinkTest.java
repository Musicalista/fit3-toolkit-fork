// SPDX-License-Identifier: Apache-2.0
package org.fit3.manager;

import java.net.Socket;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Arrays;

/** Runs the app's protocol code (Link, F3x) on a plain JVM against src/device/mock_watch.py served over TCP by android/test/mock_tcp.py. */
public final class LinkTest {
    static int fails = 0, n = 0;
    static void ok(String what, boolean c) { n++; if (!c) fails++; System.out.println((c ? "PASS " : "FAIL ") + what); }
    static Link link(int port) throws Exception { Socket s = new Socket("127.0.0.1", port); return new Link(s, s.getInputStream(), s.getOutputStream()); }

    public static void main(String[] a) throws Exception {
        int port = Integer.parseInt(a[0]); byte[] app = Files.readAllBytes(Paths.get(a[1]));
        F3x f = F3x.parse(app); ok("parse a good .f3x: name " + f.name, f.name.equals("App Manager") && f.size == app.length);
        byte[] bad = app.clone(); bad[bad.length - 1] ^= 1;
        try { F3x.parse(bad); ok("a damaged file is refused", false); } catch (F3x.Invalid e) { ok("a damaged file is refused (" + e.getMessage() + ")", true); }
        byte[] other = app.clone(); other[8] ^= 1;
        try { F3x.parse(other); ok("another firmware is refused", false); } catch (F3x.Invalid e) { ok("another firmware is refused", true); }

        try (Link l = link(port)) { ok("an empty slot reads as null", l.readFile(F3x.slotPath(3), 65536) == null); }
        try (Link l = link(port)) { l.writeSlot(app, F3x.slotPath(3), null); }
        try (Link l = link(port)) { ok("write then read back: identical", Arrays.equals(l.readFile(F3x.slotPath(3), 65536), app)); }
        try (Link l = link(port)) { l.writeSlot(F3x.TOMBSTONE, F3x.slotPath(3), null); }
        try (Link l = link(port)) { ok("the tombstone reads back", Arrays.equals(l.readFile(F3x.slotPath(3), 65536), F3x.TOMBSTONE)); }
        try (Link l = link(port)) { l.writeSlot(app, "/user/ota/R390_WEB_FOTA.bin", null); ok("a path outside the slots is refused", false); } catch (Link.Error e) { ok("a path outside the slots is refused", true); }
        try (Link l = link(port)) { l.writeSlot(bad, F3x.slotPath(4), null); ok("a damaged file is never written", false); } catch (Link.Error e) { ok("a damaged file is never written", true); }
        if (a.length > 3) {                                            // a Game Boy ROM (src/emu/gbtest_rom.py): the game goes only to /user/gb/rom.gb, and only if it is a ROM
            byte[] rom = Files.readAllBytes(Paths.get(a[3]));
            ok("the test ROM parses: " + GbRom.parse(rom).title, GbRom.parse(rom).size == rom.length);
            try (Link l = link(port)) { l.writeGame(rom, null); }
            try (Link l = link(port)) { ok("the game reads back identical from /user/gb/rom.gb", Arrays.equals(l.readFile(GbRom.PATH, GbRom.MAX), rom)); }
            byte[] badRom = rom.clone(); badRom[0x14d] ^= 1;
            try (Link l = link(port)) { l.writeGame(badRom, null); ok("a file that is not a ROM is not sent", false); } catch (Link.Error e) { ok("a file that is not a ROM is not sent", true); }
            try (Link l = link(port)) { l.writeGame(app, null); ok("an .f3x is not sent as a game", false); } catch (Link.Error e) { ok("an .f3x is not sent as a game", true); }
        }
        if (a.length > 2) {                                            // a second mock that refuses every file like a watch without /user/hub ("open error:-2, 331")
            try (Link l = link(Integer.parseInt(a[2]))) { l.writeSlot(app, F3x.slotPath(0), null); ok("a refused file is reported", false); }
            catch (Link.Error e) { ok("a refused file is reported with the watch's answer: " + e.getMessage(), e.getMessage().contains("open error:-2, 331") && e.getMessage().contains("/user/hub")); }
        }
        System.out.println(n + " checks, " + fails + " failed"); System.exit(fails == 0 ? 0 : 1);
    }
}
