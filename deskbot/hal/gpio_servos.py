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
"""
from __future__ import annotations

from .servos import SAFE_RANGES, NEUTRAL, Pose, clamp

# BCM pin per joint. Hardware-PWM-capable pins (12, 13, 18, 19) give the
# smoothest motion. Only wire up what's physically connected.
PINS: dict[str, int] = {
    "roll": 12,
    "pitch": 13,
    "yaw": 18,
}


class GpioServos:
    """Real SG90s driven straight off Pi GPIO pins."""

    def __init__(self, pins: dict[str, int] | None = None):
        from gpiozero import AngularServo

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
        self.target = self.pose  # hardware moves on its own; assume commanded
        self.relaxed = False
        self.set_pose(**{joint: NEUTRAL for joint in self.pins})

    def set_pose(self, yaw: float | None = None, pitch: float | None = None,
                 roll: float | None = None):
        for joint, val in (("yaw", yaw), ("pitch", pitch), ("roll", roll)):
            if val is None or joint not in self._servos:
                continue
            a = clamp(joint, val)
            self._servos[joint].angle = a - 90.0
            setattr(self.pose, joint, a)
        self.relaxed = False

    def relax(self):
        for s in self._servos.values():
            s.detach()  # stop sending pulses
        self.relaxed = True

    def update(self, dt: float):
        pass  # physical servos move themselves

    def close(self):
        self.relax()
        for s in self._servos.values():
            s.close()
