# FLY-C3RX Shared Core V1 - calibration.py
import json
import os

CONFIG_FILE = "butterfly_cfg.json"
# The order is a protocol contract. Never use list(DEFAULT) for BLE indices.
KEYS = (
    "device_name", "left_center", "right_center", "up_angle",
    "down_angle", "min_hz", "max_hz",
    "k1_up", "k1_down", "k2_up", "k2_down",
    "k3_up", "k3_down", "k4_up", "k4_down"
)
DEFAULT = {
    "device_name": "Test",
    "left_center": 90, "right_center": 90,
    "up_angle": 20, "down_angle": 60,
    "min_hz": 1.0, "max_hz": 3.0,
    "k1_up": 10, "k1_down": -10,
    "k2_up": -10, "k2_down": 10,
    "k3_up": -10, "k3_down": -10,
    "k4_up": 10, "k4_down": 10
}

def validate(key, value):
    if key not in DEFAULT:
        raise ValueError("unknown key")
    if key == "device_name":
        value = str(value).strip()
        if not value or len(value.encode("utf-8")) > 20:
            raise ValueError("invalid name")
        return value
    if key in ("min_hz", "max_hz"):
        value = float(value)
        low, high = 0.1, 5.0
    else:
        value = int(value)
        if key in ("left_center", "right_center"):
            low, high = 20, 160
        elif key in ("up_angle", "down_angle"):
            low, high = 0, 90
        else:
            low, high = -40, 40
    if not low <= value <= high:
        raise ValueError("out of range")
    return value

def servo_angle_limits(cfg):
    """Return the full possible angle range of each servo for K0-K8."""
    combos = {5: (1, 3), 6: (2, 3), 7: (1, 4), 8: (2, 4)}
    left_offsets = [0]
    right_offsets = [0]
    for k in range(1, 9):
        keys = combos.get(k, (k,))
        left_offsets.append(sum(cfg["k%d_up" % n] for n in keys))
        right_offsets.append(sum(cfg["k%d_down" % n] for n in keys))
    # Left moving midpoint = center + (down-up)/2;
    # right midpoint is mirrored. Flap amplitude = (up+down)/2.
    # Therefore left extremes = center-up, center+down;
    # right extremes = center-down, center+up.
    # Include stopped neutral (amplitude ramps from zero to full).
    up = cfg["up_angle"]
    down = cfg["down_angle"]
    return (
        (cfg["left_center"] + min(left_offsets) - up,
         cfg["left_center"] + max(left_offsets) + down),
        (cfg["right_center"] + min(right_offsets) - down,
         cfg["right_center"] + max(right_offsets) + up)
    )

def check(cfg):
    for key in KEYS:
        validate(key, cfg[key])
    if cfg["min_hz"] > cfg["max_hz"]:
        raise ValueError("min_hz > max_hz")
    left, right = servo_angle_limits(cfg)
    if left[0] < 0 or left[1] > 180:
        raise ValueError("left servo total angle outside 0..180: %s" % (left,))
    if right[0] < 0 or right[1] > 180:
        raise ValueError("right servo total angle outside 0..180: %s" % (right,))

class Calibration:
    def __init__(self):
        self.config = DEFAULT.copy()
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                candidate = self.config.copy()
                for key in KEYS:
                    if key in saved:
                        candidate[key] = validate(key, saved[key])
                check(candidate)
                self.config = candidate
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print("Config defaults or previous valid config used:", exc)
        try:
            os.stat(CONFIG_FILE)
        except OSError:
            self.save()  # First boot: create file immediately.

    def set(self, key, value):
        value = validate(key, value)
        candidate = self.config.copy()
        candidate[key] = value
        check(candidate)
        self.config[key] = value
        return value

    def save(self):
        check(self.config)
        temp = CONFIG_FILE + ".tmp"
        with open(temp, "w") as f:
            json.dump(self.config, f)
            f.flush()
        try:
            os.remove(CONFIG_FILE)
        except OSError:
            pass
        os.rename(temp, CONFIG_FILE)
