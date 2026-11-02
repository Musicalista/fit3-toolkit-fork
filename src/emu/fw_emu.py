# SPDX-License-Identifier: Apache-2.0
"""fw_emu.py: run single functions of the Fit3 main image (R390XXU0AZA3) in Unicorn on a PC.

    from fw_emu import FwEmu
    e = FwEmu()                              # loads local/re/main-stock.bin at 0x2c080000 (alias 0x0c080000)
    r0 = e.call(0x2c27cb84, 0)               # lv_obj_create(NULL); returns r0 (and r1 as e.r1)
    e.u32(addr), e.write(addr, b".."), e.cstr(addr), e.alloc(n)

Model: Cortex-M4 (Thumb-2), flash image mapped at 0x2c080000 and, as a copy, at 0x0c080000; 8 MB RAM at 0x20000000; any other
address (MMIO, unmapped) is mapped on first touch as a zero page and logged (e.mmio_log), never fatal. Functions can be replaced
by Python (hook) or stubbed (stub: return a constant). The firmware heap (0x2c14a7e4 alloc, 0x2c14a7ec realloc, 0x2c14a7fe free)
is replaced by a bump allocator that fills memory with a poison byte, so fields a constructor does not write stay recognisable.
Not emulated: interrupts, RTOS scheduling, peripherals, timing. A call that runs too long raises EmuTimeout.
Python must be run with -I; the unicorn package lives in local/venv (see src/emu/README.md)."""
import os, struct
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED, UcError,
                     UC_MEM_FETCH_UNMAPPED, UC_MEM_READ_UNMAPPED)
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR,
                               UC_ARM_REG_PC, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_CPU_ARM_CORTEX_M4)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMAGE = os.path.join(HERE, "..", "..", "local", "re", "main-stock.bin")
FLASH, ALIAS, RAM, RAM_SIZE = 0x2c080000, 0x0c080000, 0x20000000, 0x800000
STACK_TOP = RAM + RAM_SIZE - 0x1000           # stack grows down from here
HEAP_BASE, HEAP_END = RAM + 0x400000, RAM + 0x7c0000   # bump allocator area (the firmware's own statics live below 0x20140000)
RET_ADDR = 0x20000100                          # return trap: calls end when pc reaches it (inside RAM, never used by firmware)
FW_ALLOC, FW_REALLOC, FW_FREE = 0x2c14a7e4, 0x2c14a7ec, 0x2c14a7fe
ARGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)


class EmuTimeout(Exception): pass
class EmuFault(Exception): pass


