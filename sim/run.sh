#!/bin/bash
# usage: sim/run.sh <app> [sim_gui.py args]     e.g.  sim/run.sh tenis      sim/run.sh styledemo --data local/assets/fonts
# builds apps/<app>/<app>.c (or the SDK's own fit3-store/apps/src/<app>.c) for the PC and opens it in a window; the simulated
# watch's files (saves, and fonts when you point --data at local/assets/fonts) live in the --data folder, default sim/data.
# one-time: python3 sim/genfont.py sim/kbd_font.h      (stand-in 8x12 font, see sim/README.md)
set -e
cd "$(dirname "$0")/.."; APP=${1:?app name}; shift || true
SRC=apps/$APP/$APP.c; [ -f "$SRC" ] || SRC=fit3-store/apps/src/$APP.c
[ -f sim/kbd_font.h ] || python3 -I sim/genfont.py sim/kbd_font.h
mkdir -p build
gcc -shared -fPIC -O1 -finput-charset=UTF-8 -fexec-charset=ISO-8859-1 -I apps/include -I fit3-store/apps -I sim -o build/libsim_$APP.so sim/sim_live.c "$SRC"
exec python3 -I sim/sim_gui.py build/libsim_$APP.so "$@"
