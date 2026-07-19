"""Virtual bot — the whole HAL running on your PC, no hardware needed.

    .venv\\Scripts\\python demo_bot.py

Left panel:  the bot (front view). Head moves on the simulated servos, face
             is the real eye engine, base glow is the simulated WS2812B.
Right panel: top-down radar view. Move the mouse over it = a person walking
             around the room; the bot tracks them (servo yaw + pupil gaze).

Keys:
  F           toggle person-following (on by default)
  arrows      manual yaw/pitch nudge (takes over from follow while you steer)
  Q / E       roll nudge
  N           re-center neck           R       relax servos / press again to wake
  SPACE       blink
  P / O       IMU: pick up / put down
  S / T       IMU: shake / tap
  1..8        expressions (neutral happy sad angry surprised sleepy love dizzy)
  C           clear person             ESC     quit
"""
from __future__ import annotations

import math
import pygame

from deskbot.animation.eyes import EyeController
from deskbot.hal.imu import SimImu
from deskbot.hal.led import SimLed
from deskbot.hal.radar import SimRadar
from deskbot.hal.servos import NEUTRAL, SimServos

WIN_W, WIN_H = 960, 560
BOT_PANEL = pygame.Rect(0, 0, 560, WIN_H)
RADAR_PANEL = pygame.Rect(560, 0, WIN_W - 560, WIN_H)
RADAR_RANGE_MM = 4000.0  # top-down view covers 4 m deep, +/-4 m wide

EXPR_KEYS = {
    pygame.K_1: "neutral", pygame.K_2: "happy", pygame.K_3: "sad",
    pygame.K_4: "angry", pygame.K_5: "surprised", pygame.K_6: "sleepy",
    pygame.K_7: "love", pygame.K_8: "dizzy",
}


def radar_to_screen(x_mm: float, y_mm: float) -> tuple[int, int]:
    """Sensor sits at the bottom-center of the radar panel, y goes up."""
    sx = RADAR_PANEL.centerx + x_mm / RADAR_RANGE_MM * (RADAR_PANEL.w / 2 - 10)
    sy = RADAR_PANEL.bottom - 30 - y_mm / RADAR_RANGE_MM * (RADAR_PANEL.h - 60)
    return int(sx), int(sy)


def screen_to_radar(sx: int, sy: int) -> tuple[float, float]:
    x = (sx - RADAR_PANEL.centerx) / (RADAR_PANEL.w / 2 - 10) * RADAR_RANGE_MM
    y = (RADAR_PANEL.bottom - 30 - sy) / (RADAR_PANEL.h - 60) * RADAR_RANGE_MM
    return x, max(0.0, y)


def draw_bot(screen, servos: SimServos, led: SimLed, face: pygame.Surface):
    cx = BOT_PANEL.centerx
    base_y = BOT_PANEL.bottom - 90

    # LED glow in the base
    glow = pygame.Surface((240, 240), pygame.SRCALPHA)
    r, g, b = led.color
    for rad, alpha in ((110, 25), (75, 45), (45, 80)):
        pygame.draw.circle(glow, (r, g, b, alpha), (120, 120), rad)
    screen.blit(glow, (cx - 120, base_y - 100))

    # base box + radar window slit
    pygame.draw.rect(screen, (58, 58, 66), (cx - 90, base_y, 180, 70),
                     border_radius=12)
    pygame.draw.rect(screen, (30, 30, 36), (cx - 40, base_y + 46, 80, 12),
                     border_radius=6)

    # pose -> screen: yaw = head x offset, pitch = lean (y offset + shift),
    # roll = head rotation. 90 deg = neutral everywhere.
    yaw_n = (servos.pose.yaw - NEUTRAL) / 70.0        # -1..1
    pitch_n = (servos.pose.pitch - NEUTRAL) / 40.0
    roll_deg = servos.pose.roll - NEUTRAL

    head_cx = cx + yaw_n * 120
    head_cy = base_y - 150 + pitch_n * 45

    # mid segment: trapezoid from base toward head
    top_w, bot_w = 46, 70
    pygame.draw.polygon(screen, (74, 74, 84), [
        (cx - bot_w / 2, base_y + 4),
        (cx + bot_w / 2, base_y + 4),
        (head_cx + top_w / 2, head_cy + 55),
        (head_cx - top_w / 2, head_cy + 55),
    ])

    # head: rounded box carrying the face, rotated by roll
    head = pygame.Surface((190, 130), pygame.SRCALPHA)
    pygame.draw.rect(head, (44, 44, 52), (0, 0, 190, 130), border_radius=22)
    pygame.draw.rect(head, (12, 12, 14), (17, 21, 156, 88), border_radius=8)
    head.blit(pygame.transform.smoothscale(face, (150, 82)), (20, 24))
    rotated = pygame.transform.rotozoom(head, -roll_deg, 1.0)
    screen.blit(rotated, rotated.get_rect(center=(head_cx, head_cy)))


