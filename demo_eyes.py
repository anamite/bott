"""Interactive eye demo — runs the exact code that will later run on the Pi.

    .venv\\Scripts\\python demo_eyes.py

Keys:
  1..0, q..u      expressions
  s d f g h j k l z x v b n m , . /   animations (party, tired, thumbs_up,
                          pew, laugh, cry, hearts, shock, music, rage,
                          confused, pew3d, glasses, blast, freeze, drink,
                          hack, ... weather: sunny/rainy/winter/cloudy via TAB)
  TAB             cycle through everything
  SPACE           blink now
  A               toggle auto mode (random expressions + animations)
  arrows          manual gaze override, C releases it
  ESC             quit
"""
from __future__ import annotations

import random
import pygame

from deskbot.animation.eyes import EXPRESSIONS, EyeController
from deskbot.animation.overlays import ANIMATIONS
from deskbot.hal.display import SimDisplay

EXPR_NAMES = list(EXPRESSIONS)
ANIM_NAMES = list(ANIMATIONS)
ALL_NAMES = EXPR_NAMES + ANIM_NAMES

KEYMAP: dict[str, str] = {}
for _k, _n in zip("1234567890qwertyu", EXPR_NAMES):
    KEYMAP[_k] = _n
for _k, _n in zip("sdfghjklzxvbnm,./", ANIM_NAMES):
    KEYMAP[_k] = _n


def _play(ctrl: EyeController, name: str):
    if name in ANIMATIONS:
        ctrl.set_animation(name)
    else:
        ctrl.set_expression(name)
    print("->", name)


def main():
    disp = SimDisplay(scale=7)
    ctrl = EyeController()
    clock = pygame.time.Clock()
    auto = False
    auto_next = 0.0
    gaze = None
    cursor = 0

    print("Expressions:")
    for k, n in KEYMAP.items():
        kind = "anim" if n in ANIMATIONS else "expr"
        print(f"  {k} -> {n} ({kind})")
    print("TAB cycle | SPACE blink | A auto | arrows gaze, C center | ESC quit")

    t = 0.0
    running = True
    while running:
        dt = clock.tick(50) / 1000.0
        t += dt

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_SPACE:
                    ctrl.blink_now()
                elif ev.key == pygame.K_a:
                    auto = not auto
                    print(f"auto mode: {auto}")
                elif ev.key == pygame.K_TAB:
                    cursor = (cursor + 1) % len(ALL_NAMES)
                    _play(ctrl, ALL_NAMES[cursor])
                elif ev.key == pygame.K_c:
                    gaze = None
                    ctrl.look_at(None)
                elif ev.unicode in KEYMAP:
                    _play(ctrl, KEYMAP[ev.unicode])

        pressed = pygame.key.get_pressed()
        dx = (pressed[pygame.K_RIGHT] - pressed[pygame.K_LEFT]) * 8
        dy = (pressed[pygame.K_DOWN] - pressed[pygame.K_UP]) * 4
        if dx or dy:
            gaze = (dx, dy)
        if gaze:
            ctrl.look_at(*gaze)

        if auto and t >= auto_next:
            auto_next = t + random.uniform(2.5, 5.5)
            _play(ctrl, random.choice(ALL_NAMES))

        disp.show(ctrl.update(dt))

    disp.close()


if __name__ == "__main__":
    main()
