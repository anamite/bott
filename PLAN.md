# Desk Bot — Complete Build Plan

A small 3-DOF desk companion with a face, that notices people, has moods, and never looks scripted.

---

## 1. Hardware inventory & what each part is for

| Part | Likely exact model | Role in the bot |
|---|---|---|
| 3x 9g micro servos | SG90 / MG90S, 180° | 3-DOF neck: **base yaw** (left/right), **mid pitch** (lean forward/back), **head roll/nod** (tilt) |
| 1.3" mono OLED | SH1106, 128x64, I2C | The face — procedurally drawn eyes (not sprite loops) |
| mmWave radar (x,y tracking) | HLK-LD2450 (UART) — gives up to 3 human targets as (x, y, velocity) | The bot's "peripheral vision": who is near, where, approaching/leaving |
| Gyro + accel + temp | MPU6050 (I2C) | Detects being picked up, shaken, tapped, table bumps; temp adds ambient flavor |
| 1x WS2812B LED | single addressable RGB | Mood light (diffused inside body or as a "heart") |
| Compute (later) | Raspberry Pi (+ 5MP cam, Phase 6) | Runs everything in Python |

**Verify early:** confirm the radar is an LD2450 (x,y multi-target) vs LD2410 (distance+presence only). The whole "gaze tracking" feature depends on getting x,y coordinates. Also confirm OLED driver chip (SH1106 vs SSD1306 — different libraries/offsets).

### Wiring / power (matters more than it seems)
- **Servos must NOT be powered from the Pi's 5V pin.** 3 stalled SG90s can pull >2A and brown-out the Pi. Use a separate 5V 3A supply (or a buck from a single 5V/4A brick), **common ground** with the Pi.
- Servo signals: either 3 GPIO pins with `pigpio` hardware-timed PWM (fine for 3 servos), or a PCA9685 board (~$2) for jitter-free PWM. Recommended: **PCA9685** — I2C, shares the bus with OLED+MPU6050, zero servo jitter.
- I2C bus: OLED (0x3C), MPU6050 (0x68), PCA9685 (0x40) — all coexist fine.
- LD2450: UART @ 256000 baud → Pi's `/dev/serial0`.
- WS2812B: Pi's SPI or PWM pin via `rpi_ws281x` / `neopixel` lib (single LED is easy).
- Add a 470–1000µF cap across servo power rail; servos cause voltage dips that glitch the OLED otherwise.

---

## 2. Mechanical design (3D printed)

Matches your sketch: stacked segments, each rotated by one servo.

1. **Base box** — houses Pi (or cable to Pi), radar module facing forward through a plastic-safe window (mmWave passes through PLA ≤2mm — no hole needed, keep metal/wires out of the beam path), WS2812B diffused behind a thin printed panel. Base servo mounted horizontally, output shaft up → yaw.
2. **Mid segment** — sits on base servo horn. Contains servo #2 mounted sideways, shaft horizontal → pitch (lean). Route wires through a center channel with slack loop for rotation.
3. **Head** — on servo #3 (roll or nod — pick **nod** if you want "yes" gestures and looking up at a standing person; pick **roll** for cuter head-tilts; **recommendation: roll** — head-tilt is the single most charming motion a desk bot can do, and pitch already covers up/down via the mid segment). Head carries OLED (face) and MPU6050 (mounted here so it feels head motion + pickup).

Design notes:
- Keep the head light — OLED + MPU only. Heavy heads make 9g servos hum, overheat, and jitter at hold.
- Design servo pockets to friction-fit SG90 body (22.5 x 12.2 x 26.5mm typical, but measure yours) with screw bosses.
- Give every joint a mechanical end-stop consideration: define safe angle ranges in software (e.g., yaw 20°–160°) so a bug can't grind a servo into the frame.
- Print a **calibration jig pose**: all joints at 90° = bot looking straight ahead. Assemble horns at that pose.
- Wire channel: leave a 6–8mm channel through the neck; use 28AWG silicone wire for everything crossing joints.

