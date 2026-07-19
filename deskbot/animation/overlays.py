"""Animation overlays: particles, glyphs and mouths layered over the eyes.

An overlay gets three hooks per frame, all in *logical* 128x64 coordinates
(multiplied by the supersample factor when drawing):

    step(dt)              advance particles/timers
    modify(left, right, t) optionally puppet the eye parameters
    draw(d, s, t)          draw decorations into the supersampled canvas
"""
from __future__ import annotations

import math
import random

W, H = 128, 64
EYE_L, EYE_R, EYE_CY = 39, 89, 32


class Overlay:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def step(self, dt: float):
        pass

    def modify(self, left: dict, right: dict, t: float):
        pass

    def draw(self, d, s: int, t: float):
        pass


# ---------------------------------------------------------------------------
# glyph helpers (coords logical, s = supersample factor)
# ---------------------------------------------------------------------------

def _heart(d, cx, cy, size, s):
    cx, cy, size = cx * s, cy * s, size * s
    r = size * 0.27
    yo = -size * 0.12
    d.ellipse([cx - 2 * r, cy + yo - r, cx, cy + yo + r], fill=255)
    d.ellipse([cx, cy + yo - r, cx + 2 * r, cy + yo + r], fill=255)
    d.polygon([(cx - 1.93 * r, cy + yo + r * 0.2),
               (cx + 1.93 * r, cy + yo + r * 0.2),
               (cx, cy + size * 0.52)], fill=255)


def _drop(d, cx, cy, size, s):
    """Teardrop, pointy end up."""
    cx, cy, size = cx * s, cy * s, size * s
    r = size * 0.38
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    d.polygon([(cx, cy - size * 0.95),
               (cx - r * 0.9, cy - r * 0.25),
               (cx + r * 0.9, cy - r * 0.25)], fill=255)


def _note(d, cx, cy, size, s):
    cx, cy, size = cx * s, cy * s, size * s
    rx, ry = size * 0.30, size * 0.22
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    x = cx + rx - s * 0.4
    d.line([(x, cy), (x, cy - size * 0.95)], fill=255, width=max(2, int(s * 1.1)))
    d.line([(x, cy - size * 0.95), (x + size * 0.42, cy - size * 0.7)],
           fill=255, width=max(2, int(s * 1.1)))


def _spark(d, cx, cy, size, s):
    """4-point sparkle."""
    cx, cy, r = cx * s, cy * s, size * s / 2
    q = r * 0.28
    d.polygon([(cx, cy - r), (cx + q, cy - q), (cx + r, cy), (cx + q, cy + q),
               (cx, cy + r), (cx - q, cy + q), (cx - r, cy), (cx - q, cy - q)],
              fill=255)


def _cloud(d, cx, cy, size, s):
    cx, cy, size = cx * s, cy * s, size * s
    r = size * 0.3
    for ox, oy, rr in ((-0.55, 0.1, 0.8), (0.0, -0.25, 1.0), (0.55, 0.1, 0.8)):
        cr = r * rr
        d.ellipse([cx + ox * size - cr, cy + oy * size - cr,
                   cx + ox * size + cr, cy + oy * size + cr], fill=255)


def _thumb(d, cx, cy, size, s, scale=1.0):
    if scale <= 0.05:
        return
    cx, cy, size = cx * s, cy * s, size * s * scale
    # fist
    d.rounded_rectangle([cx - size * 0.28, cy - size * 0.10,
                         cx + size * 0.30, cy + size * 0.42],
                        radius=size * 0.09, fill=255)
    # thumb sticking up on the left
    d.rounded_rectangle([cx - size * 0.46, cy - size * 0.46,
                         cx - size * 0.20, cy + 0.06 * size],
                        radius=size * 0.11, fill=255)
    # black separation between thumb and fist
    d.line([(cx - size * 0.24, cy - size * 0.08),
            (cx - size * 0.24, cy + size * 0.30)],
           fill=0, width=max(2, int(s * 0.8)))
    # finger separation notches
    for i in range(1, 4):
        y = cy - size * 0.10 + i * size * 0.13
        d.line([(cx - size * 0.05, y), (cx + size * 0.30, y)],
               fill=0, width=max(2, int(s * 0.8)))


