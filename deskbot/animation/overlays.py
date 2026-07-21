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

def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 2


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


def _gun(d, cx, cy, size, s, kick=0.0):
    """Small pixel-art pistol, muzzle pointing right. Returns muzzle tip (x, y)."""
    cx, cy, size = (cx - kick) * s, cy * s, size * s

    # chunky rear body/slide
    body_w, body_h = size * 0.34, size * 0.30
    body_x0 = cx - size * 0.06
    d.rounded_rectangle([body_x0, cy - body_h / 2, body_x0 + body_w, cy + body_h / 2],
                        radius=body_h * 0.22, fill=255)

    # thin barrel sticking out the front (right)
    bl, bh = size * 0.42, size * 0.13
    bx0 = body_x0 + body_w - size * 0.03
    d.rectangle([bx0, cy - bh / 2, bx0 + bl, cy + bh / 2], fill=255)

    # trigger guard: small outline loop under the body
    gr_r = body_h * 0.24
    gr_cx, gr_cy = body_x0 + body_w * 0.42, cy + body_h * 0.42
    d.arc([gr_cx - gr_r, gr_cy - gr_r * 0.6, gr_cx + gr_r, gr_cy + gr_r * 1.4],
          start=200, end=340, fill=255, width=max(1, int(s * 0.6)))

    # grip, hanging down and angled back (left) from the body
    gw, gh = size * 0.24, size * 0.46
    gx0 = body_x0 + size * 0.02
    gy0 = cy + body_h * 0.42
    d.polygon([(gx0, gy0),
               (gx0 + gw, gy0),
               (gx0 + gw * 0.62, gy0 + gh),
               (gx0 - gw * 0.30, gy0 + gh)], fill=255)

    return (bx0 + bl) / s, cy / s


def _flake(d, cx, cy, r, s):
    """Six-arm snowflake with little branch ticks."""
    cx, cy, r = cx * s, cy * s, r * s
    wdt = max(1, int(s * 0.55))
    for i in range(3):
        a = i * math.pi / 3 + math.pi / 6
        dx, dy = math.cos(a) * r, math.sin(a) * r
        d.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=255, width=wdt)
    q = r * 0.35
    d.line([(cx - q, cy), (cx + q, cy)], fill=255, width=wdt)


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
    """Gunslinger squint: one eye winks shut to aim, the other narrows, a
    pixel-art pistol sits below the face, and the bot fires 3-round bursts
    with bold tracers, muzzle flash, drifting smoke and a recoil kick."""

    BURST_GAP = 0.65      # pause between bursts
    PELLET_GAP = 0.075    # time between pellets within a burst
    BURST_SIZE = 3
    SPEED = 190

    GUN_X, GUN_Y, GUN_SIZE = 18, 50, 30

    def __init__(self, rng):
        super().__init__(rng)
        self.bullets: list[list] = []   # [x, y, trail[(x,y),...]]
        self.smoke: list[dict] = []
        self.burst_cd = 0.35
        self.pellet_cd = 0.0
        self.left_in_burst = 0
        self.flash = 0.0
        self.flash_at = (0.0, 0.0)
        self.kick = 0.0
        # matches the geometry _gun() draws, kept in sync so bullets spawn
        # exactly at the drawn barrel tip
        self.muzzle = (self.GUN_X + self.GUN_SIZE * 0.75, self.GUN_Y)

    def step(self, dt):
        self.burst_cd -= dt
        self.pellet_cd -= dt
        self.flash = max(0.0, self.flash - dt)
        self.kick = max(0.0, self.kick - dt * 16)

        if self.left_in_burst <= 0 and self.burst_cd <= 0:
            self.left_in_burst = self.BURST_SIZE
            self.pellet_cd = 0.0
        if self.left_in_burst > 0 and self.pellet_cd <= 0:
            self.left_in_burst -= 1
            self.pellet_cd = self.PELLET_GAP
            mx, my = self.muzzle
            y = my + self.rng.uniform(-1.0, 1.0)
            self.bullets.append([mx, y, []])
            self.flash = 0.06
            self.flash_at = (mx + 1, y)
            self.kick = 4.0
            self.smoke.append({"x": mx - 4, "y": my - 4, "age": 0.0})
            if self.left_in_burst == 0:
                self.burst_cd = self.BURST_GAP

        for b in self.bullets:
            b[2].append((b[0], b[1]))
            if len(b[2]) > 5:
                b[2].pop(0)
            b[0] += self.SPEED * dt
        self.bullets = [b for b in self.bullets if b[0] < W + 8]

        for sm in self.smoke:
            sm["age"] += dt
            sm["y"] -= 7 * dt
            sm["x"] += 4 * dt
        self.smoke = [sm for sm in self.smoke if sm["age"] < 0.55]

    def modify(self, left, right, t):
        # right eye winks shut to sight down, left eye narrows to aim
        right["open"] = 0.0
        right["bot_curve"] = 0.0
        left["open"] = min(left["open"], 0.45)
        left["top_lid"] = max(left["top_lid"], 0.10)
        for p in (left, right):
            p["dx"] += 3 - self.kick * 0.6  # lean in, recoil on fire

    def draw(self, d, s, t):
        _gun(d, self.GUN_X, self.GUN_Y, self.GUN_SIZE, s, kick=self.kick * 0.5)
        for x, y, trail in self.bullets:
            n = len(trail)
            for i, (tx, ty) in enumerate(trail):
                shade = (i + 1) / max(1, n)
                d.line([(tx * s, ty * s), ((tx - 6) * s, ty * s)],
                       fill=255, width=max(1, int(s * 0.7 * shade)))
            d.ellipse([(x - 1.6) * s, (y - 1.6) * s, (x + 1.6) * s, (y + 1.6) * s],
                      fill=255)
        for sm in self.smoke:
            k = sm["age"] / 0.55
            if k < 0.8:
                _cloud(d, sm["x"], sm["y"], 4 + k * 8, s)
        if self.flash > 0:
            _spark(d, self.flash_at[0], self.flash_at[1], 13, s)
            _spark(d, self.flash_at[0] + 2, self.flash_at[1] - 1, 7, s)
        # cocky little smirk
        d.line([(58 * s, 50 * s), (70 * s, 47 * s)],
               fill=255, width=max(2, int(s * 1.2)))


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


