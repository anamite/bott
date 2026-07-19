"""IMU HAL: MPU6050 accel/gyro/temp + simulator.

Both backends expose read() -> ImuSample. Accel in g, gyro in deg/s, temp
in Celsius. At rest the accel magnitude is ~1.0 (gravity); the perception
layer detects pickup/shake/tap from departures of |a| from 1 g.

The simulator sits at rest with realistic noise; inject events from test /
demo code with pickup(), put_down(), shake(), tap() and the sample stream
will look like the real thing.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class ImuSample:
    ax: float; ay: float; az: float       # g
    gx: float; gy: float; gz: float       # deg/s
    temp: float                           # Celsius

    @property
    def accel_mag(self) -> float:
        return math.sqrt(self.ax ** 2 + self.ay ** 2 + self.az ** 2)


class Mpu6050Imu:
    """Real MPU6050 @ 0x68 over I2C (Raspberry Pi). Requires smbus2."""

    PWR_MGMT_1 = 0x6B
    DATA_START = 0x3B  # accel(6) temp(2) gyro(6) — one 14-byte burst

    def __init__(self, bus: int = 1, address: int = 0x68):
        from smbus2 import SMBus
        self.bus = SMBus(bus)
        self.addr = address
        self.bus.write_byte_data(self.addr, self.PWR_MGMT_1, 0)  # wake up

    def read(self) -> ImuSample:
        raw = self.bus.read_i2c_block_data(self.addr, self.DATA_START, 14)

        def i16(i):
            v = (raw[i] << 8) | raw[i + 1]
            return v - 65536 if v > 32767 else v

        # default full-scale ranges: +/-2g -> 16384 LSB/g, +/-250dps -> 131
        return ImuSample(
            ax=i16(0) / 16384.0, ay=i16(2) / 16384.0, az=i16(4) / 16384.0,
            temp=i16(6) / 340.0 + 36.53,
            gx=i16(8) / 131.0, gy=i16(10) / 131.0, gz=i16(12) / 131.0,
        )

    def close(self):
        self.bus.close()


class SimImu:
    """Rest + noise, with injectable events. Call update(dt) every frame."""

    def __init__(self, seed: int | None = None, temp: float = 24.0):
        self.rng = random.Random(seed)
        self.temp = temp
        self._t = 0.0
        self._held = False
        self._shake_until = 0.0
        self._tap_at: float | None = None
        self._lift = 0.0        # transient vertical accel from pickup/putdown

    # -- event injection ----------------------------------------------------

    def pickup(self):
        self._held = True
        self._lift = 0.35       # brief upward jolt

    def put_down(self):
        self._held = False
        self._lift = -0.30

    def shake(self, duration: float = 0.8):
        self._shake_until = self._t + duration

    def tap(self):
        self._tap_at = self._t

    # -- stream -------------------------------------------------------------

    def update(self, dt: float):
        self._t += dt
        self._lift *= math.exp(-dt * 6.0)   # jolts decay fast

    def read(self) -> ImuSample:
        n = lambda s: self.rng.gauss(0, s)
        ax, ay = n(0.004), n(0.004)
        az = 1.0 + n(0.004) + self._lift
        gx, gy, gz = n(0.3), n(0.3), n(0.3)

        if self._held:  # hand tremor: slow wobble on everything
            w = self._t * 2 * math.pi
            ax += 0.03 * math.sin(w * 1.3)
            ay += 0.03 * math.sin(w * 1.7 + 1.0)
            gx += 4.0 * math.sin(w * 1.1)
            gz += 4.0 * math.sin(w * 0.9 + 2.0)

        if self._t < self._shake_until:  # violent oscillation
            w = self._t * 2 * math.pi * 6.0
            ax += 1.2 * math.sin(w)
            ay += 0.8 * math.sin(w * 1.3 + 0.7)
            gz += 180.0 * math.sin(w)

        if self._tap_at is not None:  # single sharp accel spike, |a| ~= 1g
            if self._t - self._tap_at < 0.03:
                az += 0.6
            else:
                self._tap_at = None

        return ImuSample(ax, ay, az, gx, gy, gz,
                         self.temp + self.rng.gauss(0, 0.05))

    def close(self):
        pass


def auto_imu(**kwargs):
    try:
        return Mpu6050Imu()
    except Exception:
        return SimImu(**kwargs)