def _question(d, cx, cy, size, s):
    cx, cy, size = cx * s, cy * s, size * s
    r = size * 0.30
    wdt = max(2, int(s * 1.3))
    d.arc([cx - r, cy - size * 0.5, cx + r, cy - size * 0.5 + 2 * r],
          start=150, end=430, fill=255, width=wdt)
    d.line([(cx + r * 0.55, cy - size * 0.5 + 1.7 * r),
            (cx, cy + size * 0.18)], fill=255, width=wdt)
    dr = size * 0.09
    d.ellipse([cx - dr, cy + size * 0.38 - dr, cx + dr, cy + size * 0.38 + dr],
              fill=255)


def _smile(d, cx, cy, w, s, frown=False):
    cx, cy, w = cx * s, cy * s, w * s
    h = w * 0.55
    wdt = max(2, int(s * 1.4))
    if frown:
        d.arc([cx - w / 2, cy, cx + w / 2, cy + 2 * h], 180, 360,
              fill=255, width=wdt)
    else:
        d.arc([cx - w / 2, cy - 2 * h, cx + w / 2, cy], 0, 180,
              fill=255, width=wdt)


# ---------------------------------------------------------------------------
# overlays
# ---------------------------------------------------------------------------

class Confetti(Overlay):
    N = 22

    def __init__(self, rng):
        super().__init__(rng)
        self.p = [self._spawn(top=False) for _ in range(self.N)]

    def _spawn(self, top=True):
        r = self.rng
        return {
            "x": r.uniform(0, W), "y": r.uniform(-20, -2) if top else r.uniform(-40, H),
            "vy": r.uniform(22, 48), "amp": r.uniform(2, 9),
            "ph": r.uniform(0, 6.28), "kind": r.randrange(3),
            "sz": r.uniform(1.6, 3.2),
        }

    def step(self, dt):
        for p in self.p:
            p["y"] += p["vy"] * dt
            if p["y"] > H + 4:
                p.update(self._spawn(top=True))

    def draw(self, d, s, t):
        for p in self.p:
            x = (p["x"] + math.sin(t * 2.2 + p["ph"]) * p["amp"]) * s
            y = p["y"] * s
            z = p["sz"] * s
            if p["kind"] == 0:
                d.rectangle([x, y, x + z, y + z], fill=255)
            elif p["kind"] == 1:
                a = t * 4 + p["ph"]
                d.line([(x - math.cos(a) * z, y - math.sin(a) * z),
                        (x + math.cos(a) * z, y + math.sin(a) * z)],
                       fill=255, width=max(2, int(s * 0.7)))
            else:
                d.ellipse([x - z * 0.6, y - z * 0.6, x + z * 0.6, y + z * 0.6],
                          fill=255)


class Sweat(Overlay):
    CYCLE = 2.6

    def draw(self, d, s, t):
        p = (t % self.CYCLE) / self.CYCLE
        x = 112
        if p < 0.62:  # slide down the "temple", growing
            k = p / 0.62
            _drop(d, x, 10 + k * 22, 4.5 + k * 3.0, s)
        elif p < 0.82:  # fall off
            k = (p - 0.62) / 0.2
            _drop(d, x, 32 + k * 38, 7.5, s)
        # flat exhausted mouth
        d.line([(58 * s, 54 * s), (72 * s, 54 * s)],
               fill=255, width=max(2, int(s * 1.4)))


class ThumbsUp(Overlay):
    def modify(self, left, right, t):
        pass

    def draw(self, d, s, t):
        # pop in with a little overshoot, then bounce gently
        k = min(1.0, t * 3.2)
        scale = k * (1 + 0.35 * math.sin(min(k, 1.0) * math.pi))
        bounce = abs(math.sin(t * 3.0)) * 1.5 if k >= 1 else 0
        _thumb(d, 106, 31 - bounce, 34, s, scale)
        _smile(d, 46, 53, 15, s)


