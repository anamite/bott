"""Sweep the 28BYJ-48 stepper (roll axis, ULN2003 on GPIO5/6/13/19) to verify wiring.

Run on the Pi:  python tools/test_stepper.py
Ctrl+C to stop -- the coils are de-energized and released on exit.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deskbot.hal.servos import SAFE_RANGES
from deskbot.hal.stepper import Gpio28BYJ48Stepper

JOINT = "roll"
STEP_DELAY = 0.02  # s between commanded-angle updates
STEP_SIZE = 2.0    # degrees per commanded step


def main():
    lo, hi = SAFE_RANGES[JOINT]
    stepper = Gpio28BYJ48Stepper()
    print(f"{JOINT} stepper on GPIO5/6/13/19, sweeping {lo}-{hi} deg. Ctrl+C to stop.")
    print("(NEUTRAL=90 is wherever the horn was pointing at power-on -- "
          "hand-center it before running if that matters.)")

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
            stepper.set_pose(roll=angle)
            stepper.update(STEP_DELAY)
            print(f"\r{JOINT} -> {angle:6.1f} deg", end="", flush=True)
            time.sleep(STEP_DELAY)
    except KeyboardInterrupt:
        print("\nstopping, releasing stepper")
    finally:
        stepper.close()


if __name__ == "__main__":
    main()
