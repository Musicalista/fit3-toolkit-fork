# sim/

A PC simulator for light apps. `host_api.c` is a software version of the loader's API (`F3Api`, see [../sdk/README.md](../sdk/README.md)): a 256 x 402 RGB565 canvas, clipped
`rect/rrect/disc/text/ctext/num`, an 8 x 12 text grid, files in a folder, a simulated clock and battery, `vibrate` logged to stderr, `malloc` with a leak count. `sim_live.c` exports it to
Python (ctypes) and `sim_gui.py` shows it in a Tk window (mouse = finger, the top-right corner = the loader's close button). Needs `gcc`, Python with Tk, NumPy and Pillow; nothing outside this repository.

```
python3 -I sim/genfont.py sim/kbd_font.h              # once (run.sh does it if missing); makes the stand-in font from the Linux console font
sim/run.sh tenis                                      # build and open an app from apps/
sim/run.sh styledemo --data local/assets/fonts        # --data = the simulated watch's files (only the last path component of a file name is used)
python3 -I sim/sim_gui.py build/libsim_tenis.so --shot out.ppm --script "128,100 t30"   # no window; taps "x,y", idle ticks "tN"
python3 -I sim/sim_gui.py build/libsim_tenis.so --monkey 3                                # no window; 6000 random gestures, checks the app survives and frees its memory
```

`--lang pt` sets the Portuguese flag. The monkey run exits with status 1 if the app quits early or calls the API with arguments no loader should see (negative sizes, text scale outside 1..12, bad file descriptors).
For logic tests without the simulator see `apps/tenis/test_logic.c` (it `#include`s the app and calls its functions).

The stand-in font has the right cell size (8 x 12) but not the watch's glyph shapes, and the simulator does not model the loader's scrolling, vibration or screen-off behaviour; `wday` counts from 0 = Sunday
because the real numbering is not documented. `sim/data/` and `sim/kbd_font.h` are generated and git-ignored.
