
import network
import espnow
import time


class RemoteReceiver:

    def __init__(self, remote_id=1):

        try:
            remote_id = int(remote_id)
        except:
            remote_id = 1

        if remote_id < 1:
            remote_id = 1

        if remote_id > 12:
            remote_id = 12

        self.group = "S{:02d}".format(remote_id)

        self._bits = "000000000000"
        self._value = 0

        self._last_rx = None
        self._timeout = 500

        self._sta = network.WLAN(network.STA_IF)
        self._sta.active(True)
        self._sta.disconnect()

        self._esp = espnow.ESPNow()
        self._esp.active(True)


    def _update(self):

        while True:

            try:
                host, msg = self._esp.irecv(0)
            except:
                return

            if not msg:
                return

            try:
                text = msg.decode()
            except:
                continue

            if len(text) != 16:
                continue

            if text[0:3] != self.group:
                continue

            if text[15] != "#":
                continue

            bits = text[3:15]

            if any(b not in "01" for b in bits):
                continue

            self._bits = bits
            self._value = self._bits_to_value(bits)
            self._last_rx = time.ticks_ms()


    def _bits_to_value(self, bits):

        value = 0

        for i, bit in enumerate(bits):

            if bit == "1":
                value |= 1 << i

        return value


    def is_connected(self):

        self._update()

        if self._last_rx is None:
            return False

        return (
            time.ticks_diff(
                time.ticks_ms(),
                self._last_rx
            ) < self._timeout
        )


    def get_keys(self):

        self._update()
        return self._bits


    def get_key(self):

        self._update()

        for i in range(12):

            if self._bits[i] == "1":
                return "K" + str(i + 1)

        return "K33"


    def get_value(self):

        self._update()
        return self._value
