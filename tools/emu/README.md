# tools/emu: run firmware functions on a PC

`fw_emu.py` loads the main image of R390XXU0AZA3 (`local/re/main-stock.bin`, never in git) into Unicorn (Cortex-M4, Thumb) and calls single functions.
`probe_lvgl.py` uses it to check the LVGL claims of `docs/research/T1-lvgl.md`; results in `docs/research/T6-emulator.md`.

## Setup (once)

```
python3 -m venv local/venv && local/venv/bin/pip install unicorn capstone      # local/ is outside git
```

## Use

```
local/venv/bin/python -I tools/emu/probe_lvgl.py          # PASS/FAIL per claim; exit 1 on any FAIL
local/venv/bin/python -I tools/emu/test_emu.py            # tests of the harness and of the probe (skips without the image)
```

```python
import sys; sys.path.insert(0, "tools/emu")
from fw_emu import FwEmu
e = FwEmu()
e.call(0x2c27cb30)                       # lv_init
scr = e.call(0x2c27cb84, 0)              # lv_obj_create(NULL) -> r0; e.u32(scr + 0x24) is the flags word
e.hook(0x2c28a9fc, lambda em: 0)         # replace a firmware function by Python; e.stub(addr, ret) returns a constant
```

A display is needed before widgets exist: see `Probe._display` (draw buffer + driver + `lv_disp_drv_register`, a replay of `disp_init`).

## What is emulated

- Flash at `0x2c080000` and as a copy at `0x0c080000` (code runs through both; `hook()` patches both). 8 MB RAM at `0x20000000`.
- Heap: the firmware allocator (`0x2c14a7e4/ec/fe`) is replaced by a bump allocator that fills memory with `0xA5`, so fields a constructor does not write are visible. Requested sizes are in `e.allocs`.
- Any other address (peripherals, unmapped) is mapped as a zero page on first touch and logged in `e.mmio_log`; a call into unmapped code returns 0 (`e.unmapped_fetch`). A runaway call raises `EmuTimeout`, a CPU fault `EmuFault` (`e.trace()` keeps the last PCs).

## Limits (all of them matter)

- No C-runtime start-up: **`.data` is not initialised** (we did not find where the image keeps it). Function pointers in `.data` are NULL; `seed_text_functions()` installs Python versions of the two lv_txt pointers that labels need. Other `.data` values read as 0.
- No interrupts, no RTOS, no timers, no real display or touch: `lv_timer_handler`, flushing and indev reads are not run. Time-dependent behaviour is not tested.
- Jumps into the peripheral range (`0x40000000..0x5fffffff`) fault (execute-never).
- Code written into RAM after it ran needs `write_code()` (translation cache flush).
- It checks what the firmware code writes into memory, not how the real watch behaves; a PASS here is "the function does this on a fresh LVGL state".

## Tests of the loader

`test_loader_v2.py` (the tennis window; `F3_WINDOW`, `F3_CREATE`, `F3_EVENT`, `F3_IMAGE` select another replaced window), `test_icon.py` (the app-list icon), `test_slots.py` (builds a package for
every replaceable app-list entry and runs the window test on each; run it with the system `python3 -I`, it starts the emulator's venv itself). The window tests need the patched main image:
`python3 -I tools/firmware/fwx.py local/firmware/<package>.bin main local/re/main-v2.bin`.

## Screenshots of the tennis window (`screenshot.py`)

`local/venv/bin/python -I tools/emu/screenshot.py build/shots` renders a short match (empty page, in progress, stats, finished) by running **the firmware's own LVGL code** in the emulator: the
fonts are loaded by the firmware's `fonts_init` from the files you pulled from your watch (`tools/device/f3_pull.py`, `local/assets/fonts`), the window is created by the patched stock address and
LVGL's software renderer draws into a 256 x 402 RGB565 buffer. Text, colours, cards, pills and layout are what the watch computes.

Known limit: **a filled box that is a child of a card with rounded corners is drawn black** (our serve dot) or not at all (our divider) here, while the same box on the screen or in a square card
is right. It is not known whether the watch does the same (it probably does not: the stock pages have such children). Do not use these pictures to judge those two details; the emulator also
fails when such a box overlaps a card on the screen level. The renderer needs `unicorn` and Pillow in the venv (`local/venv/bin/pip install unicorn capstone pillow`).