class Pew3D(Overlay):
    """Bullet-time shot straight at the viewer: a targeting reticle spins in
    and locks on, then the bullet screws in from the distance through a
    warp-speed tunnel of streaks, the screen strobes on impact, and the
    "glass" spiderwebs with cracks and shockwave rings before the shards
    drop away to reveal the eyes again. Runs on its own internal clock
    (self.local_t) so it can loop through phases independent of the eye
    controller's tween timer.
    """

    CYCLE = 3.0
    P_LOCK = 0.55
    P_FLY = 0.6
    P_IMPACT = 0.14
    P_SHATTER = 1.15
    P_CLEAR = CYCLE - (P_LOCK + P_FLY + P_IMPACT + P_SHATTER)

    CX, CY = 64, 30

    def __init__(self, rng):
        super().__init__(rng)
        self.local_t = 0.0
        self._roll_cycle()

    def _roll_cycle(self):
        r = self.rng
        # warp-tunnel streaks: (angle, cycle phase)
        self.rays = [(i / 14 * 2 * math.pi + r.uniform(-0.12, 0.12), r.random())
                     for i in range(14)]
        # glass cracks: jagged polylines radiating out of the impact point
        self.cracks = []
        for i in range(8):
            a = i / 8 * 2 * math.pi + r.uniform(-0.28, 0.28)
            pts, rad = [(self.CX, self.CY)], 5.0
            while rad < 58:
                aa = a + r.uniform(-0.25, 0.25)
                pts.append((self.CX + math.cos(aa) * rad * 1.35,
                            self.CY + math.sin(aa) * rad * 0.85))
                rad += r.uniform(8, 14)
            self.cracks.append({"pts": pts, "fall": r.uniform(0.7, 1.6)})

    def step(self, dt):
        self.local_t += dt
        if self.local_t >= self.CYCLE:
            self.local_t -= self.CYCLE
            self._roll_cycle()

    def _phase(self):
        t = self.local_t
        for name, dur in (("lock", self.P_LOCK), ("fly", self.P_FLY),
                          ("impact", self.P_IMPACT), ("shatter", self.P_SHATTER)):
            if t < dur:
                return name, t / dur
            t -= dur
        return "clear", min(1.0, t / self.P_CLEAR)

    def modify(self, left, right, t):
        phase, k = self._phase()
        if phase == "lock":
            # eyes go small and worried so the reticle reads around them
            for p in (left, right):
                p["w"] *= 0.68
                p["h"] *= 0.55
                p["top_lid"] = max(p["top_lid"], 0.12)
        elif phase == "fly":
            flinch = k * k
            for p in (left, right):
                p["w"] *= 0.68 - 0.25 * flinch
                p["h"] *= 0.55 - 0.3 * flinch
                p["dy"] -= 2.0 * flinch
                p["dx"] += math.sin(t * 45) * 1.5 * flinch
        elif phase == "impact":
            for p in (left, right):
                p["scale"] = 0.0
        elif phase == "shatter":
            shake = max(0.0, 1.0 - k * 3.0)
            for p in (left, right):
                # gone while the glass hangs, pop back as the shards fall
                p["scale"] = 0.0 if k < 0.6 else min(1.0, (k - 0.6) / 0.32)
                p["dx"] += math.sin(t * 60) * 3.5 * shake
                p["dy"] += math.cos(t * 48) * 2.0 * shake

    def _reticle(self, d, s, k):
        cx, cy = self.CX, self.CY
        rad = 34 - _ease_out(k) * 21          # spiral in and tighten
        spin = math.degrees(self.local_t * 4.5)
        locked = k > 0.78
        wdt = max(2, int(s * 1.1))
        rx, ry = rad * 1.25, rad * 0.85
        box = [(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s]
        for i in range(4):                     # four spinning arc segments
            a0 = spin + i * 90
            d.arc(box, start=a0, end=a0 + 55, fill=255, width=wdt)
        for i in range(4):                     # compass tick marks
            a = math.radians(i * 90)
            x0, y0 = cx + math.cos(a) * rx * 0.75, cy + math.sin(a) * ry * 0.75
            x1, y1 = cx + math.cos(a) * rx * 1.05, cy + math.sin(a) * ry * 1.05
            d.line([(x0 * s, y0 * s), (x1 * s, y1 * s)], fill=255, width=wdt)
        # center dot: appears and double-blinks once locked
        if not locked or int(self.local_t * 16) % 2:
            r = 2.2 if locked else 1.2
            d.ellipse([(cx - r) * s, (cy - r * 0.8) * s,
                       (cx + r) * s, (cy + r * 0.8) * s], fill=255)

    def draw(self, d, s, t):
        phase, k = self._phase()
        cx, cy = self.CX, self.CY

        if phase == "lock":
            self._reticle(d, s, k)

        elif phase == "fly":
            # warp-speed streaks rushing outward past the viewer
            for a, ph in self.rays:
                prog = (self.local_t * 2.6 + ph) % 1.0
                r0 = 8 + prog * 62
                r1 = r0 + 5 + k * 16
                d.line([((cx + math.cos(a) * r0 * 1.4) * s,
                         (cy + math.sin(a) * r0 * 0.8) * s),
                        ((cx + math.cos(a) * r1 * 1.4) * s,
                         (cy + math.sin(a) * r1 * 0.8) * s)],
                       fill=255, width=max(1, int(s * (0.5 + prog))))
            # the bullet screws in, wobbling less as it gets close
            r = 1.5 + (k ** 2.2) * 54
            bx = cx + math.sin(self.local_t * 26) * 2.5 * (1 - k)
            d.ellipse([(bx - r) * s, (cy - r * 0.8) * s,
                       (bx + r) * s, (cy + r * 0.8) * s], fill=255)
            if r > 6:  # rifling stripe shows the spin
                a = self.local_t * 11
                px, py = math.cos(a), math.sin(a)
                d.line([((bx - px * r * 0.85) * s, (cy - py * r * 0.65) * s),
                        ((bx + px * r * 0.85) * s, (cy + py * r * 0.65) * s)],
                       fill=0, width=max(2, int(r * s * 0.16)))

        elif phase == "impact":
            # white strobe with black flicker frames for punch
            if int(self.local_t * 60) % 3:
                d.rectangle([0, 0, W * s, H * s], fill=255)

        elif phase == "shatter":
            reveal = min(1.0, k * 3.5)
            drop_k = max(0.0, (k - 0.5) / 0.5) ** 2
            wdt = max(2, int(s * 1.1))
            for cr in self.cracks:
                pts = cr["pts"]
                n = max(2, int(1 + reveal * (len(pts) - 1)))
                dy_off = drop_k * 90 * cr["fall"]
                seg = [((x) * s, (y + dy_off) * s) for x, y in pts[:n]]
                if seg[0][1] < (H + 10) * s:
                    d.line(seg, fill=255, width=wdt)
            # shockwave rings racing outward right after impact
            for i in range(2):
                rk = k * 2.4 - i * 0.4
                if 0.0 < rk < 1.0:
                    rr = 8 + rk * 58
                    d.ellipse([(cx - rr * 1.3) * s, (cy - rr * 0.85) * s,
                               (cx + rr * 1.3) * s, (cy + rr * 0.85) * s],
                              outline=255,
                              width=max(1, int(s * 2.2 * (1 - rk))))
            if k < 0.35:  # residual impact flare
                _spark(d, cx, cy + drop_k * 40, 16 * (1 - k * 2.4), s)


class EyeShot(Overlay):
    """The reverse of Pew3D: instead of a bullet flying OUT of the screen at
    the viewer, this is the viewer's shot flying INTO the screen at the bot.
    A tracer starts big and close (like it just left the muzzle right at the
    camera) and rockets away into the depth of the scene, shrinking as it
    goes, until it lands square on one eye. That eye shatters into a small
    spiderweb of cracks with a few shards flicking loose and falling, while
    the other eye stays open and flinches wide at the hit -- then the
    cracked eye knits back together with a satisfied little pop and a
    spark, good as new. Re-picks left/right eye each cycle for variety and
    runs on its own clock, independent of the eye controller's tween timer.
    """

    CYCLE = 3.4
    P_FLY = 0.42
    P_IMPACT = 0.10
    P_CRACK = 0.95
    P_HEAL = 0.45
    P_REST = CYCLE - (P_FLY + P_IMPACT + P_CRACK + P_HEAL)

    def __init__(self, rng):
        super().__init__(rng)
        self.local_t = 0.0
        self._roll_cycle()

    def _roll_cycle(self):
        r = self.rng
        self.target_x = EYE_R if r.random() < 0.5 else EYE_L
        # jagged crack polylines radiating from the impact point, sized to
        # roughly one eye's footprint rather than the whole face
        self.cracks = []
        for i in range(7):
            a = i / 7 * 2 * math.pi + r.uniform(-0.3, 0.3)
            pts, rad = [(self.target_x, EYE_CY)], 3.0
            while rad < 20:
                aa = a + r.uniform(-0.22, 0.22)
                pts.append((self.target_x + math.cos(aa) * rad,
                            EYE_CY + math.sin(aa) * rad * 0.8))
                rad += r.uniform(4, 7)
            self.cracks.append({"pts": pts, "fall": r.uniform(0.6, 1.4)})
        self.shards = [{"a": r.uniform(0, 2 * math.pi), "sp": r.uniform(0.5, 1.1),
                        "sz": r.uniform(1.2, 2.6)} for _ in range(7)]

    def step(self, dt):
        self.local_t += dt
        if self.local_t >= self.CYCLE:
            self.local_t -= self.CYCLE
            self._roll_cycle()

    def _phase(self):
        t = self.local_t
        for name, dur in (("fly", self.P_FLY), ("impact", self.P_IMPACT),
                          ("crack", self.P_CRACK), ("heal", self.P_HEAL)):
            if t < dur:
                return name, t / dur
            t -= dur
        return "rest", min(1.0, t / self.P_REST)

    def modify(self, left, right, t):
        phase, k = self._phase()
        target = right if self.target_x == EYE_R else left
        other = left if target is right else right

        if phase == "fly":
            flinch = k * k
            target["top_lid"] = max(target["top_lid"], 0.10 * flinch)
            other["w"] *= 1.0 + 0.04 * flinch
        elif phase in ("impact", "crack"):
            # the real eye is gone -- the crack glyph in draw() takes over
            target["scale"] = 0.0
            other["w"] *= 1.12
            other["h"] *= 1.12
            other["top_lid"] = 0.0
            if phase == "crack":
                other["dx"] += math.sin(t * 30) * 0.6 * max(0.0, 1.0 - k * 1.5)
        elif phase == "heal":
            e = _ease_out(k)
            target["scale"] = min(1.0, e * 1.08)
            other["w"] *= 1.0 + 0.06 * (1 - e)
            other["h"] *= 1.0 + 0.06 * (1 - e)

    def _draw_tracer(self, d, s, k):
        # recedes from right at the camera toward the target eye, shrinking
        # and trailing a speed-line burst as it tunnels away from the viewer
        e = k ** 1.6
        x = 64 + (self.target_x - 64) * e
        r = 30 * (1 - e) + 1.5
        for i in range(10):
            a = i / 10 * 2 * math.pi
            r0 = r * 0.4
            r1 = r0 + 4 + (1 - e) * 10
            d.line([((x + math.cos(a) * r0) * s, (EYE_CY + math.sin(a) * r0 * 0.8) * s),
                    ((x + math.cos(a) * r1) * s, (EYE_CY + math.sin(a) * r1 * 0.8) * s)],
                   fill=255, width=max(1, int(s * 0.6)))
        d.ellipse([(x - r) * s, (EYE_CY - r * 0.8) * s,
                   (x + r) * s, (EYE_CY + r * 0.8) * s], fill=255)
        if r > 5:
            a = self.local_t * 14
            px, py = math.cos(a), math.sin(a)
            d.line([((x - px * r * 0.8) * s, (EYE_CY - py * r * 0.6) * s),
                    ((x + px * r * 0.8) * s, (EYE_CY + py * r * 0.6) * s)],
                   fill=0, width=max(2, int(r * s * 0.16)))

    def draw(self, d, s, t):
        phase, k = self._phase()

        if phase == "fly":
            self._draw_tracer(d, s, k)

        elif phase == "impact":
            if int(self.local_t * 70) % 3:
                r = 18
                d.ellipse([(self.target_x - r) * s, (EYE_CY - r * 0.8) * s,
                           (self.target_x + r) * s, (EYE_CY + r * 0.8) * s], fill=255)

        elif phase == "crack":
            reveal = min(1.0, k * 3.2)
            drop_k = max(0.0, (k - 0.45) / 0.55) ** 2
            wdt = max(1, int(s * 0.9))
            for cr in self.cracks:
                pts = cr["pts"]
                n = max(2, int(1 + reveal * (len(pts) - 1)))
                dy_off = drop_k * 26 * cr["fall"]
                seg = [(x * s, (y + dy_off) * s) for x, y in pts[:n]]
                d.line(seg, fill=255, width=wdt)
            if k < 0.85:
                ke = 1.0 - (1.0 - min(1.0, k * 2.2)) ** 2
                for sh in self.shards:
                    dist = (2 + ke * 16) * sh["sp"]
                    x = self.target_x + math.cos(sh["a"]) * dist
                    y = EYE_CY + math.sin(sh["a"]) * dist * 0.7 + k * k * 22
                    z = sh["sz"] * s
                    d.rectangle([x * s, y * s, x * s + z, y * s + z], fill=255)
            if k < 0.5:  # dim eye-socket ring so it doesn't read as a hole
                rr = 3 + k * 6
                d.ellipse([(self.target_x - rr) * s, (EYE_CY - rr * 0.8) * s,
                           (self.target_x + rr) * s, (EYE_CY + rr * 0.8) * s],
                          outline=255, width=max(1, int(s * 0.7)))

        elif phase == "heal":
            if k < 0.35:
                _spark(d, self.target_x, EYE_CY, 10 * (1 - k / 0.35), s)


class Glasses(Overlay):
    """Deal-with-it sunglasses drop in from the top and land with a springy
    overshoot. The eyes shrink down into little pupils that stay visible
    through the lenses, wandering around inside the frames, while a glint
    sweeps across and the bot smirks."""

    LENS_W, LENS_H = 38, 27
    LAND = 0.55         # seconds until the drop finishes
    COVER_Y = 14        # once the frames pass this height they hide the eyes

    def __init__(self, rng):
        super().__init__(rng)
        self._look = (0.0, 0.0, 1.0)   # captured gaze (dx, dy, open)

    def _gy(self, t):
        """Glasses center height, shared with modify() so the mini eyes bob
        with the frames instead of sliding behind them."""
        k = min(1.0, t / self.LAND)
        c1, c3 = 1.70158, 2.70158           # ease-out-back overshoot
        e = 1 + c3 * (k - 1) ** 3 + c1 * (k - 1) ** 2
        gy = -36 + e * 66
        if t > self.LAND + 0.3:
            gy += math.sin((t - self.LAND) * 2.4) * 1.2
        return gy

    def modify(self, left, right, t):
        # steal the controller's live gaze/blink for the mini eyes, then
        # hide the real eyes once the frames have dropped over them
        self._look = (left["dx"], left["dy"], left["open"])
        if self._gy(t) > self.COVER_Y:
            for p in (left, right):
                p["scale"] = 0.0
        else:
            for p in (left, right):
                p["top_lid"] = max(p["top_lid"], 0.15)

    def draw(self, d, s, t):
        gy = self._gy(t)
        hw, hh = self.LENS_W / 2, self.LENS_H / 2
        wdt = max(2, int(s * 1.7))

        for ex in (EYE_L, EYE_R):
            box = [(ex - hw) * s, (gy - hh) * s, (ex + hw) * s, (gy + hh) * s]
            d.rounded_rectangle(box, radius=6 * s, fill=0)
            d.rounded_rectangle(box, radius=6 * s, outline=255, width=wdt)
        # bridge and temple arms
        d.line([((EYE_L + hw) * s, (gy - 6) * s), ((EYE_R - hw) * s, (gy - 6) * s)],
               fill=255, width=wdt)
        d.line([((EYE_L - hw) * s, (gy - 5) * s), (0, (gy - 10) * s)],
               fill=255, width=wdt)
        d.line([((EYE_R + hw) * s, (gy - 5) * s), (W * s, (gy - 10) * s)],
               fill=255, width=wdt)

        # mini eyes visible through the lenses: shrink down after the frames
        # land, then wander around inside them
        if gy > self.COVER_Y:
            gx, gyy, open_ = self._look
            sk = _ease_out(min(1.0, max(0.0, (t - self.LAND + 0.15) / 0.5)))
            ew = 20 - 8 * sk
            eh = (17 - 7 * sk) * max(0.12, open_)
            wander = sk * 1.0
            ox = gx * 0.5 + (4.0 * math.sin(t * 0.9) + 2.0 * math.sin(t * 2.3)) * wander
            oy = gyy * 0.4 + 1.6 * math.sin(t * 1.4 + 1.0) * wander
            ox = max(-hw + ew / 2 + 3, min(hw - ew / 2 - 3, ox))
            oy = max(-hh + eh / 2 + 3, min(hh - eh / 2 - 3, oy))
            for ex in (EYE_L, EYE_R):
                cx, cy = ex + ox, gy + oy
                d.rounded_rectangle([(cx - ew / 2) * s, (cy - eh / 2) * s,
                                     (cx + ew / 2) * s, (cy + eh / 2) * s],
                                    radius=min(ew, eh) * 0.35 * s, fill=255)

        # periodic glint sweeping diagonally across both lenses
        if t > self.LAND + 0.15:
            gp = ((t - self.LAND - 0.15) % 2.4) / 2.4
            if gp < 0.3:
                sweep = gp / 0.3
                for ex in (EYE_L, EYE_R):
                    x0, y0 = ex - hw, gy - hh
                    sx = x0 - 8 + sweep * (self.LENS_W + 18)
                    for off, gw in ((0.0, 2.6), (5.5, 1.1)):
                        yy = y0 + 2.0
                        while yy < gy + hh - 1.5:
                            xx = sx + off - (yy - y0) * 0.55
                            if x0 + 2.5 <= xx <= ex + hw - 2.5 - gw:
                                d.rectangle([xx * s, yy * s,
                                             (xx + gw) * s, (yy + 1.2) * s],
                                            fill=255)
                            yy += 1.0
        # smug little smirk
        d.line([(57 * s, 53 * s), (70 * s, 50 * s)],
               fill=255, width=max(2, int(s * 1.3)))
        d.line([(70 * s, 50 * s), (72 * s, 51.5 * s)],
               fill=255, width=max(2, int(s * 1.3)))


class Blast(Overlay):
    """Cartoon bomb detonation: the two eyeballs slide together and squish
    into one ball — which IS the bomb — a fuse pops out and burns down with
    a spark, then a strobe flash, a hollow ring fireball with flying debris
    and a shockwave, and drifting smoke as the eyes pop back in. Loops on
    its own clock."""

    CYCLE = 4.0
    P_MERGE = 0.7
    P_FUSE = 1.05
    P_FLASH = 0.12
    P_BOOM = 0.95
    P_SMOKE = CYCLE - (P_MERGE + P_FUSE + P_FLASH + P_BOOM)

    BX, BY = 64, 42       # bomb spot = where the eyes merge
    EX, EY = 64, 40       # explosion center

    FUSE = [(64.0, 33.5), (66.0, 30.0), (69.5, 28.0), (73.5, 29.0)]

    def __init__(self, rng):
        super().__init__(rng)
        self.local_t = 0.0
        self._roll_cycle()

    def _roll_cycle(self):
        r = self.rng
        self.debris = [{"a": r.uniform(0, 2 * math.pi), "sp": r.uniform(0.5, 1.15),
                        "sz": r.uniform(1.5, 3.2)} for _ in range(11)]
        self.spikes = [r.uniform(0.78, 1.0) for _ in range(14)]
        self.puffs = [{"x": self.EX + r.uniform(-16, 16), "ph": r.uniform(0, 6.28),
                       "sp": r.uniform(14, 24)} for _ in range(3)]

    def step(self, dt):
        self.local_t += dt
        if self.local_t >= self.CYCLE:
            self.local_t -= self.CYCLE
            self._roll_cycle()

    def _phase(self):
        t = self.local_t
        for name, dur in (("merge", self.P_MERGE), ("fuse", self.P_FUSE),
                          ("flash", self.P_FLASH), ("boom", self.P_BOOM)):
            if t < dur:
                return name, t / dur
            t -= dur
        return "smoke", min(1.0, t / self.P_SMOKE)

    def modify(self, left, right, t):
        phase, k = self._phase()
        if phase == "merge":
            # the eyeballs roll together and squish into one ball at the
            # bomb spot; near the end they wobble as they fuse
            e = _ease_out(k)
            wob = math.sin(t * 22) * 1.2 * max(0.0, k - 0.6)
            left["dx"] += (self.BX - EYE_L) * e
            right["dx"] -= (EYE_R - self.BX) * e
            for p in (left, right):
                p["dy"] += (self.BY - EYE_CY) * e + wob
                p["w"] *= 1.0 - 0.35 * e
                p["h"] *= 1.0 - 0.5 * e
                p["round"] = min(1.0, p["round"] + 0.6 * e)
        elif phase == "fuse":
            # the merged ball IS the bomb now; hide the real eyes
            for p in (left, right):
                p["scale"] = 0.0
        elif phase in ("flash", "boom"):
            for p in (left, right):
                p["scale"] = 0.0
        else:  # smoke: pop back in, a bit dazed
            for p in (left, right):
                p["scale"] = min(1.0, k * 2.2)
                p["dx"] += math.sin(t * 2.2) * 2.0

    def draw(self, d, s, t):
        phase, k = self._phase()

        if phase == "merge":
            # the eyes themselves are the show; ignite hint at the very end
            if k > 0.9:
                _spark(d, self.FUSE[0][0], self.FUSE[0][1] - 1, 4, s)
            return

        if phase == "fuse":
            # bomb body (the merged eyeballs), pulsing faster near zero
            r = 9 * (1 + 0.06 * math.sin(self.local_t * (6 + 18 * k)))
            d.ellipse([(self.BX - r) * s, (self.BY - r) * s,
                       (self.BX + r) * s, (self.BY + r) * s], fill=255)
            d.ellipse([(self.BX - r * 0.42) * s, (self.BY - r * 0.55) * s,
                       (self.BX - r * 0.05) * s, (self.BY - r * 0.18) * s],
                      fill=0)  # shine
            # fuse burning down toward the bomb
            n = len(self.FUSE)
            left_frac = 1.0 - k
            segs = max(1, int(math.ceil(left_frac * (n - 1))))
            pts = self.FUSE[:segs + 1]
            d.line([(x * s, y * s) for x, y in pts],
                   fill=255, width=max(2, int(s * 1.0)))
            tip = pts[-1]
            flick = 4.5 + math.sin(self.local_t * 42) * 2.0
            _spark(d, tip[0] + self.rng.uniform(-0.8, 0.8),
                   tip[1] + self.rng.uniform(-0.8, 0.8), flick, s)

        elif phase == "flash":
            if int(self.local_t * 60) % 3:
                d.rectangle([0, 0, W * s, H * s], fill=255)

        elif phase == "boom":
            ke = 1.0 - (1.0 - k) ** 2.2
            R = 8 + ke * 58
            n = len(self.spikes)
            spin = self.local_t * 1.6

            def burst(scale):
                pts = []
                for i, jit in enumerate(self.spikes):
                    rr = R * scale * (1.0 if i % 2 == 0 else 0.6) * jit
                    a = i / n * 2 * math.pi + spin
                    pts.append(((self.EX + math.cos(a) * rr * 1.25) * s,
                                (self.EY + math.sin(a) * rr * 0.8) * s))
                return pts

            d.polygon(burst(1.0), fill=255)
            if R > 20:  # hollow it out into a ring fireball
                d.polygon(burst(0.55), fill=0)
            # shockwave ring racing ahead of the fireball
            rk = min(1.0, k * 1.5)
            rr = R * 1.5
            if rk < 1.0:
                d.ellipse([(self.EX - rr * 1.25) * s, (self.EY - rr * 0.8) * s,
                           (self.EX + rr * 1.25) * s, (self.EY + rr * 0.8) * s],
                          outline=255, width=max(1, int(s * 2.4 * (1 - rk))))
            # debris hurled outward with a bit of gravity
            if k < 0.85:
                for db in self.debris:
                    dist = (6 + ke * 68) * db["sp"]
                    x = self.EX + math.cos(db["a"]) * dist * 1.25
                    y = self.EY + math.sin(db["a"]) * dist * 0.8 + k * k * 16
                    z = db["sz"] * s
                    d.rectangle([x * s, y * s, x * s + z, y * s + z], fill=255)

        else:  # smoke
            for pf in self.puffs:
                y = 44 - k * pf["sp"]
                x = pf["x"] + math.sin(t * 2.0 + pf["ph"]) * 2.5
                size = 7 + k * 9
                if k < 0.85:
                    _cloud(d, x, y, size, s)
            # smoldering crater sparks
            if int(self.local_t * 14) % 2 and k < 0.6:
                _spark(d, self.EX + math.sin(t * 7) * 4, 48, 4, s)


class Freeze(Overlay):
    """Feeling cold: snowflakes drift down, icicles grow from the top edge,
    the eyes shiver with periodic full-body shudders, and the bot exhales
    little puffs of breath over a trembling mouth. Brrr."""

    def __init__(self, rng):
        super().__init__(rng)
        r = self.rng
        self.flakes = [self._spawn_flake(anywhere=True) for _ in range(9)]
        self.icicles = [{"x": 5 + i * 17 + r.uniform(-4, 4),
                         "len": r.uniform(6, 14),
                         "ph": r.uniform(0, 6.28)} for i in range(8)]
        self.puffs: list[dict] = []
        self.cool = 0.9

    def _spawn_flake(self, anywhere=False):
        r = self.rng
        return {"x": r.uniform(3, 125),
                "y": r.uniform(-8, H) if anywhere else r.uniform(-10, -3),
                "vy": r.uniform(9, 17), "ph": r.uniform(0, 6.28),
                "sz": r.uniform(2.0, 3.4)}

    def step(self, dt):
        for f in self.flakes:
            f["y"] += f["vy"] * dt
            if f["y"] > H + 4:
                f.update(self._spawn_flake())
        self.cool -= dt
        if self.cool <= 0:
            self.cool = 1.9
            self.puffs.append({"x": 64.0, "y": 54.0, "age": 0.0})
        for pf in self.puffs:
            pf["age"] += dt
            pf["y"] -= 9 * dt
            pf["x"] += 6 * dt
        self.puffs = [pf for pf in self.puffs if pf["age"] < 1.0]

    def modify(self, left, right, t):
        # constant fine shiver plus a big shudder that rolls through
        shudder = max(0.0, math.sin(t * 1.1)) ** 8
        amp = 0.7 + 2.6 * shudder
        jx = math.sin(t * 33.0) * amp
        jy = math.sin(t * 27.0) * amp * 0.35
        for p in (left, right):
            p["dx"] += jx
            p["dy"] += jy + 1.0
            p["top_lid"] = max(p["top_lid"], 0.22 + 0.12 * shudder)
            p["w"] *= 1.0 - 0.06 * shudder     # hunch together when shuddering

    def draw(self, d, s, t):
        # icicles growing down from the top edge
        grow = _ease_out(min(1.0, t / 1.8))
        for i, ic in enumerate(self.icicles):
            ln = ic["len"] * grow
            if ln < 1.5:
                continue
            x = ic["x"]
            d.polygon([((x - 2.4) * s, 0), ((x + 2.4) * s, 0),
                       (x * s, ln * s)], fill=255)
            # occasional glint at a tip
            if int(t * 2.5 + ic["ph"]) % 9 == 0:
                _spark(d, x, ln + 2, 3.5, s)
        # falling snow, swaying as it drifts
        for f in self.flakes:
            x = f["x"] + math.sin(t * 1.6 + f["ph"]) * 3.0
            _flake(d, x, f["y"], f["sz"], s)
        # breath puffs drifting up and away
        for pf in self.puffs:
            k = pf["age"]
            if k < 0.8 or int(t * 18) % 2:      # flicker out at the end
                _cloud(d, pf["x"], pf["y"], 3.5 + k * 6, s)
        # chattering wavy mouth
        pts = [((x) * s, (55 + math.sin(x * 0.9 + t * 24) * 1.3) * s)
               for x in range(55, 74, 2)]
        d.line(pts, fill=255, width=max(2, int(s * 1.2)))


class Drink(Overlay):
    """Refreshment break: a glass of water rises up to the face, the bot
    gulps it down with happy closed eyes bobbing on every glug while the
    water level steps down and bubbles rise, then a satisfied "ahh" with
    sparkles before the empty glass drops away. Loops on its own clock."""

    CYCLE = 4.0
    P_RAISE = 0.5
    P_DRINK = 2.0
    P_AHH = 1.0
    P_LOWER = CYCLE - (P_RAISE + P_DRINK + P_AHH)

    GX, GY = 64, 41       # glass top-center while drinking
    GH = 20               # glass height
    TOP_HW, BOT_HW = 10, 7

    def __init__(self, rng):
        super().__init__(rng)
        self.local_t = 0.0
        self.bubbles = [{"x": rng.uniform(-3.5, 3.5), "ph": rng.uniform(0, 6.28),
                         "sp": rng.uniform(6, 11)} for _ in range(2)]

    def step(self, dt):
        self.local_t += dt
        if self.local_t >= self.CYCLE:
            self.local_t -= self.CYCLE

    def _phase(self):
        t = self.local_t
        for name, dur in (("raise", self.P_RAISE), ("drink", self.P_DRINK),
                          ("ahh", self.P_AHH)):
            if t < dur:
                return name, t / dur
            t -= dur
        return "lower", min(1.0, t / self.P_LOWER)

    def modify(self, left, right, t):
        phase, k = self._phase()
        if phase == "raise":
            # notice the glass: peek down at it
            for p in (left, right):
                p["dy"] += 3 * _ease_out(k)
            left["dx"] += 3 * _ease_out(k)
            right["dx"] -= 3 * _ease_out(k)
        elif phase == "drink":
            gulp = max(0.0, math.sin(t * 7.0))
            for p in (left, right):
                p["bot_curve"] = max(p["bot_curve"], 0.55)   # blissful arcs
                p["top_lid"] = max(p["top_lid"], 0.30)
                p["dy"] += 2 + gulp * 1.8                    # bob per glug
        elif phase == "ahh":
            for p in (left, right):
                p["bot_curve"] = max(p["bot_curve"], 0.6)
                p["h"] *= 1.05
                p["dy"] -= 1.5 * math.sin(k * math.pi)       # content lift

    def _glass(self, d, s, rise, level, t):
        """Glass outline + wavy water at `level` (1 full .. 0 empty)."""
        gx, gy = self.GX, self.GY + rise
        y1 = gy + self.GH
        wdt = max(2, int(s * 1.1))
        d.line([((gx - self.TOP_HW) * s, gy * s), ((gx - self.BOT_HW) * s, y1 * s)],
               fill=255, width=wdt)
        d.line([((gx + self.TOP_HW) * s, gy * s), ((gx + self.BOT_HW) * s, y1 * s)],
               fill=255, width=wdt)
        d.line([((gx - self.BOT_HW) * s, y1 * s), ((gx + self.BOT_HW) * s, y1 * s)],
               fill=255, width=wdt)
        if level > 0.03:
            ws = gy + 2 + (1.0 - level) * (self.GH - 4)
            f = (ws - gy) / self.GH
            hw = self.TOP_HW + (self.BOT_HW - self.TOP_HW) * f
            wob = math.sin(t * 9.0) * 0.7
            d.polygon([((gx - hw + 1) * s, (ws + wob) * s),
                       ((gx + hw - 1) * s, (ws - wob) * s),
                       ((gx + self.BOT_HW - 1) * s, (y1 - 1) * s),
                       ((gx - self.BOT_HW + 1) * s, (y1 - 1) * s)], fill=255)
            # bubbles rising through the water (black, inside the fill)
            depth = y1 - ws
            if depth > 7:
                for b in self.bubbles:
                    by = y1 - 2.5 - ((t * b["sp"] + b["ph"] * 3) % (depth - 4))
                    if ws + 2 < by < y1 - 2:
                        r = 0.9 * s
                        bx = (gx + b["x"]) * s
                        d.ellipse([bx - r, by * s - r, bx + r, by * s + r], fill=0)

    def draw(self, d, s, t):
        phase, k = self._phase()
        if phase == "raise":
            self._glass(d, s, (1 - _ease_out(k)) * 26, 1.0, t)
        elif phase == "drink":
            self._glass(d, s, 0.0, 1.0 - k, t)
            # stray droplets flicking off on each gulp
            if math.sin(t * 7.0) > 0.85:
                _drop(d, self.GX - 13, self.GY + 4, 3.5, s)
        elif phase == "ahh":
            if k < 0.7:  # sparkles of satisfaction
                for i, (ox, oy) in enumerate(((-28, -2), (28, -5), (0, -12))):
                    ph = (t * 3 + i) % 3
                    if ph < 1.6:
                        _spark(d, self.GX + ox, self.GY + oy,
                               8 * math.sin(ph / 1.6 * math.pi), s)
            # happy open "ahh" mouth
            r = (3.6 + math.sin(min(k, 0.5) * math.pi) * 1.4)
            d.pieslice([(64 - r) * s, (52 - r * 0.4) * s,
                        (64 + r) * s, (52 + r * 1.2) * s], 0, 180, fill=255)
        else:  # lower: empty glass drops away
            self._glass(d, s, _ease_out(k) * 28, 0.0, t)


class Hypnotized(Overlay):
    """Classic hypnosis gag: the eyes swirl into tight spirals that spin
    continuously, growing outward from the center like a swirl pattern
    instead of popping in instantly. A gentle bob keeps it feeling alive
    rather than static."""

    TURNS = 2.3
    RATE = 3.6      # rotations per second
    EASE = 0.6      # seconds for the eyes to swirl into the spiral

    def modify(self, left, right, t):
        k = _ease_out(min(1.0, t / self.EASE))
        for p in (left, right):
            # eyes narrow and get pulled toward center as the swirl forms,
            # then vanish once the spiral has fully grown in
            p["top_lid"] = max(p["top_lid"], k * 0.5)
            p["scale"] = 1.0 - k

    def _spiral(self, d, cx, cy, r, phase, s):
        steps = 34
        pts = []
        for i in range(steps + 1):
            frac = i / steps
            ang = phase + frac * self.TURNS * 2 * math.pi
            rad = r * frac
            pts.append(((cx + math.cos(ang) * rad) * s,
                        (cy + math.sin(ang) * rad * 0.88) * s))
        d.line(pts, fill=255, width=max(2, int(s * 1.3)))

    def draw(self, d, s, t):
        grow = _ease_out(min(1.0, t / self.EASE))
        if grow <= 0.02:
            return
        bob = math.sin(t * 1.4) * 1.2
        phase = t * self.RATE * 2 * math.pi
        for ex in (EYE_L, EYE_R):
            cy = EYE_CY + bob
            r = 15.5 * grow
            d.ellipse([(ex - r) * s, (cy - r * 0.88) * s,
                       (ex + r) * s, (cy + r * 0.88) * s],
                      outline=255, width=max(2, int(s * 1.1)))
            self._spiral(d, ex, cy, max(0.0, r - 2.0 * grow), phase, s)
            d.ellipse([(ex - 1.4) * s, (cy - 1.4) * s,
                       (ex + 1.4) * s, (cy + 1.4) * s], fill=255)
        # slack, dazed half-open mouth, fading in with the swirl
        if grow > 0.3:
            mk = min(1.0, (grow - 0.3) / 0.5)
            hw = 6 * mk
            d.line([((64 - hw) * s, (54 + bob) * s), ((64 + hw) * s, (54 + bob) * s)],
                   fill=255, width=max(2, int(s * 1.3)))


def _zed(d, cx, cy, size, s):
    cx, cy, size = cx * s, cy * s, size * s
    w, h = size * 0.5, size * 0.5
    wdt = max(1, int(s * 0.5))
    d.line([(cx - w, cy - h), (cx + w, cy - h)], fill=255, width=wdt)
    d.line([(cx + w, cy - h), (cx - w, cy + h)], fill=255, width=wdt)
    d.line([(cx - w, cy + h), (cx + w, cy + h)], fill=255, width=wdt)


class Sleep(Overlay):
    """Cute, peaceful sleeping: the real (big) eyes ease shut over ~half a
    second into soft closed-eye arcs rather than snapping away, the whole
    face breathes with a slow bob, and a little stream of "Z"s drifts up
    and away, growing as they rise. Restful, not the CRT power-down look
    of the 'sleep' expression."""

    EASE = 0.55   # seconds to drift from open eyes into the sleepy arcs

    def modify(self, left, right, t):
        k = _ease_out(min(1.0, t / self.EASE))
        for p in (left, right):
            # droop shut like a slow blink, then shrink away entirely so
            # the sleepy arcs take over smoothly instead of a hard cut
            p["top_lid"] = max(p["top_lid"], k * 0.85)
            p["open"] = p["open"] * (1.0 - k)
            p["scale"] = 1.0 - k

    def draw(self, d, s, t):
        k = _ease_out(min(1.0, t / self.EASE))
        if k <= 0.02:
            return
        bob = math.sin(t * 1.1) * 1.6
        wdt = max(2, int(s * 1.6))
        for ex in (EYE_L, EYE_R):
            cy = EYE_CY + 5 + bob
            w = 15 * k
            d.arc([(ex - w / 2) * s, (cy - 7 * k) * s,
                   (ex + w / 2) * s, (cy + 9 * k) * s],
                  200, 340, fill=255, width=wdt)
        _smile(d, 64, 52 + bob, 10 * k, s)
        if t > self.EASE:
            zt = t - self.EASE
            for i in range(3):
                ph = (zt * 0.45 + i / 3.0) % 1.0
                if ph < 0.88:
                    zk = ph / 0.88
                    x = 92 + i * 4 + zk * 12
                    y = 16 - zk * 24 + bob
                    sz = 3.5 + zk * 5.5
                    _zed(d, x, y, sz, s)


class SpaceGlasses(Overlay):
    """Wraparound safety-goggles (single wide lens, padded frame, side
    straps) drop in from the top and land on the face with a springy
    overshoot — same beat as putting on protective eyewear. Once worn, a
    starfield warps past behind/around the head, streaking outward like the
    bot is rocketing through space, with a glint sweeping the lens now and
    then."""

    LENS_W, LENS_H = 92, 26     # single wraparound lens
    PAD = 5                     # padded foam-frame thickness
    LAND = 0.55
    COVER_Y = 14

    N_STARS = 22
    MAX_R = 72
    CX, CY = 64, EYE_CY

    def __init__(self, rng):
        super().__init__(rng)
        self.stars = [self._spawn(warm=True) for _ in range(self.N_STARS)]

    def _spawn(self, warm=False):
        r = self.rng
        return {"a": r.uniform(0, 2 * math.pi),
                "r": r.uniform(0, self.MAX_R) if warm else r.uniform(0, 4),
                "sp": r.uniform(26, 60)}

    def step(self, dt):
        for st in self.stars:
            st["r"] += st["sp"] * dt
            if st["r"] > self.MAX_R:
                st.update(self._spawn())

    def _gy(self, t):
        """Goggle center height: eased drop-in with a springy overshoot,
        then a slow idle sway once worn."""
        k = min(1.0, t / self.LAND)
        c1, c3 = 1.70158, 2.70158
        e = 1 + c3 * (k - 1) ** 3 + c1 * (k - 1) ** 2
        gy = -40 + e * (EYE_CY + 40)
        if t > self.LAND + 0.3:
            gy += math.sin((t - self.LAND) * 2.4) * 1.2
        return gy

    def modify(self, left, right, t):
        if self._gy(t) > self.COVER_Y:
            for p in (left, right):
                p["scale"] = 0.0
        else:
            for p in (left, right):
                p["top_lid"] = max(p["top_lid"], 0.15)

    def draw(self, d, s, t):
        gy = self._gy(t)
        cx = self.CX
        hw, hh = self.LENS_W / 2, self.LENS_H / 2

        if t > self.LAND:
            for st in self.stars:
                a, r = st["a"], st["r"]
                trail = 3 + (r / self.MAX_R) * 11
                x0 = self.CX + math.cos(a) * r * 1.4
                y0 = self.CY + math.sin(a) * r * 0.9
                x1 = self.CX + math.cos(a) * (r - trail) * 1.4
                y1 = self.CY + math.sin(a) * (r - trail) * 0.9
                wdt = max(1, int(s * (0.4 + 1.6 * (r / self.MAX_R))))
                d.line([(x0 * s, y0 * s), (x1 * s, y1 * s)], fill=255, width=wdt)

        # padded outer frame ring
        wdt_outer = max(2, int(s * 2.4))
        obox = [(cx - hw - self.PAD) * s, (gy - hh - self.PAD) * s,
                (cx + hw + self.PAD) * s, (gy + hh + self.PAD) * s]
        d.rounded_rectangle(obox, radius=11 * s, outline=255, width=wdt_outer)

        # elastic strap around the head
        wdt_strap = max(2, int(s * 2.0))
        d.line([(obox[0], (gy - 2) * s), (0, (gy - 9) * s)], fill=255, width=wdt_strap)
        d.line([(obox[2], (gy - 2) * s), (W * s, (gy - 9) * s)], fill=255, width=wdt_strap)

        # vent holes on the top edge of the pad
        for vx in (cx - hw * 0.5, cx + hw * 0.5):
            d.ellipse([(vx - 1.6) * s, (gy - hh - self.PAD * 0.3) * s,
                       (vx + 1.6) * s, (gy - hh + self.PAD * 0.7) * s],
                      outline=255, width=max(1, int(s * 0.8)))

        # single dark wraparound lens
        ibox = [(cx - hw) * s, (gy - hh) * s, (cx + hw) * s, (gy + hh) * s]
        d.rounded_rectangle(ibox, radius=8 * s, fill=0)
        d.rounded_rectangle(ibox, radius=8 * s, outline=255, width=max(2, int(s * 1.3)))

        # periodic diagonal glint sweeping the lens
        if t > self.LAND + 0.15:
            gp = ((t - self.LAND - 0.15) % 2.6) / 2.6
            if gp < 0.28:
                sweep = gp / 0.28
                x0, y0 = cx - hw, gy - hh
                sx = x0 - 10 + sweep * (self.LENS_W + 20)
                yy = y0 + 2.0
                while yy < gy + hh - 1.5:
                    xx = sx - (yy - y0) * 0.5
                    if x0 + 2.5 <= xx <= cx + hw - 2.5 - 2.6:
                        d.rectangle([xx * s, yy * s, (xx + 2.6) * s, (yy + 1.2) * s],
                                    fill=255)
                    yy += 1.2

        # smug little smirk
        d.line([(57 * s, (53 + (gy - EYE_CY) * 0.15) * s),
                (70 * s, (50 + (gy - EYE_CY) * 0.15) * s)],
               fill=255, width=max(2, int(s * 1.3)))


class Hack(Overlay):
    """The whole face powers down CRT-style — both eyes squash into a line
    that shrinks to a dot — then a little terminal window boots up in its
    place: code lines scroll by, a progress bar fills, the screen glitches
    and jitters, and when the bar hits 100% a checkmark flashes, the screen
    collapses, and the eyes pop back. Loops on its own clock."""

    CYCLE = 4.6
    P_COLLAPSE = 0.45
    P_BOOT = 0.3
    P_HACK = 2.5
    P_DONE = 0.35
    P_OFF = 0.35
    P_BACK = CYCLE - (P_COLLAPSE + P_BOOT + P_HACK + P_DONE + P_OFF)

    CX, CY = 64, 32
    SW, SH = 78, 46       # terminal size
    ROWS = 7
    ROW_H = 4.2

    def __init__(self, rng):
        super().__init__(rng)
        self.local_t = 0.0
        self.rows: list[list[tuple[float, float]]] = []
        self.row_cd = 0.0

    def _make_row(self):
        r = self.rng
        x = 3.0 + r.choice((0, 4, 8))
        segs = []
        for _ in range(r.randrange(2, 5)):
            w = r.uniform(4, 14)
            if x + w > self.SW - 16:
                break
            segs.append((x, w))
            x += w + 3
        return segs

    def step(self, dt):
        self.local_t += dt
        if self.local_t >= self.CYCLE:
            self.local_t -= self.CYCLE
            self.rows.clear()
        phase, _ = self._phase()
        if phase == "hack":
            self.row_cd -= dt
            if self.row_cd <= 0:
                self.row_cd = 0.13
                self.rows.append(self._make_row())
                if len(self.rows) > self.ROWS:
                    self.rows.pop(0)

    def _phase(self):
        t = self.local_t
        for name, dur in (("collapse", self.P_COLLAPSE), ("boot", self.P_BOOT),
                          ("hack", self.P_HACK), ("done", self.P_DONE),
                          ("off", self.P_OFF)):
            if t < dur:
                return name, t / dur
            t -= dur
        return "back", min(1.0, t / self.P_BACK)

    def modify(self, left, right, t):
        phase, k = self._phase()
        if phase == "collapse":
            # CRT power-down: eyes rush together and squash flat
            e = _ease_out(k)
            left["dx"] += (self.CX - EYE_L) * e
            right["dx"] -= (EYE_R - self.CX) * e
            for p in (left, right):
                p["h"] *= 1.0 - 0.9 * e
                p["w"] *= 1.0 - 0.45 * e
        elif phase == "back":
            for p in (left, right):
                p["scale"] = min(1.0, _ease_out(k) * 1.06)
        else:
            for p in (left, right):
                p["scale"] = 0.0

    def _frame(self, d, s, hw, hh, jx=0.0, jy=0.0):
        cx, cy = self.CX + jx, self.CY + jy
        d.rounded_rectangle([(cx - hw) * s, (cy - hh) * s,
                             (cx + hw) * s, (cy + hh) * s],
                            radius=3 * s, outline=255, width=max(2, int(s * 1.0)))
        return cx, cy

    def draw(self, d, s, t):
        phase, k = self._phase()
        hw, hh = self.SW / 2, self.SH / 2

        if phase == "boot":
            # a dot stretches into a line, then the line opens into a screen
            if k < 0.4:
                w = hw * (k / 0.4)
                d.line([((self.CX - w) * s, self.CY * s),
                        ((self.CX + w) * s, self.CY * s)],
                       fill=255, width=max(2, int(s * 1.4)))
            else:
                self._frame(d, s, hw, hh * (k - 0.4) / 0.6)

        elif phase == "hack":
            glitching = (self.local_t % 0.9) < 0.09
            jx = self.rng.uniform(-1.2, 1.2) if glitching else 0.0
            jy = self.rng.uniform(-0.8, 0.8) if glitching else 0.0
            cx, cy = self._frame(d, s, hw, hh, jx, jy)
            x0, y0 = cx - hw, cy - hh
            # title bar with window dots
            d.line([(x0 * s, (y0 + 6) * s), ((cx + hw) * s, (y0 + 6) * s)],
                   fill=255, width=max(1, int(s * 0.8)))
            for i in range(3):
                bx = x0 + 4 + i * 4.5
                d.ellipse([(bx - 1.1) * s, (y0 + 2) * s,
                           (bx + 1.1) * s, (y0 + 4.4) * s], fill=255)
            # scrolling code lines (token dashes)
            for i, segs in enumerate(self.rows):
                ry = y0 + 9 + i * self.ROW_H
                ox = ((i * 37 + int(self.local_t * 60)) % 7 - 3) if glitching else 0
                for sx, wdt in segs:
                    d.rectangle([(x0 + sx + ox) * s, ry * s,
                                 (x0 + sx + ox + wdt) * s, (ry + 1.8) * s],
                                fill=255)
            # blinking cursor after the newest line
            if self.rows and int(self.local_t * 5) % 2:
                last = self.rows[-1]
                lx = (last[-1][0] + last[-1][1] + 2) if last else 4
                ly = y0 + 9 + (len(self.rows) - 1) * self.ROW_H
                d.rectangle([(x0 + lx) * s, ly * s,
                             (x0 + lx + 2.5) * s, (ly + 2.2) * s], fill=255)
            # glitch noise streaks
            if glitching:
                for _ in range(2):
                    ny = y0 + self.rng.uniform(8, self.SH - 4)
                    nx = x0 + self.rng.uniform(2, self.SW - 24)
                    d.rectangle([nx * s, ny * s, (nx + self.rng.uniform(8, 20)) * s,
                                 (ny + 1.2) * s], fill=255)
            # progress bar along the bottom
            bw, by = self.SW - 12, cy + hh - 7
            d.rectangle([(x0 + 6) * s, by * s, (x0 + 6 + bw) * s, (by + 4) * s],
                        outline=255, width=max(1, int(s * 0.8)))
            d.rectangle([(x0 + 7) * s, (by + 1) * s,
                         (x0 + 7 + (bw - 2) * k) * s, (by + 3) * s], fill=255)

        elif phase == "done":
            # flash the frame and stamp a big checkmark
            if int(self.local_t * 30) % 3:
                cx, cy = self._frame(d, s, hw, hh)
                wdt = max(3, int(s * 2.2))
                d.line([((cx - 12) * s, cy * s), ((cx - 3) * s, (cy + 9) * s)],
                       fill=255, width=wdt)
                d.line([((cx - 3) * s, (cy + 9) * s), ((cx + 13) * s, (cy - 8) * s)],
                       fill=255, width=wdt)

        elif phase == "off":
            # screen collapses to a line, the line to a fading dot
            if k < 0.55:
                self._frame(d, s, hw, hh * (1 - k / 0.55) + 0.5)
            else:
                w = hw * (1 - (k - 0.55) / 0.45)
                d.line([((self.CX - w) * s, self.CY * s),
                        ((self.CX + w) * s, self.CY * s)],
                       fill=255, width=max(2, int(s * 1.4)))


class Alarm(Overlay):
    """Rise and shine: the eyes glide together and squish into one round
    alarm clock -- twin bells, striker, stubby feet. The ring builds up,
    rattles at full blast, then rings itself out with a decaying wobble.
    A calm beat, then the clock shrinks away and the eyes pop back with a
    springy overshoot. Loops on its own clock."""

    CYCLE = 4.6
    P_MERGE = 0.7
    P_RING = 2.5
    P_CALM = 0.4
    P_BACK = CYCLE - (P_MERGE + P_RING + P_CALM)

    CX, CY = 64, 34
    R = 15

    def __init__(self, rng):
        super().__init__(rng)
        self.local_t = 0.0

    def step(self, dt):
        self.local_t += dt
        if self.local_t >= self.CYCLE:
            self.local_t -= self.CYCLE

    def _phase(self):
        t = self.local_t
        for name, dur in (("merge", self.P_MERGE), ("ring", self.P_RING),
                          ("calm", self.P_CALM)):
            if t < dur:
                return name, t / dur
            t -= dur
        return "back", min(1.0, t / self.P_BACK)

    # ------------------------------------------------------------------ #
    # easing helpers (local so the overlay is self-contained)
    @staticmethod
    def _smooth(k):
        """smoothstep: gentle in AND out"""
        return k * k * (3.0 - 2.0 * k)

    @staticmethod
    def _back_out(k):
        """ease-out with a small springy overshoot"""
        c = 1.70158
        k -= 1.0
        return 1.0 + k * k * ((c + 1.0) * k + c)

    def _envelope(self, k):
        """ring intensity over the ring phase: quick ramp-up, full
        sustain, then a smooth ring-out so it dies down naturally."""
        if k < 0.12:                      # wind up
            return self._smooth(k / 0.12)
        if k < 0.72:                      # full blast
            return 1.0
        return 1.0 - self._smooth((k - 0.72) / 0.28)  # ring out

    def _shake(self, t, amp):
        # one dominant frequency + a soft harmonic = lively but not jittery
        return (math.sin(t * 42.0) * 2.2 + math.sin(t * 21.0) * 0.8) * amp

    # ------------------------------------------------------------------ #
    def modify(self, left, right, t):
        phase, k = self._phase()
        if phase == "merge":
            # eyes glide together with a tiny squash-and-settle
            e = self._smooth(k)
            settle = self._back_out(k) if k > 0.6 else e
            left["dx"] += (self.CX - EYE_L) * e
            right["dx"] -= (EYE_R - self.CX) * e
            for p in (left, right):
                p["dy"] += (self.CY - EYE_CY) * e
                p["top_lid"] = 0.0   # stay fully open, not sleepy-lidded
                p["w"] *= 1.0 - 0.30 * settle
                p["h"] *= 1.0 - 0.45 * settle
                p["round"] = min(1.0, p["round"] + 0.8 * e)
                # fade the eyes right at the end so the clock takes over
                if k > 0.85:
                    p["scale"] = max(0.0, 1.0 - (k - 0.85) / 0.15)
        elif phase in ("ring", "calm"):
            for p in (left, right):
                p["scale"] = 0.0
        else:  # back: eyes pop in with overshoot, tiny residual wobble
            e = self._back_out(min(1.0, k * 1.15))
            wob = math.sin(self.local_t * 18.0) * 0.8 * max(0.0, 1.0 - k * 2.0)
            for p in (left, right):
                p["scale"] = max(0.0, e)
                p["dx"] += wob

    # ------------------------------------------------------------------ #
    def _bell(self, d, cx, cy, r, s, tilt):
        """dome bell; tilt shifts it like it's rocking on its post"""
        d.pieslice([(cx + tilt - r) * s, (cy - r) * s,
                    (cx + tilt + r) * s, (cy + r) * s], 180, 360, fill=255)

    def draw(self, d, s, t):
        phase, k = self._phase()
        if phase == "merge" and k < 0.85:
            return

        cx, cy, r = self.CX, self.CY, float(self.R)

        # grow in during the tail of merge, shrink out during back
        if phase == "merge":
            r *= self._smooth((k - 0.85) / 0.15)
        elif phase == "back":
            r *= 1.0 - self._smooth(min(1.0, k * 1.6))
        if r < 1.5:
            return

        env = self._envelope(k) if phase == "ring" else 0.0
        ringing = env > 0.02

        # whole clock judders; amplitude follows the envelope
        cx += self._shake(self.local_t, env)
        # slight hop at full blast
        cy -= abs(math.sin(self.local_t * 42.0)) * 0.9 * env

        # --- stubby feet ------------------------------------------------
        wdt = max(2, int(s * 1.3))
        for fx in (cx - r * 0.55, cx + r * 0.55):
            d.line([(fx * s, (cy + r * 0.85) * s),
                    (fx * s, (cy + r * 1.18) * s)], fill=255, width=wdt)

        # --- twin bells + striker --------------------------------------
        rock = math.sin(self.local_t * 24.0) * 1.8 * env
        self._bell(d, cx - r * 0.62, cy - r * 0.88, r * 0.52, s, -rock)
        self._bell(d, cx + r * 0.62, cy - r * 0.88, r * 0.52, s, rock)
        # striker swings opposite the bells
        sw = -rock * 1.4
        d.ellipse([(cx + sw - r * 0.15) * s, (cy - r * 1.30) * s,
                   (cx + sw + r * 0.15) * s, (cy - r * 1.00) * s], fill=255)

        # --- clock body + face -----------------------------------------
        d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s],
                  fill=255)
        d.ellipse([(cx - r * 0.8) * s, (cy - r * 0.8) * s,
                   (cx + r * 0.8) * s, (cy + r * 0.8) * s], fill=0)

        for i in range(12):
            a = i * math.pi / 6
            r0, r1 = r * 0.62, r * 0.74
            d.line([((cx + math.cos(a) * r0) * s, (cy + math.sin(a) * r0) * s),
                    ((cx + math.cos(a) * r1) * s, (cy + math.sin(a) * r1) * s)],
                   fill=255, width=max(1, int(s * 0.6)))

        # --- hands: spin scales with envelope, glide back to 12 --------
        wdt_h = max(2, int(s * 1.2))
        base = -math.pi / 2
        if phase == "ring":
            spin = self._smooth(min(1.0, env * 1.2))
            ha = base + self.local_t * 11.0 * spin
            ma = base + self.local_t * 18.0 * spin
        else:
            ha = ma = base
        for ang, ln in ((ha, 0.35), (ma, 0.55)):
            d.line([(cx * s, cy * s),
                    ((cx + math.cos(ang) * r * ln) * s,
                     (cy + math.sin(ang) * r * ln) * s)],
                   fill=255, width=wdt_h)
        d.ellipse([(cx - 1.2) * s, (cy - 1.2) * s,
                   (cx + 1.2) * s, (cy + 1.2) * s], fill=255)

        # --- sound waves: concentric arcs radiating from the sides -----
        if ringing:
            for i in range(3):
                ph = (self.local_t * 1.8 + i / 3.0) % 1.0
                rr = r * (1.35 + ph * 1.1)
                fade = (1.0 - ph) * env
                if fade < 0.08:
                    continue
                wdt_a = max(1, int(s * 1.5 * fade))
                # left arcs open leftward, right arcs open rightward,
                # both centered ON the clock so they radiate outward
                d.arc([(cx - rr) * s, (cy - rr) * s,
                       (cx + rr) * s, (cy + rr) * s],
                      150, 210, fill=255, width=wdt_a)
                d.arc([(cx - rr) * s, (cy - rr) * s,
                       (cx + rr) * s, (cy + rr) * s],
                      -30, 30, fill=255, width=wdt_a)
                

