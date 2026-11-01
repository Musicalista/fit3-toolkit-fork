# Apps

Four demo apps. Use them as they are, or copy one and make it yours.

| App | Source | Description | Size (`.f3x`) |
|---|---|---|---|
| **Counter** | [`counter.c`](counter.c) | A tap counter: tap the card to add one, `-1` to undo, `Reset` to start over; the value is saved. The smallest complete app: a card, two buttons, a timer and a saved value. **Start here.** | 3,586 B |
| **Dice** | [`dice.c`](dice.c) | Rolls one or two dice and shows the sum. Shows drawing with plain boxes, a button that changes the mode and random numbers. | 3,761 B |
| **Tennis Score** | [`tennis.c`](tennis.c) | A score keeper for a tennis match: points, games, sets and tie-break, who serves, undo, match, game and set timers and match stats; the match is saved. The biggest demo: an overlay closed by the back gesture and scoring rules tested on the PC ([`../test_score.c`](../test_score.c)). | 6,181 B |
| **Mars Production** | [`mars.c`](mars.c) | A production tracker for the board game *Terraforming Mars*: the six production tracks (credits, steel, titanium, plants, energy, heat) with round −/+ buttons and a `Reset` that asks twice; the values are saved. Shows a list of rows with buttons and a two-step confirmation. | 3,982 B |

Size is the installable file: header, code, relocation table and the 2,112-byte icon. *Terraforming Mars* is a game by FryxGames; this app is unofficial and not affiliated with them.

## Use them

Each app can be **built into the firmware** or **installed later as a file**:

```sh
# as a file, no flashing (needs the hub on the watch):
python3 -I src/f3x/build_f3x.py src/watch/apps/dice.c dice.f3x --icon-kind dice
python3 -I src/device/f3x_install.py install dice.f3x

# or inside the firmware package (in the order given):
python3 -I src/build_firmware.py stock-aza3.bin hub.bin --hub tennis,counter,dice,mars
```

## Write your own

```sh
cp src/watch/apps/counter.c src/watch/apps/myapp.c      # 1. copy the smallest app
$EDITOR src/watch/apps/myapp.c                          # 2. change it
python3 -I src/f3x/build_f3x.py src/watch/apps/myapp.c myapp.f3x --name "My app" --icon my64x64.png    # 3. build (the icon is a 64 x 64 PNG with transparency)
python3 -I src/device/f3x_install.py install myapp.f3x  # 4. put it on the watch
```

An app is a file that includes `../ui.h` and ends with `APP_EXPORT(id, "Name", &ICON, create, back, destroy)`:

```c
void *create(lv_obj_t *root);     // build the page as children of root, return your state (from app_malloc)
int   back(void *state);          // the back gesture: return 1 if you used it (closed an overlay), 0 to leave the app
void  destroy(void *state);       // stop timers, save, app_free(state); the host deletes the widgets
```

`ui.h` gives you what is needed: colours (`C_*`), fonts (`FT_*`), `mk_box`, `mk_text`, `mk_pill`, `blob_save` / `blob_load`, and the firmware's LVGL functions (`lv_timer_create`, `lv_obj_add_event_cb`, ...).

**Rules** (the builder refuses what breaks them):

- **No globals.** Keep state in the block you allocate. The code is relocated when it is loaded, so no `.data` or `.bss`.
- **No libc, no libgcc.** Call the firmware's own functions (they are in `ui.h`; all known addresses are in [`docs/symbols.csv`](../../../docs/symbols.csv)).
- Write files **rarely and small** (a small blob 3 s after a change, and in `destroy`); big or frequent writes restarted the watch.
- `FT_HUGE` has only digits and `:-/`; a missing glyph is not drawn.
- Leave the window manager's questions to `hub.c`; your app never sees them.

To make your app part of the firmware build too, add it to `APPS` in [`../gen.py`](../gen.py) and, for a drawn icon, a `_glyph_<name>` and a colour in [`../../assets/mkicon.py`](../../assets/mkicon.py).
The format of the file: [docs/f3x.md](../../../docs/f3x.md). Try an app on the PC first: [src/emu](../../emu/README.md) runs the real firmware's LVGL functions, and `test_mars.py` shows how to test an app.
