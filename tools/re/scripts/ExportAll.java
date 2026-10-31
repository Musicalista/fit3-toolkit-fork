// SPDX-License-Identifier: Apache-2.0
// Exports what the other tools need: functions.csv, strings.csv (with the functions that reference each string), calls.csv (direct calls and function-pointer references), and with
// the argument "decomp" the decompiled C of every function into decomp/<address>.c (16 threads). Arguments: <output directory> [decomp]
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;

public class ExportAll extends GhidraScript {
    private static String q(String s) { return "\"" + s.replace("\"", "\"\"").replace("\n", "\\n").replace("\r", "") + "\""; }
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs(); File out = new File(a[0]); out.mkdirs(); boolean decomp = a.length > 1 && a[1].equals("decomp");
        FunctionManager fm = currentProgram.getFunctionManager(); ReferenceManager rm = currentProgram.getReferenceManager();
        try (PrintWriter w = new PrintWriter(new File(out, "functions.csv")); PrintWriter c = new PrintWriter(new File(out, "calls.csv"))) {
            w.println("address,size,name,callers"); c.println("from_function,from_address,to_function,kind");
            for (Function f : fm.getFunctions(true)) {
                int callers = 0; for (Reference r : rm.getReferencesTo(f.getEntryPoint())) callers++;
                w.println("0x" + f.getEntryPoint() + "," + f.getBody().getNumAddresses() + "," + q(f.getName()) + "," + callers);
                for (Address ad : f.getBody().getAddresses(true)) for (Reference r : rm.getReferencesFrom(ad)) {
                    Function t = fm.getFunctionAt(r.getToAddress()); if (t == null || t == f) continue;
                    c.println("0x" + f.getEntryPoint() + ",0x" + ad + ",0x" + t.getEntryPoint() + "," + (r.getReferenceType().isCall() ? "call" : r.getReferenceType().isJump() ? "jump" : "ref"));
                }
            }
        }
        int n = 0;
        try (PrintWriter w = new PrintWriter(new File(out, "strings.csv"))) {
            w.println("address,string,referenced_from_functions");
            for (Data d : currentProgram.getListing().getDefinedData(true)) {
                if (!d.hasStringValue()) continue;
                StringDataInstance si = StringDataInstance.getStringDataInstance(d); String s = si.getStringValue(); if (s == null || s.length() < 4) continue;
                Set<String> fs = new TreeSet<>(); for (Reference r : rm.getReferencesTo(d.getAddress())) { Function f = fm.getFunctionContaining(r.getFromAddress()); fs.add(f != null ? "0x" + f.getEntryPoint() : "data:0x" + r.getFromAddress()); }
                w.println("0x" + d.getAddress() + "," + q(s) + "," + q(String.join(" ", fs))); n++;
            }
        }
        println("ExportAll: " + fm.getFunctionCount() + " functions, " + n + " strings");
        if (!decomp) return;
        File dd = new File(out, "decomp"); dd.mkdirs(); List<Function> fl = new ArrayList<>(); for (Function f : fm.getFunctions(true)) fl.add(f);
        ExecutorService ex = Executors.newFixedThreadPool(16); ThreadLocal<DecompInterface> tl = ThreadLocal.withInitial(() -> { DecompInterface di = new DecompInterface(); di.openProgram(currentProgram); return di; });
        List<Future<?>> fut = new ArrayList<>(); final int[] done = {0};
        for (Function f : fl) fut.add(ex.submit(() -> {
            try { DecompileResults r = tl.get().decompileFunction(f, 40, monitor); String src = r.decompileCompleted() ? r.getDecompiledFunction().getC() : "/* decompilation failed: " + r.getErrorMessage() + " */";
                try (PrintWriter p = new PrintWriter(new File(dd, f.getEntryPoint() + ".c"))) { p.println("// " + f.getName() + " @ 0x" + f.getEntryPoint()); p.print(src); } } catch (Exception e) { }
            synchronized (done) { if (++done[0] % 1000 == 0) println("decompiled " + done[0] + " / " + fl.size()); }
        }));
        for (Future<?> x : fut) x.get(); ex.shutdown(); println("ExportAll: decompiled " + fl.size() + " functions");
    }
}