def _puffcloud(d, cx, cy, size, s, halo=0.0):
    """Solid puffy cloud with a flat base; overlapping puffs so it reads as
    one shape at weather-icon sizes. halo > 0 punches a black outline ring
    first so the cloud reads on top of things behind it."""
    if size < 2.0:
        return
    puffs = ((-0.42, -0.02, 0.34), (0.0, -0.22, 0.44), (0.42, -0.02, 0.34))
    if halo > 0:
        for ox, oy, rf in puffs:
            cr = size * rf + halo
            d.ellipse([(cx + ox * size - cr) * s, (cy + oy * size - cr) * s,
                       (cx + ox * size + cr) * s, (cy + oy * size + cr) * s],
                      fill=0)
        d.rectangle([(cx - 0.55 * size) * s, (cy - halo) * s,
                     (cx + 0.55 * size) * s, (cy + 0.30 * size + halo) * s],
                    fill=0)
    for ox, oy, rf in puffs:
        cr = size * rf
        d.ellipse([(cx + ox * size - cr) * s, (cy + oy * size - cr) * s,
                   (cx + ox * size + cr) * s, (cy + oy * size + cr) * s],
                  fill=255)
    d.rounded_rectangle([(cx - 0.55 * size) * s, cy * s,
                         (cx + 0.55 * size) * s, (cy + 0.30 * size) * s],
                        radius=0.12 * size * s, fill=255)


