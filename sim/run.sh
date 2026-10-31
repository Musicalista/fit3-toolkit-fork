#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# usage: sim/run.sh <app> [sim_gui.py args]     e.g.  sim/run.sh tenis      sim/run.sh styledemo --data local/assets/fonts
# builds apps/<app>/<app>.c for the PC and opens it in a window; the simulated watch's files (saves, and fonts when you point --data at local/assets/fonts)
# live in the --data folder, default sim/data. Nothing outside this repository is needed (the SDK is sdk/).
# one-time: python3 sim/genfont.py sim/kbd_font.h      (stand-in 8x12 font, see sim/README.md; run.sh does it when the file is missing)
set -e
cd "$(dirname "$0")/.."; APP=${1:?app name}; shift || true
SRC=apps/$APP/$APP.c; [ -f "$SRC" ] || { echo "no such app: $SRC" >&2; exit 1; }
[ -f sim/kbd_font.h ] || python3 -I sim/genfont.py sim/kbd_font.h
mkdir -p build
gcc -shared -fPIC -O1 -finput-charset=UTF-8 -fexec-charset=ISO-8859-1 -I sdk -I apps/include -I sim -o build/libsim_$APP.so sim/sim_live.c sim/host_api.c "$SRC"
exec python3 -I sim/sim_gui.py build/libsim_$APP.so "$@"
