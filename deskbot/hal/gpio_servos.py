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

Motion is eased with a critically-damped second-order filter (SmoothDamp):
set_pose() only records a target; the easing walks the commanded angle
toward it through a tracked *velocity*. Because velocity ramps up from zero
and then bleeds back to zero, the move eases BOTH in and out (an S-curve),
unlike a plain low-pass filter that starts at full speed and only eases out.
It never overshoots and tracks a moving target smoothly.

By default a background thread runs that easing at a steady 100 Hz, so the
head stays smooth even when the caller's main loop is slow (e.g. blocked on
a slow OLED write). Callers just call set_pose(); they do NOT need to call
update(). Pass update_hz=0 to disable the thread and drive update(dt)
yourself instead.
"""
from __future__ import annotations

import threading
import time

from .servos import SAFE_RANGES, NEUTRAL, Pose, clamp

# BCM pin per joint. Hardware-PWM-capable pins (12, 13, 18, 19) give the
# smoothest motion. Only wire up what's physically connected.
PINS: dict[str, int] = {
    "roll": 12,
    "pitch": 13,
    "yaw": 18,
}


def _smooth_damp(cur: float, tgt: float, vel: float, smooth_time: float,
                 dt: float, max_speed: float) -> tuple[float, float]:
    """One SmoothDamp step (Game Programming Gems 4 / Unity). Returns the
    new (position, velocity). Eases in and out, critically damped, no
    overshoot. `smooth_time` ~= seconds to substantially reach the target."""
    smooth_time = max(1e-4, smooth_time)
    omega = 2.0 / smooth_time
    x = omega * dt
    exp = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)

    change = cur - tgt
    max_change = max_speed * smooth_time
    change = max(-max_change, min(max_change, change))  # velocity cap
    tgt_capped = cur - change

    temp = (vel + omega * change) * dt
    vel = (vel - omega * temp) * exp
    out = tgt_capped + (change + temp) * exp

    # kill overshoot: if we crossed the real target, snap and stop
    if (tgt - cur > 0.0) == (out > tgt):
        out = tgt
        vel = (out - tgt_capped) / dt if dt > 0 else 0.0
    return out, vel


class GpioServos:
    """Real SG90s driven straight off Pi GPIO pins, with eased motion.

    smooth_time: seconds to substantially reach a new target. Bigger =
        slower, dreamier moves; smaller = snappier. 0.35 feels organic for
        a head; 0.15 is quick, 0.8 is very languid.
    max_speed: hard deg/s cap on the eased motion, so even a huge jump
        can't slam the horn at full servo speed.
    update_hz: rate of the background easing thread. 0 disables the thread
        and you drive update(dt) yourself.
    """

    def __init__(self, pins: dict[str, int] | None = None,
                 smooth_time: float = 0.35, max_speed: float = 250.0,
                 update_hz: float = 100.0):
        from gpiozero import AngularServo

        self.smooth_time = smooth_time
        self.max_speed = max_speed
        self.pins = pins or {"roll": PINS["roll"]}
        self._servos: dict[str, AngularServo] = {}
        self._vel: dict[str, float] = {}
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
            self._vel[joint] = 0.0

        self.pose = Pose()
        self.target = Pose()
        self.relaxed = False
        for joint in self.pins:
            self._servos[joint].angle = NEUTRAL - 90.0  # snap to start pose once

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if update_hz:
            self._thread = threading.Thread(
                target=self._run, args=(update_hz,), daemon=True)
            self._thread.start()

    def set_pose(self, yaw: float | None = None, pitch: float | None = None,
                 roll: float | None = None):
        """Record a target. The easing (thread or manual update) moves to it."""
        with self._lock:
            for joint, val in (("yaw", yaw), ("pitch", pitch), ("roll", roll)):
                if val is None or joint not in self._servos:
                    continue
                setattr(self.target, joint, clamp(joint, val))
            self.relaxed = False

    def relax(self):
        with self._lock:
            for s in self._servos.values():
                s.detach()  # stop sending pulses
            self.relaxed = True

    def update(self, dt: float):
        """Only needed when update_hz=0. With the thread running, it owns
        motion and this is a no-op."""
        if self._thread is None:
            self._step(dt)

    # -- internals ----------------------------------------------------------

    def _run(self, hz: float):
        period = 1.0 / hz
        last = time.monotonic()
        while not self._stop.is_set():
            now = time.monotonic()
            dt = now - last
            last = now
            self._step(dt)
            time.sleep(max(0.0, period - (time.monotonic() - now)))

    def _step(self, dt: float):
        with self._lock:
            if self.relaxed or dt <= 0:
                return
            for joint, servo in self._servos.items():
                cur = getattr(self.pose, joint)
                tgt = getattr(self.target, joint)
                # settled: hold still, no pointless micro-writes (also quieter)
                if abs(tgt - cur) < 0.05 and abs(self._vel[joint]) < 0.5:
                    self._vel[joint] = 0.0
                    continue
                cur, self._vel[joint] = _smooth_damp(
                    cur, tgt, self._vel[joint], self.smooth_time, dt,
                    self.max_speed)
                setattr(self.pose, joint, cur)
                servo.angle = cur - 90.0

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self.relax()
        for s in self._servos.values():
            s.close()
