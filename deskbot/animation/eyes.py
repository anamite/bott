"""Parametric procedural eye engine for a 128x64 1-bit OLED.

Eyes are not sprites: each eye is a solid rounded shape described by a small
set of float parameters. An "expression" is just a target parameter set; the
controller tweens between them and layers blinks, saccades, breathing and
per-expression micro-motion on top. Everything renders supersampled and is
thresholded down to crisp 1-bit for the OLED.
"""
from __future__ import annotations

import math
import random
from PIL import Image, ImageDraw, ImageChops

# Logical screen
W, H = 128, 64
SS = 4  # supersampling factor

# Eye base geometry (logical px)
EYE_CY = 32
EYE_DX = 25          # distance of each eye center from screen center
EYE_SPACING = 2 * EYE_DX

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

# Per-eye parameter defaults. Angles are defined for the LEFT eye and are
# mirrored automatically for the right eye (positive top_angle = lid slants
# down toward the nose = angry).
BASE = {
    "dx": 0.0,        # gaze / expression shift, px (same direction both eyes)
    "dy": 0.0,
    "w": 32.0,
    "h": 42.0,
    "round": 0.45,    # corner radius as fraction of min(w, h)/2, 0..1
    "top_lid": 0.0,   # 0..1 coverage from the top
    "top_angle": 0.0, # degrees; + = inner corner covered more (angry)
    "bot_lid": 0.0,   # straight lower lid coverage
    "bot_angle": 0.0,
    "bot_curve": 0.0, # 0..1 curved "happy arch" cut from below
    "open": 1.0,      # blink: 1 open .. 0 closed (squash & stretch applied)
    "scale": 1.0,     # overall pop scale (used when morphing shape modes)
    "mode": "normal", # normal | heart | cross  (string, switched mid-tween)
}

_FLOAT_KEYS = [k for k, v in BASE.items() if isinstance(v, float)]

# Expression library. Values override BASE; an optional "r" sub-dict
# overrides the right eye only (for asymmetric faces).
EXPRESSIONS: dict[str, dict] = {
    "neutral":    {},
    "happy":      {"bot_curve": 0.45, "dy": -1.0},
    "joy":        {"bot_curve": 0.62, "h": 46.0, "dy": 1.0},
    "sad":        {"top_lid": 0.30, "top_angle": -14.0, "dy": 4.0, "h": 38.0},
    "angry":      {"top_lid": 0.40, "top_angle": 20.0},
    "furious":    {"top_lid": 0.52, "top_angle": 28.0, "bot_lid": 0.12, "w": 34.0},
    "surprised":  {"w": 38.0, "h": 50.0, "round": 0.85, "dy": -1.0},
    "sleepy":     {"top_lid": 0.55, "dy": 3.0, "h": 38.0},
    "sleep":      {"open": 0.0, "dy": 4.0},
    "suspicious": {"top_lid": 0.42, "bot_lid": 0.14},
    "skeptic":    {"top_lid": 0.38, "r": {"top_lid": 0.08}},
    "wink":       {"bot_curve": 0.45, "r": {"open": 0.0, "bot_curve": 0.0}},
    "love":       {"mode": "heart"},
    "dizzy":      {"mode": "cross"},
    "bored":      {"top_lid": 0.48, "dx": 5.0},
    "scared":     {"w": 25.0, "h": 33.0, "round": 0.7, "dy": -1.0},
    "mischief":   {"top_lid": 0.20, "top_angle": 10.0, "bot_lid": 0.30},
    "curious":    {"h": 46.0, "w": 34.0, "r": {"h": 36.0, "w": 30.0, "top_lid": 0.12}},
}


def _expr_params(name: str) -> tuple[dict, dict]:
    """Resolve an expression name to (left, right) full parameter dicts."""
    spec = EXPRESSIONS[name]
    left = dict(BASE)
    right = dict(BASE)
    for k, v in spec.items():
        if k == "r":
            continue
        left[k] = v
        right[k] = v
    for k, v in spec.get("r", {}).items():
        right[k] = v
    return left, right


