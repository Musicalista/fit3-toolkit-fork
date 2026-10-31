/* f3ui.h: colours and small widgets in the style of the watch's own UI (black background, dark rounded cards, pill buttons, switches).
 * Sampled from Samsung's promotional render of the Fit3 UI (reference-images/, not in git): cards #242424, secondary buttons #2c-#34, blue (67,144,246), grey text about 150.
 * They are still estimates, not Samsung's values.
 * Greys are multiples of 8 on purpose: RGB565 has 5 bits for red and blue but 6 for green, other values get a green tint. Needs f3app.h. */
#ifndef F3UI_H
#define F3UI_H
#include "f3app.h"

#define UI_BG       RGB(0, 0, 0)                  /* OLED black */
#define UI_CARD     RGB(32, 32, 32)               /* card / list row */
#define UI_CARD_HI  RGB(48, 48, 48)               /* secondary button ("Reply" pill) */
#define UI_TEXT     RGB(255, 255, 255)
#define UI_DIM      RGB(152, 152, 152)            /* secondary text */
#define UI_BLUE     RGB(62, 145, 255)             /* accent */
#define UI_GREEN    RGB(48, 209, 130)
#define UI_RED      RGB(255, 69, 58)
#define UI_ORANGE   RGB(255, 159, 10)
#define UI_TEAL     RGB(28, 197, 151)             /* app icon: Samsung Health */
#define UI_PURPLE   RGB(84, 77, 185)              /* app icon: Media Controller */
#define UI_OFF      RGB(72, 72, 72)               /* switch track when off */

static void ui_clear(const F3Api *A) { A->rect(A->fb, 0, 0, F3_W, F3_H, UI_BG); }
static void ui_card(const F3Api *A, int x, int y, int w, int h) { A->rrect(A->fb, x, y, w, h, 24, UI_CARD); }
static void ui_pill(const F3Api *A, int x, int y, int w, int h, u16 color) { A->rrect(A->fb, x, y, w, h, h / 2, color); }
static void ui_switch(const F3Api *A, int x, int y, int on) {                                 /* 56 x 32 */
    ui_pill(A, x, y, 56, 32, on ? UI_BLUE : UI_OFF); A->disc(A->fb, on ? x + 40 : x + 16, y + 16, 12, UI_TEXT);
}
static void ui_chevron(const F3Api *A, int x, int y, u16 color) { for (int i = 0; i < 7; i++) { A->disc(A->fb, x + (i < 4 ? i : 6 - i) * 2, y + i * 2, 1, color); A->disc(A->fb, x + (i < 4 ? i : 6 - i) * 2 + 1, y + i * 2, 1, color); } }
static int ui_in(int px, int py, int x, int y, int w, int h) { return px >= x && px < x + w && py >= y && py < y + h; }
#endif