class _Weather(Overlay):
    """Base for the weather report animations: the eyes start normal, glance
    up, then shrink away while an animated weather scene plays on the left
    and the current temperature (°C) counts up big on the right; finally the
    eyes pop back in. Loops on its own clock. Subclasses implement _scene().

    The displayed temperature is freely settable at runtime via
    set_weather_temp(value, kind) at module level, or by assigning the TEMP
    class attribute (e.g. WeatherSunny.TEMP = 31.5).
    """

    CYCLE = 6.2
    P_LOOK = 0.8      # normal eyes, little glance up at the "sky"
    P_IN = 0.45       # eyes shrink away, scene grows in
    P_SHOW = 3.4      # weather + temperature
    P_OUT = 0.45      # scene shrinks, eyes pop back
    P_REST = CYCLE - (P_LOOK + P_IN + P_SHOW + P_OUT)

    ICON_X, ICON_Y = 33, 32   # weather icon center
    TEMP_X, TEMP_Y = 90, 32   # temperature readout center

    TEMP = 21.0               # degrees Celsius shown; override freely

    def __init__(self, rng):
        super().__init__(rng)
        self.local_t = 0.0

    def step(self, dt):
        self.local_t += dt
        if self.local_t >= self.CYCLE:
            self.local_t -= self.CYCLE

    def _phase(self):
        t = self.local_t
        for name, dur in (("look", self.P_LOOK), ("in", self.P_IN),
                          ("show", self.P_SHOW), ("out", self.P_OUT)):
            if t < dur:
                return name, t / dur
            t -= dur
        return "rest", min(1.0, t / self.P_REST)

    def _vis(self):
        """Scene visibility 0..1 across in/show/out."""
        phase, k = self._phase()
        if phase == "in":
            return _ease_out(k)
        if phase == "show":
            return 1.0
        if phase == "out":
            return 1.0 - _ease_out(k)
        return 0.0

    def modify(self, left, right, t):
        phase, k = self._phase()
        if phase == "look":
            # notice the weather: glance up
            e = _ease_out(min(1.0, k * 2.5))
            for p in (left, right):
                p["dy"] -= 3.0 * e
        elif phase == "in":
            for p in (left, right):
                p["scale"] = 1.0 - _ease_out(k)
        elif phase == "show":
            for p in (left, right):
                p["scale"] = 0.0
        elif phase == "out":
            for p in (left, right):
                p["scale"] = _ease_out(k)

    # -- temperature readout -------------------------------------------------

    _SEG = {
        "0": [[(0, 0), (1, 0), (1, 2), (0, 2), (0, 0)]],
        "1": [[(0.5, 0), (0.5, 2)]],
        "2": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 2), (1, 2)]],
        "3": [[(0, 0), (1, 0), (1, 2), (0, 2)], [(0.35, 1), (1, 1)]],
        "4": [[(0, 0), (0, 1), (1, 1)], [(1, 0), (1, 2)]],
        "5": [[(1, 0), (0, 0), (0, 1), (1, 1), (1, 2), (0, 2)]],
        "6": [[(1, 0), (0, 0), (0, 2), (1, 2), (1, 1), (0, 1)]],
        "7": [[(0, 0), (1, 0), (0.55, 2)]],
        "8": [[(0, 0), (1, 0), (1, 2), (0, 2), (0, 0)], [(0, 1), (1, 1)]],
        "9": [[(1, 1), (0, 1), (0, 0), (1, 0), (1, 2), (0, 2)]],
        "-": [[(0, 1), (1, 1)]],
        "C": [[(1, 0.15), (0.15, 0.15), (0.15, 2), (1, 2)]],
    }

    def _draw_temp(self, d, s, vis):
        txt = f"{int(round(float(self.TEMP)))}"
        size = 11.0 * vis                 # digit height (logical px)
        if size < 2.0:
            return
        dw, gap = size * 0.55, size * 0.28
        deg_r = size * 0.16
        # total width: digits + degree circle + C glyph
        n = len(txt)
        total = n * dw + (n - 1) * gap + gap + 2 * deg_r + gap + dw * 0.9
        x = self.TEMP_X - total / 2 + (1.0 - vis) * 10   # slides in
        cy = self.TEMP_Y
        wdt = max(2, int(s * 1.35))

        def stroke(char, ox, w):
            for line in self._SEG[char]:
                d.line([((ox + px * w) * s, (cy - size / 2 + py * size / 2) * s)
                        for px, py in line], fill=255, width=wdt, joint="curve")

        for ch in txt:
            stroke(ch if ch in self._SEG else "-", x, dw)
            x += dw + gap
        # degree ring at the top
        d.ellipse([x * s, (cy - size / 2) * s,
                   (x + 2 * deg_r) * s, (cy - size / 2 + 2 * deg_r) * s],
                  outline=255, width=max(2, int(s * 1.0)))
        x += 2 * deg_r + gap
        stroke("C", x, dw * 0.9)

    def _scene(self, d, s, t, vis):
        raise NotImplementedError

    def draw(self, d, s, t):
        vis = self._vis()
        if vis <= 0.03:
            return
        self._scene(d, s, self.local_t, vis)
        self._draw_temp(d, s, vis)


