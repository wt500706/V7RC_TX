# ESP32 MicroPython - BLE Butterfly
# Based on original working cosine flapping program.
# K1 climb / K2 descend / K3 left / K4 right (one key at a time).
import machine
import time
import math
import ble_remote

# =================================================
# User adjustable settings
# =================================================
SL_PIN = 7
SR_PIN = 20
SL_BASE_ANGLE = 90.0
SR_BASE_ANGLE = 90.0

# Normal flight: independently adjustable up/down command amplitudes
UP_ANGLE = 70.0
DOWN_ANGLE = 50.0

# Positive = increase amplitude; negative = decrease amplitude (degrees)
# K1: intended climb, both wings
K1_UP_ADJUST = 10.0
K1_DOWN_ADJUST = -10.0
# K2: intended descend, both wings
K2_UP_ADJUST = -10.0
K2_DOWN_ADJUST = 10.0
# K3: intended left turn, left wing only
K3_LEFT_UP_ADJUST = -10.0
K3_LEFT_DOWN_ADJUST = -10.0
# K4: intended right turn, right wing only
K4_RIGHT_UP_ADJUST = -10.0
K4_RIGHT_DOWN_ADJUST = -10.0

MIN_HZ = 1.0
MAX_HZ = 3.0
HZ_SMOOTH = 0.08
SIGNAL_TIMEOUT_MS = 500
LOOP_DELAY_MS = 5
PWM_MIN_US = 500
PWM_MAX_US = 2500
PWM_FREQ = 50


def clamp(value, low, high):
    return min(high, max(low, value))


def servo_angle_to_us(angle):
    angle = clamp(angle, 0.0, 180.0)
    return int(PWM_MIN_US + angle * (PWM_MAX_US - PWM_MIN_US) / 180.0)


def servo_write_angle(pwm, angle):
    us = servo_angle_to_us(angle)
    pwm.duty_u16(int(us * 65535 * PWM_FREQ / 1000000))


def speed_to_hz(speed):
    if speed <= 0:
        return 0.0
    speed = min(speed, 15)
    return MIN_HZ + (MAX_HZ - MIN_HZ) * (speed - 1) / 14.0


def get_wing_amplitudes(action):
    # Start with normal cruise settings for each wing.
    left_up = UP_ANGLE
    left_down = DOWN_ANGLE
    right_up = UP_ANGLE
    right_down = DOWN_ANGLE

    # Only ONE action applies, even when several keys are pressed.
    if action == 1:       # K1: climb
        left_up += K1_UP_ADJUST
        right_up += K1_UP_ADJUST
        left_down += K1_DOWN_ADJUST
        right_down += K1_DOWN_ADJUST
    elif action == 2:     # K2: descend
        left_up += K2_UP_ADJUST
        right_up += K2_UP_ADJUST
        left_down += K2_DOWN_ADJUST
        right_down += K2_DOWN_ADJUST
    elif action == 3:     # K3: left
        left_up += K3_LEFT_UP_ADJUST
        left_down += K3_LEFT_DOWN_ADJUST
    elif action == 4:     # K4: right
        right_up += K4_RIGHT_UP_ADJUST
        right_down += K4_RIGHT_DOWN_ADJUST

    # Amplitudes must be non-negative. Servo commands are separately clamped.
    return (max(0.0, left_up), max(0.0, left_down),
            max(0.0, right_up), max(0.0, right_down))


# =================================================
# Hardware and BLE initialization (unchanged)
# =================================================
servo_l = machine.PWM(machine.Pin(SL_PIN), freq=PWM_FREQ)
servo_r = machine.PWM(machine.Pin(SR_PIN), freq=PWM_FREQ)
servo_write_angle(servo_l, SL_BASE_ANGLE)
servo_write_angle(servo_r, SR_BASE_ANGLE)

remote = ble_remote.RemoteReceiver()
remote.start()
time.sleep(1)
print('Butterfly Cosine Independent Up/Down Ready')
print('Base L:{:.1f} R:{:.1f}'.format(SL_BASE_ANGLE, SR_BASE_ANGLE))
print('UP:{:.1f} DOWN:{:.1f} MaxHz:{:.2f}'.format(UP_ANGLE, DOWN_ANGLE, MAX_HZ))

speed = 0
action = 0  # 0=normal, 1=K1, 2=K2, 3=K3, 4=K4
target_hz = 0.0
current_hz = 0.0
phase = math.pi / 2.0
last_phase_time = time.ticks_ms()
last_packet_time = last_phase_time
last_data = None

while True:
    now = time.ticks_ms()

    if remote.is_connected_now():
        data = remote.get_value()
        if isinstance(data, int):
            last_packet_time = now
            # Fixed priority: K1 > K2 > K3 > K4; never combine actions.
            if data & 0x01:
                action = 1
            elif data & 0x02:
                action = 2
            elif data & 0x04:
                action = 3
            elif data & 0x08:
                action = 4
            else:
                action = 0

            speed = (data >> 8) & 0x0F
            target_hz = speed_to_hz(speed)
            if data != last_data:
                action_name = ('NORMAL', 'UP', 'DOWN', 'LEFT', 'RIGHT')[action]
                print('Hz:{:.2f} | {}'.format(target_hz, action_name))
                last_data = data

    if time.ticks_diff(now, last_packet_time) > SIGNAL_TIMEOUT_MS:
        speed = 0
        target_hz = 0.0
        action = 0
        last_data = None

    dt_ms = time.ticks_diff(now, last_phase_time)
    last_phase_time = now
    dt = clamp(dt_ms, 0, 100) / 1000.0
    current_hz += (target_hz - current_hz) * HZ_SMOOTH

    left_up, left_down, right_up, right_down = get_wing_amplitudes(action)

    if target_hz == 0.0 and current_hz < 0.05:
        current_hz = 0.0
        phase = math.pi / 2.0
        servo_write_angle(servo_l, SL_BASE_ANGLE)
        servo_write_angle(servo_r, SR_BASE_ANGLE)
        time.sleep_ms(LOOP_DELAY_MS)
        continue

    # Original cosine phase calculation; only the amplitude selection changes.
    phase = (phase + 2.0 * math.pi * current_hz * dt) % (2.0 * math.pi)
    wave = math.cos(phase)
    if wave >= 0.0:
        left_offset = wave * left_up
        right_offset = wave * right_up
    else:
        left_offset = wave * left_down
        right_offset = wave * right_down

    servo_write_angle(servo_l, SL_BASE_ANGLE + left_offset)
    servo_write_angle(servo_r, SR_BASE_ANGLE - right_offset)
    time.sleep_ms(LOOP_DELAY_MS)
