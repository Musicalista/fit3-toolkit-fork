# The watch's fonts and images

These files are on the watch (`/nand/system/font/`, `/nand/system/image/`), not in firmware packages. Read them with `tools/device/f3_pull.py` (read-only). They are
Samsung's: keep your copies in `local/` (git-ignored) and do not redistribute them; see [legal.md](legal.md).

## Fonts: LVGL binary fonts

`FONT_ROBOTO_<size>_GBK_en.bin`, `FONT_ROBOTO_MEDIUM_<size>_GBK_en.bin`, `FONT_ROBOTO_BOLD_60_GBK_en.bin`, `FONT_LED_DIGITAL_32_GBK_en.bin`. The format is the one written by
`lv_font_conv --format bin` (LVGL 8): a sequence of tables, each `u32 length | 4-char tag | data`: `head`, `cmap`, `loca`, `glyf`, `kern`.

- `head` (offsets from the table start): `+8` version, `+14` size, `+16` ascent, `+18` descent (signed), `+34` index_to_loc_format, `+36` advance format (1 = 1/16 px),
  `+37` bits per pixel, `+38` xy bits, `+39` wh bits, `+40` advance bits, `+41` compression (0 here).
- `cmap`: `+8` subtable count, 16-byte headers (data offset, first code, range length, first glyph id, entry count, format, pad). Formats seen: 2 (consecutive) and 3 (sparse list).
- `loca`: `+8` entry count, then u16 (or u32) offsets **from the start of the `glyf` table**.
- `glyf`: per glyph a bit stream: advance, x, y (signed), w, h, then w*h pixels of `bpp` bits, MSB first. The glyph is drawn with its bottom at `baseline - y`.

All the fonts we pulled are uncompressed, 2 bits per pixel, ASCII 0x20..0x7a (some also `°`); the big ones are digits only (Bold 60, Medium 86, LED 32). Sizes: 0.9 to 50 KB.
`tools/assets/lvfont.py` decodes them on a PC; `apps/include/f3font.h` does it on the watch. No kerning is applied.

## Images: `app_*.res`, `common.res`, ...

A pack of records without a directory. The type we decoded: `hdr(4) | "IDX8" "IDX8" | width u16 BE | height u16 BE | palette bytes u16 BE | 2 bytes | width*height palette indices | palette (BGRA, 4 bytes per colour)`.
`app_worldclock.res` starts with the 256 x 189 picture of the globe that is the World clock background (the first record). Other records (some without the `IDX8` tag, some with
a different header) are **not decoded yet**, and we have not looked at which pack holds the icons of the app list.
