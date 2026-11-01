# src/re/

Reverse-engineering helpers around **Ghidra** (headless): automatic function discovery, cross references, a call graph and decompiled C for every function of the main image. The findings are in [docs/details.md](../../docs/details.md) and [docs/symbols.csv](../../docs/symbols.csv).

| File | What |
|---|---|
| `setup.sh` | downloads Ghidra and the JDK it needs into `local/tools` (once) |
| `env.sh` | `source` it: sets `JAVA_HOME`, `GHIDRA_INSTALL_DIR` and `RE_OUT` (`local/re`) |
| `analyze.sh <name> <main.bin> [decomp]` | imports a main image (get it with `src/firmware/fwx.py <pkg> main out.bin`; linked at `0x2c080000`), analyses it, exports `functions.csv`, `strings.csv`, `calls.csv` and with `decomp` the C of every function to `local/re/<name>/` |
| `scripts/SeedFunctions.java` | before the analysis: creates Thumb functions at code pointers found in the image (function tables, literal pools, the `0x0c......` flash alias) |
| `scripts/ExportAll.java` | after the analysis: the exports above (decompilation on 16 threads) |

On the stock main image (about 15k functions, 22k strings, 114k call edges) the analysis takes a few minutes, the decompilation runs on 16 threads. `setup.sh` fetches the latest Ghidra and the JDK it asks for (12.2 asked for JDK 25); `SeedFunctions.java` maps the flash alias `0x0c......` so that jump tables resolve.

> [!CAUTION]
> The outputs are derived from Samsung's firmware: keep them in `local/` (git-ignored). Share findings as notes and address/name lists, never as dumps.
