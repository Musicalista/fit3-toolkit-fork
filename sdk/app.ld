/* SPDX-License-Identifier: Apache-2.0 */
/* Linker script for Fit3 light apps. The whole app is one flat image linked at address 0: code, read-only data and initialised data in that order,
 * followed by the zero-initialised data, which is not stored in the file. tools/appcc.py reads __image_end and __bss_end to fill in the file header. */
ENTRY(f3app_main)
SECTIONS
{
    . = 0;
    .text : { *(.text.f3app_main) *(.text .text.*) *(.rodata .rodata.*) }
    .data : { *(.data .data.*) }
    __image_end = .;
    .bss (NOLOAD) : { *(.bss .bss.*) *(COMMON) }
    __bss_end = .;
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) *(.eh_frame*) }
}
