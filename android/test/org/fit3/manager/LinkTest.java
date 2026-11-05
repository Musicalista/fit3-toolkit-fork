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
        System.out.println(n + " checks, " + fails + " failed"); System.exit(fails == 0 ? 0 : 1);
    }
}
