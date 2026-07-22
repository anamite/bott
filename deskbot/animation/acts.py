"""Acts: named performances pairing face + neck gesture + LED.

An Act is one row of the bot's repertoire: which eye animation (overlay) or
plain expression to show, which gesture primitive the neck plays (with
amplitude/speed/cycle scaling), and what the mood LED does meanwhile.

play() fires all three channels and returns how long the act runs in
seconds (gesture length + hold); the caller restores whatever idle state it
wants afterwards (the demo goes back to neutral eyes + idle glow).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import gestures

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Act:
    anim: str | None = None        # overlay animation (overlays.ANIMATIONS)...
    expr: str | None = None        # ...or plain expression — exactly one
    gesture: str | None = None     # primitive in gestures.PRIMITIVES
    amp: float = 1.0
    speed: float = 1.0
    cycles: int = 1
    led: RGB | None = None
    led_period: float | None = None   # None = steady color, else pulse
    hold: float = 0.8              # extra seconds after the gesture ends


# The repertoire. Every screen overlay gets a body; a few expression-only
# acts round out the social basics (greet, nope, curious...).
ACTS: dict[str, Act] = {
    # -- overlay-backed performances ------------------------------------
    "party":     Act(anim="party", gesture="bounce", cycles=7, speed=1.2,
                     led=(255, 60, 180), led_period=0.5),
    "laugh":     Act(anim="laugh", gesture="throwback", amp=1.1,
                     led=(255, 190, 40), led_period=0.6),
    "cry":       Act(anim="cry", gesture="droop", amp=1.1, speed=0.8,
                     led=(40, 80, 255), led_period=2.5),
    "hearts":    Act(anim="hearts", gesture="sway", cycles=2, speed=0.9,
                     led=(255, 70, 120), led_period=1.2),
    "shock":     Act(anim="shock", gesture="flinch", amp=1.3,
                     led=(255, 255, 255)),
    "music":     Act(anim="music", gesture="sway", cycles=3, speed=1.5,
                     led=(80, 40, 255), led_period=0.8),
    "rage":      Act(anim="rage", gesture="shiver", amp=1.6, cycles=2,
                     led=(255, 30, 10), led_period=0.35),
    "confused":  Act(anim="confused", gesture="double_tilt",
                     led=(180, 80, 255)),
    "tired":     Act(anim="tired", gesture="droop", speed=0.9,
                     led=(200, 120, 40), led_period=3.0),
    "thumbs_up": Act(anim="thumbs_up", gesture="perk",
                     led=(60, 255, 90)),
    "pew":       Act(anim="pew", gesture="recoil",
                     led=(255, 220, 60), led_period=0.15, hold=0.3),
    "pew3d":     Act(anim="pew3d", gesture="impact_slam",
                     led=(60, 220, 255), hold=0.2),
    "glasses":   Act(anim="glasses", gesture="tilt", amp=0.8, speed=0.8,
                     led=(30, 200, 200)),
    "blast":     Act(anim="blast", gesture="kaboom",
                     led=(255, 120, 20), led_period=0.4, hold=0.3),
    "freeze":    Act(anim="freeze", gesture="shiver", amp=0.7, speed=1.3,
                     cycles=3, led=(120, 200, 255), led_period=1.5),
    "drink":     Act(anim="drink", gesture="tilt", amp=0.6, speed=0.7,
                     led=(40, 160, 255)),
    "hack":      Act(anim="hack", gesture="lean_in", amp=1.2, speed=0.6,
                     led=(40, 255, 60), led_period=0.7, hold=2.0),
    "hypno":     Act(anim="hypno", gesture="sway", cycles=3, speed=0.7,
                     led=(160, 40, 255), led_period=1.8),
    "sleep":     Act(anim="sleep", gesture="droop", amp=1.3, speed=0.5,
                     led=(20, 40, 90), led_period=4.0, hold=2.0),
    "space":     Act(anim="space", gesture="scan", speed=0.7,
                     led=(30, 60, 200), led_period=2.2),

    # -- expression-only social basics ----------------------------------
    "greet":     Act(expr="happy", gesture="nod",
                     led=(255, 180, 60), led_period=1.0),
    "yes":       Act(expr="happy", gesture="nod", amp=1.1),
    "nope":      Act(expr="sad", gesture="shake"),
    "curious":   Act(expr="curious", gesture="double_tilt", amp=1.1,
                     led=(30, 200, 200)),
    "sneeze":    Act(expr="surprised", gesture="sneeze",
                     led=(255, 255, 255)),
    "dizzy":     Act(expr="dizzy", gesture="sway", cycles=2, speed=1.6,
                     led=(120, 255, 80), led_period=0.6),
    "wiggle":    Act(expr="joy", gesture="wiggle",
                     led=(255, 120, 200)),
    "lookaround": Act(expr="neutral", gesture="scan", speed=0.8),

    # -- cute quick acts: fast, snappy, small amplitude for charm not drama --
    "boop":       Act(expr="happy", gesture="nod", amp=1.15, speed=1.8,
                      led=(255, 200, 80), hold=0.15),
    "peekaboo":   Act(expr="curious", gesture="double_tilt", amp=0.8,
                      speed=1.6, led=(120, 220, 255), hold=0.2),
    "eager":      Act(expr="surprised", gesture="perk", amp=1.1, speed=1.7,
                      led=(255, 240, 120), hold=0.15),
    "shy":        Act(expr="bored", gesture="tilt", amp=0.5, speed=1.5,
                      led=(200, 140, 255), hold=0.3),
    "aww":        Act(expr="love", gesture="sway", amp=0.8, speed=1.3,
                      led=(255, 110, 170), led_period=0.9, hold=0.3),
    "oopsie":     Act(expr="surprised", gesture="flinch", amp=0.9, speed=1.6,
                      led=(255, 255, 255), hold=0.2),
    "sleepy_nod": Act(expr="sleepy", gesture="droop", amp=0.8, speed=1.4,
                      led=(160, 120, 60), led_period=2.0, hold=0.4),
    "cheeky_wink": Act(expr="wink", gesture="tilt", amp=0.6, speed=1.6,
                      led=(255, 180, 60), hold=0.25),
    "wiggle_happy": Act(expr="joy", gesture="wiggle", amp=1.0, speed=1.5,
                      led=(255, 140, 210), hold=0.15),
    "huh":        Act(expr="skeptic", gesture="double_tilt", amp=0.7,
                      speed=1.4, led=(180, 120, 255), hold=0.25),
}


def play(name: str, eyes, gesture_ctl, led) -> float:
    """Fire an act on all three channels. Returns run length in seconds."""
    act = ACTS[name]
    if act.anim is not None:
        eyes.set_animation(act.anim)
    elif act.expr is not None:
        eyes.set_expression(act.expr)
    g_dur = 0.0
    if act.gesture is not None:
        gesture_ctl.play(act.gesture, amp=act.amp, speed=act.speed,
                         cycles=act.cycles)
        g_dur = gestures.duration(act.gesture, act.speed, act.cycles)
    if act.led is not None:
        if act.led_period is not None:
            led.pulse(act.led, act.led_period)
        else:
            led.set_color(act.led)
    return g_dur + act.hold