class WeatherSunny(_Weather):
    """Beaming sun: the disc pulses gently while its rays spin and breathe,
    and a couple of heat-shimmer squiggles rise beside it."""

    TEMP = 31.0

    def _scene(self, d, s, t, vis):
        cx, cy = self.ICON_X, self.ICON_Y
        r = (9.5 + math.sin(t * 2.2) * 0.5) * vis
        d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s],
                  fill=255)
        spin = t * 0.9
        wdt = max(2, int(s * 1.2))
        for i in range(8):
            a = spin + i * math.pi / 4
            ln = (3.5 + math.sin(t * 3.0 + i * 1.3) * 1.6) * vis
            r0 = r + 2.5
            d.line([((cx + math.cos(a) * r0) * s, (cy + math.sin(a) * r0) * s),
                    ((cx + math.cos(a) * (r0 + ln)) * s,
                     (cy + math.sin(a) * (r0 + ln)) * s)],
                   fill=255, width=wdt)
        # occasional sparkle glinting off the sun
        if vis > 0.6 and int(t * 2.0) % 3 == 0:
            _spark(d, cx + 16, cy - 12, 5, s)


class WeatherRainy(_Weather):
    """Rain cloud: streaking angled raindrops fall out of a drifting cloud
    and land with tiny splash ticks."""

    TEMP = 17.0

    def _scene(self, d, s, t, vis):
        cx, cy = self.ICON_X, self.ICON_Y - 10
        drift = math.sin(t * 0.8) * 1.5
        _puffcloud(d, cx + drift, cy, 16 * vis, s)
        wdt = max(2, int(s * 0.9))
        # procedural rain: staggered streaks recycling from cloud to ground
        for i in range(8):
            ph = (t * 1.5 + i * 0.37) % 1.0
            x = cx - 13 + i * 3.8 + drift * 0.5
            y = cy + 7 + ph * 26 * vis
            if ph < 0.88:
                d.line([(x * s, y * s), ((x - 1.6) * s, (y + 4.5) * s)],
                       fill=255, width=wdt)
            else:  # splash tick at the bottom of the fall
                sy = cy + 7 + 26 * vis + 4
                d.line([((x - 3) * s, sy * s), ((x - 4.5) * s, (sy - 2) * s)],
                       fill=255, width=wdt)
                d.line([((x - 1) * s, sy * s), ((x + 0.5) * s, (sy - 2) * s)],
                       fill=255, width=wdt)


