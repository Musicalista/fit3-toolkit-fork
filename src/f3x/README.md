# f3x: the installable app format

`.f3x` is one app as a file: compiled code, its icon and the list of addresses to move when it is loaded. The Application Hub on the watch reads it from `/user/hub/aNN.f3x` (16 slots), checks the CRC,
relocates it in the heap and runs it. The format in full: [docs/f3x.md](../../docs/f3x.md).

| File | What |
|---|---|
| [`build_f3x.py`](build_f3x.py) | C source of an app → an `.f3x` file; `--check` validates a file |
| [`f3x.py`](f3x.py) | the format: build, parse, relocations, refusals |
| [`test_f3x_format.py`](test_f3x_format.py) | tests of the format and of everything the builder refuses |

```sh
python3 -I src/f3x/build_f3x.py src/watch/apps/counter.c counter.f3x                  # build (name and icon come from the source)
python3 -I src/f3x/build_f3x.py src/watch/apps/counter.c counter.f3x --name "Count" --icon my64x64.png
python3 -I src/f3x/build_f3x.py --check counter.f3x                                    # what is inside, and is it valid
python3 -I src/f3x/test_f3x_format.py                                                  # tests
```

The builder compiles the app **twice**, linked at two different addresses, and keeps the words that differ: those are the addresses to move. It refuses an app with `.data` or `.bss`, calls to libc or
libgcc, or an image over 32 kB. Nothing is sent to a watch from here; [`src/device/f3x_install.py`](../device/README.md) does that.
