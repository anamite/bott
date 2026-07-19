"""Servo HAL: SG90s wired directly to Pi GPIO, no PCA9685 board.

Same set_pose/relax/update/close/pose interface as hal.servos.Pca9685Servos,
so it's a drop-in swap once more joints are wired up. Reuses SAFE_RANGES,
NEUTRAL and clamp() from hal.servos so both backends agree on what's a
mechanically safe angle.

Wiring per joint: signal wire on its own GPIO pin (never tie two servos'
signal wires together -- each needs an independent pulse). Power (V+) and
GND are bussed across servos from a shared external 5V supply; that
supply's GND must also be tied to a Pi GND pin, or the pulses have no
common reference and the servo won't track correctly.

Only builds servos for joints actually passed in `pins` -- bring hardware
up one joint at a time. Right now only roll (GPIO12) is wired.

gpiozero defaults to software PWM (RPi.GPIO backend), which is fine for
slow head moves but can jitter under CPU load. If jitter shows up, install
pigpio + run pigpiod and gpiozero will pick it up automatically for real
hardware PWM on pins 12/13/18/19.

Motion is eased in software: set_pose() only records a target, and
update(dt) exponentially smooths the commanded angle toward it (a one-pole
low-pass filter -- fast start, natural deceleration into the target, the
James Bruton "95% old + 5% new" trick in frame-rate-independent form). A
deg/s slew cap on top keeps big jumps from slamming the horn. Callers must
call update(dt) every frame for the servo to actually move.
"""
from __future__ import annotations

import math

from .servos import SAFE_RANGES, NEUTRAL, Pose, clamp

# BCM pin per joint. Hardware-PWM-capable pins (12, 13, 18, 19) give the
# smoothest motion. Only wire up what's physically connected.
PINS: dict[str, int] = {
    "roll": 12,
    "pitch": 13,
    "yaw": 18,
}


class GpioServos:
    """Real SG90s driven straight off Pi GPIO pins, with software easing.

    smoothing: 1/s low-pass rate. Higher = snappier, lower = dreamier.
        6.0 feels organic for head moves (equivalent to ~5-6% new-target
        weight per 10 ms tick, the ratio Bruton lands on). 2.0 is very
        sluggish, 15.0 is nearly direct.
    max_speed: hard deg/s cap layered on the filter so a huge target jump
        still can't slam the horn at full servo speed.
    """

    def __init__(self, pins: dict[str, int] | None = None,
                 smoothing: float = 6.0, max_speed: float = 250.0):
        from gpiozero import AngularServo

        self.smoothing = smoothing
        self.max_speed = max_speed
        self.pins = pins or {"roll": PINS["roll"]}
        self._servos: dict[str, AngularServo] = {}
        for joint, pin in self.pins.items():
            lo, hi = SAFE_RANGES[joint]
            # AngularServo is centered on 0; servo-space is 0-180 (90=neutral),
            # so shift by -90 to map onto it.
            self._servos[joint] = AngularServo(
                pin,
                min_angle=lo - 90.0,
                max_angle=hi - 90.0,
                min_pulse_width=0.0005,
                max_pulse_width=0.0024,
            )

        self.pose = Pose()
        self.target = Pose()
        self.relaxed = False
        for joint in self.pins:
            self._servos[joint].angle = NEUTRAL - 90.0  # snap to start pose once

    def set_pose(self, yaw: float | None = None, pitch: float | None = None,
                 roll: float | None = None):
        """Record a target; call update(dt) every frame to actually move."""
        for joint, val in (("yaw", yaw), ("pitch", pitch), ("roll", roll)):
            if val is None or joint not in self._servos:
                continue
            setattr(self.target, joint, clamp(joint, val))
        self.relaxed = False

    def relax(self):
        for s in self._servos.values():
            s.detach()  # stop sending pulses
        self.relaxed = True

    def update(self, dt: float):
        if self.relaxed:
            return
        # frame-rate-independent version of "new = 5% target + 95% old":
        # the blend weight comes from dt, so speed doesn't drift with fps
        k = 1.0 - math.exp(-dt * self.smoothing)
        step = self.max_speed * dt
        for joint, servo in self._servos.items():
            cur, tgt = getattr(self.pose, joint), getattr(self.target, joint)
            d = (tgt - cur) * k
            d = max(-step, min(step, d))          # slew cap on top
            cur = cur + d
            if abs(tgt - cur) < 0.05:             # settle: stop micro-writes
                cur = tgt
            setattr(self.pose, joint, cur)
            servo.angle = cur - 90.0

    def close(self):
        self.relax()
        for s in self._servos.values():
            s.close()