class WeatherWinter(_Weather):
    """Winter: a big six-armed snowflake spins slowly while small flakes
    drift down and a snow mound builds along the bottom."""

    TEMP = -4.0

    def _scene(self, d, s, t, vis):
        cx, cy = self.ICON_X, self.ICON_Y - 2
        r = 11 * vis
        rot = t * 0.55
        wdt = max(2, int(s * 1.0))
        for i in range(6):
            a = rot + i * math.pi / 3
            dx, dy = math.cos(a), math.sin(a)
            d.line([(cx * s, cy * s),
                    ((cx + dx * r) * s, (cy + dy * r) * s)], fill=255, width=wdt)
            # branch ticks partway out each arm
            bx, by = cx + dx * r * 0.62, cy + dy * r * 0.62
            for da in (0.55, -0.55):
                d.line([(bx * s, by * s),
                        ((bx + math.cos(a + da) * r * 0.3) * s,
                         (by + math.sin(a + da) * r * 0.3) * s)],
                       fill=255, width=wdt)
        # small flakes drifting down around it
        for i in range(5):
            ph = (t * 0.35 + i * 0.21) % 1.0
            x = 10 + i * 11 + math.sin(t * 1.5 + i) * 3
            y = ph * (H + 8) - 4
            if vis > 0.5:
                _flake(d, x, y, 2.2, s)
        # snow mound on the ground under the icon
        my = H - 4 * vis
        d.ellipse([(cx - 22) * s, my * s, (cx + 22) * s, (H + 6) * s], fill=255)


