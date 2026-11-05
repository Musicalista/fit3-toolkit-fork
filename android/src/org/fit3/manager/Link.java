// SPDX-License-Identifier: Apache-2.0
package org.fit3.manager;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import java.io.ByteArrayOutputStream;
import java.io.Closeable;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.UUID;
import java.util.regex.Pattern;
import java.util.zip.CRC32;

/** One session of the watch's file service over Bluetooth RFCOMM (docs/protocol.md), ported from src/device/f3_link.py, f3_flash.py write_file and f3x_install.py.
 *  Writes are refused for every path except /user/hub/a00.f3x .. a15.f3x, and for every content that is not a valid .f3x or the tombstone. */
final class Link implements Closeable {
    static final UUID SPP = UUID.fromString("db764ac8-4b08-7f25-aafe-59d03c27bae3");
    static final int CHANNEL = 29, BLOCK = 39600;
    private static final Pattern SLOT_PATH = Pattern.compile("/user/hub/a(0[0-9]|1[0-5])\\.f3x");

    static final class Error extends IOException { Error(String m) { super(m); } }
    interface Progress { void on(int done, int total); }

    private final Closeable s; private final InputStream in; private final OutputStream out;

    private Link(BluetoothSocket s) throws IOException { this(s, s.getInputStream(), s.getOutputStream()); }
    Link(Closeable s, InputStream in, OutputStream out) { this.s = s; this.in = in; this.out = out; }      // also used by the JVM test (android/test)

    @SuppressLint("MissingPermission")
    static Link open(BluetoothAdapter adapter, String addr) throws IOException {
        if (!BluetoothAdapter.checkBluetoothAddress(addr)) throw new Error("endereço do relógio inválido: " + addr);
        BluetoothDevice dev = adapter.getRemoteDevice(addr);
        IOException last = null;
        for (int i = 0; i < 6; i++) {                                  // the channel needs a few seconds to be released after a session
            try { adapter.cancelDiscovery(); } catch (SecurityException ignored) { }
            BluetoothSocket sock = null;
            try {
                try {                                                  // the fixed channel, like the PC tools; the UUID lookup (SDP) as a fallback
                    Method m = dev.getClass().getMethod("createInsecureRfcommSocket", int.class);
                    sock = (BluetoothSocket) m.invoke(dev, CHANNEL);
                } catch (Exception e) { sock = dev.createInsecureRfcommSocketToServiceRecord(SPP); }
                try { sock.connect(); }
                catch (IOException e) { try { sock.close(); } catch (IOException ignored) { } sock = dev.createInsecureRfcommSocketToServiceRecord(SPP); sock.connect(); }
                sleep(500); return new Link(sock);
            } catch (IOException e) {
                last = e; if (sock != null) try { sock.close(); } catch (IOException ignored) { }
                sleep(4000);
            }
        }
        throw new Error("não consegui conectar ao relógio (" + (last == null ? "?" : last.getMessage()) + "). Force a parada do Galaxy Wearable, confira se o relógio está com o firmware do hub com os patches de Bluetooth e tente de novo.");
    }