class FwEmu:
    def __init__(self, image=None, poison=0xA5, max_insns=3_000_000):
        self.img = open(image or DEFAULT_IMAGE, "rb").read()
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS); self.uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
        sz = (len(self.img) + 0xfff) & ~0xfff
        for base in (FLASH, ALIAS):
            self.uc.mem_map(base, sz); self.uc.mem_write(base, self.img)
        self.uc.mem_map(RAM, RAM_SIZE)
        self.poison, self.max_insns = poison, max_insns
        self.mmio_log, self.unmapped_fetch, self.stub_log, self.calls = [], [], [], []
        self.hooks, self._pages = {}, set()
        self.heap = HEAP_BASE; self.allocs = []         # [(ptr, size)] in order
        self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._unmapped)
        self.uc.mem_write(RET_ADDR & ~1, b"\x70\x47")    # bx lr, never executed (we stop on arrival)
        self.hook(FW_ALLOC, lambda e: e._malloc(e.arg(0)))
        self.hook(FW_REALLOC, lambda e: e._realloc(e.arg(0), e.arg(1)))
        self.hook(FW_FREE, lambda e: 0)

    # ---- memory helpers
    def u32(self, a): return struct.unpack("<I", self.uc.mem_read(a, 4))[0]
    def u16(self, a): return struct.unpack("<H", self.uc.mem_read(a, 2))[0]
    def u8(self, a): return self.uc.mem_read(a, 1)[0]
    def i32(self, a): return struct.unpack("<i", self.uc.mem_read(a, 4))[0]
    def read(self, a, n): return bytes(self.uc.mem_read(a, n))
    def write(self, a, b): self.uc.mem_write(a, bytes(b))
    def write_code(self, a, b):
        """write instructions into RAM; flushes Unicorn's translation cache (a plain write() to already executed code is not noticed)"""
        self.write(a, b); self.uc.ctl_flush_tb()
    def w32(self, a, v): self.write(a, struct.pack("<I", v & 0xffffffff))
    def cstr(self, a, n=256):
        b = self.read(a, n); return b.split(b"\0")[0].decode("latin1")
    def alloc(self, n, fill=None):
        """raw scratch memory from the same bump heap (no record in .allocs)"""
        p = self.heap; self.heap = (self.heap + n + 7) & ~7; assert self.heap < HEAP_END, "emulator heap exhausted"
        self.write(p, bytes([self.poison if fill is None else fill]) * n); return p
    def put_cstr(self, s):
        b = s.encode() + b"\0"; p = self.alloc(len(b)); self.write(p, b); return p

    # ---- registers / hooks
    def reg(self, r): return self.uc.reg_read(r)
    def arg(self, i):
        if i < 4: return self.reg(ARGS[i])
        return self.u32(self.reg(UC_ARM_REG_SP) + 4 * (i - 4))   # stack args, valid inside a hook at function entry
    def hook(self, addr, fn):
        """replace the function at addr by fn(emu) -> r0 (or None); the call returns to its caller"""
        a = addr & ~1
        for x in ((a, a - 0x20000000) if FLASH <= a < FLASH + 0x400000 else (a,)):    # code also runs through the 0x0c...... alias
            if x not in self.hooks: self.uc.hook_add(UC_HOOK_CODE, self._code, begin=x, end=x)
            self.hooks[x] = fn
    def stub(self, addr, ret=0, name=None):
        """replace a function by `return ret`; logged"""
        def f(e): e.stub_log.append((name or hex(addr), e.reg(UC_ARM_REG_LR) & ~1)); return ret
        self.hook(addr, f)
    def _malloc(self, n):
        p = self.alloc(max(n, 1)); self.allocs.append((p, n)); return p
    def _realloc(self, p, n):
        q = self._malloc(n)
        if p:
            old = [s for a, s in self.allocs if a == p]; k = min(n, old[-1] if old else n); self.write(q, self.read(p, k))
        return q
    def _code(self, uc, addr, size, _):
        h = self.hooks.get(addr)
        if h is None: return
        r = h(self)
        if r is not None: uc.reg_write(UC_ARM_REG_R0, r & 0xffffffff)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    def _unmapped(self, uc, access, addr, size, value, _):
        page = addr & ~0xfff
        if access == UC_MEM_FETCH_UNMAPPED:    # UC_MEM_FETCH_UNMAPPED / FETCH_PROT: code in an unmapped page: pretend it is a function returning 0
            self.unmapped_fetch.append(addr); uc.mem_map(page, 0x1000); uc.mem_write(page, b"\x00\x20\x70\x47" * 0x400)   # movs r0,#0; bx lr
            self._pages.add(page); return True
        self._pages.add(page); uc.mem_map(page, 0x1000)
        self.mmio_log.append((page, "R" if access == UC_MEM_READ_UNMAPPED else "W", self.reg(UC_ARM_REG_PC)))
        return True

    def seed_text_functions(self):
        """The firmware keeps its UTF-8 helpers in .data function pointers (lv_txt: next at 0x200fd858, prev at 0x200fd85c, get_length at 0x200fd864);
        we do not run the C runtime start-up that fills .data, so install Python versions (UTF-8) at those three slots."""
        def nxt(e):
            txt, ip = e.arg(0), e.arg(1); i = e.u32(ip) if ip else 0; b = e.u8(txt + i)
            n = 1 if b < 0x80 else 2 if b >> 5 == 6 else 3 if b >> 4 == 14 else 4
            ch = e.read(txt + i, n).decode("utf-8", "replace")
            if ip: e.w32(ip, i + n)
            return ord(ch[0])
        def length(e): return len(e.cstr(e.arg(0), 4096).encode("latin1").decode("utf-8", "replace"))
        def prev(e):                                    # (txt, &i): the character before i; i moves back (used by the wrapping of long labels)
            txt, ip = e.arg(0), e.arg(1); i = e.u32(ip) - 1
            while i > 0 and (e.u8(txt + i) & 0xC0) == 0x80: i -= 1
            e.w32(ip, i); b = e.u8(txt + i); n = 1 if b < 0x80 else 2 if b >> 5 == 6 else 3 if b >> 4 == 14 else 4
            return ord(e.read(txt + i, n).decode("utf-8", "replace")[0])
        for slot, addr, fn in ((0x200fd858, 0x20000400, nxt), (0x200fd85c, 0x20000420, prev), (0x200fd864, 0x20000410, length)):
            self.hook(addr, fn); self.w32(slot, addr | 1)

    def trace(self, n=64):
        """keep the last n executed instruction addresses in self.last_pcs (slow; for debugging a fault)"""
        from collections import deque
        self.last_pcs = deque(maxlen=n); self.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, _: self.last_pcs.append(a))

    # ---- calling
    def call(self, addr, *args, regs=None, max_insns=None):
        """run the function at addr (Thumb) with r0-r3 = args[:4] and the rest on the stack; returns r0. r1 is kept in self.r1"""
        uc = self.uc; sp = STACK_TOP
        stack = list(args[4:]); sp -= 4 * len(stack); sp &= ~7
        for i, v in enumerate(stack): self.w32(sp + 4 * i, v)
        for r, v in zip(ARGS, args[:4]): uc.reg_write(r, v & 0xffffffff)
        for r, v in (regs or {}).items(): uc.reg_write(r, v)
        uc.reg_write(UC_ARM_REG_SP, sp); uc.reg_write(UC_ARM_REG_LR, RET_ADDR | 1)
        self.calls.append(addr)
        try: uc.emu_start(addr | 1, RET_ADDR, count=max_insns or self.max_insns)
        except UcError as ex: raise EmuFault("%s at pc=%#x calling %#x" % (ex, self.reg(UC_ARM_REG_PC), addr))
        if self.reg(UC_ARM_REG_PC) & ~1 != RET_ADDR & ~1: raise EmuTimeout("%#x did not return in %d instructions (pc=%#x)" % (addr, max_insns or self.max_insns, self.reg(UC_ARM_REG_PC)))
        self.r1 = self.reg(UC_ARM_REG_R1); return self.reg(UC_ARM_REG_R0)