class Pew(Overlay):
    RATE = 0.16
    SPEED = 150

    def __init__(self, rng):
        super().__init__(rng)
        self.bullets: list[list[float]] = []
        self.cool = 0.3
        self.side = 0
        self.flash = 0.0
        self.flash_at = (0.0, 0.0)
        self.kick = 0.0

    def step(self, dt):
        self.cool -= dt
        self.flash -= dt
        self.kick = max(0.0, self.kick - dt * 14)
        if self.cool <= 0:
            self.cool = self.RATE
            self.side ^= 1
            ex = EYE_L if self.side else EYE_R
            ey = EYE_CY + self.rng.uniform(-3, 3)
            self.bullets.append([ex + 14, ey])
            self.flash = 0.06
            self.flash_at = (ex + 15, ey)
            self.kick = 2.2
        for b in self.bullets:
            b[0] += self.SPEED * dt
        self.bullets = [b for b in self.bullets if b[0] < W + 6]

    def modify(self, left, right, t):
        for p in (left, right):
            p["dx"] += 5 - self.kick  # aim right, recoil on shot

    def draw(self, d, s, t):
        for x, y in self.bullets:
            d.rounded_rectangle([x * s, (y - 1) * s, (x + 5) * s, (y + 1) * s],
                                radius=s, fill=255)
        if self.flash > 0:
            _spark(d, self.flash_at[0], self.flash_at[1], 7, s)


class Laugh(Overlay):
    def modify(self, left, right, t):
        j = abs(math.sin(t * 9.0)) * 1.5
        for p in (left, right):
            p["dy"] -= j

    def draw(self, d, s, t):
        h = 8 + abs(math.sin(t * 9.0)) * 6   # mouth opens with the ha-ha beat
        cx, cy, w = 64 * s, 46 * s, 15 * s
        d.pieslice([cx - w, cy - h * s, cx + w, cy + h * s], 0, 180, fill=255)


class Cry(Overlay):
    def __init__(self, rng):
        super().__init__(rng)
        self.tears: list[list[float]] = []
        self.cool = 0.2
        self.side = 0

    def step(self, dt):
        self.cool -= dt
        if self.cool <= 0:
            self.cool = 0.55
            self.side ^= 1
            x = (EYE_L if self.side else EYE_R) + self.rng.uniform(-4, 4)
            self.tears.append([x, 36.0])
        for tr in self.tears:
            tr[1] += 55 * dt
        self.tears = [tr for tr in self.tears if tr[1] < H + 6]

    def modify(self, left, right, t):
        j = math.sin(t * 30.0) * 0.6
        left["dx"] += j
        right["dx"] += j

    def draw(self, d, s, t):
        for x, y in self.tears:
            _drop(d, x, y, 5, s)
        _smile(d, 64, 56, 13, s, frown=True)


class Hearts(Overlay):
    def __init__(self, rng):
        super().__init__(rng)
        self.hs: list[dict] = []
        self.cool = 0.1

    def step(self, dt):
        self.cool -= dt
        if self.cool <= 0 and len(self.hs) < 5:
            self.cool = 0.45
            self.hs.append({
                "x": self.rng.uniform(10, 118), "y": 66.0,
                "vy": self.rng.uniform(18, 30), "ph": self.rng.uniform(0, 6.28),
                "sz": self.rng.uniform(5, 9), "born": 0.0,
            })
        for hh in self.hs:
            hh["y"] -= hh["vy"] * dt
            hh["born"] += dt
        self.hs = [hh for hh in self.hs if hh["y"] > -8]

    def draw(self, d, s, t):
        for hh in self.hs:
            x = hh["x"] + math.sin(t * 3 + hh["ph"]) * 3
            sz = hh["sz"] * min(1.0, hh["born"] * 4)
            _heart(d, x, hh["y"], sz, s)


class Shock(Overlay):
    def modify(self, left, right, t):
        j = math.sin(t * 38.0) * 1.2
        for p in (left, right):
            p["dx"] += j

    def draw(self, d, s, t):
        on = int(t * 7) % 2  # spikes flash, alternating sets
        for ex in (EYE_L, EYE_R):
            for i in range(8):
                if i % 2 != on:
                    continue
                a = math.radians(i * 45 - 90)
                r0, r1 = 26, 34
                x0 = ex + math.cos(a) * r0 * 0.95
                y0 = EYE_CY + math.sin(a) * r0 * 0.62
                x1 = ex + math.cos(a) * r1 * 0.95
                y1 = EYE_CY + math.sin(a) * r1 * 0.62
                d.line([(x0 * s, y0 * s), (x1 * s, y1 * s)],
                       fill=255, width=max(2, int(s * 1.1)))