    static void sleep(long ms) { try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } }

    void send(byte[] d) throws IOException { try { out.write(d); out.flush(); } catch (IOException e) { throw new Error("o relógio fechou a conexão"); } }
    void send(String t) throws IOException { send(t.getBytes(StandardCharsets.ISO_8859_1)); }

    /** n bytes within the timeout (the socket's stream has no timeout of its own: poll available()) */
    byte[] read(int n, int timeoutMs) throws IOException {
        byte[] b = new byte[n]; int got = 0; long end = System.currentTimeMillis() + timeoutMs;
        while (got < n) {
            int av; try { av = in.available(); } catch (IOException e) { throw new Error("o relógio fechou a conexão"); }
            if (av > 0) { int r = in.read(b, got, Math.min(av, n - got)); if (r < 0) throw new Error("o relógio fechou a conexão"); got += r; continue; }
            if (System.currentTimeMillis() > end) throw new Error("o relógio não respondeu a tempo");
            sleep(5);
        }
        return b;
    }
    void drain() throws IOException { long end = System.currentTimeMillis() + 300; while (System.currentTimeMillis() < end) { int av = in.available(); if (av > 0) in.skip(av); else sleep(20); } }
    private void expect(String t) throws IOException {
        byte[] got = read(t.length(), 30000);
        if (Arrays.equals(got, t.getBytes(StandardCharsets.ISO_8859_1))) return;
        StringBuilder all = new StringBuilder(new String(got, StandardCharsets.ISO_8859_1));
        long end = System.currentTimeMillis() + 600;                   // the rest of the answer, e.g. "open error:-2, 331"
        while (System.currentTimeMillis() < end) { int av = in.available(); if (av > 0) { byte[] b = new byte[Math.min(av, 256)]; int r = in.read(b); if (r > 0) all.append(new String(b, 0, r, StandardCharsets.ISO_8859_1)); } else sleep(20); }
        throw new Error(all.toString().replaceAll("[^\\x20-\\x7e]", " ").trim());
    }

    /** reads a whole file (always to the end: the watch must see the closing "062"); null when it does not exist */
    byte[] readFile(String path, int limit) throws IOException {
        drain(); send("061" + path + "\0"); byte[] h = read(5, 15000);
        if ((h[0] & 0xff) != 0x40) { drain(); return null; }
        int total = be32(h, 1);
        if (total < 0 || total > limit) throw new Error(path + " is " + total + " bytes, over the limit");
        ByteArrayOutputStream data = new ByteArrayOutputStream(total);
        while (data.size() < total) {
            send("062"); byte[] hh = read(5, 15000); int n = be32(hh, 1);
            if ((hh[0] & 0xff) != 0x40 || n <= 0 || n > total - data.size()) throw new Error("bloco inválido na leitura");
            data.write(read(n, 60000)); read(4, 60000);
        }
        send("062"); sleep(100); return data.toByteArray();
    }

    /** the only write: one of the sixteen slots, a valid .f3x or the tombstone */
    void writeSlot(byte[] data, String path, Progress p) throws IOException {
        if (!SLOT_PATH.matcher(path).matches()) throw new Error("gravação recusada: " + path);
        if (!Arrays.equals(data, F3x.TOMBSTONE)) try { F3x.parse(data); } catch (F3x.Invalid e) { throw new Error("gravação recusada: " + e.getMessage()); }
        drain(); send("300"); expect("300");
        send("33bin," + path + "," + data.length);
        try { expect("330"); } catch (Error e) {
            String ans = e.getMessage();
            if (ans.contains("-2")) throw new Error("a pasta /user/hub ainda não existe no relógio (resposta: \"" + ans + "\"). Abra o Application Hub no relógio uma vez: ele cria a pasta. Se mesmo assim falhar, o firmware do relógio não tem o instalador de apps: grave o firmware do hub feito com este projeto.");
            throw new Error("o relógio recusou o arquivo (resposta: \"" + ans + "\").");
        }
        for (int off = 0; off < data.length; off += BLOCK) {
            int n = Math.min(BLOCK, data.length - off); CRC32 c = new CRC32(); c.update(data, off, n); long v = c.getValue();
            byte[] blk = new byte[n + 4]; System.arraycopy(data, off, blk, 0, n);
            blk[n] = (byte) v; blk[n + 1] = (byte) (v >> 8); blk[n + 2] = (byte) (v >> 16); blk[n + 3] = (byte) (v >> 24);
            send(blk); expect("310"); if (p != null) p.on(off + n, data.length);
        }
        send("32"); expect("320"); sleep(250); send("34"); expect("340");
    }

    private static int be32(byte[] b, int o) { return ((b[o] & 0xff) << 24) | ((b[o + 1] & 0xff) << 16) | ((b[o + 2] & 0xff) << 8) | (b[o + 3] & 0xff); }

    @Override public void close() { try { s.close(); } catch (IOException ignored) { } }
}
