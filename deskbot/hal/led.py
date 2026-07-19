"""LED HAL: single WS2812B mood light + simulator.

set_color() for a steady color, pulse() for a breathing glow; update(dt)
drives the pulse. `color` always holds the currently displayed RGB so any
viewer (virtual bot window, dashboard) can just read it.
"""
from __future__ import annotations

import math

RGB = tuple[int, int, int]


class _LedBase:
    def __init__(self):
        self.color: RGB = (0, 0, 0)
        self._base: RGB = (0, 0, 0)
        self._period: float | None = None
        self._t = 0.0

    def set_color(self, rgb: RGB):
        self._base = rgb
        self._period = None
        self._apply(rgb)

    def pulse(self, rgb: RGB, period: float = 3.0):
        """Breathe rgb up and down over `period` seconds until overridden."""
        self._base = rgb
        self._period = max(0.1, period)
        self._t = 0.0

    def off(self):
        self.set_color((0, 0, 0))

    def update(self, dt: float):
        if self._period is None:
            return
        self._t += dt
        # raised-cosine breath: 0.15 floor so it never fully disappears
        k = 0.15 + 0.85 * (0.5 - 0.5 * math.cos(
            2 * math.pi * self._t / self._period))
        self._apply(tuple(int(c * k) for c in self._base))

    def _apply(self, rgb: RGB):
        self.color = rgb
        self._write(rgb)

    def _write(self, rgb: RGB):  # backend hook
        pass

    def close(self):
        self.off()


class SimLed(_LedBase):
    """Pure state — read .color from the virtual bot / dashboard."""


class Ws2812Led(_LedBase):
    """Real single WS2812B on the Pi. Requires rpi_ws281x:

        pip install rpi_ws281x   # on the Pi, needs root or /dev/mem access
    """

    def __init__(self, pin: int = 12, brightness: int = 128):
        # GPIO 12 (not 18): the I2S mic bus claims GPIO 18/19/20, and
        # rpi_ws281x can drive PWM0 from GPIO 12 just as well.
        super().__init__()
        from rpi_ws281x import PixelStrip, Color
        self._Color = Color
        self.strip = PixelStrip(1, pin, brightness=brightness)
        self.strip.begin()

    def _write(self, rgb: RGB):
        self.strip.setPixelColor(0, self._Color(*rgb))
        self.strip.show()

    def close(self):
        super().close()


def auto_led(**kwargs):
    try:
        return Ws2812Led()
    except Exception:
        return SimLed()
