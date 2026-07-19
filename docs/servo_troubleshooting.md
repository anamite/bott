# Servo (direct-GPIO) troubleshooting

Notes from bringing up `deskbot/hal/gpio_servos.py` on a Raspberry Pi 5, in a
venv built on top of a miniforge/conda base Python. Check these in order if
`tools/test_servo.py` (or any `GpioServos` use) blows up.

## 1. `RuntimeError: Cannot determine SOC peripheral base address`

gpiozero fell back to the `RPi.GPIO` pin factory, which **does not support
the Pi 5** (new BCM2712 SoC, different peripheral memory layout — `RPi.GPIO`
was never updated for it). You need the `lgpio` pin factory instead; that's
gpiozero's first choice and it'll stop falling back to `RPi.GPIO` once it's
importable.

```bash
pip install lgpio
```

## 2. `pip install lgpio` fails: `swig: No such file or directory`

The `lgpio` sdist compiles a C extension via SWIG. Install the build tool:

```bash
sudo apt install swig python3-dev
pip install lgpio
```

## 3. Still fails: `/usr/bin/ld: cannot find -llgpio`

The C *library* (`liblgpio.so`) isn't on the linker path — `swig`/`gcc` can
build the wrapper but can't link it. Rather than chasing `liblgpio-dev`,
it's simpler to reuse the apt-packaged build (see step 4), since
`python3-lgpio` already ships a prebuilt `.so` for system Python.

## 4. venv doesn't see the apt-installed `python3-lgpio`

`sudo apt install python3-lgpio` installs into `/usr/lib/python3/dist-packages`
for **system** Python. A normal venv's `pyvenv.cfg` `include-system-site-packages`
flag only helps if the venv's base interpreter *is* that system Python.

Check what your venv is actually layered on:
```bash
python -c "import sys; print(sys.path)"
```
If you see `miniforge3`/`anaconda3` paths instead of `/usr/lib/python3...`,
the venv is built on conda's Python, not `/usr/bin/python3` — flipping
`include-system-site-packages` won't reach the apt package at all.

Fix: copy the two files directly into the venv's site-packages (safe as
long as the `.so`'s SOABI tag, e.g. `cpython-313-aarch64-linux-gnu`, matches
your venv's Python — check with `dpkg -L python3-lgpio` for the exact
filename):

```bash
cp /usr/lib/python3/dist-packages/lgpio.py \
   /usr/lib/python3/dist-packages/_lgpio.cpython-313-aarch64-linux-gnu.so \
   ~/botenv/lib/python3.13/site-packages/

python -c "import lgpio; print(lgpio.__file__)"   # sanity check
```

## 5. `lgpio` imports fine, but: `'can not open gpiochip'`

Permissions, not code. `/dev/gpiochip0` is owned by `root:gpio` — your user
needs to be in the `gpio` group.

```bash
groups                        # is "gpio" missing?
sudo usermod -aG gpio $USER
```

**Group membership only applies to new logins.** `usermod` doesn't affect
your current shell. Try in order:

```bash
newgrp gpio     # quickest — new subshell with the group applied
groups          # confirm "gpio" now shows up
```

If `newgrp` doesn't stick (can happen over some SSH/IDE setups), fully log
out and back in. If it *still* doesn't show after a fresh login, reboot —
that always clears it.

## Working end state

Once `groups` shows `gpio` and `python -c "import lgpio"` succeeds with no
warnings, `tools/test_servo.py` should drive the servo with no fallback
warnings printed.
