# tools/re/

Reverse-engineering helpers around **Ghidra** (headless). The ad-hoc scripts used so far were `arm-none-eabi-objdump` plus Python scans (see [docs/firmware.md](../../docs/firmware.md)); this replaces them
with a real analysis: automatic function discovery, cross references, a call graph and decompiled C for every function.

| File | What |
|---|---|
| `setup.sh` | downloads Ghidra and the JDK it needs into `local/tools` (once) |
| `env.sh` | `source` it: sets `JAVA_HOME`, `GHIDRA_INSTALL_DIR` and `RE_OUT` (`local/re`) |
| `analyze.sh <name> <main.bin> [decomp]` | imports a main image (get it with `tools/firmware/fwx.py <pkg> main out.bin`; linked at `0x2c080000`), analyses it, exports `functions.csv`, `strings.csv`, `calls.csv` and with `decomp` the C of every function to `local/re/<name>/` |
| `scripts/SeedFunctions.java` | before the analysis: creates Thumb functions at code pointers found in the image (function tables, literal pools, the `0x0c......` flash alias) |
| `scripts/ExportAll.java` | after the analysis: the exports above (decompilation on 16 threads) |

**Status: runs.** On the stock main image (about 15k functions, 22k strings, 114k call edges; 16 threads for the decompilation, a few minutes) after three fixes: Ghidra 12.2 needs JDK 25, `DefinedDataIterator.definedStrings` is gone, and the flash alias `0x0c......` must be mapped (`SeedFunctions.java` does it) so jump tables resolve.
Keep the outputs in `local/` (they are derived from Samsung's firmware); share findings as notes and address/name lists, not as dumps.
