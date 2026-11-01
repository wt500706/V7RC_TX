# ESP32 MicroPython - BLE Butterfly
# Independent up/down amplitude, restored K1-K4 neutral-offset controls.
import machine
import time
import math
import ble_remote

# Servo pins and individual neutral calibration
SL_PIN = 7
SR_PIN = 20
SL_BASE_ANGLE = 90.0
SR_BASE_ANGLE = 90.0

# Independent command amplitudes, relative to each servo's neutral.
# Positive wave: left increases, right decreases.
UP_ANGLE = 80.0 
DOWN_ANGLE = 40.0
ACTION_OFFSET = 10.0

MIN_HZ = 1.0
MAX_HZ = 3
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


def get_base_angles(head_up, head_down, turn_left, turn_right):
    # Original K1 > K2 > K3 > K4 priority.
    base_l = SL_BASE_ANGLE
    base_r = SR_BASE_ANGLE
    if head_up:                  # K1: pitch up
        base_l += ACTION_OFFSET
        base_r -= ACTION_OFFSET
    elif head_down:              # K2: pitch down
        base_l -= ACTION_OFFSET
        base_r += ACTION_OFFSET
    elif turn_left:              # K3: turn left
        base_l -= ACTION_OFFSET
        base_r -= ACTION_OFFSET
    elif turn_right:             # K4: turn right
        base_l += ACTION_OFFSET
        base_r += ACTION_OFFSET
    return base_l, base_r

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
head_up = False
head_down = False
turn_left = False
turn_right = False
target_hz = 0.0
current_hz = 0.0
phase = math.pi / 2.0  # neutral at startup
last_phase_time = time.ticks_ms()
last_packet_time = last_phase_time
last_data = None

while True:
    now = time.ticks_ms()
    if remote.is_connected_now():
        data = remote.get_value()
        if isinstance(data, int):
            last_packet_time = now
            head_up = bool(data & 0x01)
            head_down = bool(data & 0x02)
            turn_left = bool(data & 0x04)
            turn_right = bool(data & 0x08)
            speed = (data >> 8) & 0x0F
            target_hz = speed_to_hz(speed)
            if data != last_data:
                action = ('UP' if head_up else 'DOWN' if head_down else
                          'LEFT' if turn_left else 'RIGHT' if turn_right else 'NORMAL')
                print('Hz:{:.2f} | {}'.format(target_hz, action))
                last_data = data

    if time.ticks_diff(now, last_packet_time) > SIGNAL_TIMEOUT_MS:
        speed = 0
        target_hz = 0.0
        head_up = head_down = turn_left = turn_right = False
        last_data = None

    dt_ms = time.ticks_diff(now, last_phase_time)
    last_phase_time = now
    dt = clamp(dt_ms, 0, 100) / 1000.0
    current_hz += (target_hz - current_hz) * HZ_SMOOTH
    base_l, base_r = get_base_angles(head_up, head_down, turn_left, turn_right)

    if target_hz == 0.0 and current_hz < 0.05:
        current_hz = 0.0
        phase = math.pi / 2.0
        servo_write_angle(servo_l, base_l)
        servo_write_angle(servo_r, base_r)
        time.sleep_ms(LOOP_DELAY_MS)
        continue

    phase = (phase + 2.0 * math.pi * current_hz * dt) % (2.0 * math.pi)
    wave = math.cos(phase)
    wing_offset = wave * (UP_ANGLE if wave >= 0.0 else DOWN_ANGLE)
    servo_write_angle(servo_l, base_l + wing_offset)
    servo_write_angle(servo_r, base_r - wing_offset)
    time.sleep_ms(LOOP_DELAY_MS)