def _ease(t: float) -> float:
    """Cubic ease-in-out."""
    t = max(0.0, min(1.0, t))
    return 3 * t * t - 2 * t * t * t


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class EyeRenderer:
    """Draws a (left, right) parameter pair into a 1-bit 128x64 PIL image."""

    def __init__(self, width: int = W, height: int = H, ss: int = SS):
        self.w, self.h, self.ss = width, height, ss

    def render(self, left: dict, right: dict, decor=None) -> Image.Image:
        sw, sh = self.w * self.ss, self.h * self.ss
        canvas = Image.new("L", (sw, sh), 0)
        for params, mirror in ((left, False), (right, True)):
            layer = self._render_eye(params, mirror, sw, sh)
            canvas = ImageChops.lighter(canvas, layer)
        if decor is not None:
            decor(ImageDraw.Draw(canvas))
        small = canvas.resize((self.w, self.h), Image.LANCZOS)
        return small.point(lambda v: 255 if v > 110 else 0, mode="1")

    # -- single eye ---------------------------------------------------------

    def _render_eye(self, p: dict, mirror: bool, sw: int, sh: int) -> Image.Image:
        s = self.ss
        img = Image.new("L", (sw, sh), 0)
        d = ImageDraw.Draw(img)

        sign = -1.0 if mirror else 1.0
        cx = (self.w / 2 + (EYE_DX if mirror else -EYE_DX) + p["dx"]) * s
        cy = (EYE_CY + p["dy"]) * s

        openness = max(0.0, min(1.0, p["open"]))
        scale = max(0.0, p["scale"])
        if scale <= 0.02:
            return img

        # squash & stretch: closing squashes height, bulges width slightly
        w_eff = p["w"] * (1.0 + 0.18 * (1.0 - openness)) * scale * s
        h_eff = p["h"] * openness * scale * s

        if h_eff < 2.5 * s:
            # closed: a soft horizontal line
            lw = w_eff * 0.55
            d.rounded_rectangle(
                [cx - lw, cy - 1.4 * s, cx + lw, cy + 1.4 * s],
                radius=1.4 * s, fill=255)
            return img

        mode = p.get("mode", "normal")
        if mode == "heart":
            self._draw_heart(d, cx, cy, min(w_eff, h_eff) * 1.15)
        elif mode == "cross":
            self._draw_cross(d, cx, cy, min(w_eff, h_eff) * 0.95)
        else:
            r = p["round"] * min(w_eff, h_eff) / 2
            d.rounded_rectangle(
                [cx - w_eff / 2, cy - h_eff / 2, cx + w_eff / 2, cy + h_eff / 2],
                radius=r, fill=255)

        # lids (cut with black), only meaningful for normal mode but applying
        # them to hearts/crosses during a morph looks fine too
        if p["top_lid"] > 0.0:
            self._straight_lid(d, cx, cy, w_eff, h_eff,
                               p["top_lid"], p["top_angle"] * sign, top=True)
        if p["bot_lid"] > 0.0:
            self._straight_lid(d, cx, cy, w_eff, h_eff,
                               p["bot_lid"], p["bot_angle"] * sign, top=False)
        if p["bot_curve"] > 0.0:
            self._curved_bottom(d, cx, cy, w_eff, h_eff, p["bot_curve"])
        return img

    @staticmethod
    def _straight_lid(d, cx, cy, w, h, cover, angle_deg, top):
        y = (cy - h / 2 + cover * h) if top else (cy + h / 2 - cover * h)
        a = math.radians(angle_deg)
        dx, dy = math.cos(a), math.sin(a)
        L = w * 1.2
        p1 = (cx - dx * L, y - dy * L)
        p2 = (cx + dx * L, y + dy * L)
        big = h * 2.5
        off = -big if top else big
        d.polygon([p1, p2, (p2[0], p2[1] + off), (p1[0], p1[1] + off)], fill=0)

    @staticmethod
    def _curved_bottom(d, cx, cy, w, h, curve):
        """Cut a curved chunk from below -> remaining eye is a happy arch."""
        ew, eh = w * 1.7, h * 1.8
        y0 = cy + h / 2 - curve * h          # top of the cutting ellipse
        d.ellipse([cx - ew / 2, y0, cx + ew / 2, y0 + eh], fill=0)

    @staticmethod
    def _draw_heart(d, cx, cy, size):
        r = size * 0.27
        yoff = -size * 0.12
        d.ellipse([cx - 2 * r, cy + yoff - r, cx, cy + yoff + r], fill=255)
        d.ellipse([cx, cy + yoff - r, cx + 2 * r, cy + yoff + r], fill=255)
        d.polygon([
            (cx - 1.93 * r, cy + yoff + r * 0.2),
            (cx + 1.93 * r, cy + yoff + r * 0.2),
            (cx, cy + size * 0.52),
        ], fill=255)

    @staticmethod
    def _draw_cross(d, cx, cy, size):
        t = size * 0.16
        s2 = size / 2
        for a in (45, -45):
            rad = math.radians(a)
            dx, dy = math.cos(rad) * s2, math.sin(rad) * s2
            d.line([(cx - dx, cy - dy), (cx + dx, cy + dy)],
                   fill=255, width=int(t * 2))


