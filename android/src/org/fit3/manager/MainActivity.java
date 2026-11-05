// SPDX-License-Identifier: Apache-2.0
package org.fit3.manager;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.Dialog;
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
import android.view.WindowManager;
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
    // the watch's theme (src/watch/ui.h and the photos in docs/images): black screen, navy cards with radius 26, blue pills, muted grey-blue secondary text, red for a second "Sure?"
    private static final int BG = 0xff000000, CARD = 0xff1c1a3e, TEXT = 0xffffffff, MUTED = 0xffa8b8c0, ACCENT = 0xff3b3bf2, DANGER = 0xffc83030, OK = 0xff3ecf6e;

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

        TextView title = text("Aplicativos", 32, TEXT, true); title.setGravity(Gravity.CENTER); col.addView(title);
        tvStatus = text("Toque em Atualizar para ler o relógio", 14, MUTED, false); tvStatus.setGravity(Gravity.CENTER); tvStatus.setPadding(0, dp(10), 0, dp(36)); col.addView(tvStatus);

        LinearLayout cw = card(); col.addView(cw);
        cw.addView(text("Relógio", 13, MUTED, false));
        tvWatch = text("", 17, TEXT, true); tvWatch.setPadding(0, dp(4), 0, 0); cw.addView(tvWatch);
        cw.setOnClickListener(v -> { if (!busy) chooseWatch(); });

        LinearLayout cs = card(); col.addView(cs);
        tvSummary = text("—", 15, TEXT, false); cs.addView(tvSummary);
        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal); bar.setMax(1000); bar.setVisibility(View.GONE);
        bar.setProgressTintList(android.content.res.ColorStateList.valueOf(ACCENT)); cs.addView(bar);

        TextView h = text("Instalados no relógio", 14, MUTED, false); h.setPadding(dp(8), dp(24), 0, 0); col.addView(h);
        list = new LinearLayout(this); list.setOrientation(LinearLayout.VERTICAL); col.addView(list);

        LinearLayout bottom = new LinearLayout(this); bottom.setPadding(dp(11), dp(10), dp(11), dp(18)); bottom.setBackgroundColor(BG);
        bRefresh = pill("Atualizar", CARD, v -> refresh()); bInstall = pill("Instalar", ACCENT, v -> pick());
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
            LinearLayout row = rowCard();
            ImageView im = new ImageView(this); im.setImageBitmap(s.app.iconBitmap()); row.addView(im, new LinearLayout.LayoutParams(dp(60), dp(60)));
            LinearLayout tx = new LinearLayout(this); tx.setOrientation(LinearLayout.VERTICAL); tx.setPadding(dp(14), 0, 0, 0);
            tx.addView(text(s.app.name, 20, TEXT, true));
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
        Sheet sh = new Sheet("Escolha o relógio");
        LinearLayout rows = new LinearLayout(this); rows.setOrientation(LinearLayout.VERTICAL);
        for (String[] dv : devs) {
            LinearLayout r = rowCard(); LinearLayout tx = new LinearLayout(this); tx.setOrientation(LinearLayout.VERTICAL);
            tx.addView(text(dv[0], 18, TEXT, true)); tx.addView(text(dv[1], 13, MUTED, false)); r.addView(tx);
            r.setOnClickListener(v -> { sh.d.dismiss(); saveWatch(dv[0], dv[1]); }); rows.addView(r);
        }
        LinearLayout r = rowCard(); r.addView(text("Digitar o endereço…", 18, TEXT, true)); r.setOnClickListener(v -> { sh.d.dismiss(); enterAddress(); }); rows.addView(r);
        ScrollView sc = new ScrollView(this); sc.addView(rows);
        sh.view(sc); sh.close("Cancelar", CARD); sh.show();
    }
    private void enterAddress() {
        EditText e = new EditText(this); e.setHint("AA:BB:CC:DD:EE:FF"); e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS); e.setText(addr());
        e.setTextColor(TEXT); e.setHintTextColor(MUTED); e.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18); e.setGravity(Gravity.CENTER);
        e.setBackground(round(CARD, 26)); e.setPadding(dp(16), dp(16), dp(16), dp(16));
        Sheet sh = new Sheet("Endereço do relógio").msg("Em Configurações > Sobre a pulseira, ou na lista de dispositivos Bluetooth do telefone.").view(e);
        sh.close("Cancelar", CARD);
        sh.button("OK", ACCENT, v -> {
            String val = e.getText().toString().trim().toUpperCase(Locale.ROOT);
            if (BluetoothAdapter.checkBluetoothAddress(val)) { sh.d.dismiss(); saveWatch("Galaxy Fit3", val); } else { e.setTextColor(DANGER); }
        });
        sh.show();
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
        try { bytes = readUri(data.getData()); }
        catch (IOException e) { dialog("Não deu para ler o arquivo", e.getMessage()); return; }
        try { app = F3x.parse(bytes); }
        catch (F3x.Invalid e) {
            GbRom game;
            try { game = GbRom.parse(bytes); }
            catch (F3x.Invalid g) { dialog("Arquivo inválido", "Não é um app .f3x para o firmware R390XXU0AZA3 (" + e.getMessage() + ") nem um jogo de Game Boy (" + g.getMessage() + ")."); return; }
            confirmGame(bytes, game); return;
        }
        final byte[] fb = bytes; final F3x fa = app;
        ImageView im = new ImageView(this); im.setImageBitmap(app.iconBitmap());
        LinearLayout.LayoutParams ip = new LinearLayout.LayoutParams(dp(72), dp(72)); ip.gravity = Gravity.CENTER_HORIZONTAL; ip.bottomMargin = dp(10); im.setLayoutParams(ip);
        Sheet sh = new Sheet("Instalar app?").view(im);
        TextView nm = text(app.name, 20, TEXT, true); nm.setGravity(Gravity.CENTER); sh.view(nm);
        sh.msg(String.format(Locale.getDefault(), "%.1f kB", app.size / 1024f));
        sh.msg("Feche o Galaxy Wearable (Forçar parada) antes de continuar.", TEXT);
        sh.close("Cancelar", CARD);
        sh.button("Instalar", ACCENT, v -> { sh.d.dismiss(); install(fb, fa); });
        sh.show();
    }
    private byte[] readUri(Uri u) throws IOException {
        try (InputStream in = getContentResolver().openInputStream(u)) {
            if (in == null) throw new IOException("sem acesso ao arquivo");
            ByteArrayOutputStream o = new ByteArrayOutputStream(); byte[] b = new byte[8192]; int r;
            while ((r = in.read(b)) > 0) { o.write(b, 0, r); if (o.size() > GbRom.MAX) throw new IOException("arquivo grande demais (máximo 1 MB)"); }
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

    private void confirmGame(byte[] data, GbRom game) {
        Sheet sh = new Sheet("Enviar jogo?");
        TextView nm = text(game.title, 20, TEXT, true); nm.setGravity(Gravity.CENTER); sh.view(nm);
        sh.msg(String.format(Locale.getDefault(), "%d kB. Ele substitui o jogo que estiver no app Game Boy do relógio.", game.size / 1024));
        sh.msg("Use só jogos que você tem direito de usar. Feche o Galaxy Wearable (Forçar parada) antes.", TEXT);
        sh.close("Cancelar", CARD);
        sh.button("Enviar", ACCENT, v -> { sh.d.dismiss(); sendGame(data, game); });
        sh.show();
    }
    private void sendGame(byte[] data, GbRom game) {
        job("Conectando…", () -> {
            status("Enviando " + game.title + "…");
            try (Link l = Link.open(adapter(), addr())) { l.writeGame(data, this::progress); }
            Link.sleep(2200);
            status("Conferindo…");
            byte[] got;
            try (Link l = Link.open(adapter(), addr())) { got = l.readFile(GbRom.PATH, GbRom.MAX); }
            if (!Arrays.equals(got, data)) throw new IOException("O jogo no relógio não confere com o arquivo. Tente de novo.");
            status(game.title + " enviado: abra o app Game Boy no relógio");
        });
    }

    private void confirmRemove(Slot s) {
        ImageView im = new ImageView(this); im.setImageBitmap(s.app.iconBitmap());
        LinearLayout.LayoutParams ip = new LinearLayout.LayoutParams(dp(72), dp(72)); ip.gravity = Gravity.CENTER_HORIZONTAL; ip.bottomMargin = dp(10); im.setLayoutParams(ip);
        Sheet sh = new Sheet("Remover app?").view(im);
        TextView nm = text(s.app.name, 20, TEXT, true); nm.setGravity(Gravity.CENTER); sh.view(nm);
        sh.msg(String.format(Locale.getDefault(), "Espaço %02d · %.1f kB", s.n, s.app.size / 1024f));
        final boolean[] armed = { false };
        TextView rm = sh.button("Remover", ACCENT, null);
        rm.setOnClickListener(v -> {
            if (!armed[0]) { armed[0] = true; rm.setText("Tem certeza?"); rm.setBackground(round(DANGER, 100)); return; }      // the hub's two steps
            sh.d.dismiss(); remove(s);
        });
        sh.close("Cancelar", CARD);
        sh.show();
    }
    private void remove(Slot s) {
        job("Conectando…", () -> {
            writeAndVerify(s.n, F3x.TOMBSTONE, "Removendo " + s.app.name);
            ui.post(() -> { if (slots != null) slots.set(s.n, new Slot(s.n, null, true)); });
            status(s.app.name + " removido");
        });
    }

    /** a sheet in the watch's style (the hub's "Remove app?" sheet): black, centred white title, muted text, pills side by side at the bottom */
    private final class Sheet {
        final Dialog d = new Dialog(MainActivity.this); final LinearLayout box = new LinearLayout(MainActivity.this), buttons = new LinearLayout(MainActivity.this);
        Sheet(String title) {
            d.requestWindowFeature(Window.FEATURE_NO_TITLE);
            box.setOrientation(LinearLayout.VERTICAL); box.setBackground(round(BG, 30)); box.setPadding(dp(18), dp(26), dp(18), dp(18));
            GradientDrawable g = (GradientDrawable) box.getBackground(); g.setStroke(dp(1), CARD);
            TextView t = text(title, 24, TEXT, true); t.setGravity(Gravity.CENTER); t.setPadding(0, 0, 0, dp(14)); box.addView(t);
            buttons.setPadding(0, dp(18), 0, 0);
        }
        Sheet msg(String m, int color) { TextView t = text(m, 16, color, false); t.setGravity(Gravity.CENTER); t.setPadding(dp(6), dp(4), dp(6), dp(4)); box.addView(t); return this; }
        Sheet msg(String m) { return msg(m, MUTED); }
        Sheet view(View v) { box.addView(v); return this; }
        TextView button(String label, int color, View.OnClickListener l) { TextView b = pill(label, color, l); buttons.addView(b); return b; }
        Sheet close(String label, int color) { final Dialog dd = d; button(label, color, new View.OnClickListener() { @Override public void onClick(View v) { dd.dismiss(); } }); return this; }
        void show() {
            if (buttons.getChildCount() > 0) box.addView(buttons);
            d.setContentView(box);
            Window w = d.getWindow();
            if (w != null) {
                w.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(Color.TRANSPARENT));
                w.setLayout(getResources().getDisplayMetrics().widthPixels - dp(24), ViewGroup.LayoutParams.WRAP_CONTENT);
                w.setGravity(Gravity.BOTTOM); w.getAttributes().y = dp(16); w.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND); w.setDimAmount(0.7f);
            }
            d.show();
        }
    }
    /** a row in the watch's style: a navy card with radius 26 */
    private LinearLayout rowCard() {
        LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.setGravity(Gravity.CENTER_VERTICAL);
        row.setBackground(round(CARD, 26)); row.setPadding(dp(14), dp(14), dp(14), dp(14)); row.setMinimumHeight(dp(84));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT); lp.topMargin = dp(10); row.setLayoutParams(lp); return row;
    }
    private void dialog(String title, String msg) { new Sheet(title).msg(msg).close("OK", ACCENT).show(); }

    @Override public void onRequestPermissionsResult(int req, String[] p, int[] r) {
        if (req == REQ_PERM && (r.length == 0 || r[0] != PackageManager.PERMISSION_GRANTED)) dialog("Permissão", "O app precisa da permissão de Dispositivos próximos para falar com o relógio.");
    }
}
