"""Interactive servo zero-error calibration (run on the Raspberry Pi).

Walks through yaw, pitch, roll one at a time. For each, the servo is driven to
its nominal NEUTRAL (90 deg). You then nudge it with the keyboard until the head
is *physically* centered/level, and the script records how far off 90 the true
center is. At the end it prints all three offsets so they can be baked into the
servo code.

    python tools/calibrate_servos.py

Controls (per joint):
    a / d   nudge  -1 / +1 deg   (fine)
    A / D   nudge  -5 / +5 deg   (coarse)
    z / c   nudge -0.2 / +0.2    (super fine)
    r       reset this joint back to 90
    n       accept this joint, move to the next one
    q       quit immediately (discards unfinished joints)

Requires: pip install adafruit-circuitpython-servokit
"""
from __future__ import annotations

import sys

# --- import the project's servo config so we stay consistent -----------------
sys.path.insert(0, __file__.rsplit("tools", 1)[0])
from deskbot.hal.servos import JOINTS, NEUTRAL  # noqa: E402

CHANNELS = {"yaw": 2, "pitch": 1, "roll": 0}  # matches Pca9685Servos.CHANNELS

# During calibration we allow the full physical servo travel so the true
# center can be found even when it sits outside the logical SAFE_RANGES.
PHYS_MIN, PHYS_MAX = 0.0, 180.0


def _read_key() -> str:
    """Read a single keypress without needing Enter (POSIX / Windows)."""
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except ImportError:
        import msvcrt  # Windows

        return msvcrt.getwch()


def main() -> None:
    from adafruit_servokit import ServoKit

    kit = ServoKit(channels=16, address=0x40)
    for ch in CHANNELS.values():
        kit.servo[ch].set_pulse_width_range(500, 2400)

    offsets: dict[str, float] = {}

    print(__doc__)
    print("=" * 60)

    for joint in JOINTS:
        ch = CHANNELS[joint]
        lo, hi = PHYS_MIN, PHYS_MAX
        angle = NEUTRAL
        kit.servo[ch].angle = angle
        print(f"\n>>> Calibrating {joint.upper()} (channel {ch}). "
              f"Center it, then press 'n'.")

        while True:
            offset = angle - NEUTRAL
            print(f"    {joint}: angle={angle:6.1f}  offset={offset:+5.1f}   ",
                  end="\r", flush=True)
            key = _read_key()

            if key == "a":
                angle -= 1
            elif key == "d":
                angle += 1
            elif key == "A":
                angle -= 5
            elif key == "D":
                angle += 5
            elif key == "z":
                angle -= 0.2
            elif key == "c":
                angle += 0.2
            elif key == "r":
                angle = NEUTRAL
            elif key == "n":
                offsets[joint] = round(angle - NEUTRAL, 1)
                print(f"\n    -> {joint} true center at {angle:.1f} "
                      f"(offset {offsets[joint]:+.1f})")
                break
            elif key == "q":
                print("\nAborted.")
                for c in CHANNELS.values():
                    kit.servo[c].angle = None
                return

            angle = max(lo, min(hi, angle))
            kit.servo[ch].angle = angle

    # release the servos so they stop buzzing
    for c in CHANNELS.values():
        kit.servo[c].angle = None

    print("\n" + "=" * 60)
    print("CALIBRATION DONE. Zero-error offsets (add to 90):\n")
    print("    OFFSETS = {")
    for joint in JOINTS:
        print(f'        "{joint}": {offsets[joint]:+.1f},')
    print("    }")
    print("\nPaste this to me and I'll bake it into the servo code.")


if __name__ == "__main__":
    main()
