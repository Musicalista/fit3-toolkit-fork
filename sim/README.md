# sim/

A PC simulator for light apps: `sim_live.c` wraps the SDK's `host_game.c` (a software version of the loader's API, 256 x 402 RGB565) and `sim_gui.py` shows it in a Tk window
(mouse = finger, the top-right corner = the loader's close button). Needs `gcc`, Python with Tk, NumPy and Pillow, and the SDK checkout in `fit3-store/`.

```
python3 -I sim/genfont.py sim/kbd_font.h              # once; the SDK's own font header is not published
sim/run.sh tenis                                      # build and open an app from apps/ (or from the SDK's apps/src)
sim/run.sh styledemo --data local/assets/fonts        # --data = the simulated watch's files
python3 -I sim/sim_gui.py build/libsim_tenis.so --shot out.ppm --script "128,100 t30"   # no window; taps "x,y", idle ticks "tN"
```

The stand-in font has the right cell size (8 x 12) but not the watch's glyph shapes, and the simulator does not model the loader's scrolling, vibration or screen-off behaviour.
`sim/data/` and `sim/kbd_font.h` are generated and git-ignored.
