"""Sweep the roll servo (GPIO12, direct-wired, no PCA9685) to verify wiring.

Run on the Pi:  python tools/test_servo.py
Ctrl+C to stop -- the servo is relaxed and released on exit.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deskbot.hal.servos import SAFE_RANGES
from deskbot.hal.gpio_servos import GpioServos

JOINT = "roll"
PIN = 12
STEP_DELAY = 0.02  # s between angle steps
STEP_SIZE = 2.0    # degrees per step


def main():
    lo, hi = SAFE_RANGES[JOINT]
    servos = GpioServos({JOINT: PIN})
    print(f"{JOINT} servo on GPIO{PIN}, sweeping {lo}-{hi} deg. Ctrl+C to stop.")

    try:
        angle = 90.0
        direction = 1
        while True:
            angle += STEP_SIZE * direction
            if angle >= hi:
                angle = hi
                direction = -1
            elif angle <= lo:
                angle = lo
                direction = 1
            servos.set_pose(roll=angle)
            print(f"\r{JOINT} -> {angle:6.1f} deg", end="", flush=True)
            time.sleep(STEP_DELAY)
    except KeyboardInterrupt:
        print("\nstopping, relaxing servo")
    finally:
        servos.close()


if __name__ == "__main__":
    main()
