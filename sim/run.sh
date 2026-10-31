#!/bin/bash
# usage: sim/run.sh [app] [extra sim_gui.py args]   (default app: tenis). The save files of the simulated watch live in sim/data.
set -e
cd "$(dirname "$0")/.."; APP=${1:-tenis}; shift || true
gcc -shared -fPIC -O1 -finput-charset=UTF-8 -fexec-charset=ISO-8859-1 -I fit3-store/apps -I sim -o sim/libsim_$APP.so sim/sim_live.c fit3-store/apps/src/$APP.c
exec python3 -I sim/sim_gui.py sim/libsim_$APP.so "$@"
