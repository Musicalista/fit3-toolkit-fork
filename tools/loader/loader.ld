/* link address of the loader in the free flash of R390XXU0AZA3 (stock has zeros from 0x2c3a0524 to 0x2c3af920; build_package.py checks it) */
MEMORY { FLASH (rx) : ORIGIN = 0x2c3a0524, LENGTH = 0xF3FC }
SECTIONS {
  .text : { KEEP(*(.text.entry)) *(.text .text.*) *(.rodata .rodata.*) . = ALIGN(4); } > FLASH
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) *(.ARM.attributes) }
}
ASSERT(SIZEOF(.text) > 0, "empty loader")
