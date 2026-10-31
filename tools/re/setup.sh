#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# One-time setup of the reverse-engineering toolchain under local/tools (git-ignored, no root needed): the latest Ghidra and the JDK it asks for.
# Ghidra reads its minimum Java version from Ghidra/application.properties (12.2 needs JDK 25), so the JDK is fetched after Ghidra is unpacked.
# Idempotent: it only downloads what is missing. About 570 MB + 140 MB. Then: source tools/re/env.sh; tools/re/analyze.sh <name> <main-image.bin> [decomp]
set -e
cd "$(dirname "$0")/../.."; mkdir -p local/tools; cd local/tools
if ! ls -d ghidra_* >/dev/null 2>&1; then
  URL=$(curl -s https://api.github.com/repos/NationalSecurityAgency/ghidra/releases/latest | python3 -c 'import json,sys; print([a["browser_download_url"] for a in json.load(sys.stdin)["assets"] if a["name"].endswith(".zip")][0])')
  echo "downloading $URL"; curl -L -o ghidra.zip "$URL"; unzip -q ghidra.zip; rm ghidra.zip
fi
JV=$(grep -E '^application.java.min=' ghidra_*/Ghidra/application.properties | head -1 | cut -d= -f2)
if ! ls -d jdk-${JV}* >/dev/null 2>&1; then
  echo "downloading JDK $JV"; curl -L -o jdk.tar.gz "https://api.adoptium.net/v3/binary/latest/${JV}/ga/linux/x64/jdk/hotspot/normal/eclipse"; tar xzf jdk.tar.gz; rm jdk.tar.gz
fi
sed -i "s#jdk-[0-9]*\*#jdk-${JV}*#" ../../tools/re/env.sh
ls -d ghidra_* jdk-*
