"""Standalone PCA9685 servo test -- moves yaw, pitch, roll one at a time.

Run directly on the Pi:

    python hw_servo_test.py

Unlike hw_test.py (which uses auto_servos() and silently falls back to the
simulator if the board can't be reached), this constructs Pca9685Servos
directly so any connection/import error is printed instead of hidden.
"""
from __future__ import annotations

import time

from deskbot.hal.servos import Pca9685Servos, SAFE_RANGES, NEUTRAL

STEP_PAUSE = 1.0  # seconds to hold at each position


def sweep_joint(servos: Pca9685Servos, joint: str):
    lo, hi = SAFE_RANGES[joint]
    mid = NEUTRAL
    print(f"\n-- {joint} (channel {servos.CHANNELS[joint]}, range {lo}-{hi}) --")
    for label, angle in (("neutral", mid), ("min", lo), ("max", hi), ("neutral", mid)):
        print(f"  {joint} -> {label} ({angle}deg)")
        servos.set_pose(**{joint: angle})
        time.sleep(STEP_PAUSE)


def main():
    print("Connecting to PCA9685...")
    servos = Pca9685Servos()
    print("Connected. Channel map:", servos.CHANNELS)

    try:
        for joint in ("yaw", "pitch", "roll"):
            sweep_joint(servos, joint)
        print("\nDone. Relaxing servos.")
    except KeyboardInterrupt:
        print("\nInterrupted, relaxing servos.")
    finally:
        servos.relax()


if __name__ == "__main__":
    main()
