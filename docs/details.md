# Details: how the Fit3 firmware works, as far as this project needs it

For the Samsung Galaxy Fit3 (SM-R390), firmware **R390XXU0AZA3** only. Addresses are those of its main image (linked at `0x2c080000`: the offset in the file is the address minus `0x2c080000`;
pointers stored in tables often use the alias `0x0c......`, add `0x20000000`). Named addresses are in [symbols.csv](symbols.csv). These are our findings, meant for interoperability; they quote no Samsung code.

Confidence marks: **watch** = seen working on a real watch, **emu** = the real firmware code run on the PC (`src/emu`), **code** = read from the disassembly, **?** = unknown.

## 1. The platform

- BES1502x (Cortex-M4F, Thumb-2), FreeRTOS, **LVGL 8.3.x** (minor version unknown) with `LV_USE_LARGE_COORD`: `lv_obj_t` is 44 bytes, coordinates are 32-bit, the flags word is at `+0x24`,
  `lv_area_t` is 16 bytes. `LV_EVENT_DELETE` is **33**. `lv_scr_load` has no animation; transitions are the window manager's own (section 2). [emu, code]
- Display **256 x 402**, RGB565, two full-frame buffers of `0x32400` bytes. Stock content is 254 px wide (1 px margin). [code]
- All UI code runs in one task (`thread_gui`, 12 KB stack). Whatever you call there blocks the interface: no delays, no big writes. [code]
- The image has an empty area of **62,460 bytes** (`0x2c3a0524..0x2c3af920`, zeros) where our code lives; nothing there runs at boot. [watch]

## 2. Windows: the app framework

**Window records.** The firmware has 166 windows (ids `0x00..0xa5`), one record of `0x30` bytes each: flash `0x2c3b4200 + id*0x30`, RAM copy `0x200fb4e4 + id*0x30`. [code]

| Offset | Field |
|---|---|
| `+2` | flags: low nibble = layer, `0x10` = delete the screen when leaving, `0x20` = keeps a screen snapshot, `0x40`/`0x80` = screen-off policy |
| `+0x10` | the window's `lv_obj` screen (runtime) |
| `+0x1c` | `create(param) -> lv_obj*`: builds the screen with `lv_obj_create(NULL)` |
| `+0x20` | post-enter function |
| `+0x24` | **window event function** `fn(class, kind, data)` (below) |
| `+0x28` | rarely used hook |
| `+0x2c` | `destroy()`, called just before `lv_obj_del(screen)` |

**Lifecycle.** `wm_open(op, id, arg, transition)` (`0x2c225ddc`; op 0 switch, 2 push, 3 back with id -1) creates the window with `+0x1c` if it has no screen, loads it, and sends the event function `kind 0` (entered).
Leaving sends `kind 1`; for a window with the "delete the screen" flag `destroy` follows, then `lv_obj_del`, which sends `LV_EVENT_DELETE` to the screen and its children. LCD off/on arrive as `kind 2/3` (`0x2c14b948`). [watch]

**The app list** (`0x2c2104ac`) is built from a static 12-row template at `0x2c30021c` (12 bytes per row: kind, window id, `char*` icon image-ID string, text ID). A tap calls `wm_open(2, window, 0, 0xf)`.

| Row | Window | Name | Text ID | Row | Window | Name | Text ID |
|---|---|---|---|---|---|---|---|
| 0 | `0x08` | Health | 172 | 6 | `0x1d` | Timer | 4315 |
| 1 | `0x1c` | Media Controller | 173 | 7 | `0x90` | Alarm | 179 |
| 2 | `0x22` | Find My Phone | 174 | 8 | `0x4d` | Stopwatch | 180 |
| 3 | `0x4a` | Weather | 175 | **9** | **`0x2b`** | **World Clock** | **181** |
| 4 | `0x4e` | Calendar | 176 | 10 | `0x47` | Camera Remote | 182 |
| 5 | `0x36` | Settings | 177 | 11 | `0x8c` | Calculator | 183 |

World Clock and Camera Remote are listed only when enabled in the phone app. [code]

**The window manager asks questions and uses the answers.** This is the rule that cost us the most time. The event function is not only a notification: the manager calls it and acts on the return value. [emu, watch]

