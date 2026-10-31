// SPDX-License-Identifier: Apache-2.0
// Creates Thumb functions at the code pointers found in the image (function-pointer tables, literal pools, the 0x0c... alias used by the registry), before the auto analysis.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.ProgramContext;
import java.math.BigInteger;

public class SeedFunctions extends GhidraScript {
    @Override
    public void run() throws Exception {
        long base = currentProgram.getMinAddress().getOffset(), size = currentProgram.getMemory().getBlocks()[0].getSize();
        try {   // the flash alias 0x0c...: jump tables and pointers use it, so map it onto the image (otherwise the decompiler cannot follow them)
            Address alias = toAddr(base - 0x20000000L);
            if (currentProgram.getMemory().getBlock(alias) == null)
                currentProgram.getMemory().createByteMappedBlock("flash_alias", alias, toAddr(base), size, false);
        } catch (Exception e) { println("alias block not created: " + e); }
        byte[] b = new byte[(int) size]; currentProgram.getMemory().getBytes(toAddr(base), b);
        Register tmode = currentProgram.getLanguage().getRegister("TMode"); ProgramContext ctx = currentProgram.getProgramContext();
        int seeded = 0, skipped = 0;
        for (int o = 0; o + 4 <= size; o += 4) {
            long v = (b[o] & 0xffL) | ((b[o + 1] & 0xffL) << 8) | ((b[o + 2] & 0xffL) << 16) | ((b[o + 3] & 0xffL) << 24);
            if ((v >>> 24) == 0x0c) v += 0x20000000L;                       // flash alias used by function-pointer tables
            if ((v & 1) == 0 || v - 1 < base || v - 1 + 4 > base + size) continue;
            int t = (int) (v - 1 - base), h1 = (b[t] & 0xff) | ((b[t + 1] & 0xff) << 8), h2 = (b[t + 2] & 0xff) | ((b[t + 3] & 0xff) << 8);
            boolean prologue = (h1 & 0xFF00) == 0xB500 || (h1 == 0xE92D && (h2 & 0x4000) != 0);       // push {..., lr} / stmdb sp!, {..., lr}
            if (!prologue) continue;
            Address a = toAddr(v - 1);
            if (getFunctionAt(a) != null || getInstructionContaining(a) != null) continue;
            try {
                ctx.setValue(tmode, a, a, BigInteger.ONE);
                if (disassemble(a)) { createFunction(a, null); seeded++; }
            } catch (ghidra.program.model.listing.ContextChangeException e) { skipped++; }
        }
        println("SeedFunctions: " + seeded + " functions seeded, " + skipped + " skipped (context conflict)");
    }
}
