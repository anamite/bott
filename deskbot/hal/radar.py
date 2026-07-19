"""Radar HAL: HLK-LD2450 mmWave multi-target tracker + simulator.

Both backends expose read() -> list[Target] (may be empty; call it often).
Coordinates follow the LD2450 convention: origin at the sensor, x in mm
(+ = right of the sensor), y in mm (distance out from the sensor face),
speed in cm/s (+ = moving away).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class Target:
    x: float          # mm, + right
    y: float          # mm, out from sensor
    speed: float      # cm/s, + receding
    distance: float   # mm, straight-line

    @property
    def angle(self) -> float:
        """Bearing in degrees, 0 = dead ahead, + = target to the right."""
        return math.degrees(math.atan2(self.x, self.y))


def _i16_signmag(raw: int) -> float:
    """LD2450 sign-magnitude int16: bit 15 set = positive, clear = negative."""
    return float(raw & 0x7FFF) if raw & 0x8000 else -float(raw)


class Ld2450Radar:
    """Real sensor on a serial port (Pi: /dev/serial0 @ 256000 baud).

    Frame: AA FF 03 00 | 3 targets x 8 bytes | 55 CC   (30 bytes total)
    Per target: x i16, y i16, speed i16 (all sign-magnitude), resolution u16.
    An all-zero target slot means "no target".
    """

    HEAD = b"\xaa\xff\x03\x00"
    TAIL = b"\x55\xcc"
    FRAME = 30

    def __init__(self, port: str = "/dev/serial0", baud: int = 256000):
        import serial
        self.ser = serial.Serial(port, baud, timeout=0)
        self._buf = b""

    def read(self) -> list[Target]:
        self._buf += self.ser.read(4096)
        targets: list[Target] = []
        while True:
            i = self._buf.find(self.HEAD)
            if i < 0 or len(self._buf) - i < self.FRAME:
                if i > 0:
                    self._buf = self._buf[i:]
                break
            frame = self._buf[i:i + self.FRAME]
            self._buf = self._buf[i + self.FRAME:]
            if frame[-2:] != self.TAIL:
                continue
            targets = self._parse(frame[4:-2])  # keep newest complete frame
        return targets

    @staticmethod
    def _parse(body: bytes) -> list[Target]:
        out = []
        for t in range(3):
            b = body[t * 8:(t + 1) * 8]
            if b == b"\x00" * 8:
                continue
            x = _i16_signmag(int.from_bytes(b[0:2], "little"))
            y = _i16_signmag(int.from_bytes(b[2:4], "little"))
            speed = _i16_signmag(int.from_bytes(b[4:6], "little"))
            out.append(Target(x, y, speed, math.hypot(x, y)))
        return out

    def close(self):
        self.ser.close()


class SimRadar:
    """Synthetic person for PC development.

    Two modes:
      - external: call set_person(x_mm, y_mm) (e.g. from mouse) / clear_person()
      - wander:   enable with auto_wander=True; a person strolls in, loiters,
                  and leaves on their own, forever.
    """

    def __init__(self, auto_wander: bool = False, seed: int | None = None):
        self.rng = random.Random(seed)
        self.auto_wander = auto_wander
        self._person: tuple[float, float] | None = None
        self._prev: tuple[float, float] | None = None
        # wander state
        self._pos = [0.0, 4000.0]
        self._goal = [0.0, 4000.0]
        self._present = False
        self._timer = self.rng.uniform(2, 6)

    def set_person(self, x_mm: float, y_mm: float):
        self._person = (x_mm, y_mm)

    def clear_person(self):
        self._person = None
        self._prev = None

    def update(self, dt: float):
        if not self.auto_wander:
            return
        self._timer -= dt
        if self._timer <= 0:
            if not self._present:
                self._present = True
                side = self.rng.choice((-1, 1))
                self._pos = [side * 3000.0, 3500.0]
                self._goal = [self.rng.uniform(-800, 800),
                              self.rng.uniform(900, 2000)]
                self._timer = self.rng.uniform(8, 25)   # how long they stay
            else:
                self._present = False
                self._timer = self.rng.uniform(5, 20)   # empty-room time
        if self._present:
            for i in (0, 1):
                d = self._goal[i] - self._pos[i]
                self._pos[i] += d * min(1.0, dt * 0.8)
            if abs(self._goal[0] - self._pos[0]) < 100:  # drift while loitering
                self._goal[0] += self.rng.uniform(-150, 150)

    def read(self) -> list[Target]:
        pos = self._person if self._person is not None \
            else (tuple(self._pos) if (self.auto_wander and self._present)
                  else None)
        if pos is None:
            self._prev = None
            return []
        x = pos[0] + self.rng.gauss(0, 15)   # sensor noise, mm
        y = pos[1] + self.rng.gauss(0, 15)
        speed = 0.0
        if self._prev is not None:
            # radial speed in cm/s, + receding (matches LD2450)
            speed = (math.hypot(x, y) - math.hypot(*self._prev)) / 10.0
        self._prev = (x, y)
        return [Target(x, y, speed, math.hypot(x, y))]

    def close(self):
        pass


def auto_radar(port: str = "/dev/serial0", **kwargs):
    try:
        return Ld2450Radar(port)
    except Exception:
        return SimRadar(**kwargs)
