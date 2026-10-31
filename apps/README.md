# apps/

| App | What | Notes |
|---|---|---|
| `tenis/` | tennis score tracker: points, games, sets, tie-break, serve, durations, 16-step undo, statistics page | verified on the watch; `test_logic.c` tests the scoring on a PC |
| `styledemo/` | the watch's own Roboto fonts and dark cards, pills and a switch | font loading from `/nand/` is being verified |
| `include/f3font.h` | reads LVGL binary fonts and draws anti-aliased text | header-only, no libc |
| `include/f3ui.h` | palette and widgets in the stock look | colours are estimates |

Each app is `apps/<name>/<name>.c` plus a one-line `meta` (launcher id, colours, names). Build with `python3 -I tools/build_app.py <name>`, run with `sim/run.sh <name>`.
Rules of thumb and lessons: [../docs/apps.md](../docs/apps.md).
