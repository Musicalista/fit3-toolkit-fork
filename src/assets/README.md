# assets: decoders and generators

Notes on the formats: [docs/assets.md](../../docs/assets.md). Tools that read the watch's resources (which you copy from your own watch with [`../device/f3_pull.py`](../device/README.md); they are Samsung's, keep them local) and tools that draw our own.

| Tool | Does |
|---|---|
| [`lvres.py`](lvres.py) | decode the image packs (`/nand/system/image/*.res`): `info`, `png`, `ids`, `icons` |
| [`lvlang.py`](lvlang.py) | read the language packs: strings by ID, embedded fonts |
| [`lvfont.py`](lvfont.py) | decode the watch's LVGL fonts and render text to a PNG |
| [`mkfont.py`](mkfont.py) | a TTF to a static LVGL font in C (Latin and the Polish letters) for the reply keyboard |
| [`mkicon.py`](mkicon.py) | **our own** app icons (tennis, hub, counter, dice, mars) as 64 × 64 images for the firmware and for the hub's list |
| [`test_lvres.py`](test_lvres.py) | a test of the image-pack decoder on a synthetic pack |

```sh
python3 -I src/assets/lvres.py png pack.res out/                                  # one PNG per image of a pack
python3 -I src/assets/lvfont.py FONT_ROBOTO_22_GBK_en.bin "Hello 12:30" hello.png 4
python3 -I src/assets/mkicon.py build/icon.bin build/icon.png --kind mars         # the icon and a preview
```

`mkicon.py` needs numpy and Pillow. To give an app a drawn icon, add its glyph and colour to `mkicon.py`; or give `build_f3x.py` a 64 × 64 PNG of your own.
