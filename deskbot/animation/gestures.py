"""Servo gesture engine: short procedural neck motions layered on the pose.

A gesture primitive is a pure function of normalized phase u in [0, 1]
returning (yaw, pitch, roll) offsets in degrees at amplitude 1. Every
primitive starts and ends at zero offset, so the controller's output can be
added on top of whatever base pose + gaze the behavior loop already
commands — gestures compose with person-tracking for free.

The controller plays one gesture at a time (amplitude-, speed- and
cycle-scaled) and low-pass filters its output, so starting, interrupting or
finishing a gesture never snaps the head.

Sign conventions match the servo targets in demo_bot: offsets are plain
degrees added to the commanded angle of each joint (90 = neutral;
+pitch leans down/forward, -pitch leans up/back).
"""
from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# envelope helpers, all defined on u in [0, 1]
# ---------------------------------------------------------------------------

def _smooth(u: float) -> float:
    """Smoothstep 0..1."""
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def _bump(u: float) -> float:
    """Rise and return, peak 1 at u=0.5."""
    return math.sin(math.pi * max(0.0, min(1.0, u)))


def _plateau(u: float, a: float = 0.25, b: float = 0.75) -> float:
    """Smooth rise by a, hold at 1, smooth fall from b."""
    if u < a:
        return _smooth(u / a)
    if u > b:
        return _smooth((1.0 - u) / (1.0 - b))
    return 1.0


def _snap(u: float, attack: float = 0.1) -> float:
    """Fast attack to 1, eased release back to 0 (flinches, perks)."""
    if u < attack:
        return _smooth(u / attack)
    return _smooth((1.0 - u) / (1.0 - attack))


# ---------------------------------------------------------------------------
# primitives: name -> (duration_s at speed 1, fn(u) -> (yaw, pitch, roll))
# amplitudes are tuned for "readable but not violent" at amp=1; acts scale.
# ---------------------------------------------------------------------------

def _nod(u):          # "yes": two enveloped pitch bobs
    return (0.0, 9.0 * math.sin(4 * math.pi * u) * _bump(u), 0.0)


def _shake(u):        # "no": three enveloped yaw swings
    return (14.0 * math.sin(6 * math.pi * u) * _bump(u), 0.0, 0.0)


def _tilt(u):         # single head-tilt, hold, back — the charm move
    return (0.0, 0.0, 16.0 * _plateau(u, 0.22, 0.72))


def _double_tilt(u):  # curious: tilt one way, then the other
    return (0.0, 0.0, 15.0 * math.sin(2 * math.pi * u))


def _bounce(u):       # one hop per cycle; loop it for party/laugh energy
    return (0.0, -6.0 * _bump(u), 0.0)


def _sway(u):         # lazy figure-of-motion, loopable (music, hypno)
    # yaw lags roll by 0.8 rad; the +sin(0.8) bias keeps endpoints at zero
    return (5.0 * (math.sin(2 * math.pi * u - 0.8) + math.sin(0.8)), 0.0,
            9.0 * math.sin(2 * math.pi * u))


def _wiggle(u):       # fast happy roll shimmy
    return (0.0, 0.0, 13.0 * math.sin(8 * math.pi * u) * _bump(u))


def _flinch(u):       # startle: snap up/back, eased recovery
    e = _snap(u, 0.10)
    return (0.0, -15.0 * e, 4.0 * e)


def _droop(u):        # head sinks, lingers, slowly rises (sad, sleepy)
    e = _plateau(u, 0.35, 0.78)
    return (0.0, 18.0 * e, 6.0 * e)


def _perk(u):         # quick attentive lift
    return (0.0, -11.0 * _snap(u, 0.15), 0.0)


def _shiver(u):       # small high-freq tremble (cold, rage, fear)
    e = _bump(u)
    return (3.5 * math.sin(24 * math.pi * u) * e, 0.0,
            3.0 * math.sin(24 * math.pi * u + 1.0) * e)


def _scan(u):         # slow look left, right, back to center
    return (20.0 * math.sin(2 * math.pi * u), 0.0, 0.0)


def _lean_in(u):      # hunch toward the desk, hold (hacking, peering)
    return (0.0, 10.0 * _plateau(u, 0.25, 0.75), 3.0 * _plateau(u, 0.25, 0.75))


def _throwback(u):    # head thrown back + jiggle: laughter
    return (0.0, -14.0 * _plateau(u, 0.18, 0.62)
            + 3.0 * math.sin(6 * math.pi * u) * _bump(u), 0.0)


def _sneeze(u):       # slow wind-up back... snap forward, settle
    if u < 0.5:
        p = -8.0 * _smooth(u / 0.5)
    elif u < 0.62:
        p = -8.0 + 26.0 * _smooth((u - 0.5) / 0.12)
    else:
        p = 18.0 * _smooth((1.0 - u) / 0.38)
    return (0.0, p, 0.0)


PRIMITIVES: dict[str, tuple[float, callable]] = {
    "nod":         (0.9, _nod),
    "shake":       (1.1, _shake),
    "tilt":        (1.8, _tilt),
    "double_tilt": (2.4, _double_tilt),
    "bounce":      (0.55, _bounce),
    "sway":        (2.2, _sway),
    "wiggle":      (0.8, _wiggle),
    "flinch":      (0.7, _flinch),
    "droop":       (3.2, _droop),
    "perk":        (0.9, _perk),
    "shiver":      (0.9, _shiver),
    "scan":        (3.0, _scan),
    "lean_in":     (2.0, _lean_in),
    "throwback":   (1.4, _throwback),
    "sneeze":      (1.3, _sneeze),
}


def duration(name: str, speed: float = 1.0, cycles: int = 1) -> float:
    """Wall-clock length of a gesture at the given speed/cycles."""
    return PRIMITIVES[name][0] * cycles / max(0.05, speed)


# ---------------------------------------------------------------------------
# controller
# ---------------------------------------------------------------------------

class GestureController:
    """Owns one running gesture. Call update(dt) every frame; add the
    returned (dyaw, dpitch, droll) degrees to the commanded servo targets."""

    def __init__(self, smoothing: float = 25.0):
        self.smoothing = smoothing   # 1/s low-pass rate on the output
        self._name: str | None = None
        self._fn = None
        self._dur = 1.0
        self._amp = 1.0
        self._speed = 1.0
        self._cycles = 1
        self._t = 0.0
        self._out = [0.0, 0.0, 0.0]

    @property
    def active(self) -> str | None:
        """Name of the running gesture, or None."""
        return self._name

    def play(self, name: str, amp: float = 1.0, speed: float = 1.0,
             cycles: int = 1):
        self._dur, self._fn = PRIMITIVES[name]
        self._name = name
        self._amp = amp
        self._speed = max(0.05, speed)
        self._cycles = max(1, cycles)
        self._t = 0.0

    def stop(self):
        """Abort; the low-pass filter eases the head back to base pose."""
        self._name = None

    def update(self, dt: float) -> tuple[float, float, float]:
        raw = (0.0, 0.0, 0.0)
        if self._name is not None:
            self._t += dt * self._speed
            if self._t >= self._dur * self._cycles:
                self._name = None
            else:
                u = (self._t % self._dur) / self._dur
                y, p, r = self._fn(u)
                raw = (y * self._amp, p * self._amp, r * self._amp)
        k = 1.0 - math.exp(-dt * self.smoothing)
        for i in range(3):
            self._out[i] += (raw[i] - self._out[i]) * k
        return (self._out[0], self._out[1], self._out[2])
