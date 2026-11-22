#!/usr/bin/env python3
"""
Pisica de pauza
===============
O pisica sta pe ecran cat lucrezi. Cand stai prea mult, ea se mareste,
acopera tot ecranul si adoarme. Fa si tu o pauza cat doarme ea!

Rulare:
    python pisica_pauza.py                      # 30 min lucru, 5 min pauza
    python pisica_pauza.py --lucru 45 --pauza 10
    python pisica_pauza.py --lucru 0.2 --pauza 0.3    # test rapid (in minute)

Comenzi:
- trage pisica cu mouse-ul ca s-o muti
- butonul ⚙ (stanga sus) sau click dreapta > Setari: alegi cat lucrezi si cat doarme
- click dreapta pe ea: meniu (pauza acum / resetare / inchide)
- cat doarme: apasa Esc de 5 ori repede ca s-o trezesti (urgente)
"""
import argparse
import math
import random
import sys
import time
import tkinter as tk

# culori
WARM = "#fdf3e8"
NIGHT = "#161a3a"
FUR = "#e07a38"
FUR_DARK = "#a84f1d"
BELLY = "#f7be8c"
PINK = "#f4a6b8"
EYE = "#8be37a"
OUT = "#111111"
TEXT_DARK = "#2c2d30"
TEXT_LIGHT = "#dcdcff"


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    return t * t * (3 - 2 * t)


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(lerp(x, y, t)) for x, y in zip(a, b))


def fmt(sec):
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def parse_minutes(value):
    minutes = float(value)
    if not math.isfinite(minutes) or minutes <= 0:
        raise ValueError("durata trebuie sa fie un numar finit mai mare ca 0")
    return minutes


class Pen:
    """Deseneaza in coordonate 0..100, scalate pe canvas."""

    def __init__(self, canvas, ox, oy, s):
        self.c, self.ox, self.oy, self.s = canvas, ox, oy, s

    def _f(self, pts):
        return [v for x, y in pts for v in (self.ox + x * self.s, self.oy + y * self.s)]

    def oval(self, x1, y1, x2, y2, **kw):
        kw.setdefault("width", max(1, self.s))
        self.c.create_oval(*self._f([(x1, y1), (x2, y2)]), **kw)

    def poly(self, pts, **kw):
        kw.setdefault("width", max(1, self.s))
        self.c.create_polygon(self._f(pts), **kw)

    def line(self, pts, width=1, **kw):
        self.c.create_line(self._f(pts), width=max(1, width * self.s), **kw)

    def arc(self, x1, y1, x2, y2, start, extent, width=1, **kw):
        self.c.create_arc(*self._f([(x1, y1), (x2, y2)]), start=start, extent=extent,
                          style="arc", width=max(1, width * self.s), **kw)

    def text(self, x, y, txt, size, color):
        self.c.create_text(self.ox + x * self.s, self.oy + y * self.s, text=txt, fill=color,
                           font=("Helvetica", -max(8, int(size * self.s)), "bold"))


