import ubluetooth
import time
import json
import gc
from micropython import const

_IRQ_SCAN_RESULT = const(5)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_NOTIFY = const(18)

SERVICE_UUID = ubluetooth.UUID(0x1234)
CHAR_UUID    = ubluetooth.UUID(0x5678)
CONFIG_FILE  = "mac_cfg.json"

class RemoteReceiver:
    def __init__(self):
        self.ble = ubluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)
        self.conn_handle = None
        self.target_mac = self._load_mac()
        self.active_key = "K33"
        self.msg = "SM000000000000#"
        self.last_rx_time = 0
        self.is_connected = False
        self.is_learning = False

    def get_key(self):

        now = time.ticks_ms()

        if self.is_connected and time.ticks_diff(now, self.last_rx_time) > 1000:

            self.active_key = "K33"

        return self.active_key

    def is_connected_now(self):

        return self.is_connected
            
    def _load_mac(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                return bytes.fromhex(json.load(f)["mac"])
        except:
            return None

    def _save_mac(self, addr):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"mac": addr.hex()}, f)
        self.target_mac = bytes(addr)

    def start(self, learning=False):

        self.is_learning = learning

        try:
            self.ble.gap_scan(None)
        except:
            pass

        self.ble.gap_scan(
            30000,
            30000,
            30000,
            True
        )

    def pairing(self):

        self.start(True)

    def get_key(self):
        now = time.ticks_ms()
        if self.is_connected and time.ticks_diff(now, self.last_rx_time) > 1000:
            self.active_key = "K33"
        return self.active_key
    
    def get_value(self):

        value = 0

        if len(self.msg) >= 15:

            if self.msg[0:2] == "SM":

                bits = self.msg[2:14]

                for i in range(12):

                    if bits[i] == "1":

                        value = value + (2 ** i)

        return value

    def _irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            adv_str = bytes(adv_data)

            if b"Remote" in adv_str or b"\x34\x12" in adv_str:
                if self.is_learning and rssi > -65:
                    self.ble.gap_scan(None)
                    self._save_mac(addr)
                    self.is_learning = False
                    self.ble.gap_connect(addr_type, addr)

                elif not self.is_learning and self.target_mac and addr == self.target_mac:
                    self.ble.gap_scan(None)
                    self.ble.gap_connect(addr_type, addr)

        elif event == _IRQ_PERIPHERAL_CONNECT:
            self.conn_handle = data[0]
            self.is_connected = True
            self.ble.gattc_discover_characteristics(self.conn_handle, 1, 65535)

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            self.is_connected = False
            self.active_key = "K33"
            self.conn_handle = None
            self.start(False)

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            if data[4] == CHAR_UUID:
                self.ble.gattc_write(data[0], data[2] + 1, b'\x01\x00', 1)

        elif event == _IRQ_GATTC_NOTIFY:
            self.last_rx_time = time.ticks_ms()

            try:
                raw = bytes(data[2])
                msg = "".join([chr(b) for b in raw if 32 <= b <= 126])
                pos = msg.rfind("SM")

                if pos != -1:
                    self.msg = msg[pos : pos+15]

                    bits = self.msg[2:14]

                    found = -1

                    for i in range(12):

                        if bits[i] == '1':

                            found = i
                            break

                    self.active_key = (
                        "K33"
                        if found == -1
                        else "K" + str(found + 1)
                    )

            except:
                pass