# ---------------------------------------------------------------------------
# Controller: tweening, blinks, saccades, micro-motion
# ---------------------------------------------------------------------------

class EyeController:
    """Owns eye state over time. Call update(dt) every frame -> PIL image."""

    def __init__(self, idle: bool = True, seed: int | None = None):
        self.renderer = EyeRenderer()
        self.rng = random.Random(seed)
        self.idle = idle

        self.expression = "neutral"
        self._src = _expr_params("neutral")
        self._dst = _expr_params("neutral")
        self._t = 1.0
        self._dur = 0.25

        # blink state
        self._blink_phase = "open"      # open | closing | opening
        self._blink_t = 0.0
        self._next_blink = self._blink_delay()
        self._blink_amount = 0.0        # 0 open .. 1 closed

        # gaze (saccades + external look-at)
        self._gaze = [0.0, 0.0]
        self._gaze_target = [0.0, 0.0]
        self._next_saccade = self.rng.uniform(0.8, 2.5)
        self._external_gaze: tuple[float, float] | None = None

        self._time = 0.0
        self.animation: str | None = None
        self._overlay = None
        self._anim_t = 0.0

    # -- public API ---------------------------------------------------------

    def set_expression(self, name: str, duration: float = 0.28):
        if name not in EXPRESSIONS:
            raise KeyError(f"unknown expression {name!r}")
        self._src = self._current_pair()
        self._dst = _expr_params(name)
        self.expression = name
        self.animation = None
        self._overlay = None
        self._t = 0.0
        self._dur = max(0.01, duration)

    def set_animation(self, name: str, duration: float = 0.28):
        """Play a named overlay animation (see overlays.ANIMATIONS)."""
        from . import overlays
        base, eye_overrides, overlay_cls = overlays.ANIMATIONS[name]
        self._src = self._current_pair()
        left, right = _expr_params(base)
        if eye_overrides:
            for k, v in eye_overrides.items():
                if k == "r":
                    continue
                left[k] = v
                right[k] = v
            for k, v in eye_overrides.get("r", {}).items():
                right[k] = v
        self._dst = (left, right)
        self.expression = base          # base expr micro-motion still applies
        self.animation = name
        self._overlay = overlay_cls(self.rng)
        self._anim_t = 0.0
        self._t = 0.0
        self._dur = max(0.01, duration)

    def look_at(self, dx: float | None, dy: float | None = None):
        """External gaze override in px offsets; None releases to idle."""
        if dx is None:
            self._external_gaze = None
        else:
            self._external_gaze = (dx, dy or 0.0)

    def blink_now(self):
        if self._blink_phase == "open":
            self._blink_phase = "closing"
            self._blink_t = 0.0

    # -- internals ----------------------------------------------------------

    def _blink_delay(self):
        return self.rng.uniform(2.5, 7.0)

    def _current_pair(self) -> tuple[dict, dict]:
        t = _ease(self._t)
        out = []
        for i in (0, 1):
            src, dst = self._src[i], self._dst[i]
            p = dict(dst)
            for k in _FLOAT_KEYS:
                p[k] = _lerp(src[k], dst[k], t)
            if src["mode"] != dst["mode"]:
                # pop through zero scale at the halfway point
                p["mode"] = src["mode"] if t < 0.5 else dst["mode"]
                p["scale"] = _lerp(src["scale"], dst["scale"], t) * abs(1 - 2 * t)
            out.append(p)
        return out[0], out[1]

    def _update_blink(self, dt: float):
        if self.expression in ("sleep", "wink"):
            self._blink_amount = 0.0
            return
        if self._blink_phase == "open":
            self._next_blink -= dt
            if self._next_blink <= 0:
                self._blink_phase = "closing"
                self._blink_t = 0.0
        elif self._blink_phase == "closing":
            self._blink_t += dt
            self._blink_amount = min(1.0, self._blink_t / 0.09)
            if self._blink_amount >= 1.0:
                self._blink_phase = "opening"
                self._blink_t = 0.0
        else:  # opening
            self._blink_t += dt
            self._blink_amount = max(0.0, 1.0 - self._blink_t / 0.13)
            if self._blink_amount <= 0.0:
                self._blink_phase = "open"
                # occasional double blink
                self._next_blink = 0.15 if self.rng.random() < 0.12 \
                    else self._blink_delay()

    def _update_gaze(self, dt: float):
        if self._external_gaze is not None:
            self._gaze_target = list(self._external_gaze)
        elif self.idle:
            self._next_saccade -= dt
            if self._next_saccade <= 0:
                self._next_saccade = self.rng.uniform(0.8, 3.0)
                if self.rng.random() < 0.25:
                    self._gaze_target = [0.0, 0.0]  # re-center
                else:
                    self._gaze_target = [self.rng.uniform(-6, 6),
                                         self.rng.uniform(-2.5, 2.5)]
        # saccadic: fast exponential snap toward target
        k = 1.0 - math.exp(-dt * 18.0)
        self._gaze[0] += (self._gaze_target[0] - self._gaze[0]) * k
        self._gaze[1] += (self._gaze_target[1] - self._gaze[1]) * k

    def _micro_motion(self, left: dict, right: dict):
        """Per-expression procedural flourish. Mutates params in place."""
        tt = self._time
        e = self.expression
        if e == "dizzy":
            a = tt * 7.0
            for p in (left, right):
                p["dx"] += math.cos(a) * 3.0
                p["dy"] += math.sin(a) * 2.0
        elif e == "scared":
            j = math.sin(tt * 55.0) * 1.1
            left["dx"] += j
            right["dx"] += j
        elif e in ("joy", "love"):
            b = abs(math.sin(tt * 6.0)) * 1.8
            for p in (left, right):
                p["dy"] -= b
        elif e == "sleepy":
            droop = (math.sin(tt * 0.9) + 1) * 0.5  # slow 0..1
            for p in (left, right):
                p["top_lid"] = min(0.75, p["top_lid"] + droop * 0.12)

    def update(self, dt: float) -> Image.Image:
        self._time += dt
        if self._t < 1.0:
            self._t = min(1.0, self._t + dt / self._dur)
        self._update_blink(dt)
        self._update_gaze(dt)

        left, right = self._current_pair()

        # breathing: barely visible slow height sway
        breath = 1.0 + 0.015 * math.sin(self._time * 2 * math.pi * 0.22)
        for p in (left, right):
            p["h"] *= breath
            p["dx"] += self._gaze[0]
            p["dy"] += self._gaze[1] + (1.0 - breath) * 40
            p["open"] = p["open"] * (1.0 - self._blink_amount)

        self._micro_motion(left, right)

        decor = None
        if self._overlay is not None:
            self._anim_t += dt
            self._overlay.step(dt)
            self._overlay.modify(left, right, self._anim_t)
            ss, at = self.renderer.ss, self._anim_t
            decor = lambda d: self._overlay.draw(d, ss, at)
        return self.renderer.render(left, right, decor)
