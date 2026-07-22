"""Headless hardware bring-up test: real OLED + real PCA9685 together.

Run this directly on the Pi (not the pygame demos, which are PC-only):

    python hw_test.py

Cycles a few eye expressions while sweeping the neck through yaw/pitch/roll,
so you can confirm both the display and all three servos respond correctly
at the same time. Ctrl+C to stop -- servos relax and the display clears on
exit.
"""
from __future__ import annotations

import math
import time

from deskbot.animation.eyes import EyeController
from deskbot.hal.display import auto_display, OledDisplay
from deskbot.hal.servos import auto_servos, Pca9685Servos, NEUTRAL

EXPR_SEQUENCE = ["neutral", "happy", "surprised", "sad", "angry", "sleepy"]
EXPR_DWELL = 2.0  # seconds per expression


def main():
    disp = auto_display()
    servos = auto_servos()
    eyes = EyeController()

    print(f"display: {type(disp).__name__}  servos: {type(servos).__name__}")
    if not isinstance(disp, OledDisplay):
        print("  (no real OLED found -- falling back to SimDisplay)")
    if not isinstance(servos, Pca9685Servos):
        print("  (no real PCA9685 found -- falling back to SimServos)")

    t = 0.0
    expr_i = 0
    next_expr_at = 0.0
    last = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            dt = now - last
            last = now
            t += dt

            if t >= next_expr_at:
                name = EXPR_SEQUENCE[expr_i % len(EXPR_SEQUENCE)]
                eyes.set_expression(name)
                print(f"[{t:5.1f}s] expression -> {name}")
                expr_i += 1
                next_expr_at = t + EXPR_DWELL

            yaw = NEUTRAL + 40 * math.sin(t * 0.6)
            pitch = NEUTRAL + 20 * math.sin(t * 0.9 + 1.0)
            roll = NEUTRAL + 15 * math.sin(t * 0.5 + 2.0)
            servos.set_pose(yaw, pitch, roll)
            servos.update(dt)

            disp.show(eyes.update(dt))
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\nstopping...")
    finally:
        servos.close()
        disp.close()


if __name__ == "__main__":
    main()
