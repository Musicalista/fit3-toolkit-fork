"""Live window for a Fit3 light app: mouse = finger, the top-right corner is the watch's own close button.
usage: python3 sim_gui.py <libsim_app.so> [--data DIR] [--scale N] [--shot FILE --script "x,y x,y ..."]"""
import argparse, ctypes, os, sys, time, tkinter as tk
import numpy as np

W, H, STEP = 256, 402, 0.033

def load(path, data):
    lib = ctypes.CDLL(os.path.abspath(path))
    lib.sim_fb.restype = ctypes.POINTER(ctypes.c_ushort)
    now = time.localtime(); secs = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
    os.makedirs(data, exist_ok=True)
    if lib.sim_init(data.encode(), secs): sys.exit("f3app_main failed")
    return lib

def frame_ppm(lib):
    a = np.ctypeslib.as_array(lib.sim_fb(), shape=(H, W)).astype(np.uint16)
    rgb = np.empty((H, W, 3), np.uint8)
    rgb[..., 0] = ((a >> 11) & 31) * 255 // 31; rgb[..., 1] = ((a >> 5) & 63) * 255 // 63; rgb[..., 2] = (a & 31) * 255 // 31
    return b"P6\n%d %d\n255\n" % (W, H) + rgb.tobytes()

class Gui:
    def __init__(self, lib, scale):
        self.lib, self.scale, self.down, self.x, self.y, self.last = lib, scale, 0, 0, 0, time.monotonic()
        self.root = tk.Tk(); self.root.title("Fit3 simulator"); self.root.resizable(False, False)
        self.canvas = tk.Canvas(self.root, width=W * scale, height=H * scale, highlightthickness=0, bg="black"); self.canvas.pack()
        self.img = tk.PhotoImage(); self.item = self.canvas.create_image(0, 0, anchor="nw", image=self.img)
        self.canvas.bind("<ButtonPress-1>", self.press); self.canvas.bind("<B1-Motion>", self.move); self.canvas.bind("<ButtonRelease-1>", self.release)
        self.root.protocol("WM_DELETE_WINDOW", self.quit); self.root.bind("<Escape>", lambda e: self.quit())
        self.tick_loop()
    def pos(self, e): return max(0, min(W - 1, e.x // self.scale)), max(0, min(H - 1, e.y // self.scale))
    def press(self, e):
        self.x, self.y = self.pos(e)
        if self.x >= 216 and self.y < 34: return self.quit()                     # the watch draws its own close button here
        self.down = 1; self.step()
    def move(self, e):
        if self.down: self.x, self.y = self.pos(e)
    def release(self, e):
        if not self.down: return
        self.x, self.y = self.pos(e); self.step(); self.down = 0; self.step()
    def step(self):
        if not self.lib.sim_tick(self.down, self.x, self.y): self.quit()
    def tick_loop(self):
        n = int((time.monotonic() - self.last) / STEP)
        if n: self.last += n * STEP
        for _ in range(min(n, 10)): self.step()
        if n:
            self.img = tk.PhotoImage(data=frame_ppm(self.lib), format="PPM")
            if self.scale > 1: self.img = self.img.zoom(self.scale, self.scale)
            self.canvas.itemconfigure(self.item, image=self.img)
        self.root.after(15, self.tick_loop)
    def quit(self):
        self.lib.sim_close(); self.root.destroy()

def headless(lib, script, out):
    """no window: 'x,y' taps (press + release) separated by spaces, 'tN' idle ticks; writes a PPM of the final frame"""
    for tok in script.split():
        if tok[0] == "t": [lib.sim_tick(0, 0, 0) for _ in range(int(tok[1:]))]
        else: x, y = map(int, tok.split(",")); lib.sim_tick(1, x, y); lib.sim_tick(0, x, y)
    lib.sim_tick(0, 0, 0); open(out, "wb").write(frame_ppm(lib)); lib.sim_close()

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("lib"); ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    ap.add_argument("--scale", type=int, default=0); ap.add_argument("--shot"); ap.add_argument("--script", default="")
    a = ap.parse_args(); lib = load(a.lib, a.data)
    if a.shot: headless(lib, a.script, a.shot); sys.exit(0)
    root = tk.Tk(); scale = a.scale or (2 if root.winfo_screenheight() >= 950 else 1); root.destroy()
    Gui(lib, scale).root.mainloop()