class PisicaApp:
    SW, SH = 170, 200      # dimensiunea ferestrei mici
    GROW = 1.6             # secunde cat dureaza marirea / micsorarea

    def __init__(self, work_min, pause_min):
        self.work = work_min * 60
        self.pause = pause_min * 60

        self.root = tk.Tk()
        self.root.title("Pisica de pauza")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        if sys.platform == "win32":
            try:
                self.root.attributes("-transparentcolor", WARM)
            except tk.TclError:
                pass

        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        self.x = self.sw - self.SW - 30
        self.y = self.sh - self.SH - 80
        self.geo = ""
        self.dlg = None
        self.gear_hit = False

        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg=WARM)
        self.canvas.pack(fill="both", expand=True)

        self.state = "watch"
        self.t0 = time.monotonic()
        self.ta = 0.0
        self.last_lift = 0.0
        self.esc = []
        self.stars = [(random.random(), random.random() * 0.8, random.uniform(1, 2.6),
                       random.uniform(0, 6.28)) for _ in range(70)]

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        for b in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
            self.canvas.bind(b, self.on_menu)
        self.root.bind("<Escape>", self.on_escape)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Fa pauza acum", command=self.start_grow)
        self.menu.add_command(label="Reseteaza cronometrul", command=self.reset)
        self.menu.add_command(label="Setari (timp lucru / pauza)...", command=self.open_settings)
        self.menu.add_separator()
        self.menu.add_command(label="Inchide pisica", command=self.root.destroy)

        self.tick()

    # interactiune
    def on_press(self, e):
        self.dx, self.dy = e.x_root - self.x, e.y_root - self.y
        self.gear_hit = self.state == "watch" and e.x < 28 and e.y < 28
        if self.gear_hit:
            self.open_settings()

    def on_drag(self, e):
        if self.state == "watch" and not self.gear_hit:
            self.x, self.y = e.x_root - self.dx, e.y_root - self.dy

    def on_menu(self, e):
        if self.state == "watch":
            try:
                self.menu.tk_popup(e.x_root, e.y_root)
            finally:
                self.menu.grab_release()

    def on_escape(self, _e):
        now = time.monotonic()
        self.esc = [t for t in self.esc if now - t < 3] + [now]
        if self.state == "sleep" and len(self.esc) >= 5:
            self.start_shrink()

    def reset(self):
        self.t0 = time.monotonic()

    def open_settings(self):
        if self.dlg is not None and self.dlg.winfo_exists():
            self.dlg.lift()
            return
        d = self.dlg = tk.Toplevel(self.root)
        d.title("Setari pisica")
        d.attributes("-topmost", True)
        d.resizable(False, False)

        wv = tk.StringVar(value=f"{self.work / 60:g}")
        pv = tk.StringVar(value=f"{self.pause / 60:g}")
        rows = (("Pisica asteapta (minute de lucru):", wv, (15, 25, 30, 45, 60)),
                ("Pisica doarme (minute de pauza):", pv, (3, 5, 10, 15, 20)))
        for r, (label, var, presets) in enumerate(rows):
            tk.Label(d, text=label, anchor="w", font=("Helvetica", 10, "bold")).grid(
                row=r * 2, column=0, columnspan=6, sticky="w", padx=8, pady=(10, 0))
            for i, val in enumerate(presets):
                tk.Button(d, text=str(val), width=3,
                          command=lambda v=var, val=val: v.set(str(val))).grid(
                    row=r * 2 + 1, column=i, padx=4, pady=4)
            tk.Entry(d, textvariable=var, width=6, justify="center").grid(
                row=r * 2 + 1, column=len(presets), padx=(8, 8), pady=4)

        err = tk.Label(d, text="", fg="#b00020")
        err.grid(row=4, column=0, columnspan=6)

        def apply(_e=None):
            try:
                w = parse_minutes(wv.get().replace(",", "."))
                p = parse_minutes(pv.get().replace(",", "."))
            except ValueError:
                err.config(text="Introdu numere finite mai mari ca 0")
                return

            self.work, self.pause = w * 60, p * 60
            self.reset()
            d.destroy()

        bar = tk.Frame(d)
        bar.grid(row=5, column=0, columnspan=6, pady=(4, 10))
        tk.Button(bar, text="Aplica", width=10, command=apply).pack(side="left", padx=6)
        tk.Button(bar, text="Anuleaza", width=10, command=d.destroy).pack(side="left", padx=6)
        d.bind("<Return>", apply)
        d.bind("<Escape>", lambda _e: d.destroy())

        d.update_idletasks()
        d.geometry(f"+{(self.sw - d.winfo_width()) // 2}+{(self.sh - d.winfo_height()) // 3}")
        d.focus_force()

    # stari
    def start_grow(self):
        if self.state == "watch":
            self.state = "grow"
            self.ta = time.monotonic()

    def start_shrink(self):
        self.state = "shrink"
        self.ta = time.monotonic()

    # bucla principala
    def tick(self):
        now = time.monotonic()
        if self.state == "watch" and self.work - (now - self.t0) <= 0:
            self.start_grow()

        st = self.state
        w, h, x, y = self.SW, self.SH, self.x, self.y
        mode, night, sleepy, lines = "sit", 0.0, 0.0, []

        if st == "watch":
            el = now - self.t0
            rem = max(0, self.work - el)
            sleepy = clamp(1 - rem / 60) if rem < 60 else 0.0
            lines = ["Mi se inchid ochii..."] if sleepy > 0.3 else [f"Lucrezi de {int(el // 60)} min"]

        elif st in ("grow", "shrink"):
            e = clamp((now - self.ta) / self.GROW)
            k = ease(e) if st == "grow" else 1 - ease(e)
            w, h = lerp(self.SW, self.sw, k), lerp(self.SH, self.sh, k)
            x, y = lerp(self.x, 0, k), lerp(self.y, 0, k)
            night = k
            sleepy = 1.0 if st == "grow" else 0.0
            lines = ["Hopa... vine somnul"] if st == "grow" else ["Buna dimineata!"]
            if e >= 1:
                if st == "grow":
                    self.state, self.ta = "sleep", now
                    self.root.focus_force()
                else:
                    self.state, self.t0 = "watch", now

        elif st == "sleep":
            w, h, x, y = self.sw, self.sh, 0, 0
            mode, night = "sleep", 1.0
            rem = self.pause - (now - self.ta)
            lines = ["Shhh... pisica doarme. Fa si tu o pauza!", f"Se trezeste in {fmt(rem)}"]
            if now - self.last_lift > 1:
                self.root.lift()
                self.root.attributes("-topmost", True)
                self.last_lift = now
            if rem <= 0:
                self.start_shrink()

        geo = f"{int(w)}x{int(h)}+{int(x)}+{int(y)}"
        if geo != self.geo:
            self.root.geometry(geo)
            self.geo = geo

        self.render(w, h, mode, now, night, sleepy, lines)
        self.root.after(40, self.tick)

    # desenare
    def render(self, w, h, mode, t, night, sleepy, lines):
        c = self.canvas
        bg = mix(WARM, NIGHT, night)
        c.configure(bg=bg)
        c.delete("all")

        if night > 0.05:
            for rx, ry, r, ph in self.stars:
                col = mix(bg, "#ffffff", night * (0.5 + 0.5 * math.sin(t * 2 + ph)))
                sx, sy = rx * w, ry * h
                c.create_oval(sx - r, sy - r, sx + r, sy + r, fill=col, outline=col)

        area_h = h * 0.84
        s = min(w, area_h) / 100
        pen = Pen(c, (w - 100 * s) / 2, (area_h - 100 * s) / 2, s)
        if mode == "sleep":
            self.cat_sleep(pen, t, bg)
        else:
            self.cat_sit(pen, t, sleepy)
            if self.state == "watch":
                c.create_rectangle(3, 3, 27, 27, fill="#ffffff", outline=OUT)
                c.create_text(15, 15, text="⚙", fill=TEXT_DARK, font=("Helvetica", -16))

        fs = max(12, int(h * 0.04))
        col = mix(TEXT_DARK, TEXT_LIGHT, night)
        for i, line in enumerate(lines):
            c.create_text(w / 2, area_h + (h - area_h) * (i + 0.5) / len(lines), text=line,
                          fill=col, font=("Helvetica", -fs, "bold" if i == 0 else "normal"))

    def cat_sit(self, p, t, sleepy):
        wag = math.sin(t * 2.5)
        # coada
        p.line([(70, 94), (88, 96), (96, 82 + 4 * wag), (93, 66 + 7 * wag), (99, 54 + 9 * wag)],
               width=9, fill=FUR, smooth=True, capstyle="round")
        # corp, burtica, labute
        p.oval(24, 48, 76, 101, fill=FUR, outline=OUT)
        p.oval(37, 62, 63, 99, fill=BELLY, outline="")
        p.oval(31, 90, 48, 102, fill=BELLY, outline=OUT)
        p.oval(52, 90, 69, 102, fill=BELLY, outline=OUT)
        # urechi
        p.poly([(28, 28), (30, 3), (48, 16)], fill=FUR, outline=OUT)
        p.poly([(72, 28), (70, 3), (52, 16)], fill=FUR, outline=OUT)
        p.poly([(33, 24), (34, 10), (44, 18)], fill=PINK, outline="")
        p.poly([(67, 24), (66, 10), (56, 18)], fill=PINK, outline="")
        # cap
        p.oval(26, 14, 74, 58, fill=FUR, outline=OUT)
        for a, b in (((50, 15), (50, 23)), ((43, 16), (45, 22)), ((57, 16), (55, 22))):
            p.line([a, b], width=1.6, fill=FUR_DARK)
        # ochi
        blink = (t % 4.0) < 0.18
        ry = 6.5 * (1 - 0.8 * sleepy)
        for cx in (40, 60):
            if blink or ry < 1.6:
                p.line([(cx - 6, 36), (cx + 6, 36)], width=1.6, fill=OUT)
            else:
                p.oval(cx - 6.5, 36 - ry, cx + 6.5, 36 + ry, fill=EYE, outline=OUT)
                p.oval(cx - 1.8, 36 - ry * 0.9, cx + 1.8, 36 + ry * 0.9, fill="#1b1b1b", outline="")
                p.oval(cx - 4, 36 - ry * 0.6, cx - 2, 36 - ry * 0.2, fill="#ffffff", outline="")
        # nas, gura, mustati
        p.poly([(46, 43), (54, 43), (50, 47)], fill=PINK, outline="")
        p.line([(50, 47), (50, 50), (45, 52)], width=1, fill=OUT)
        p.line([(50, 50), (55, 52)], width=1, fill=OUT)
        for a, b in (((30, 44), (14, 41)), ((30, 47), (14, 48)),
                     ((70, 44), (86, 41)), ((70, 47), (86, 48))):
            p.line([a, b], width=0.8, fill=OUT)

    def cat_sleep(self, p, t, bg):
        br = 1 + 0.035 * math.sin(t * 1.8)    # respiratie
        # corp incolacit
        p.oval(6, 98 - 56 * br, 94, 98, fill=FUR, outline=OUT)
        for a, b in (((60, 98 - 56 * br + 4), (62, 98 - 56 * br + 16)),
                     ((72, 98 - 56 * br + 8), (74, 98 - 56 * br + 20)),
                     ((84, 98 - 56 * br + 16), (85, 98 - 56 * br + 28))):
            p.line([a, b], width=2, fill=FUR_DARK)
        # coada peste fata
        p.line([(90, 88), (96, 98), (70, 103), (40, 103), (16, 98)], width=8,
               fill=FUR_DARK, smooth=True, capstyle="round")
        # urechi
        p.poly([(12, 56), (10, 36), (26, 50)], fill=FUR, outline=OUT)
        p.poly([(46, 56), (48, 36), (32, 50)], fill=FUR, outline=OUT)
        p.poly([(14, 52), (13, 41), (22, 49)], fill=PINK, outline="")
        p.poly([(44, 52), (45, 41), (36, 49)], fill=PINK, outline="")
        # cap
        p.oval(8, 48, 50, 92, fill=FUR, outline=OUT)
        p.arc(15, 64, 27, 74, 180, 180, width=1.6, outline=OUT)
        p.arc(31, 64, 43, 74, 180, 180, width=1.6, outline=OUT)
        p.poly([(26, 77), (32, 77), (29, 80)], fill=PINK, outline="")
        p.line([(29, 80), (29, 83)], width=1, fill=OUT)
        for a, b in (((16, 80), (3, 78)), ((16, 83), (3, 85)),
                     ((42, 80), (55, 78)), ((42, 83), (55, 85))):
            p.line([a, b], width=0.8, fill=OUT)
        # labuta sub barbie
        p.oval(44, 86, 68, 101, fill=BELLY, outline=OUT)
        # Zzz
        for i in range(3):
            ph = (t * 0.4 + i / 3) % 1
            col = mix("#ffffff", bg, ph ** 2)
            p.text(40 + 28 * ph + 3 * math.sin(t * 2 + i), 38 - 36 * ph, "Z", 6 + 8 * ph, col)

    def run(self):
        self.root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="Pisica care te obliga sa faci pauza.")
    ap.add_argument("--lucru", type=parse_minutes, default=30, help="minute de lucru (implicit 30)")
    ap.add_argument("--pauza", type=parse_minutes, default=5, help="minute de pauza (implicit 5)")

    a = ap.parse_args()
    PisicaApp(a.lucru, a.pauza).run()


if __name__ == "__main__":
    main()