def draw_radar(screen, targets, font):
    pygame.draw.rect(screen, (16, 20, 24), RADAR_PANEL)
    pygame.draw.line(screen, (40, 48, 56), (RADAR_PANEL.x, 0),
                     (RADAR_PANEL.x, WIN_H), 2)
    origin = radar_to_screen(0, 0)
    for rng in (1000, 2000, 3000, 4000):  # range arcs
        rad = origin[1] - radar_to_screen(0, rng)[1]
        pygame.draw.circle(screen, (34, 44, 52), origin, rad, 1)
        lbl = font.render(f"{rng // 1000}m", True, (70, 90, 100))
        screen.blit(lbl, (origin[0] + 4, origin[1] - rad - 14))
    pygame.draw.circle(screen, (90, 200, 255), origin, 5)  # the bot

    for t in targets:
        px = radar_to_screen(t.x, t.y)
        pygame.draw.circle(screen, (255, 120, 120), px, 7)
        pygame.draw.line(screen, (60, 50, 60), origin, px, 1)
        lbl = font.render(f"{t.distance / 1000:.1f}m {t.speed:+.0f}cm/s",
                          True, (200, 150, 150))
        screen.blit(lbl, (px[0] + 10, px[1] - 8))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("deskbot — virtual bot")
    font = pygame.font.SysFont("consolas", 13)
    clock = pygame.time.Clock()

    servos = SimServos()
    radar = SimRadar()
    imu = SimImu()
    led = SimLed()
    eyes = EyeController()
    led.pulse((30, 120, 140), period=4.0)  # idle teal breathing

    follow = True
    manual = [NEUTRAL, NEUTRAL, NEUTRAL]  # yaw, pitch, roll offsets base
    manual_hold = 0.0       # seconds left where manual input overrides follow
    led_idle_at = None      # when to fall back to the idle pulse
    event_msg, event_until = "", 0.0
    peak_a = 1.0            # decaying peak of |a| so spikes stay visible
    t = 0.0
    running = True

    def flash(msg: str, dur: float = 1.6):
        nonlocal event_msg, event_until
        event_msg, event_until = msg, t + dur

    while running:
        dt = clock.tick(50) / 1000.0
        t += dt

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_f:
                    follow = not follow
                    flash(f"follow {'ON' if follow else 'OFF'}")
                elif ev.key == pygame.K_SPACE:
                    eyes.blink_now()
                elif ev.key == pygame.K_r:
                    if servos.relaxed:
                        flash("servos re-engaged")
                        manual = list(servos.pose.as_tuple())
                        manual_hold = 1.0
                        servos.set_pose(*servos.pose.as_tuple())
                    else:
                        servos.relax()
                        flash("servos RELAXED (silent) — R to wake")
                elif ev.key == pygame.K_n:
                    manual = [NEUTRAL, NEUTRAL, NEUTRAL]
                    manual_hold = 2.0
                    flash("re-centered")
                elif ev.key == pygame.K_c:
                    radar.clear_person()
                elif ev.key == pygame.K_p:
                    imu.pickup()
                    eyes.set_expression("surprised")
                    flash("IMU: picked up")
                elif ev.key == pygame.K_o:
                    imu.put_down()
                    eyes.set_expression("happy")
                    flash("IMU: put down")
                elif ev.key == pygame.K_s:
                    imu.shake()
                    eyes.set_expression("dizzy")
                    led.set_color((255, 40, 20))
                    led_idle_at = t + 2.5
                    flash("IMU: SHAKEN — grumpy!")
                elif ev.key == pygame.K_t:
                    imu.tap()
                    eyes.blink_now()
                    flash("IMU: tap")
                elif ev.key in EXPR_KEYS:
                    eyes.set_expression(EXPR_KEYS[ev.key])
                    flash(f"expression: {EXPR_KEYS[ev.key]}")

        # mouse over radar panel = person; leaving the panel removes them
        mx, my = pygame.mouse.get_pos()
        if RADAR_PANEL.collidepoint(mx, my):
            radar.set_person(*screen_to_radar(mx, my))
        else:
            radar.clear_person()

        # manual nudges; touching them claims control from follow for 2 s
        keys = pygame.key.get_pressed()
        dyaw = (keys[pygame.K_LEFT] - keys[pygame.K_RIGHT]) * 60 * dt
        dpitch = (keys[pygame.K_DOWN] - keys[pygame.K_UP]) * 40 * dt
        droll = (keys[pygame.K_e] - keys[pygame.K_q]) * 50 * dt
        if dyaw or dpitch or droll:
            if manual_hold <= 0.0:  # start from where the head actually is
                manual[0], manual[1] = servos.pose.yaw, servos.pose.pitch
            manual_hold = 2.0
            manual[0] += dyaw
            manual[1] += dpitch
            manual[2] += droll
        manual_hold = max(0.0, manual_hold - dt)

        # LED falls back to the idle glow after a reaction
        if led_idle_at is not None and t >= led_idle_at:
            led.pulse((30, 120, 140), period=4.0)
            led_idle_at = None

        # ---- the mini behavior loop (a taste of Phase 2) ----
        targets = radar.read()
        yaw_t, pitch_t = manual[0], manual[1]
        if follow and targets and manual_hold <= 0.0:
            tgt = min(targets, key=lambda a: a.distance)
            yaw_t = NEUTRAL - tgt.angle          # look at the person
            # closer person = look up a bit (they are above the desk)
            pitch_t = NEUTRAL - max(0.0, (2000 - tgt.distance) / 2000) * 18
            eyes.look_at(-tgt.angle / 60 * 8, 0)
        else:
            eyes.look_at(None)
        # breathing layer on pitch, tiny always-on life
        pitch_t += math.sin(t * 2 * math.pi * 0.25) * 1.5

        if not servos.relaxed:  # while relaxed, nothing may re-engage them
            servos.set_pose(yaw_t, pitch_t, manual[2])
        for dev in (servos, radar, imu, led):
            dev.update(dt)
        sample = imu.read()
        peak_a = max(sample.accel_mag, peak_a - 1.5 * dt)

        # ---- render ----
        face_img = eyes.update(dt).convert("RGB")
        face = pygame.image.frombytes(face_img.tobytes(), face_img.size, "RGB")

        screen.fill((22, 22, 26))
        draw_bot(screen, servos, led, face)
        draw_radar(screen, targets, font)

        mode = ("RELAXED" if servos.relaxed
                else "manual" if manual_hold > 0
                else "follow" if follow else "idle")
        hud = (f"pose y{servos.pose.yaw:6.1f} p{servos.pose.pitch:6.1f} "
               f"r{servos.pose.roll:6.1f} [{mode}] "
               f"| imu |a| now {sample.accel_mag:4.2f}g peak {peak_a:4.2f}g "
               f"{sample.temp:4.1f}C | led {led.color}")
        screen.blit(font.render(hud, True, (150, 150, 160)), (10, 8))
        if t < event_until:
            big = pygame.font.SysFont("consolas", 22, bold=True)
            msg = big.render(event_msg, True, (255, 220, 120))
            screen.blit(msg, msg.get_rect(center=(BOT_PANEL.centerx, 50)))
        pygame.display.flip()

    for dev in (servos, radar, imu, led):
        dev.close()
    pygame.quit()


if __name__ == "__main__":
    main()
