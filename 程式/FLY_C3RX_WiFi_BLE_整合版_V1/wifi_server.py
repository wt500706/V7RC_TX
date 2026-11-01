# FLY-C3RX Shared Core V1 - wifi_server.py
import network
import socket
import json
import time
import gc

def decode(s):
    out = bytearray()
    i = 0
    while i < len(s):
        if s[i] == 37 and i + 2 < len(s):
            try:
                out.append(int(s[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.append(32 if s[i] == 43 else s[i])
        i += 1
    return out.decode("utf-8")

def query(path):
    result = {}
    if b"?" not in path:
        return result
    for part in path.split(b"?", 1)[1].split(b"&"):
        if b"=" in part:
            k, v = part.split(b"=", 1)
            result[decode(k)] = decode(v)
    return result

def respond(client, content, content_type="application/json", code="200 OK"):
    if isinstance(content, str):
        content = content.encode("utf-8")
    head = ("HTTP/1.1 " + code + "\\r\\nContent-Type: " + content_type +
            "; charset=utf-8\\r\\nCache-Control: no-store\\r\\nConnection: close\\r\\nContent-Length: " +
            str(len(content)) + "\\r\\n\\r\\n").encode()
    client.write(head)
    for i in range(0, len(content), 512):
        client.write(content[i:i + 512])

class WifiServer:
    def __init__(self, commands):
        self.commands = commands
        self.ap = network.WLAN(network.AP_IF)
        self.ap.active(False)
        time.sleep_ms(300)
        self.ap.config(essid="Butterfly_" + commands.config()["device_name"], authmode=0, channel=6)
        self.ap.active(True)
        time.sleep_ms(800)
        self.ssid = self.ap.config("essid")
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("0.0.0.0", 80))
        self.server.listen(2)
        self.server.settimeout(0.01)
        print("Wi-Fi Shared V1:", self.ssid, self.ap.ifconfig()[0])

    def poll(self):
        try:
            client, addr = self.server.accept()
        except OSError:
            return
        try:
            client.settimeout(0.5)
            raw = client.recv(1024)
            if not raw:
                return
            line = raw.split(b"\\r\\n", 1)[0].split(b" ")
            if len(line) < 2:
                return
            path = line[1]
            if path == b"/" or path.startswith(b"/?"):
                with open("wifi_page.html", "rb") as f:
                    content = f.read()
                respond(client, content, "text/html")
            elif path.startswith(b"/control?"):
                q = query(path)
                self.commands.control(q.get("s", "0"), q.get("k", "0"))
                respond(client, "OK", "text/plain")
            elif path.startswith(b"/mode?"):
                mode = query(path).get("value", "")
                self.commands.mode(mode)
                respond(client, json.dumps({"ok": True, "mode": mode}))
            elif path == b"/config":
                respond(client, json.dumps({"id": self.ssid, "config": self.commands.config()}))
            elif path.startswith(b"/set?"):
                q = query(path)
                value = self.commands.set(q.get("key", ""), q.get("value", ""))
                respond(client, json.dumps({"ok": True, "value": value}))
            elif path == b"/save":
                self.commands.save()
                respond(client, json.dumps({"ok": True}))
            else:
                respond(client, "Not found", "text/plain", "404 Not Found")
        except Exception as exc:
            print("Wi-Fi request error:", exc)
            try:
                respond(client, json.dumps({"ok": False, "error": str(exc)}), code="400 Bad Request")
            except Exception:
                pass
        finally:
            try:
                client.close()
            except Exception:
                pass
            if gc.mem_free() < 12000:
                gc.collect()
