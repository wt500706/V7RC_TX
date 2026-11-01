# FLY-C3RX Shared Core V1 - ble_server.py
import bluetooth
import time
from micropython import const
from calibration import KEYS

IRQ_CONNECT = const(1)
IRQ_DISCONNECT = const(2)
IRQ_WRITE = const(3)
SERVICE = bluetooth.UUID(0x1234)
CHAR = bluetooth.UUID(0x5678)
FLAGS = bluetooth.FLAG_READ | bluetooth.FLAG_WRITE | bluetooth.FLAG_NOTIFY

class BleServer:
    def __init__(self, commands):
        self.commands = commands
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        ((self.handle,),) = self.ble.gatts_register_services(((SERVICE, ((CHAR, FLAGS),)),))
        self.ble.gatts_set_buffer(self.handle, 120, True)
        self.connections = set()
        self.inbox = []
        self.pending = []
        self.last_notify = time.ticks_ms()
        self.ble.irq(self.irq)
        self.advertise()
        print("BLE Shared V1 ready:", "Butterfly_" + commands.config()["device_name"])

    def advertise(self):
        name = ("Butterfly_" + self.commands.config()["device_name"]).encode("utf-8")
        # BLE legacy advertisement: payload must fit 31 bytes.
        name = name[:25]
        payload = bytes((2, 1, 6, len(name) + 1, 9)) + name
        self.ble.gap_advertise(100000, adv_data=payload)

    def irq(self, event, data):
        if event == IRQ_CONNECT:
            conn, _, _ = data
            self.connections.add(conn)
            print("BLE connected")
        elif event == IRQ_DISCONNECT:
            conn, _, _ = data
            self.connections.discard(conn)
            self.pending = [item for item in self.pending if item[0] != conn]
            self.commands.flight.stop()
            print("BLE disconnected")
            self.advertise()
        elif event == IRQ_WRITE:
            conn, handle = data
            if handle == self.handle and conn in self.connections:
                try:
                    message = self.ble.gatts_read(handle).decode("utf-8").strip()
                    self.inbox.append((conn, message))
                except Exception as exc:
                    print("BLE RX error:", exc)

    def notify(self, conn, message):
        try:
            if conn in self.connections:
                self.ble.gatts_notify(conn, self.handle, message.encode("utf-8"))
                if not message.startswith("V,"):
                    print("BLE TX:", message)
        except Exception as exc:
            print("BLE TX ERROR:", exc)

    def process(self, conn, message):
        print("BLE RX:", message)
        try:
            parts = message.split(",")
            cmd = parts[0]
            if cmd == "C":
                self.commands.control(int(parts[1]), int(parts[2]))
            elif cmd == "M":
                self.commands.mode("settings" if parts[1] == "1" else "flight")
                self.notify(conn, "OK,M")
            elif cmd == "G":
                # Clear stale response packets before sending a complete snapshot.
                self.pending = [p for p in self.pending if p[0] != conn]
                cfg = self.commands.config()
                for i, key in enumerate(KEYS):
                    self.pending.append((conn, "V,%d,%s" % (i, cfg[key])))
                self.pending.append((conn, "DONE"))
            elif cmd == "S":
                index = int(parts[1])
                if not 0 <= index < len(KEYS):
                    raise ValueError("index")
                self.commands.set_index(index, ",".join(parts[2:]))
                self.notify(conn, "OK,S,%d" % index)
            elif cmd == "W":
                self.commands.save()
                self.notify(conn, "OK,W")
            else:
                raise ValueError("unknown command")
        except Exception as exc:
            print("BLE command error:", exc)
            self.notify(conn, "ERR")

    def poll(self):
        if self.inbox:
            conn, message = self.inbox.pop(0)
            self.process(conn, message)
        now = time.ticks_ms()
        if self.pending and time.ticks_diff(now, self.last_notify) >= 60:
            conn, message = self.pending.pop(0)
            self.notify(conn, message)
            self.last_notify = now
