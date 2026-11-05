# android: Fit3 Apps, a phone app for the installable apps

An Android app (Java, no libraries, minSdk 26) that does what `src/device/f3x_install.py` does, from the phone: it lists the sixteen slots `/user/hub/a00.f3x .. a15.f3x`, installs an
`.f3x` file you pick (into the slot of an app with the same name, or the first free one), and removes an app by writing the tombstone. Every write is read back and compared, as the PC tool does.
It also sends a Game Boy ROM to `/user/gb/rom.gb` for the Game Boy app (the same **Instalar** button: the file is recognised as a ROM by its header). It writes nothing else: the protocol code (`Link.java`) refuses every other path and every file that is not a valid `.f3x` for R390XXU0AZA3 or (for `/user/gb/rom.gb` only) a Game Boy ROM. It cannot flash firmware.

Needs on the watch the hub firmware **with the Bluetooth patches** (the default build) and the hub opened once (it creates `/user/hub`). On the phone: **force-stop Galaxy Wearable** first; the watch
serves one session at a time. The connection is RFCOMM channel 29 (the PC tools' channel), with the service UUID as a fallback. Tried on a phone: reading the slots and installing apps work.

## Build

```sh
ANDROID_HOME=/path/to/sdk sh android/build.sh          # platforms;android-34, build-tools;35.0.0, JDK 17+  ->  local/out/fit3-apps.apk (debug-signed, key in local/)
```

## Test (no phone)

`android/test/LinkTest.java` runs `Link` and `F3x` on a plain JVM against `src/device/mock_watch.py` (served over TCP by `mock_tcp.py`):

```sh
javac --release 11 -cp $ANDROID_HOME/platforms/android-34/android.jar -d local/android/test android/src/org/fit3/manager/{F3x,Link}.java android/test/org/fit3/manager/LinkTest.java
python3 -I android/test/mock_tcp.py 47123 &
java -cp local/android/test:$ANDROID_HOME/platforms/android-34/android.jar org.fit3.manager.LinkTest 47123 some.f3x
```
