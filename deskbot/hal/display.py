"""Display HAL: same interface for the real SH1106 OLED and a PC simulator.

Everything above this layer just hands over a 1-bit 128x64 PIL image.
"""
from __future__ import annotations

from PIL import Image

W, H = 128, 64


class SimDisplay:
    """Pygame window pretending to be the 1.3\" OLED (scaled up, with a
    subtle pixel grid so it reads like the real panel)."""

    def __init__(self, scale: int = 6, title: str = "deskbot — OLED sim"):
        import pygame  # imported here so the Pi never needs pygame
        self._pg = pygame
        pygame.init()
        self.scale = scale
        self.screen = pygame.display.set_mode((W * scale, H * scale))
        pygame.display.set_caption(title)
        self._px = pygame.Surface((W, H))

    def show(self, img: Image.Image):
        pg = self._pg
        rgb = img.convert("RGB").tobytes()
        surf = pg.image.frombytes(rgb, (W, H), "RGB")
        scaled = pg.transform.scale(surf, self.screen.get_size())
        self.screen.blit(scaled, (0, 0))
        if self.scale >= 4:  # pixel grid for OLED look
            dark = (14, 14, 14)
            for x in range(0, W * self.scale, self.scale):
                pg.draw.line(self.screen, dark, (x, 0), (x, H * self.scale))
            for y in range(0, H * self.scale, self.scale):
                pg.draw.line(self.screen, dark, (0, y), (W * self.scale, y))
        pg.display.flip()

    def close(self):
        self._pg.quit()


class OledDisplay:
    """Real SH1106 128x64 over I2C (Raspberry Pi). Requires luma.oled.

    pip install luma.oled   # on the Pi
    If your panel turns out to be SSD1306, change sh1106 -> ssd1306 below.
    """

    def __init__(self, i2c_port: int = 1, address: int = 0x3C):
        from luma.core.interface.serial import i2c
        from luma.oled.device import sh1106
        serial = i2c(port=i2c_port, address=address)
        self.device = sh1106(serial, width=W, height=H)

    def show(self, img: Image.Image):
        self.device.display(img.convert("1"))

    def close(self):
        self.device.cleanup()


def auto_display(**kwargs):
    """Pick the real OLED when available, otherwise the simulator."""
    try:
        return OledDisplay()
    except Exception:
        return SimDisplay(**kwargs)