class WeatherCloudy(_Weather):
    """Cloudy: two puffy clouds drift past each other with a lazy bob, and
    a sliver of sun occasionally peeks over the big one."""

    TEMP = 22.0

    def _scene(self, d, s, t, vis):
        cx, cy = self.ICON_X, self.ICON_Y
        # sun peeking out behind, mostly hidden
        peek = max(0.0, math.sin(t * 0.5)) * 4
        r = 7 * vis
        sx, sy = cx + 9, cy - 9 - peek
        d.ellipse([(sx - r) * s, (sy - r) * s, (sx + r) * s, (sy + r) * s],
                  fill=255)
        for i in range(6):
            a = t * 0.8 + i * math.pi / 3
            d.line([((sx + math.cos(a) * (r + 2)) * s,
                     (sy + math.sin(a) * (r + 2)) * s),
                    ((sx + math.cos(a) * (r + 4.5)) * s,
                     (sy + math.sin(a) * (r + 4.5)) * s)],
                   fill=255, width=max(2, int(s * 0.9)))
        # big front cloud: black halo first so it reads on top of the sun
        bx = cx + math.sin(t * 0.6) * 2.5
        by = cy + 2 + math.sin(t * 1.1) * 1.0
        _puffcloud(d, bx, by, 17 * vis, s, halo=1.6)
        # small trailing cloud drifting the other way
        _puffcloud(d, cx - 17 + math.sin(t * 0.45 + 2) * 3, cy - 13, 9 * vis, s)


