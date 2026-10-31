# SPDX-License-Identifier: Apache-2.0
"""Tests of fw_emu.py and probe_lvgl.py. Needs local/re/main-stock.bin and the unicorn package (local/venv); skipped otherwise.
    local/venv/bin/python -I tools/emu/test_emu.py"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
IMG = os.path.join(HERE, "..", "..", "local", "re", "main-stock.bin")
try: import unicorn
except ImportError: sys.exit("skip: unicorn not installed (python3 -m venv local/venv; local/venv/bin/pip install unicorn capstone)")
if not os.path.exists(IMG): sys.exit("skip: local/re/main-stock.bin not found")
import fw_emu, probe_lvgl
ok = 0
e = fw_emu.FwEmu(IMG)
# image is mapped twice and identical
assert e.u32(0x2c081000) == 0x11223344 and e.u32(0x0c081000) == 0x11223344; ok += 1
# a pure function of the firmware: lv_mem_zero-style helper 0x2c28a9fc(p, len) (memset 0) writes zeros
p = e.alloc(16)
e.call(0x2c28a9fc, p, 8); assert e.read(p, 8) == bytes(8) and e.read(p + 8, 1) == bytes([0xA5]); ok += 1
# hook replaces a function and returns its value; stack arguments are visible
e.hook(0x2c28a9fc, lambda em: 0x1234); assert e.call(0x2c28a9fc, p, 8) == 0x1234; ok += 1
# MMIO and unmapped code never abort: a peripheral read returns 0 and is logged; a jump into nowhere returns 0 to the caller
e2 = fw_emu.FwEmu(IMG); snip = e2.alloc(8); e2.write(snip, bytes.fromhex("0868 7047".replace(" ", "")))      # ldr r0,[r1]; bx lr
assert e2.call(snip, 0, 0x40001000) == 0 and e2.mmio_log and e2.mmio_log[0][0] == 0x40001000; ok += 1
e2.write_code(snip, bytes.fromhex("0847"))                                                                        # bx r1
r = e2.call(snip, 5, 0x00300001); assert r == 0 and e2.unmapped_fetch == [0x00300000], (r, e2.unmapped_fetch); ok += 1
# a runaway function raises EmuTimeout instead of hanging
e3 = fw_emu.FwEmu(IMG, max_insns=50)
try: e3.call(0x2c27cb30); sys.exit("FAIL: no timeout")
except fw_emu.EmuTimeout: ok += 1
# the structure claims of docs/details.md
res = probe_lvgl.Probe(IMG).run(); fails = [r for r in res if r[0] == "FAIL"]
assert not fails, fails; assert sum(r[0] == "PASS" for r in res) >= 35; ok += 1
print("%d checks passed (LVGL probe: %d PASS, %d SKIP)" % (ok, sum(r[0] == "PASS" for r in res), sum(r[0] == "SKIP" for r in res)))
