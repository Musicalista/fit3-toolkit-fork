/* SPDX-License-Identifier: Apache-2.0 */
/* f3app.h: the interface between a Fit3 light app and the loader on the watch.
 *
 * An app is freestanding C built for Cortex-M4 (Thumb) by tools/appcc.py into a .f3a file. The loader copies it to RAM, relocates it and calls f3app_main()
 * once; after that it calls the tick() of the returned F3App about every 33 ms. Each tick the app redraws its whole frame into api->fb (RGB565, 256 x 402).
 * There is no C library: everything the app needs from the outside comes through the F3Api table. Never block inside tick().
 * The layout of F3Api (32-bit ARM) is part of the binary format, see sdk/README.md; append only to the end, through the reserved words. */
#ifndef F3APP_H
#define F3APP_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

#define F3_API_VERSION 1
#define F3_W 256
#define F3_H 402

/* wall clock as read from the watch's RTC; year is four digits, month runs 1..12, wday is passed through exactly as the firmware reports it */
typedef struct {
    int year, month, day, hour, min, sec, wday;
} F3Time;

typedef struct F3Api {
    u32 version;                    /* F3_API_VERSION */
    u16 *fb;                        /* pixels, row stride equal to w */
    int w, h;

    void *(*malloc)(u32 n);
    void (*free)(void *p);
    u32 (*ticks)(void);             /* milliseconds since an arbitrary start */
    void (*vibrate)(int id);        /* known ids: 1 short, 4 long, 5 error */

    /* drawing; all of it clips to the canvas. The first argument is the target buffer (normally api->fb). */
    void (*rect)(u16 *fb, int x, int y, int w, int h, u16 color);
    void (*rrect)(u16 *fb, int x, int y, int w, int h, int radius, u16 color);
    void (*disc)(u16 *fb, int cx, int cy, int r, u16 color);
    void (*text)(u16 *fb, int x, int y, const char *s, int scale, u16 color);     /* built-in 8x12 font, integer scale; (x, y) = top left */
    void (*ctext)(u16 *fb, int cx, int y, const char *s, int scale, u16 color);   /* same, horizontally centred on cx */
    void (*num)(u16 *fb, int x, int y, int value, int scale, u16 color);          /* signed decimal */

    /* files live on the watch's own file system; stay under /user/. mode is "r" or "w". fopen returns a descriptor, negative on failure. */
    int (*fopen)(const char *path, const char *mode);
    int (*fread)(int fd, void *buf, u32 n);
    int (*fwrite)(int fd, const void *buf, u32 n);
    int (*fclose)(int fd);

    u32 lang_pt;                    /* non-zero when the watch is set to Portuguese */
    void (*time)(F3Time *t);        /* NULL on loaders older than v1.7: test before calling */
    int (*battery)(void);           /* percent 0..100; NULL on older loaders as well */
    u32 reserved[6];                /* zero; room for later additions */
} F3Api;

typedef struct F3App {
    /* once per frame. pressed: finger is down; x, y: its position. tap: set for the one frame in which a tap was released.
     * Return non-zero to keep running, zero to quit. */
    int (*tick)(struct F3App *self, int pressed, int x, int y, int tap);
    void (*close)(struct F3App *self);   /* optional (may be NULL); release memory here */
} F3App;

/* the one symbol the loader looks up. Allocate the app state through api->malloc and return it, or return 0 to refuse to start. */
F3App *f3app_main(const F3Api *api);

/* pack 8-bit channels into RGB565 */
#define RGB(r, g, b) ((u16)((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3)))

#endif
