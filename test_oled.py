"""Live eye test on the real 1.3" I2C OLED (run this ON the Raspberry Pi).

    python test_oled.py                  # auto-cycle all expressions + animations
    python test_oled.py happy            # hold one expression/animation
    python test_oled.py --step           # press Enter to step through them one by one
    python test_oled.py --list           # show available names
    python test_oled.py --driver ssd1306 # if sh1106 output looks shifted/garbled

Needs: pip install luma.oled pillow   (no pygame required on the Pi)
"""
from __future__ import annotations

import argparse
import queue
import random
import threading
import time

from deskbot.animation.eyes import EXPRESSIONS, EyeController
from deskbot.animation.overlays import ANIMATIONS

ALL_NAMES = list(EXPRESSIONS) + list(ANIMATIONS)


def enter_key_listener(q: "queue.Queue[None]"):
    """Runs in a background thread; pushes an item each time Enter is pressed."""
    while True:
        try:
            input()
        except EOFError:
            return
        q.put(None)


def make_display(driver: str, address: int):
    from luma.core.interface.serial import i2c
    from luma.oled.device import sh1106, ssd1306
    serial = i2c(port=1, address=address)
    dev = {"sh1106": sh1106, "ssd1306": ssd1306}[driver](serial)
    dev.contrast(255)
    return dev


def play(ctrl: EyeController, name: str):
    if name in ANIMATIONS:
        ctrl.set_animation(name)
    else:
        ctrl.set_expression(name)
    print("->", name, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", help="expression/animation to hold")
    ap.add_argument("--driver", default="sh1106", choices=["sh1106", "ssd1306"])
    ap.add_argument("--address", default="0x3C")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--step", action="store_true",
                     help="press Enter to step through expressions/animations one at a time")
    args = ap.parse_args()

    if args.list:
        print("expressions:", ", ".join(EXPRESSIONS))
        print("animations: ", ", ".join(ANIMATIONS))
        return
    if args.name and args.name not in ALL_NAMES:
        raise SystemExit(f"unknown name {args.name!r} — try --list")

    device = make_display(args.driver, int(args.address, 16))
    ctrl = EyeController()
    if args.name:
        play(ctrl, args.name)

    step_index = -1
    key_queue: "queue.Queue[None]" = queue.Queue()
    if args.step and args.name is None:
        threading.Thread(target=enter_key_listener, args=(key_queue,), daemon=True).start()

    switch_at = time.monotonic() + 4.0
    last = time.monotonic()
    frames = 0
    fps_at = last + 5.0

    if args.step and args.name is None:
        print("running — press Enter to step, Ctrl+C to stop")
    else:
        print("running — Ctrl+C to stop")
    try:
        while True:
            now = time.monotonic()
            dt = min(now - last, 0.1)
            last = now

            if args.step and args.name is None:
                try:
                    key_queue.get_nowait()
                    step_index = (step_index + 1) % len(ALL_NAMES)
                    play(ctrl, ALL_NAMES[step_index])
                except queue.Empty:
                    pass
            elif args.name is None and now >= switch_at:
                switch_at = now + random.uniform(3.0, 5.0)
                play(ctrl, random.choice(ALL_NAMES))

            device.display(ctrl.update(dt))

            frames += 1
            if now >= fps_at:
                print(f"   {frames / 5.0:.1f} fps", flush=True)
                frames = 0
                fps_at = now + 5.0
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
