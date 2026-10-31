#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# usage: tools/re/analyze.sh <name> <main-image.bin> [decomp]
# Imports a main image (a raw binary linked at 0x2c080000, see tools/firmware/fwx.py) into a Ghidra project in local/re/proj, seeds Thumb functions from the code
# pointers found in the image, runs the auto analysis and exports functions, strings (with references), calls and, with `decomp`, the decompiled C of every function.
# Results: local/re/<name>/{functions,strings,calls}.csv and local/re/<name>/decomp/<address>.c. Takes a while; run it in the background.
set -e
source "$(dirname "$0")/env.sh"
NAME=${1:?name}; IMG=$(realpath "${2:?image}"); MODE=${3:-}
mkdir -p "$RE_OUT/proj" "$RE_OUT/$NAME"
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$RE_OUT/proj" Fit3 -import "$IMG" -overwrite -loader BinaryLoader -loader-baseAddr 0x2c080000 -processor "ARM:LE:32:Cortex" \
  -scriptPath "$(dirname "$0")/scripts" -preScript SeedFunctions.java -postScript ExportAll.java "$RE_OUT/$NAME" $MODE 2>&1 | tee "$RE_OUT/$NAME/analyze.log" | grep -E "INFO.*(Import|Analysis|ANALYZING|SeedFunctions|ExportAll|REPORT)|ERROR|Exception" | cut -c1-220
