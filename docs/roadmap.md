# Roadmap: a native-feeling entry for our apps

**Goal:** our tennis app opens from the stock app list, in the slot of an app nobody uses (World clock), and looks like a stock app. What is done and verified is in [status](status.md).

## Decisions so far

- The stock **World clock** list entry is the slot to take over.
- Our code lives in the empty flash of the firmware and is called by the window manager like any other window. A change means a new package (an 18 MB update over Bluetooth), which is fine for one app.
- Look and feel comes from calling the firmware's own LVGL functions with the stock page recipes and the firmware's Roboto font tables ([details](details.md)), not from drawing pixels.
- The **window manager's contract** matters more than the drawing: the return values of the window's event function steer the side key and the swipe-back ([details](details.md), section 2). A wrong answer is
  a visible bug, not a crash.

## Phases

| # | What | State |
|---|---|---|
| 1 | Hook the World clock page builder, rename the entry | done (stage 1b), superseded by 2 |
| 2 | Own loader in the free flash: take over the window's create/event functions with `b.w` branches, own screen, own back gesture, no stock page | **done and verified** (`loader_v1`, `loader_v2`) |
| 3 | `build_package.py` / `build_tennis.py`: stock package + patches + loader + label + icon, all checksums repaired, nothing third-party in the repository | **done** (the result is identical to the hand-built package; the only third-party input is your stock package) |
| 4 | Label and icon: a longer name (`--label`, text ID 181), our own 64 x 64 icon (`mkicon.py`, `--icon`: the list row points at an `lv_img_dsc_t` in the free flash) | **done and verified** (label and icon on the watch) |
| 5 | The tennis app as native LVGL objects: cards, Undo, Stats, save | **done and verified** |
| 6 | Choose the replaced entry (`--slot`), other languages (`--languages all`) | built and tested in the emulator for all 11 slots; World clock verified on the watch |

Why a faulty window is not a brick: nothing of ours runs at boot. A broken function restarts the watch when someone opens the entry (or, for the icon, the app list); the watch still
boots, so a package can be flashed over Bluetooth again. A package that does not pass `src/firmware/validate_fwd.py`, or that touches code that runs at boot, is what can brick a watch.

## Ideas, not planned

- A 13th row in the app list instead of replacing an entry (needs patches to the row count and the order normaliser; the phone's app list may not accept it; see [details](details.md)).
- Checking on a watch what replacing each other stock app breaks (Alarm, Timer and Stopwatch keep state outside their window), and a non-English watch for `--languages all`.
- More than one app: today one app takes one entry; a small launcher in an entry that starts several apps would need its own app format (not planned: the old `.f3a` format of Musicalista was dropped).
- Using the RTC for wall-clock times (its signature is unknown; the tracker uses ticks plus a stored shift).
- Heart rate and step counter access (getters not found yet, see [details](details.md)).

## Dependencies on third-party code

None in the code. The build needs your stock package, `arm-none-eabi-gcc` and Python with numpy; flashing from this PC needs only a Bluetooth adapter (see [howto.md](howto.md)).
