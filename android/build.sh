#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# build.sh: builds android/fit3-apps.apk with the Android SDK tools only (no Gradle, no libraries).
#   ANDROID_HOME=/path/to/sdk sh android/build.sh       needs platforms;android-34 and build-tools;35.0.0, a JDK 17+
# Signed with a debug key kept in local/ (git-ignored), created on the first build.
set -eu
cd "$(dirname "$0")"
SDK=${ANDROID_HOME:?set ANDROID_HOME}; BT=$SDK/build-tools/35.0.0; JAR=$SDK/platforms/android-34/android.jar
OUT=../local/android; KS=../local/android-debug.keystore
rm -rf "$OUT"; mkdir -p "$OUT/res" "$OUT/classes" "$OUT/dex"
"$BT/aapt2" compile --dir res -o "$OUT/res.zip"
"$BT/aapt2" link -o "$OUT/base.apk" -I "$JAR" --manifest AndroidManifest.xml "$OUT/res.zip" --java "$OUT/gen" --min-sdk-version 26 --target-sdk-version 34
javac -nowarn --release 11 -encoding UTF-8 -classpath "$JAR" -d "$OUT/classes" $(find src "$OUT/gen" -name '*.java')
"$BT/d8" --min-api 26 --release --lib "$JAR" --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')
cp "$OUT/base.apk" "$OUT/unsigned.apk"; (cd "$OUT/dex" && zip -q -j ../unsigned.apk classes.dex)
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
[ -f "$KS" ] || keytool -genkeypair -keystore "$KS" -storepass android -keypass android -alias debug -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=fit3-toolkit debug" >/dev/null 2>&1
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android --out ../local/out/fit3-apps.apk "$OUT/aligned.apk"
"$BT/apksigner" verify ../local/out/fit3-apps.apk && echo "wrote local/out/fit3-apps.apk ($(wc -c < ../local/out/fit3-apps.apk) bytes)"
