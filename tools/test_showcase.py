"""Cycle through the full act repertoire (party, shock, space, hack, ...).

Yaw/pitch aren't wired yet, so only the roll component of each gesture
drives the physical servo -- the eye overlay animations (party, shooting,
space swirl, hearts, ...) still render in full regardless, since they're
pure screen effects. LED is SimLed (state only) since the WS2812 isn't
wired yet either.

    python tools/test_showcase.py

Ctrl+C to stop -- display and servo are both released cleanly on exit.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deskbot.animation import acts
from deskbot.animation.eyes import EyeController
from deskbot.animation.gestures import GestureController
from deskbot.hal.display import auto_display
from deskbot.hal.gpio_servos import GpioServos
from deskbot.hal.led import SimLed
from deskbot.hal.servos import NEUTRAL

ROLL_PIN = 12
TARGET_FPS = 40   # frame cap; real dt is measured, not assumed


def main():
    display = auto_display()
    # snappy easing: gestures are already shaped, just de-step the servo
    servos = GpioServos({"roll": ROLL_PIN}, smooth_time=0.12)
    eyes = EyeController(idle=True)
    gesture_ctl = GestureController()
    led = SimLed()

    act_names = list(acts.ACTS)
    idx = 0

    def play_next() -> float:
        nonlocal idx
        name = act_names[idx]
        run_len = acts.play(name, eyes, gesture_ctl, led)
        print(f"act: {name} ({run_len:.1f}s)")
        idx = (idx + 1) % len(act_names)
        return time.monotonic() + run_len

    print("showcase running -- Ctrl+C to stop")
    last = time.monotonic()
    try:
        until = play_next()
        while True:
            now = time.monotonic()
            dt = now - last
            last = now

            if now >= until:
                eyes.set_expression("neutral")
                until = play_next()
            _, _, groll = gesture_ctl.update(dt)
            servos.set_pose(roll=NEUTRAL + groll)   # servo eases on its thread
            display.show(eyes.update(dt))
            elapsed = time.monotonic() - now
            time.sleep(max(0.0, 1.0 / TARGET_FPS - elapsed))
    except KeyboardInterrupt:
        print("\nstopping, relaxing servo")
    finally:
        servos.close()
        display.close()


if __name__ == "__main__":
    main()