Tools: design in Fusion 360 / Onshape / even Tinkercad. PLA is fine; PETG for the servo brackets if they get warm.

---

## 3. Software architecture (the important part)

Python on the Pi, organized as **five layers with a message bus in the middle**. Every layer is independently testable and replaceable.

```
┌─────────────────────────────────────────────────────┐
│  API layer:  FastAPI (REST) + WebSocket + MQTT(opt) │
├─────────────────────────────────────────────────────┤
│  Behavior engine:  mood model + action selection    │
├──────────────────────┬──────────────────────────────┤
│  Perception          │  Animation/Motion            │
│  (sensor fusion,     │  (procedural eyes, servo     │
│   event detection,   │   easing, layered motion)    │
│   ML classifier)     │                              │
├──────────────────────┴──────────────────────────────┤
│  HAL / drivers: servos, OLED, radar, IMU, LED       │
└─────────────────────────────────────────────────────┘
        internal event bus (asyncio queues)
```

### 3.1 HAL (hardware abstraction layer)
One module per device, each with a **simulator twin** so you can develop the whole personality on your PC before the bot exists:
- `hal/servos.py` — `set_pose(yaw, pitch, roll)` in degrees, clamped to safe ranges. PCA9685 backend + a matplotlib/pygame "virtual bot" backend.
- `hal/display.py` — hands the face renderer a 128x64 framebuffer (`luma.oled` for SH1106; pygame window in sim).
- `hal/radar.py` — parses LD2450 UART frames → list of `Target(x_mm, y_mm, speed, distance)`.
- `hal/imu.py` — MPU6050 @ 100Hz → accel/gyro/temp.
- `hal/led.py` — `set_color(rgb)`, `pulse(rgb, period)`.

### 3.2 Perception layer
Turns raw streams into **events** and **continuous signals** on the bus.

Continuous signals (published ~10–20Hz):
- `person.position` (x, y from radar, smoothed with a one-euro filter or simple EMA)
- `person.count`, `person.nearest_distance`, `person.approach_speed`
- `motion.self` (is the bot itself moving — from IMU, needed to ignore radar noise while the head moves)
- `ambient.temperature`

Discrete events (edge-triggered, debounced):
- `person.arrived` / `person.left` / `person.settled` (sat down nearby)
- `person.approaching_fast` (someone walking straight at the desk)
- `bot.picked_up` (accel magnitude departs from 1g), `bot.put_down`, `bot.shaken`, `bot.tapped` (high-freq accel spike), `table.bumped` (spike while |a|≈1g)
- `time.morning` / `time.night` etc. (circadian events)

### 3.3 Behavior engine — how it feels *alive* and not hard-coded
This is the core of your request. Three mechanisms, stacked:

**A. Mood state, not scripted reactions.**
The bot has a continuous 2D emotional state — **valence** (happy↔grumpy) and **arousal** (excited↔sleepy) — both floats in [-1, 1] that **decay toward a personality baseline** over minutes. Events don't trigger animations directly; they *push the mood vector*:
- person arrives → arousal +0.4, valence +0.3
- shaken → arousal +0.8, valence −0.5
- alone for 30 min → arousal drifts to −0.6 (drowsy)
- night time → baseline arousal lowered (circadian)

Everything visible — eye shape, blink rate, motion speed, idle posture, LED color — is a **function of the current mood vector**. Same event at different moods = different-looking reaction, for free. This is the #1 trick that kills the "canned animation" feel.

**B. Utility-based action selection with habituation.**
A small scheduler scores candidate behaviors every tick: `score = base_desire(mood, signals) + noise − habituation`. Highest scorer wins.
- **Habituation**: every time a behavior runs, its score is suppressed and recovers over ~minutes. Wave at it 5 times → 5 escalating-then-bored responses, not 5 identical ones. This is also biologically honest and reads as personality.
- **Noise**: small random utility jitter so ties break differently each time.
- Reactions are *interruptible*: a `picked_up` event preempts anything.

