"""Mic HAL: INMP441 I2S mic pair (stereo) + simulator.

Both backends expose read() -> Levels (call it often; it never blocks).
Levels are linear RMS in 0..1 per channel, computed over the most recent
audio block. With two mics (L/R pin tied low on one, high on the other)
`balance` gives a crude left/right sound bearing.

Pi wiring (both mics share the bus): SCK -> GPIO 18, WS -> GPIO 19,
SD -> GPIO 20, VDD -> 3.3V. L/R pin: GND = left channel, 3.3V = right.
Enable in /boot/firmware/config.txt:
    dtparam=i2s=on
    dtoverlay=googlevoicehat-soundcard
"""
from __future__ import annotations

import math
import random
import threading
from dataclasses import dataclass


@dataclass
class Levels:
    rms_l: float   # 0..1 linear RMS, left mic
    rms_r: float   # 0..1 linear RMS, right mic

    @property
    def level(self) -> float:
        """Loudest channel, 0..1. Use this if you don't care about direction."""
        return max(self.rms_l, self.rms_r)

    @property
    def db(self) -> float:
        """Level in dBFS (0 = full scale, quiet room is around -60)."""
        return 20 * math.log10(max(self.level, 1e-6))

    @property
    def balance(self) -> float:
        """-1 = all left, +1 = all right, 0 = centered/silence."""
        s = self.rms_l + self.rms_r
        return (self.rms_r - self.rms_l) / s if s > 1e-6 else 0.0


class I2sMic:
    """Real INMP441 pair via sounddevice. On the Pi:

        pip install sounddevice   # needs libportaudio2 (apt install)

    Audio is captured on a background thread (sounddevice's own); read()
    just returns the latest per-channel RMS, so it's safe to call from the
    animation loop at any rate. INMP441 samples are 24-bit left-justified
    in 32-bit frames, so int32 full scale is the correct normalizer.
    """

    def __init__(self, device: str | int | None = None,
                 samplerate: int = 48000, blocksize: int = 1024):
        import numpy as np
        import sounddevice as sd
        self._np = np
        self._lock = threading.Lock()
        self._rms = (0.0, 0.0)
        if device is None:
            device = self._find_device(sd)
        self.stream = sd.InputStream(
            device=device, channels=2, samplerate=samplerate,
            blocksize=blocksize, dtype="int32", callback=self._on_block)
        self.stream.start()

    @staticmethod
    def _find_device(sd) -> int:
        for i, d in enumerate(sd.query_devices()):
            if "voicehat" in d["name"].lower() and d["max_input_channels"] >= 2:
                return i
        return sd.default.device[0]

    def _on_block(self, indata, frames, time, status):
        x = indata.astype(self._np.float64) / 2147483648.0
        rms = self._np.sqrt((x * x).mean(axis=0))
        with self._lock:
            self._rms = (float(rms[0]), float(rms[1]))

    def read(self) -> Levels:
        with self._lock:
            l, r = self._rms
        return Levels(l, r)

    def close(self):
        self.stream.stop()
        self.stream.close()


class SimMic:
    """Synthetic room sound for PC development.

    Quiet ambient hiss by default. Call bang(loudness, balance) to fake a
    clap (decays on its own), or set_level() to hold a level (e.g. from a
    keyboard key). Call update(dt) every frame like the other sim HALs.
    """

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self._held: tuple[float, float] | None = None
        self._event = [0.0, 0.0]

    def bang(self, loudness: float = 0.8, balance: float = 0.0):
        """One-shot sound: balance -1 (left) .. +1 (right)."""
        self._event[0] = loudness * min(1.0, 1.0 - balance)
        self._event[1] = loudness * min(1.0, 1.0 + balance)

    def set_level(self, level: float | None, balance: float = 0.0):
        """Hold a steady level until set_level(None)."""
        if level is None:
            self._held = None
        else:
            self._held = (level * min(1.0, 1.0 - balance),
                          level * min(1.0, 1.0 + balance))

    def update(self, dt: float):
        decay = math.exp(-dt * 8.0)   # claps die out in ~0.5 s
        self._event[0] *= decay
        self._event[1] *= decay

    def read(self) -> Levels:
        floor = 0.002 + abs(self.rng.gauss(0, 0.001))   # room tone
        l, r = self._held if self._held is not None else (0.0, 0.0)
        return Levels(max(floor, l, self._event[0]),
                      max(floor, r, self._event[1]))

    def close(self):
        pass


def auto_mic(**kwargs):
    try:
        return I2sMic()
    except Exception:
        return SimMic(**kwargs)
