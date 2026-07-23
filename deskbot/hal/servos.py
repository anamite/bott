"""Servo HAL: 3-DOF neck pose (yaw, pitch, roll) in degrees.

Same interface for the real PCA9685 board and a PC simulator. All angles are
servo-space degrees where 90 = calibration pose (bot looking straight ahead);
everything is clamped to SAFE_RANGES so a behavior bug can never grind a horn
into the printed frame.

The simulator models real servo motion (slew-rate limited, no teleporting) so
animation code tuned against it transfers to hardware unchanged. Rendering of
the virtual bot lives in the demo/viewer, not here — the HAL stays drawless.
"""
from __future__ import annotations

from dataclasses import dataclass

# Mechanical safe ranges, degrees. Tighten these after the frame is printed.
SAFE_RANGES: dict[str, tuple[float, float]] = {
    "yaw":   (20.0, 160.0),
    "pitch": (50.0, 130.0),
    "roll":  (60.0, 120.0),
}

NEUTRAL = 90.0
JOINTS = ("yaw", "pitch", "roll")

# Per-servo zero error, degrees. The 3D-printed horns don't seat with their
# true center at 90, so logical 90 (bot looking straight ahead) maps to a raw
# servo angle of 90 + offset. Measured with tools/calibrate_servos.py.
ZERO_OFFSETS: dict[str, float] = {
    "yaw":   -6.0,
    "pitch": -86.0,
    "roll":  -15.0,
}


def clamp(joint: str, angle: float) -> float:
    lo, hi = SAFE_RANGES[joint]
    return max(lo, min(hi, angle))


@dataclass
class Pose:
    yaw: float = NEUTRAL
    pitch: float = NEUTRAL
    roll: float = NEUTRAL

    def clamped(self) -> "Pose":
        return Pose(clamp("yaw", self.yaw),
                    clamp("pitch", self.pitch),
                    clamp("roll", self.roll))

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.yaw, self.pitch, self.roll)


class SimServos:
    """Slew-rate-limited servo model. Call update(dt) every frame.

    An SG90 does ~60 deg per 0.1 s unloaded; with a printed head on it,
    ~400 deg/s is honest. `pose` is where the servos actually are right now,
    `target` is the last commanded pose.
    """

    def __init__(self, max_speed: float = 400.0):
        self.max_speed = max_speed
        self.pose = Pose()
        self.target = Pose()
        self.relaxed = False

    def set_pose(self, yaw: float | None = None, pitch: float | None = None,
                 roll: float | None = None):
        if yaw is not None:
            self.target.yaw = clamp("yaw", yaw)
        if pitch is not None:
            self.target.pitch = clamp("pitch", pitch)
        if roll is not None:
            self.target.roll = clamp("roll", roll)
        self.relaxed = False

    def relax(self):
        """Detach: real servos stop holding (and stop buzzing). In sim the
        pose simply freezes where it is."""
        self.relaxed = True

    def update(self, dt: float):
        if self.relaxed:
            return
        step = self.max_speed * dt
        for j in JOINTS:
            cur, tgt = getattr(self.pose, j), getattr(self.target, j)
            d = tgt - cur
            if abs(d) <= step:
                setattr(self.pose, j, tgt)
            else:
                setattr(self.pose, j, cur + step * (1 if d > 0 else -1))

    def close(self):
        pass


class Pca9685Servos:
    """Real neck via PCA9685 @ 0x40 (Raspberry Pi). Requires adafruit libs:

        pip install adafruit-circuitpython-servokit   # on the Pi

    Channel map: 0 = roll, 1 = pitch, 2 = yaw.
    """

    CHANNELS = {"yaw": 2, "pitch": 1, "roll": 0}

    def __init__(self, address: int = 0x40):
        from adafruit_servokit import ServoKit
        self.kit = ServoKit(channels=16, address=address)
        for ch in self.CHANNELS.values():
            # SG90s want ~500-2400us for the full 180 degrees
            self.kit.servo[ch].set_pulse_width_range(500, 2400)
        self.pose = Pose()
        self.target = self.pose  # hardware moves on its own; assume commanded
        self.relaxed = False
        self.set_pose(NEUTRAL, NEUTRAL, NEUTRAL)

    def set_pose(self, yaw: float | None = None, pitch: float | None = None,
                 roll: float | None = None):
        for joint, val in (("yaw", yaw), ("pitch", pitch), ("roll", roll)):
            if val is None:
                continue
            a = clamp(joint, val)
            # Apply the servo's zero error, then clamp to physical travel.
            raw = max(0.0, min(180.0, a + ZERO_OFFSETS[joint]))
            self.kit.servo[self.CHANNELS[joint]].angle = raw
            setattr(self.pose, joint, a)  # store logical angle, not raw
        self.relaxed = False

    def relax(self):
        for ch in self.CHANNELS.values():
            self.kit.servo[ch].angle = None  # stop sending pulses
        self.relaxed = True

    def update(self, dt: float):
        pass  # physical servos move themselves

    def close(self):
        self.relax()


def auto_servos(**kwargs):
    """Pick real hardware when available, otherwise the simulator."""
    try:
        return Pca9685Servos()
    except Exception:
        return SimServos(**kwargs)