**C. Procedural animation, never fixed keyframes.**
- **Layered motion**: final servo pose = `base_posture(mood)` + `breathing(sine, 0.2–0.3Hz, amplitude ∝ arousal)` + `gaze(look-at person)` + `reaction overlay` + `micro-noise (Perlin)`. The bot literally never sits perfectly still — like breathing, it's subtle but the difference between "device" and "creature".
- **Gaze**: radar gives person (x,y) → `atan2` → yaw target; distance → pitch (look up when close). Add **saccades**: gaze jumps in quick steps with tiny overshoot, plus occasional random glances away. Smooth-only tracking looks robotic; saccadic tracking looks sentient.
- **Eyes are parametric, not sprites**: each eye = rounded-rect/ellipse with parameters (height, width, top-lid angle, bottom-lid, pupil offset). Mood maps to parameters continuously — infinite in-between expressions. Blink = timed lid animation with randomized interval (2–8s, faster when aroused, slow heavy blinks when sleepy) and occasional double-blinks. Pupils track the person too (micro gaze inside the screen — huge lifelike payoff, zero extra hardware).
- **Easing everywhere**: all servo moves through an easing function (ease-out for glances, ease-in-out for postures, overshoot+settle for surprised). A tiny tween engine (~50 lines) covers this.

**Behavior library (each is a parameterized *family*, mood-modulated):**
| Behavior | Trigger | What happens |
|---|---|---|
| Idle-alive | always-on base layer | breathing, micro-drift, blinks, occasional look-around, sighs |
| Notice | person.arrived | perk up (arousal spike), snap gaze to them, eyes widen |
| Track | person present | lazy or eager gaze-following depending on arousal |
| Greet | person.settled + high valence | happy eyes, head-tilt wiggle, LED warm pulse |
| Startle | approaching_fast / table.bump / loud shake | flinch back (pitch), wide eyes, then settle |
| Grumpy | shaken / repeatedly poked | narrowed eyes, turns *away* from person, cold LED |
| Sleepy | low arousal | head droops in stages, slow blinks, eventually "sleeps" (eyes closed, dim breathing LED); wakes on events |
| Curious | new radar pattern / after boredom | slow scan of the room, head tilts |
| Airborne | picked_up | eyes wide, gaze "down", LED alert; relief wiggle on put_down |
| Sneeze/quirks | rare random (Poisson) | one-off charm animations, mood-gated |

### 3.4 The ML piece (kept honest and doable)
Skip heavyweight models; two small, genuinely useful ones:

1. **Radar track classifier** (Phase 5): window of 2–3s of (x, y, v) → classes like `walk_by`, `approach`, `leave`, `loiter`, `hand_wave_over_desk`. Collect labeled data with a logging script (press a key = label). Train **scikit-learn RandomForest or a tiny 1D-CNN** on ~15 features (path curvature, mean/var of speed, heading change...). Runs in microseconds on a Pi. Now the bot distinguishes "someone walked past" from "someone came to see me" — that's the behavior that makes visitors say "wait, did it just...?"
2. **Person-signature (stretch)**: cluster approach trajectories + typical times → "this is probably the usual human" vs "new person" → familiar vs shy greeting.

Explicitly *not* recommended on this hardware for v1: speech, LLM-in-the-loop for reflexes (latency kills liveliness — though an optional cloud call for a rare "daily thought" shown on the face is a fun add-on).

### 3.5 API layer (control + live data out)
FastAPI app running alongside:
- `GET /state` — mood vector, current behavior, pose, person targets, temp, uptime
- `GET /events` + **WebSocket `/ws`** — live event/telemetry stream (drives any external dashboard, home automation, OBS overlay...)
- `POST /trigger/{behavior}` — force any behavior family (`greet`, `sleep`, `startle`, ...) with optional intensity param
- `POST /mood` — nudge or set valence/arousal
- `POST /say` — show text/expression on the face for N seconds
- `POST /led` — override LED
- `GET /config` / `PATCH /config` — personality baseline, servo limits, behavior weights — **all tunables live in one `personality.yaml`**, hot-reloadable
- Optional: MQTT publish (`deskbot/state`, `deskbot/events`) for Home Assistant integration.

