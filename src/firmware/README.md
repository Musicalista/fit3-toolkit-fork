# firmware: read, patch and rebuild packages

A firmware package is a `.bin` container with a header, the updater and a packet of components, each checked with a CRC32 ([docs/firmware.md](../../docs/firmware.md)). You bring the stock one;
nothing of Samsung's is here.

| Tool | Does |
|---|---|
| [`build_package.py`](build_package.py) | stock package + Bluetooth patches + our code in the free flash + the take-over of an app-list entry + name + icon, every checksum repaired and validated. Usually called by [`../build_firmware.py`](../README.md). `--list-slots` prints the entries you can replace |
| [`validate_fwd.py`](validate_fwd.py) | an independent re-implementation of the checks of [fit3-flasher](https://github.com/yuriyurin/fit3-flasher): layout, every CRC32, the stock updater's SHA-256 |
| [`fwd.py`](fwd.py) | the library: `Package.load()`, `raw(path)`, `set_raw(path, data)`, `save()`. Loading and saving reproduce a package byte for byte |
| [`fwx.py`](fwx.py) | list and extract components (read-only) |

```sh
python3 -I src/firmware/validate_fwd.py hub.bin                            # check a package before you flash it
python3 -I src/firmware/fwx.py stock-aza3.bin list                         # the components of a package
python3 -I src/firmware/fwx.py stock-aza3.bin main main.bin               # the main image (code is linked at 0x2c080000 + file offset)
python3 -I src/firmware/build_package.py stock-aza3.bin --list-slots       # which entries of the app list can be replaced
```

The tests (`test_fwd.py`, `test_build_package.py`) need your stock package at `local/firmware/stock-aza3.bin` and are skipped without it. Every old byte that a patch replaces is checked first: on
another firmware version the build stops and writes nothing.
