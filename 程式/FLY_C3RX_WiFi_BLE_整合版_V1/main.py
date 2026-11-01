# FLY-C3RX Shared Core V1
# Select exactly one mode: "wifi" or "ble". Reboot after changing.
TRANSPORT = "ble"

import time
from calibration import Calibration
from flight_control import FlightControl
from communication import Commands

calibration = Calibration()
flight = FlightControl(calibration)
commands = Commands(calibration, flight)

if TRANSPORT == "wifi":
    from wifi_server import WifiServer
    transport = WifiServer(commands)
elif TRANSPORT == "ble":
    from ble_server import BleServer
    transport = BleServer(commands)
else:
    raise ValueError("TRANSPORT must be wifi or ble")

print("FLY-C3RX Shared Core V1", TRANSPORT)
while True:
    transport.poll()
    flight.update()
    time.sleep_ms(10)
