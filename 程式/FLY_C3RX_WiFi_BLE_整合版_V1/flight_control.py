# FLY-C3RX Shared Core V1 - flight_control.py
import math
import time
from machine import Pin, PWM

TIMEOUT_MS = 500

class FlightControl:
    def __init__(self, calibration):
        self.cfg = calibration.config
        self.left = PWM(Pin(7), freq=50)
        self.right = PWM(Pin(10), freq=50)
        self.mode = "flight"
        self.speed = 0
        self.key = 0
        self.last_seen = time.ticks_ms()
        self.last_step = self.last_seen
        self.phase = 0.0
        self.hz = 0.0
        self.amp = 0.0
        self._write_centers()

    @staticmethod
    def _servo(pwm, angle):
        angle = max(0, min(180, angle))
        pwm.duty_u16(int((500 + angle * 2000 / 180) * 65535 / 20000))

    def _write_centers(self):
        self._servo(self.left, self.cfg["left_center"])
        self._servo(self.right, self.cfg["right_center"])

    def _offsets(self, key):
        def pair(n):
            return (self.cfg["k%d_up" % n], self.cfg["k%d_down" % n])
        if 1 <= key <= 4:
            return pair(key)
        combos = {5: (1, 3), 6: (2, 3), 7: (1, 4), 8: (2, 4)}
        if key in combos:
            a, b = combos[key]
            x, y = pair(a)
            z, w = pair(b)
            return x + z, y + w
        return 0, 0

    def control(self, speed, key):
        if self.mode != "flight":
            return
        self.speed = max(0, min(15, int(speed)))
        self.key = max(0, min(8, int(key)))
        self.last_seen = time.ticks_ms()

    def stop(self):
        self.speed = 0
        self.key = 0
        self.hz = 0.0
        self.amp = 0.0
        self.phase = 0.0
        self._write_centers()

    def set_mode(self, mode):
        if mode not in ("flight", "settings"):
            raise ValueError("invalid mode")
        self.mode = mode
        self.stop()
        self.last_seen = time.ticks_ms()

    def calibration_changed(self, key):
        if self.mode == "settings" and key != "device_name":
            # In settings all servo movements stop; center adjustments act immediately.
            self._write_centers()

    def update(self):
        now = time.ticks_ms()
        dt_ms = max(0, min(100, time.ticks_diff(now, self.last_step)))
        self.last_step = now
        if dt_ms == 0:
            return
        if self.mode == "settings":
            return
        active = time.ticks_diff(now, self.last_seen) <= TIMEOUT_MS
        s = self.speed if active else 0
        k = self.key if active else 0
        target = (self.cfg["min_hz"] + (self.cfg["max_hz"] - self.cfg["min_hz"]) * (s - 1) / 14) if s else 0.0
        alpha = 1 - math.exp(-dt_ms / 180.0)
        self.hz += (target - self.hz) * alpha
        self.amp += ((1.0 if s else 0.0) - self.amp) * alpha
        if self.amp < 0.001 and not s:
            self.amp = 0.0
            self.hz = 0.0
            self.phase = 0.0
        else:
            self.phase = (self.phase + 2 * math.pi * self.hz * dt_ms / 1000) % (2 * math.pi)
        wave = math.sin(self.phase)
        # Physical upstroke is the negative half-cycle on this mechanism.
        # The two calibration values define a total excursion; flight uses
        # the midpoint amplitude for equal up/down strokes.
        amplitude = (self.cfg["up_angle"] + self.cfg["down_angle"]) / 2.0
        # Shift the moving midpoint without changing the stationary neutral.
        # For UP=20, DOWN=60: left moving center = 90+20 = 110,
        # right moving center = 90-20 = 70 (mirrored servos).
        shift = (self.cfg["down_angle"] - self.cfg["up_angle"]) / 2.0
        flap = wave * amplitude
        dl, dr = self._offsets(k)
        # Fade between the stationary neutral and the moving midpoint.
        self._servo(self.left, self.cfg["left_center"] + dl + (shift + flap) * self.amp)
        self._servo(self.right, self.cfg["right_center"] + dr - (shift + flap) * self.amp)
