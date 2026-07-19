# Running the eyes on the real OLED (Raspberry Pi)

## 1. Wiring (4 jumper wires, Pi power OFF while connecting)

| OLED pin | Raspberry Pi pin | Notes |
|---|---|---|
| VCC | Pin 1 (3.3V) | 3.3V is the safe choice; do NOT use 5V unless the module explicitly says 5V-tolerant |
| GND | Pin 6 (GND) | any GND pin works |
| SCK (= SCL) | Pin 5 (GPIO 3 / SCL) | I2C clock |
| SDA | Pin 3 (GPIO 2 / SDA) | I2C data |

Pin numbering: with the Pi's USB ports facing you and the GPIO header top-right,
pin 1 is the corner pin nearest the SD card slot (it has a square solder pad).
Odd pins are the inner row: 1, 3, 5 are the first three inner-row pins — so
VCC, SDA, SCK end up on three neighboring pins, GND one pin further out.

## 2. Enable I2C and speed it up

```bash
sudo raspi-config          # Interface Options -> I2C -> enable
```

Then raise the I2C clock or the animation will feel like a slideshow
(default 100 kHz ≈ 5 fps, 400 kHz ≈ 20+ fps). Edit the boot config:

```bash
sudo nano /boot/firmware/config.txt      # older OS: /boot/config.txt
```

Find the line `dtparam=i2c_arm=on` and change/extend it to:

```
dtparam=i2c_arm=on,i2c_arm_baudrate=400000
```

Reboot, then verify the display is detected:

```bash
sudo reboot
sudo apt install -y i2c-tools
i2cdetect -y 1
```

You should see `3c` in the grid. If you see `3d`, pass `--address 0x3D` to the
test script. If the grid is empty, re-check wiring (SDA/SCK swapped is the
usual culprit).

## 3. Install Python deps

```bash
sudo apt install -y python3-pip python3-venv libopenjp2-7
cd ~
python3 -m venv botenv
source botenv/bin/activate
pip install luma.oled pillow
```

## 4. Copy the project to the Pi

From the Windows laptop (PowerShell), with the Pi on the same network:

```powershell
scp -r "C:\Users\anand\CLAWD Folder\Bot_hard" pi@raspberrypi.local:~/Bot_hard
```

(replace `pi` / `raspberrypi.local` with your username / Pi's address; a USB
stick works just as well. The `.venv` folder does not need to be copied.)

## 5. Run it

```bash
cd ~/Bot_hard
source ~/botenv/bin/activate
python test_oled.py            # auto-cycles everything, prints fps
python test_oled.py --list     # see all names
python test_oled.py hearts     # hold one animation
```

## Troubleshooting

- **Image wraps / is shifted 2 px / has noise columns at the edges** — your
  panel is an SSD1306, not SH1106: run `python test_oled.py --driver ssd1306`.
  (1.3" panels are usually SH1106; 0.96" are usually SSD1306.)
- **`No such device` / OSError on start** — I2C not enabled or wrong address;
  re-run `i2cdetect -y 1`.
- **Choppy animation** — baudrate line from step 2 missing, or still 100000.
- **Display glitches when servos run later** — power dip; that's why the
  servos get their own 5V supply (see PLAN.md).
- **`i2cdetect: command not found`** — the `i2c-tools` package isn't
  installed:
  ```bash
  sudo apt update && sudo apt install -y i2c-tools
  ```
- **`PermissionError: [Errno 13] Permission denied: '/dev/i2c-1'`** — your
  user isn't in the `i2c` group yet, so it can't open the I2C device node:
  ```bash
  sudo usermod -aG i2c $USER
  sudo reboot     # group membership only takes effect after a fresh login
  ```
  After the reboot, re-activate the venv and re-run `python test_oled.py` —
  no `sudo` needed. (In a pinch, `sudo ~/botenv/bin/python test_oled.py`
  works immediately without a reboot, but fixing group membership is the
  permanent solution.)
