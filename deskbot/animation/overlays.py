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


class Glasses(Overlay):
    """Deal-with-it sunglasses drop in from the top, land with a springy
    overshoot, then a glint sweeps across the lenses while the bot smirks
    and bobs its head."""

    LENS_W, LENS_H = 38, 27
    LAND = 0.55         # seconds until the drop finishes

    def _gy(self, t):
        """Glasses center height, shared with modify() so the eyes bob with
        the frames instead of sliding behind them."""
        k = min(1.0, t / self.LAND)
        c1, c3 = 1.70158, 2.70158           # ease-out-back overshoot
        e = 1 + c3 * (k - 1) ** 3 + c1 * (k - 1) ** 2
        gy = -36 + e * 66
        if t > self.LAND + 0.3:
            gy += math.sin((t - self.LAND) * 2.4) * 1.2
        return gy

    def modify(self, left, right, t):
        bob = self._gy(t) - 30
        for p in (left, right):
            p["top_lid"] = max(p["top_lid"], 0.20)   # too cool to open wide
            p["h"] = min(p["h"], 25.0)               # tuck fully behind lens
            p["dy"] += -2.0 + (bob if t > self.LAND else 0.0)

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
    """Cartoon bomb detonation: a bomb sits between the eyes with a sparking
    fuse burning down while the bot nervously eyes it, then a strobe flash,
    a hollow ring fireball with flying debris and a shockwave, and drifting
    smoke as the eyes creep back open. Loops on its own clock."""

    CYCLE = 3.4
    P_FUSE = 1.15
    P_FLASH = 0.12
    P_BOOM = 0.95
    P_SMOKE = CYCLE - (P_FUSE + P_FLASH + P_BOOM)

    BX, BY = 64, 49       # bomb resting spot
    EX, EY = 64, 40       # explosion center

    FUSE = [(64.0, 41.0), (66.0, 37.5), (69.5, 35.5), (73.5, 36.5)]

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
        for name, dur in (("fuse", self.P_FUSE), ("flash", self.P_FLASH),
                          ("boom", self.P_BOOM)):
            if t < dur:
                return name, t / dur
            t -= dur
        return "smoke", min(1.0, t / self.P_SMOKE)

    def modify(self, left, right, t):
        phase, k = self._phase()
        if phase == "fuse":
            # cross-eyed nervous stare down at the bomb, shiver building
            shiver = math.sin(t * 34) * 1.4 * k
            left["dx"] += 5 + shiver
            right["dx"] += -5 + shiver
            for p in (left, right):
                p["dy"] += 4
                p["h"] *= 1.0 - 0.1 * k
        elif phase in ("flash", "boom"):
            for p in (left, right):
                p["scale"] = 0.0
        else:  # smoke: pop back in, a bit dazed
            for p in (left, right):
                p["scale"] = min(1.0, k * 2.2)
                p["dx"] += math.sin(t * 2.2) * 2.0

    def draw(self, d, s, t):
        phase, k = self._phase()

        if phase == "fuse":
            # bomb body, pulsing faster as detonation nears
            r = 8 * (1 + 0.06 * math.sin(self.local_t * (6 + 18 * k)))
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
                _spark(d, self.EX + math.sin(t * 7) * 4, 52, 4, s)


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
    "glasses":   ("neutral", {"dy": -1.0}, Glasses),
    "blast":     ("scared", {"w": 27.0}, Blast),
}
