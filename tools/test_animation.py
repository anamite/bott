"""Peaceful idle: OLED eyes + roll servo driven from ONE breathing clock.

The whole point here is that the head and the face read as a single calm
creature, not two loops running side by side. A single slow "breath" phase
drives both:

  * the head gently sways left/right on the roll servo, and
  * the eyes lean their gaze the same way the head tilts,

so the two channels are phase-locked by construction. The eye engine's own
soft blinks and breathing ride on top. The servo eases itself on a
background thread, so its motion stays smooth even though the OLED refresh
is comparatively slow.

    python tools/test_animation.py

Ctrl+C to stop -- display and servo are released cleanly on exit.
"""
from __future__ import annotations

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deskbot.animation.eyes import EyeController
from deskbot.hal.display import auto_display
from deskbot.hal.gpio_servos import GpioServos
from deskbot.hal.servos import NEUTRAL

ROLL_PIN = 12
BREATH_PERIOD = 6.0     # seconds per full sway cycle -- slow = calm
ROLL_AMPLITUDE = 6.0    # degrees either side of neutral -- gentle
GAZE_LEAN = 4.0         # px the eyes drift toward the tilt direction
TARGET_FPS = 40


def main():
    display = auto_display()
    # dreamy easing; servo self-updates on its own thread
    servos = GpioServos({"roll": ROLL_PIN}, smooth_time=0.5)
    eyes = EyeController(idle=True)

    print("peaceful idle running -- Ctrl+C to stop")
    t = 0.0
    last = time.monotonic()
    try:
        while True:
            now = time.monotonic()
            dt = now - last
            last = now
            t += dt

            # one clock -> both channels, so they can't drift apart
            wave = math.sin(2 * math.pi * t / BREATH_PERIOD)   # -1..1 breath
            servos.set_pose(roll=NEUTRAL + ROLL_AMPLITUDE * wave)
            eyes.look_at(GAZE_LEAN * wave, 0.0)   # eyes lean into the tilt

            display.show(eyes.update(dt))
            time.sleep(max(0.0, 1.0 / TARGET_FPS - (time.monotonic() - now)))
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        servos.close()
        display.close()


if __name__ == "__main__":
    main()
