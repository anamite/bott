"""Render every expression to one labeled PNG grid for visual inspection."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from deskbot.animation.eyes import EXPRESSIONS, EyeController
from deskbot.animation.overlays import ANIMATIONS

SCALE = 3
COLS = 4
PAD = 8
LABEL_H = 14


def settled_frame(name: str) -> Image.Image:
    ctrl = EyeController(idle=False, seed=1)
    if name in ANIMATIONS:
        ctrl.set_animation(name, duration=0.01)
        n_frames = 60  # let particles populate
    else:
        ctrl.set_expression(name, duration=0.01)
        n_frames = 30
    frame = None
    for _ in range(n_frames):
        frame = ctrl.update(1 / 50)
    return frame


def main(out_path: str):
    names = list(EXPRESSIONS) + list(ANIMATIONS)
    rows = (len(names) + COLS - 1) // COLS
    cw, ch = 128 * SCALE + PAD, 64 * SCALE + LABEL_H + PAD
    sheet = Image.new("RGB", (COLS * cw + PAD, rows * ch + PAD), (24, 24, 30))
    d = ImageDraw.Draw(sheet)

    for i, name in enumerate(names):
        cx = PAD + (i % COLS) * cw
        cy = PAD + (i // COLS) * ch
        frame = settled_frame(name).convert("RGB")
        frame = frame.resize((128 * SCALE, 64 * SCALE), Image.NEAREST)
        sheet.paste(frame, (cx, cy))
        d.rectangle([cx, cy, cx + 128 * SCALE, cy + 64 * SCALE],
                    outline=(70, 70, 80))
        d.text((cx + 2, cy + 64 * SCALE + 2), name, fill=(220, 220, 220))

    sheet.save(out_path)
    print("saved", out_path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "eyes_sheet.png")
