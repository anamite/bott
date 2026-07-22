"""Try acts (face + neck gesture + LED together) on real hardware.

Run directly on the Pi:

    python hw_acts_test.py            # interactive: type an act name, Enter
    python hw_acts_test.py boop       # play one act once and exit
    python hw_acts_test.py --all      # play every act back to back

Uses the real OLED + PCA9685 (+ WS2812B LED if wired) via auto_*(), same
HAL the rest of the project uses, so what you see here is exactly what a
behavior loop would produce.
"""
from __future__ import annotations

import sys
import time

from deskbot.animation import acts
from deskbot.animation.eyes import EyeController
from deskbot.animation.gestures import GestureController
from deskbot.hal.display import auto_display
from deskbot.hal.led import auto_led
from deskbot.hal.servos import auto_servos, NEUTRAL

FRAME_DT = 0.02  # ~50 fps loop


def run_act(name: str, disp, servos, led, eyes, gestures):
    print(f"-> {name}")
    run_len = acts.play(name, eyes, gestures, led)
    end = time.monotonic() + run_len
    last = time.monotonic()
    while time.monotonic() < end:
        now = time.monotonic()
        dt = min(now - last, 0.05)
        last = now

        gyaw, gpitch, groll = gestures.update(dt)
        servos.set_pose(NEUTRAL + gyaw, NEUTRAL + gpitch, NEUTRAL + groll)
        servos.update(dt)
        led.update(dt)
        disp.show(eyes.update(dt))
        time.sleep(FRAME_DT)

    # settle back to neutral face/pose/LED between acts
    eyes.set_expression("neutral")
    led.pulse((30, 120, 140), period=4.0)
    settle_end = time.monotonic() + 0.6
    last = time.monotonic()
    while time.monotonic() < settle_end:
        now = time.monotonic()
        dt = min(now - last, 0.05)
        last = now
        gyaw, gpitch, groll = gestures.update(dt)
        servos.set_pose(NEUTRAL + gyaw, NEUTRAL + gpitch, NEUTRAL + groll)
        servos.update(dt)
        led.update(dt)
        disp.show(eyes.update(dt))
        time.sleep(FRAME_DT)


def main():
    disp = auto_display()
    servos = auto_servos()
    led = auto_led()
    eyes = EyeController()
    gestures = GestureController()

    print(f"display={type(disp).__name__} servos={type(servos).__name__} "
          f"led={type(led).__name__}")

    names = list(acts.ACTS)
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--all":
            for n in names:
                run_act(n, disp, servos, led, eyes, gestures)
        elif len(sys.argv) > 1:
            name = sys.argv[1]
            if name not in acts.ACTS:
                print(f"unknown act {name!r}. Available:\n  " + "\n  ".join(names))
                return
            run_act(name, disp, servos, led, eyes, gestures)
        else:
            print("Acts:\n  " + "\n  ".join(names))
            print("Type an act name and Enter (empty to quit):")
            while True:
                name = input("> ").strip()
                if not name:
                    break
                if name not in acts.ACTS:
                    print(f"unknown act {name!r}")
                    continue
                run_act(name, disp, servos, led, eyes, gestures)
    except KeyboardInterrupt:
        print("\nstopping...")
    finally:
        servos.set_pose(NEUTRAL, NEUTRAL, NEUTRAL)
        servos.update(1.0)
        servos.close()
        led.close()
        disp.close()


if __name__ == "__main__":
    main()
