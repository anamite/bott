"""Live idle behavior loop on real hardware -- gazes around on its own and
randomly plays acts (face + neck gesture + LED together), forever.

Run directly on the Pi:

    python hw_live.py                      # random acts every ~4-10s
    python hw_live.py --min 8 --max 20      # play less often
    python hw_live.py --seed 1              # repeatable random choices

Ctrl+C to stop -- servos relax and the display/LED clear on exit.

Between acts the head isn't dead-still: it gets a small always-on breathing
sway (same idea as demo_bot's idle layer), and the eyes run their own
saccades/blinks (EyeController(idle=True) already does this whenever
look_at() hasn't been given an external target). Acts briefly take over
both channels, then everything eases back to idle.
"""
from __future__ import annotations

import argparse
import math
import random
import time

from deskbot.animation import acts
from deskbot.animation.eyes import EyeController
from deskbot.animation.gestures import GestureController
from deskbot.hal.display import auto_display
from deskbot.hal.led import auto_led
from deskbot.hal.servos import auto_servos, NEUTRAL

FRAME_DT = 0.02
IDLE_COLOR = (30, 120, 140)
IDLE_PERIOD = 4.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=4.0, help="min seconds idle between acts")
    ap.add_argument("--max", type=float, default=10.0, help="max seconds idle between acts")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    disp = auto_display()
    servos = auto_servos()
    led = auto_led()
    eyes = EyeController(idle=True, seed=args.seed)
    gestures = GestureController()

    print(f"display={type(disp).__name__} servos={type(servos).__name__} "
          f"led={type(led).__name__}")
    print("Ctrl+C to stop.\n")

    act_names = list(acts.ACTS)
    led.pulse(IDLE_COLOR, period=IDLE_PERIOD)

    t = 0.0
    next_act_at = rng.uniform(args.min, args.max)
    act_until = None
    last = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            dt = min(now - last, 0.05)
            last = now
            t += dt

            # fire a random act when idle time is up
            if act_until is None and t >= next_act_at:
                name = rng.choice(act_names)
                run_len = acts.play(name, eyes, gestures, led)
                act_until = t + run_len
                print(f"[{t:6.1f}s] act -> {name} ({run_len:.1f}s)")

            # act finished -> back to idle face/pose/LED
            if act_until is not None and t >= act_until:
                act_until = None
                eyes.set_expression("neutral")
                led.pulse(IDLE_COLOR, period=IDLE_PERIOD)
                next_act_at = t + rng.uniform(args.min, args.max)

            gyaw, gpitch, groll = gestures.update(dt)

            # idle breathing: tiny always-on pitch sway when no act is running
            if act_until is None:
                gpitch += math.sin(t * 2 * math.pi * 0.25) * 1.5

            servos.set_pose(NEUTRAL + gyaw, NEUTRAL + gpitch, NEUTRAL + groll)
            servos.update(dt)
            led.update(dt)
            disp.show(eyes.update(dt))
            time.sleep(FRAME_DT)
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