class Music(Overlay):
    def __init__(self, rng):
        super().__init__(rng)
        self.notes: list[dict] = []
        self.cool = 0.2

    def step(self, dt):
        self.cool -= dt
        if self.cool <= 0 and len(self.notes) < 3:
            self.cool = 0.8
            self.notes.append({
                "x": self.rng.uniform(14, 110), "y": 68.0,
                "vy": self.rng.uniform(16, 24), "ph": self.rng.uniform(0, 6.28),
                "sz": self.rng.uniform(7, 10),
            })
        for n in self.notes:
            n["y"] -= n["vy"] * dt
        self.notes = [n for n in self.notes if n["y"] > -10]

    def modify(self, left, right, t):
        bob = math.sin(t * 4.0) * 3.0
        for p in (left, right):
            p["dx"] += bob

    def draw(self, d, s, t):
        for n in self.notes:
            x = n["x"] + math.sin(t * 2.5 + n["ph"]) * 2.5
            _note(d, x, n["y"], n["sz"], s)
        # whistling 'o' mouth, swaying with the head-bob
        mx = 64 + math.sin(t * 4.0) * 3.0
        r = 3.2 * s
        d.ellipse([mx * s - r, 53 * s - r, mx * s + r, 53 * s + r],
                  outline=255, width=max(2, int(s * 1.3)))


class Rage(Overlay):
    def __init__(self, rng):
        super().__init__(rng)
        self.puffs: list[dict] = []
        self.cool = 0.15
        self.side = 0

    def step(self, dt):
        self.cool -= dt
        if self.cool <= 0:
            self.cool = 0.7
            self.side ^= 1
            self.puffs.append({"x": 24 if self.side else 104,
                               "y": 10.0, "age": 0.0})
        for pf in self.puffs:
            pf["age"] += dt
            pf["y"] -= 6 * dt
        self.puffs = [pf for pf in self.puffs if pf["age"] < 0.9]

    def modify(self, left, right, t):
        for p in (left, right):
            p["dx"] += math.sin(t * 42.0) * 1.3
            p["dy"] += math.sin(t * 35.0) * 0.5

    def draw(self, d, s, t):
        for pf in self.puffs:
            k = pf["age"] / 0.9
            size = 6 + k * 8
            if k < 0.75:  # grow then pop out of existence
                _cloud(d, pf["x"], pf["y"], size, s)


class Confused(Overlay):
    def modify(self, left, right, t):
        for p in (left, right):
            p["dx"] += math.sin(t * 1.8) * 2.0

    def draw(self, d, s, t):
        k = min(1.0, t * 3.0)
        sway = math.sin(t * 2.6) * 2.5
        _question(d, 106 + sway, 14 + math.sin(t * 3.4) * 1.5, 16 * k, s)


# name -> (base expression, eye parameter overrides, overlay class)
ANIMATIONS: dict[str, tuple[str, dict | None, type[Overlay]]] = {
    "party":     ("joy", {"h": 34.0, "dy": -2.0}, Confetti),
    "tired":     ("sleepy", {"dy": -4.0}, Sweat),
    "thumbs_up": ("happy", {"dx": -16.0, "w": 22.0, "h": 30.0, "dy": -2.0}, ThumbsUp),
    "pew":       ("mischief", None, Pew),
    "laugh":     ("joy", {"h": 26.0, "dy": -14.0, "w": 28.0, "bot_curve": 0.55}, Laugh),
    "cry":       ("sad", {"h": 26.0, "dy": -10.0, "w": 28.0}, Cry),
    "hearts":    ("love", None, Hearts),
    "shock":     ("surprised", {"h": 36.0, "w": 30.0}, Shock),
    "music":     ("happy", {"h": 28.0, "dy": -9.0}, Music),
    "rage":      ("furious", None, Rage),
    "confused":  ("skeptic", {"dx": -6.0}, Confused),
}