def set_weather_temp(value: float, kind: str | None = None):
    """Set the temperature (°C) shown by the weather animations.

    kind: 'sunny' | 'rainy' | 'winter' | 'cloudy', or None to set all four.
    """
    kinds = {"sunny": WeatherSunny, "rainy": WeatherRainy,
             "winter": WeatherWinter, "cloudy": WeatherCloudy}
    if kind is None:
        for cls in kinds.values():
            cls.TEMP = float(value)
    else:
        kinds[kind].TEMP = float(value)


# name -> (base expression, eye parameter overrides, overlay class)
ANIMATIONS: dict[str, tuple[str, dict | None, type[Overlay]]] = {
    "party":     ("joy", {"h": 34.0, "dy": -2.0}, Confetti),
    "tired":     ("sleepy", {"dy": -4.0}, Sweat),
    "thumbs_up": ("happy", {"dx": -16.0, "w": 22.0, "h": 30.0, "dy": -2.0}, ThumbsUp),
    "pew":       ("mischief", {"w": 21.0, "h": 27.0, "dy": -3.0}, Pew),
    "laugh":     ("joy", {"h": 26.0, "dy": -14.0, "w": 28.0, "bot_curve": 0.55}, Laugh),
    "cry":       ("sad", {"h": 26.0, "dy": -10.0, "w": 28.0}, Cry),
    "hearts":    ("love", None, Hearts),
    "shock":     ("surprised", {"h": 36.0, "w": 30.0}, Shock),
    "music":     ("happy", {"h": 28.0, "dy": -9.0}, Music),
    "rage":      ("furious", None, Rage),
    "confused":  ("skeptic", {"dx": -6.0}, Confused),
    "pew3d":     ("surprised", None, Pew3D),
    "eyeshot":   ("surprised", None, EyeShot),
    "glasses":   ("neutral", {"dy": -1.0}, Glasses),
    "blast":     ("scared", {"w": 27.0}, Blast),
    "freeze":    ("sad", {"h": 36.0}, Freeze),
    "drink":     ("happy", {"dy": -2.0}, Drink),
    "hack":      ("neutral", None, Hack),
    "alarm":     ("sleepy", {"top_lid": 0.0, "dy": 0.0}, Alarm),
    "hypno":     ("neutral", None, Hypnotized),
    "sleep":     ("neutral", None, Sleep),
    "space":     ("neutral", None, SpaceGlasses),
    "sunny":     ("neutral", None, WeatherSunny),
    "rainy":     ("neutral", None, WeatherRainy),
    "winter":    ("neutral", None, WeatherWinter),
    "cloudy":    ("neutral", None, WeatherCloudy),
}
