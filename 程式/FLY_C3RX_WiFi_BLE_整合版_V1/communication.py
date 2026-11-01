# FLY-C3RX Shared Core V1 - communication.py
# Common API used by both transports.
from calibration import KEYS

class Commands:
    def __init__(self, calibration, flight):
        self.calibration = calibration
        self.flight = flight

    def control(self, speed, key):
        self.flight.control(speed, key)

    def mode(self, name):
        self.flight.set_mode(name)

    def config(self):
        return self.calibration.config

    def set(self, key, value):
        if self.flight.mode != "settings":
            raise ValueError("settings mode required")
        result = self.calibration.set(key, value)
        self.flight.calibration_changed(key)
        return result

    def set_index(self, index, value):
        return self.set(KEYS[index], value)

    def save(self):
        if self.flight.mode != "settings":
            raise ValueError("settings mode required")
        self.calibration.save()
