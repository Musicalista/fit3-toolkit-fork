// SPDX-License-Identifier: Apache-2.0
package org.fit3.manager;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Fit3 Apps: lists, installs and removes the .f3x apps of the Application Hub from the phone. One UI look: big header, rounded cards, pill buttons. */
public final class MainActivity extends Activity {
    private static final int REQ_PICK = 1, REQ_PERM = 2;
    private static final int BG = 0xff000000, CARD = 0xff17171d, TEXT = 0xfffafafa, MUTED = 0xff9a9aa3, ACCENT = 0xff3e91ff, DANGER = 0xffff5247, OK = 0xff3ecf6e;

    /** what a slot holds: nothing (no file), free (a tombstone or a file the hub ignores) or an app */
    private static final class Slot { final int n; final F3x app; final boolean exists; Slot(int n, F3x app, boolean exists) { this.n = n; this.app = app; this.exists = exists; } }

    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private SharedPreferences prefs;
    private TextView tvWatch, tvStatus, tvSummary;
    private ProgressBar bar;
    private LinearLayout list;
    private TextView bRefresh, bInstall;
    private List<Slot> slots;                                          // null until the first refresh
    private boolean busy;

    // ---------------------------------------------------------------- UI
    private int dp(float v) { return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics())); }
    private GradientDrawable round(int color, float radiusDp) { GradientDrawable g = new GradientDrawable(); g.setColor(color); g.setCornerRadius(dp(radiusDp)); return g; }
    private TextView text(String s, float sp, int color, boolean bold) {
        TextView t = new TextView(this); t.setText(s); t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp); t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL)); return t;
    }
    private LinearLayout card() {
        LinearLayout c = new LinearLayout(this); c.setOrientation(LinearLayout.VERTICAL); c.setBackground(round(CARD, 26)); c.setPadding(dp(22), dp(18), dp(22), dp(18));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT); lp.topMargin = dp(12); c.setLayoutParams(lp); return c;
    }
    private TextView pill(String s, int color, View.OnClickListener l) {
        TextView b = text(s, 16, Color.WHITE, true); b.setGravity(Gravity.CENTER); b.setBackground(round(color, 100)); b.setPadding(dp(20), dp(14), dp(20), dp(14)); b.setOnClickListener(l);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1); lp.setMargins(dp(5), 0, dp(5), 0); b.setLayoutParams(lp); return b;
    }

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        prefs = getSharedPreferences("fit3", MODE_PRIVATE);
        Window w = getWindow(); w.setStatusBarColor(BG); w.setNavigationBarColor(BG);

        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(BG);
        ScrollView sv = new ScrollView(this); sv.setFillViewport(true);
        LinearLayout col = new LinearLayout(this); col.setOrientation(LinearLayout.VERTICAL); col.setPadding(dp(16), dp(72), dp(16), dp(24));
        sv.addView(col); root.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        TextView title = text("Apps do Fit3", 34, TEXT, false); title.setGravity(Gravity.CENTER); col.addView(title);
        tvStatus = text("Toque em Atualizar para ler o relógio", 14, MUTED, false); tvStatus.setGravity(Gravity.CENTER); tvStatus.setPadding(0, dp(10), 0, dp(36)); col.addView(tvStatus);

        LinearLayout cw = card(); col.addView(cw);
        cw.addView(text("Relógio", 13, MUTED, false));
        tvWatch = text("", 17, TEXT, true); tvWatch.setPadding(0, dp(4), 0, 0); cw.addView(tvWatch);
        cw.setOnClickListener(v -> { if (!busy) chooseWatch(); });

        LinearLayout cs = card(); col.addView(cs);
        tvSummary = text("—", 15, TEXT, false); cs.addView(tvSummary);
        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal); bar.setMax(1000); bar.setVisibility(View.GONE);
        bar.setProgressTintList(android.content.res.ColorStateList.valueOf(ACCENT)); cs.addView(bar);

        TextView h = text("Apps instalados", 14, MUTED, false); h.setPadding(dp(8), dp(24), 0, 0); col.addView(h);
        list = new LinearLayout(this); list.setOrientation(LinearLayout.VERTICAL); col.addView(list);

        LinearLayout bottom = new LinearLayout(this); bottom.setPadding(dp(11), dp(10), dp(11), dp(18)); bottom.setBackgroundColor(BG);
        bRefresh = pill("Atualizar", 0xff2c2c35, v -> refresh()); bInstall = pill("Instalar app", ACCENT, v -> pick());
        bottom.addView(bRefresh); bottom.addView(bInstall); root.addView(bottom);
        setContentView(root);

        showWatch(); renderSlots();
        if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[] { Manifest.permission.BLUETOOTH_CONNECT }, REQ_PERM);
    }

    @Override protected void onDestroy() { worker.shutdownNow(); super.onDestroy(); }

    private void setBusy(boolean on, String status) {
        busy = on; tvStatus.setText(status); bar.setVisibility(on ? View.VISIBLE : View.GONE); bar.setIndeterminate(true);
        bRefresh.setAlpha(on ? 0.4f : 1f); bInstall.setAlpha(on ? 0.4f : 1f);
    }
    private void status(String s) { ui.post(() -> tvStatus.setText(s)); }
    private void progress(int done, int total) { ui.post(() -> { bar.setIndeterminate(false); bar.setProgress((int) (1000L * done / Math.max(1, total))); }); }

    private void renderSlots() {
        list.removeAllViews();
        if (slots == null) { tvSummary.setText("Ainda não lido"); return; }
        int apps = 0, used = 0, bytes = 0;
        for (Slot s : slots) if (s.app != null) { apps++; used++; bytes += s.app.size; }
        tvSummary.setText(String.format(Locale.getDefault(), "%d %s · %d de 16 espaços livres · %.1f kB", apps, apps == 1 ? "app" : "apps", 16 - used, bytes / 1024f));
        for (Slot s : slots) {
            if (s.app == null) continue;
            LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.setGravity(Gravity.CENTER_VERTICAL);
            row.setBackground(round(CARD, 26)); row.setPadding(dp(14), dp(12), dp(14), dp(12));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT); lp.topMargin = dp(10); row.setLayoutParams(lp);
            ImageView im = new ImageView(this); im.setImageBitmap(s.app.iconBitmap()); row.addView(im, new LinearLayout.LayoutParams(dp(52), dp(52)));
            LinearLayout tx = new LinearLayout(this); tx.setOrientation(LinearLayout.VERTICAL); tx.setPadding(dp(14), 0, 0, 0);
            tx.addView(text(s.app.name, 17, TEXT, true));
            tx.addView(text(String.format(Locale.getDefault(), "Espaço %02d · %.1f kB", s.n, s.app.size / 1024f), 13, MUTED, false));
            row.addView(tx);
            row.setOnClickListener(v -> { if (!busy) confirmRemove(s); });
            list.addView(row);
        }
        if (apps == 0) { TextView t = text("Nenhum app instalado", 15, MUTED, false); t.setGravity(Gravity.CENTER); t.setPadding(0, dp(28), 0, 0); list.addView(t); }
    }

    // ---------------------------------------------------------------- the watch
    private String addr() { return prefs.getString("addr", ""); }
    private void showWatch() { String a = addr(); tvWatch.setText(a.isEmpty() ? "Toque para escolher" : prefs.getString("name", "Galaxy Fit3") + "  ·  " + a); }

    private BluetoothAdapter adapter() { BluetoothManager m = (BluetoothManager) getSystemService(BLUETOOTH_SERVICE); return m == null ? null : m.getAdapter(); }
    private boolean ready() {
        BluetoothAdapter a = adapter();
        if (a == null) { dialog("Bluetooth", "Este telefone não tem Bluetooth."); return false; }
        if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[] { Manifest.permission.BLUETOOTH_CONNECT }, REQ_PERM); return false;
        }
        if (!a.isEnabled()) { dialog("Bluetooth", "Ligue o Bluetooth e tente de novo."); return false; }
        if (addr().isEmpty()) { chooseWatch(); return false; }
        return true;
    }

    @SuppressLint("MissingPermission")
    private void chooseWatch() {
        BluetoothAdapter a = adapter();
        if (a == null) return;
        if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[] { Manifest.permission.BLUETOOTH_CONNECT }, REQ_PERM); return;
        }
        final List<String[]> devs = new ArrayList<>();
        Set<BluetoothDevice> bonded = a.getBondedDevices();
        if (bonded != null) for (BluetoothDevice d : bonded) {
            String n = d.getName() == null ? d.getAddress() : d.getName();
            if (n.toLowerCase(Locale.ROOT).contains("fit")) devs.add(0, new String[] { n, d.getAddress() }); else devs.add(new String[] { n, d.getAddress() });
        }
        String[] items = new String[devs.size() + 1];
        for (int i = 0; i < devs.size(); i++) items[i] = devs.get(i)[0] + "\n" + devs.get(i)[1];
        items[devs.size()] = "Digitar o endereço…";
        new AlertDialog.Builder(this).setTitle("Escolha o relógio").setItems(items, (d, i) -> {
            if (i < devs.size()) saveWatch(devs.get(i)[0], devs.get(i)[1]); else enterAddress();
        }).show();
    }
    private void enterAddress() {
        EditText e = new EditText(this); e.setHint("AA:BB:CC:DD:EE:FF"); e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS); e.setText(addr());
        LinearLayout box = new LinearLayout(this); box.setPadding(dp(22), dp(8), dp(22), 0); box.addView(e, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        new AlertDialog.Builder(this).setTitle("Endereço Bluetooth do relógio").setView(box).setNegativeButton("Cancelar", null).setPositiveButton("OK", (d, i) -> {
            String v = e.getText().toString().trim().toUpperCase(Locale.ROOT);
            if (BluetoothAdapter.checkBluetoothAddress(v)) saveWatch("Galaxy Fit3", v); else dialog("Endereço inválido", "Use o formato AA:BB:CC:DD:EE:FF.");
        }).show();
    }
    private void saveWatch(String name, String a) { prefs.edit().putString("addr", a).putString("name", name).apply(); slots = null; showWatch(); renderSlots(); }

    // ---------------------------------------------------------------- jobs (one at a time, on the worker thread)
    private interface Job { void run() throws Exception; }
    private void job(String start, Job j) {
        if (busy || !ready()) return;
        setBusy(true, start);
        worker.execute(() -> {
            String err = null;
            try { j.run(); } catch (Exception e) { err = e.getMessage() == null ? e.toString() : e.getMessage(); }
            final String fe = err;
            ui.post(() -> { setBusy(false, fe == null ? tvStatus.getText().toString() : "Erro"); renderSlots(); if (fe != null) dialog("Não deu certo", fe); });
        });
    }

    /** reads the sixteen slots in one session */
    private List<Slot> readSlots() throws IOException {
        List<Slot> out = new ArrayList<>();
        try (Link l = Link.open(adapter(), addr())) {
            for (int n = 0; n < F3x.SLOTS; n++) {
                status("Lendo espaço " + (n + 1) + " de 16…"); progress(n, F3x.SLOTS);
                byte[] d = l.readFile(F3x.slotPath(n), 64 * 1024); F3x app = null;
                if (d != null) try { app = F3x.parse(d); } catch (F3x.Invalid ignored) { }
                out.add(new Slot(n, app, d != null)); Link.sleep(250);
            }
        }
        return out;
    }
    private void refresh() { job("Conectando…", () -> { List<Slot> s = readSlots(); ui.post(() -> slots = s); status("Atualizado"); }); }

    /** writes, reconnects and reads the file back (as f3x_install.py does) */
    private void writeAndVerify(int slot, byte[] data, String what) throws IOException {
        String path = F3x.slotPath(slot);
        Link.sleep(2200);
        status(what + "…");
        try (Link l = Link.open(adapter(), addr())) { l.writeSlot(data, path, this::progress); }
        Link.sleep(2200);
        status("Conferindo…");
        byte[] got;
        try (Link l = Link.open(adapter(), addr())) { got = l.readFile(path, 64 * 1024); }
        if (!Arrays.equals(got, data)) throw new IOException("O arquivo no relógio não confere com o original. Tente de novo.");
    }

    private void pick() {
        if (busy) return;
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT); i.addCategory(Intent.CATEGORY_OPENABLE); i.setType("*/*");
        startActivityForResult(i, REQ_PICK);
    }
    @Override protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != REQ_PICK || res != RESULT_OK || data == null || data.getData() == null) return;
        byte[] bytes; F3x app;
        try { bytes = readUri(data.getData()); app = F3x.parse(bytes); }
        catch (F3x.Invalid e) { dialog("Arquivo inválido", "Este não é um app .f3x para o firmware R390XXU0AZA3: " + e.getMessage()); return; }
        catch (IOException e) { dialog("Não deu para ler o arquivo", e.getMessage()); return; }
        final byte[] fb = bytes; final F3x fa = app;
        new AlertDialog.Builder(this).setTitle("Instalar " + app.name + "?")
            .setMessage(String.format(Locale.getDefault(), "%.1f kB. O app aparece no Application Hub na próxima vez que você abrir o hub.\n\nFeche o Galaxy Wearable (forçar parada) antes de continuar.", app.size / 1024f))
            .setNegativeButton("Cancelar", null).setPositiveButton("Instalar", (d, i) -> install(fb, fa)).show();
    }
    private byte[] readUri(Uri u) throws IOException {
        try (InputStream in = getContentResolver().openInputStream(u)) {
            if (in == null) throw new IOException("sem acesso ao arquivo");
            ByteArrayOutputStream o = new ByteArrayOutputStream(); byte[] b = new byte[8192]; int r;
            while ((r = in.read(b)) > 0) { o.write(b, 0, r); if (o.size() > 64 * 1024) throw new IOException("arquivo grande demais para um app .f3x"); }
            return o.toByteArray();
        }
    }
    private void install(byte[] data, F3x app) {
        job("Conectando…", () -> {
            List<Slot> table = readSlots(); ui.post(() -> slots = table);
            int target = -1;
            for (Slot s : table) if (s.app != null && s.app.name.equals(app.name)) { target = s.n; break; }       // same name: update in place
            if (target < 0) for (Slot s : table) if (s.app == null) { target = s.n; break; }
            if (target < 0) throw new IOException("Os 16 espaços estão ocupados. Remova um app primeiro.");
            writeAndVerify(target, data, "Enviando " + app.name);
            final int t = target; List<Slot> after = new ArrayList<>(table); after.set(t, new Slot(t, app, true));
            ui.post(() -> slots = after); status(app.name + " instalado no espaço " + String.format(Locale.ROOT, "%02d", t));
        });
    }

    private void confirmRemove(Slot s) {
        new AlertDialog.Builder(this).setTitle("Remover " + s.app.name + "?")
            .setMessage(String.format(Locale.getDefault(), "Espaço %02d · %.1f kB. O app some do Application Hub.", s.n, s.app.size / 1024f))
            .setNegativeButton("Cancelar", null).setPositiveButton("Remover", (d, i) -> remove(s)).show();
    }
    private void remove(Slot s) {
        job("Conectando…", () -> {
            writeAndVerify(s.n, F3x.TOMBSTONE, "Removendo " + s.app.name);
            ui.post(() -> { if (slots != null) slots.set(s.n, new Slot(s.n, null, true)); });
            status(s.app.name + " removido");
        });
    }

    private void dialog(String title, String msg) { new AlertDialog.Builder(this).setTitle(title).setMessage(msg).setPositiveButton("OK", null).show(); }

    @Override public void onRequestPermissionsResult(int req, String[] p, int[] r) {
        if (req == REQ_PERM && (r.length == 0 || r[0] != PackageManager.PERMISSION_GRANTED)) dialog("Permissão", "O app precisa da permissão de Dispositivos próximos para falar com o relógio.");
    }
}
