"""Stepper HAL: 28BYJ-48 + ULN2003 driver, single-joint (roll) test rig.

Same set_pose/relax/update/close/pose interface as hal.gpio_servos.GpioServos,
so it drops into the same animation code (acts/gestures) with the servo
swapped out. Only "roll" is implemented -- this exists to answer one
question, whether a 28BYJ-48 feels better than the SG90 for head roll, not to
be a general 3-DOF replacement.

Key difference from a servo: a stepper has no absolute position sensor. It
only knows how many half-steps it has moved since power-on. NEUTRAL (90 deg,
see hal.servos) is therefore just "wherever the horn was pointing when this
script started," not a calibrated zero -- rotate the horn to true-center by
hand before running, same as you would after any stepper power cycle.

Wiring (ULN2003 driver board):
    IN1 -> GPIO5   IN2 -> GPIO6   IN3 -> GPIO13   IN4 -> GPIO19
    driver 5V  -> external 5V supply, NOT the Pi's 5V pin -- the motor can
                  pull more current than the Pi's onboard regulator likes.
    driver GND -> a Pi GND pin, shared with the external supply's GND (common
                  reference, same reasoning as the servo wiring in
                  gpio_servos.py -- without it the step pulses have nothing
                  to be measured against).
    Pi only ever drives the 4 logic pins (IN1-IN4); it never touches the
    motor's own power leads.

28BYJ-48 spec: 5V unipolar, ~64:1 internal gearing, 4096 half-steps/rev when
driven with the 8-step half-step sequence used below (smoother and quieter
than 4-step full-step, at the cost of half the top speed).

python tools/test_stepper.py sweeps it standalone to check wiring before
wiring it into the showcase.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .servos import SAFE_RANGES, NEUTRAL, clamp

# BCM pins for the ULN2003 driver's IN1-IN4.
PINS: dict[str, int] = {"in1": 5, "in2": 6, "in3": 13, "in4": 19}

STEPS_PER_REV = 4096  # half-steps, 28BYJ-48 with its 64:1 gearbox
STEPS_PER_DEG = STEPS_PER_REV / 360.0

# 8-step half-step drive sequence for IN1..IN4.
HALF_STEP_SEQUENCE: tuple[tuple[int, int, int, int], ...] = (
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
)

STEP_PULSE_DELAY = 0.0015  # s between half-steps; lower risks skipped steps


@dataclass
class RollPose:
    roll: float = NEUTRAL


class SimStepper:
    """Slew-rate-limited stand-in, same shape as hal.servos.SimServos.

    max_step_rate is half-steps/s; converted to deg/s internally so the
    slewing feels like the real motor's top comfortable speed rather than an
    arbitrary deg/s pulled from nowhere.
    """

    def __init__(self, max_step_rate: float = 500.0):
        self.max_speed = max_step_rate / STEPS_PER_DEG  # deg/s
        self.pose = RollPose()
        self.target = RollPose()
        self.relaxed = False

    def set_pose(self, yaw: float | None = None, pitch: float | None = None,
                 roll: float | None = None):
        if roll is not None:
            self.target.roll = clamp("roll", roll)
        self.relaxed = False

    def relax(self):
        self.relaxed = True

    def update(self, dt: float):
        if self.relaxed:
            return
        step = self.max_speed * dt
        d = self.target.roll - self.pose.roll
        if abs(d) <= step:
            self.pose.roll = self.target.roll
        else:
            self.pose.roll += step * (1 if d > 0 else -1)

    def close(self):
        pass


class Gpio28BYJ48Stepper:
    """Real 28BYJ-48 via ULN2003, driven straight off Pi GPIO pins.

    update(dt) advances a bounded number of half-steps toward the target
    each call (a fractional-step accumulator carries remainders forward so
    slow dt*max_step_rate doesn't stall motion entirely). Each half-step
    pulses the coils and sleeps STEP_PULSE_DELAY, so unlike the servo HAL,
    update() here is not instantaneous -- driving a stepper is inherently a
    blocking, step-by-step affair. That's real hardware behavior, not a bug.
    """

    def __init__(self, pins: dict[str, int] | None = None,
                 max_step_rate: float = 500.0):
        from gpiozero import DigitalOutputDevice

        self.max_step_rate = max_step_rate  # half-steps/s
        self.pins = pins or dict(PINS)
        self._outs = [
            DigitalOutputDevice(self.pins["in1"]),
            DigitalOutputDevice(self.pins["in2"]),
            DigitalOutputDevice(self.pins["in3"]),
            DigitalOutputDevice(self.pins["in4"]),
        ]

        self.step_index = 0     # position within HALF_STEP_SEQUENCE
        self.current_step = 0   # absolute half-steps from power-on reference
        self.target_step = 0
        self._accum = 0.0

        self.pose = RollPose()
        self.target = RollPose()
        self.relaxed = False
        self._apply_phase()  # energize so the rotor holds its start position

    def _apply_phase(self):
        for out, val in zip(self._outs, HALF_STEP_SEQUENCE[self.step_index]):
            out.value = val

    def set_pose(self, yaw: float | None = None, pitch: float | None = None,
                 roll: float | None = None):
        if roll is not None:
            angle = clamp("roll", roll)
            self.target.roll = angle
            self.target_step = round((angle - NEUTRAL) * STEPS_PER_DEG)
        self.relaxed = False

    def relax(self):
        for out in self._outs:
            out.value = 0  # de-energize coils; rotor free-spins, no torque
        self.relaxed = True

    def update(self, dt: float):
        if self.relaxed:
            return
        self._accum += self.max_step_rate * dt
        n = int(self._accum)
        if n <= 0:
            return
        self._accum -= n

        diff = self.target_step - self.current_step
        n = min(n, abs(diff))
        direction = 1 if diff > 0 else -1
        for _ in range(n):
            self.current_step += direction
            self.step_index = (self.step_index + direction) % 8
            self._apply_phase()
            time.sleep(STEP_PULSE_DELAY)

        self.pose.roll = NEUTRAL + self.current_step / STEPS_PER_DEG

    def close(self):
        self.relax()
        for out in self._outs:
            out.close()


def auto_stepper(**kwargs):
    """Pick real hardware when available, otherwise the simulator."""
    try:
        return Gpio28BYJ48Stepper(**kwargs)
    except Exception:
        return SimStepper()