| Query `(class 0, kind)` | What the manager does with the return value |
|---|---|
| `6` | writes a 16-byte table of neighbouring windows into the pointer in `data` (used to choose a transition) |
| `7` | bit 1 set: the manager runs its **own swipe-back** and picks the transition from query 9 |
| `8` | **side-key policy mask**: bit 2 the power-off menu (probably the long press), bit 6 the short press -> watch face (`wm_request(1, 2, ...)`), bit 7 double press, bit 9 another press. The stock windows answer `0x2c4`. |
| `9` | the default transition kind of that swipe |

A function that returns garbage (an uninitialised `r0`) looks like a working window with a **dead side key and a back animation that runs the wrong way**. Answer `0x2c4` to query 8 and `0` to everything else you do not
implement. The arguments reach you unmasked, use only their low byte. Keys (`0x400..0x408` messages from `thread_sidekey`) go through `wm_key_dispatch` (`0x2c225f2c`), never through LVGL.

**Keys and what they open.** `wm_key_dispatch` (`0x2c225f2c`) turns the side key's messages into actions, after asking the current window for its key policy: `0x406` the short press goes to the watch face;
`0x407` the **double press opens the app the user chose** in the watch's settings (KV `0xf8`, an index into a table of 14 windows at `0x2c315c6e`: the app list, a workout page, Health, Media Controller, Find My Phone,
Weather, Calendar, Settings, Timer, Alarm, Stopwatch, **World Clock**, Camera Remote, Calculator); `0x404` is the power-off menu. `0x408` calls `0x2c15ee70`, which is **the emergency SOS trigger**
(`app_emergency_sos_started_handle`): it must never be hooked. So an app that wants a key shortcut replaces one of those 14 windows and the user assigns the double press to it; no code patch is needed. [code]

**Transitions** (the fourth argument of `wm_open`, also stored in the history): 0 none; `0x14` / 10 the old screen slides right and reveals the target (the "back" slide); `0x13` / 9 the old screen slides left;
`0xf` / 1 the target slides in from the right (a push from the list); `0x10` / 2 the target slides in from the left; kinds 3, 4, 7, 8, `0xb`, `0xc`, `0x11`, `0x12`, `0x15`, `0x16` move vertically. Kinds come in mirror pairs
(1/10, 2/9, 15/20, 16/19, ...). [emu: the frame function was run for every kind]

**Taking a window over** (what `build_package.py` does): a `b.w` branch at the entry of the stock create and event functions of the chosen entry, and `bx lr` in its other record functions, so none of the stock code runs on
state that never exists. None of the 11 replaceable windows has other callers of these functions (Ghidra call graph). [emu; World clock also on the watch]

## 3. Resources

**Image packs** `/nand/system/image/*.res` have no directory. An image `src` is a decimal ID string (`"21"`); two flash tables map it: `0x2c300a84` (52 packs: path, first ID, last ID) and `0x2c300cf4`
(per ID: offset and size). A record is `lv_img_header_t` (4 bytes: `cf:5`, width and height, 11 bits each) plus a body. Formats seen: `cf 0x1b` Samsung IDX8 (`"IDX8"`, size, palette, indices, BGRA palette) and `cf 5`
(3 bytes per pixel: RGB565 little endian + alpha). `src/assets/lvres.py` decodes both. The app-list icons are IDs 10..21 of `app_applist.res`, **64 x 64** each; World Clock's is ID 21. [watch, code]