### 3.6 Tech stack summary
- Python 3.11+, `asyncio` throughout (one process, tasks per layer, `asyncio.Queue` bus)
- `luma.oled` + PIL (face), `smbus2` (I2C), `pyserial` (radar), `adafruit-pca9685`, `rpi_ws281x`, `numpy`, `scikit-learn`, `fastapi`+`uvicorn`
- `personality.yaml` for every magic number — tune the character without touching code
- Repo layout:
```
deskbot/
  hal/            # drivers + simulators
  perception/     # fusion, events, ml/
  behavior/       # mood.py, selector.py, behaviors/
  animation/      # tween.py, layers.py, eyes.py
  api/            # server.py, schemas.py
  main.py         # wires the bus, starts tasks
  personality.yaml
tools/            # calibration, radar visualizer, data logger
cad/              # printable files
```

---

## 4. Build phases (each ends with something that works)

**Phase 0 — Bench validation (no printing yet)**
Breadboard everything to the Pi. Small scripts: sweep each servo, draw on OLED, print radar targets live (build a little matplotlib x,y scatter — you'll need this visualizer forever), stream IMU, light the LED. *Confirms exact part models and pinout; kills 90% of later mystery bugs.*

**Phase 1 — Body + face**
Print base/mid/head, assemble at 90° calibration pose. Implement HAL + safe-range clamping + tween engine. Implement parametric eyes with blink. Milestone: *bot sits on desk, breathes, blinks, looks around randomly. Already cute.*

**Phase 2 — Senses + gaze**
Radar and IMU into the perception layer, event detection, look-at with saccades, pupil tracking, startle/pickup reactions. Milestone: *it watches you walk around the room and flinches when you bump the table.*

**Phase 3 — Personality**
Mood model, utility selector, habituation, circadian rhythm, full behavior library, LED-as-mood. Tune `personality.yaml` for a week. Milestone: *it has good days and bad days.*

**Phase 4 — API**
FastAPI + WebSocket + triggers + config endpoints. Simple web dashboard (single HTML page hitting `/ws`) showing mood, radar plot, event log. Milestone: *curl makes it wave; dashboard shows its inner life.*

**Phase 5 — ML**
Data logger → label sessions → train track classifier → new events (`walk_by`, `approach`, `wave`) feed the behavior engine. Milestone: *it ignores passers-by but perks up for visitors.*

**Phase 6 — Camera (later, as you said)**
5MP Pi cam in the head: face *detection* first (gaze correction — look at your face, not your torso), then optional face recognition for per-person moods, motion-based "what are you holding" curiosity. Radar remains primary (works in dark, cheap on CPU); camera activates only when radar says someone is close — good for CPU and privacy.

---

## 5. Known risks / gotchas
- **9g servo hold-jitter**: SG90s buzz when holding load. Mitigate: light head, PCA9685, and *detach/relax* servos during long sleep states (also silent = more lifelike sleep).
- **Radar behind the head motion**: mount radar in the static base, not the moving head, or tracking eats itself.
- **MPU6050 on a moving head** sees servo motion as "events" — gate IMU event detection with "is a servo currently commanded" (the `motion.self` signal).
- **OLED burn-in**: shift the face by ±2px slowly; blank in sleep.
- **Radar multipath** on a cluttered desk gives ghost targets — require target persistence (N consecutive frames) before `person.arrived`.
- **Pi choice**: Pi Zero 2 W is enough for everything through Phase 5; Pi 4/5 needed once the camera does recognition.

---

## 6. What "best result" looks like
A creature, not a gadget: it breathes, gets bored, notices you before you say anything, sulks when shaken, falls asleep at night, greets the person it knows — and every one of those is emergent from ~4 numbers (valence, arousal, habituation, noise) modulating parameterized motion, which is why it never repeats itself exactly. Plus a clean HTTP/WebSocket surface so it doubles as a desk-presence sensor for anything else you build.
