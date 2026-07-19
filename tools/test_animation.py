"""Slow, peaceful idle animation: OLED eyes + roll servo, paired together.

Only the roll servo is wired right now (GPIO12, direct -- see
deskbot/hal/gpio_servos.py). This drives a gentle, continuous sway synced
to a slow breathing-style eye cycle so the two channels read as one calm
performance instead of two independent loops. Run on the Pi:

    python tools/test_animation.py

Ctrl+C to stop -- display and servo are both released cleanly on exit.
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
PERIOD = 7.0          # seconds per full sway cycle -- slow and calm
ROLL_AMPLITUDE = 8.0  # degrees either side of neutral, gentle not dramatic
FPS = 40


def main():
    display = auto_display()
    servos = GpioServos({"roll": ROLL_PIN})
    eyes = EyeController(idle=True)

    print("peaceful idle animation running -- Ctrl+C to stop")
    t = 0.0
    expression = "neutral"
    try:
        while True:
            dt = 1.0 / FPS
            t += dt

            phase = (t % PERIOD) / PERIOD
            wave = math.sin(2 * math.pi * phase)
            servos.set_pose(roll=NEUTRAL + ROLL_AMPLITUDE * wave)

            # eyes drift between neutral and a soft droop on the same
            # rhythm as the sway, so face + neck read as one slow breath
            target = "sleepy" if wave > 0 else "neutral"
            if target != expression:
                expression = target
                eyes.set_expression(expression, duration=PERIOD / 2)

            display.show(eyes.update(dt))
            time.sleep(dt)
    except KeyboardInterrupt:
        print("\nstopping, relaxing servo")
    finally:
        servos.close()
        display.close()


if __name__ == "__main__":
    main()