**Small icons.** LVGL's built-in decoder draws indexed images too: a 40 x 40 icon with 16 colours (`cf 9`, `INDEXED_4BIT`: a 64-byte palette of B, G, R, A entries, then 4 bits per pixel) takes 864 bytes against 4.8 KB
as RGB565 with alpha (checked by rendering it with the firmware's own LVGL code). [emu]

**Our own icon** is an `lv_img_dsc_t` (cf 5, 64 x 64, 12,288 bytes) in the free flash and the row's icon pointer points at it. The firmware's decoder accepts only ID strings and rejects anything else
(first check: the source type), so LVGL's built-in decoder handles it. [watch]

**Language packs** `language_xx.res` (69 of them, a ZIP with one entry, unzipped by the firmware to `/user/language.res`): a 0x18-byte header, `count x {string offset, font key}`, the strings, and the UI fonts embedded
in the file. `src/assets/lvlang.py` reads and edits them; `set_string` appends a string and fixes every later offset. The app-list name is text ID 181 for World Clock. [watch]

**Fonts.** The watch-face fonts (`/nand/system/font/FONT_ROBOTO_*.bin`) are loaded once at boot by `fonts_init` (`0x2c1006b0`) into RAM tables of `lv_font_t*`: Roboto at `0x2010b130`
(86, 50, 48, 40, 36, 34, 32, 30, 28, 26, 24, 22, 20 px), Roboto Medium at `0x2010b0e0` (86, 48, 44, 40, 36, 32, 30, 28, 24, 23, 20 px), plus Bold 60 and a LED digit font. Use `*(lv_font_t**)(table + 4*index)`; do not load
your own. The stock *settings* pages use different fonts, embedded in the language pack. [watch]

## 4. Services an app can call (from the GUI task)

| What | Address | Notes |
|---|---|---|
| Files | `fopen(path, "r"/"w")` `0x2c0c575c`, `read` `0x2c142dcc`, `write` `0x2c142ee0`, `close` `0x2c142c24` | yaffs2 on NAND. Keep writes small and rare: 2 KB after every tap restarted the watch (cause unknown); 128 bytes 3 s after a change did not |
| Create a directory | `mkdir_p(path)` `0x2c1435e0` | path of at most 127 characters; `open error:-2` means the directory is missing |
| Vibration | `motor_once(id, flag)` `0x2c1423f8` | ids index 80 patterns (`0x2c2e8b74`): 1 short (80 ms), 4 three pulses; `flag != 0` respects the user's setting |
| Keep the screen on | `0x2c224f2c()` | call on every tick; `0x2c224d60(1)` disables screen-off until you restore it |
| Time | `lv_tick_get` `0x2c288ef4` (ms) | the RTC call has an unknown signature, so we do not use it |
| Memory | `app_malloc` `0x2c0eb00c`, `app_free` `0x2c0eb018`; `lv_mem_alloc` `0x2c28a658` | two heaps |
| Settings store | KV read/write `0x2c0ea3c8` / `0x2c0ea438` | the length must equal the record's size, or the firmware asserts and restarts |

**Never from an app:** `rm -rf` (`0x2c1437f0`), anything that blocks (`osDelay`). Not found: step counter and heart-rate getters. [code]

## 5. Touch

The stock chain: panel interrupt, a task takes a mutex and reads the panel driver (`0x2c0a76d8`), pushes a 16-byte record into a ring, and the LVGL input device polls it every 5 ms. The old app loader read the
panel driver from inside the LVGL task without the mutex, which is the likely reason its touch was flaky. In an event handler use `lv_indev_get_point(lv_indev_get_act(), &p)` (`0x2c279310`, `0x2c279240`)
and `lv_indev_get_gesture_dir` (`0x2c279336`: 1 left, 2 **right = back**, 4 and 8 up and down). Taps are `LV_EVENT_CLICKED`. Touch through LVGL is as responsive as in the stock apps. [watch]

## 6. Look and feel of the stock pages

Colours (RGB565): screen `0x0000`, card `0x2124`, divider `0x4a49`, primary pill `0x5ade`, secondary text `0xadd8`, white text. Cards are 254 px wide with radius 26 and padding 12 and 17; pills 216 x 60 with
radius 100 at `BOTTOM_MID`; switches are images (`1276` off, `1278` on). A page is `lv_obj_create(NULL)` with a black background, no scrollbar and one event callback with filter ALL for the back gesture.
Children set `EVENT_BUBBLE` so the screen sees their events. [code]

## 7. The emulator and its limits

`src/emu` runs real functions of the firmware in Unicorn. It confirmed the structure sizes above, the whole window lifecycle and the answers to the manager's queries, and renders the app's screens with the firmware's
own drawing code (`screenshot.py`). It does **not** model the display, touch, the RTOS or the C start-up: `.data` is not initialised, so the lv_txt function pointers are installed by the harness; and a filled box that is the
child of a card with rounded corners is drawn black (the serve dot and divider are drawn right on the watch), so judge such details on the watch.

## 8. Not known

Where the image stores the `.data` initialisers; the signature of the RTC call; the heart-rate and step getters; the layouts of image formats `cf 6` and `0x15..0x1a`; why 2 KB writes restart the watch; what the
phone app does with a window it does not know (we only replace existing entries).
