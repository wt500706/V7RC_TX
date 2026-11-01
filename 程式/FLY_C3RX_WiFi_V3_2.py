# FLY-C3RX Wi-Fi V3: 8 directions + config page; MicroPython ESP32-C3
# Wi-Fi receiver + calibrated dual-servo flapping control
import network
import socket
import time
import gc
import json
import os
import math
from machine import Pin, PWM

CONFIG_FILE = 'butterfly_cfg.json'
TIMEOUT_MS = 500
AP_CHANNEL = 6
DEFAULT = {
    'device_name': 'Test',
    'left_center': 90, 'right_center': 90,
    'up_angle': 40, 'down_angle': 55,
    'min_hz': 0.5, 'max_hz': 2.5,
    'k1_up': 10, 'k1_down': -10,
    'k2_up': -10, 'k2_down': 10,
    'k3_up': -10, 'k3_down': -10,
    'k4_up': 10, 'k4_down': 10
}

def load_config():
    cfg = DEFAULT.copy()
    try:
        with open(CONFIG_FILE, 'r') as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            for key in DEFAULT:
                if key in saved:
                    cfg[key] = saved[key]
    except (OSError, ValueError):
        pass
    return cfg

config = load_config()
if CONFIG_FILE not in os.listdir():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def valid(key, value):
    if key not in DEFAULT:
        raise ValueError('unknown parameter')
    if key == 'device_name':
        value = value.strip()
        if not value or len(value.encode('utf-8')) > 20:
            raise ValueError('invalid name')
        return value
    v = float(value) if key in ('min_hz', 'max_hz') else int(value)
    if key in ('left_center', 'right_center'):
        lo, hi = 20, 160
    elif key in ('up_angle', 'down_angle'):
        lo, hi = 0, 90
    elif key in ('min_hz', 'max_hz'):
        lo, hi = 0.1, 5.0
    else:
        lo, hi = -40, 40
    if not lo <= v <= hi:
        raise ValueError('out of range')
    return v

def check_config(cfg):
    if cfg['min_hz'] > cfg['max_hz']:
        raise ValueError('min_hz > max_hz')
    # Actual servo motion must additionally be limited by flight controller.

def save_config():
    check_config(config)
    temp = CONFIG_FILE + '.tmp'
    with open(temp, 'w') as f:
        json.dump(config, f)
        f.flush()
    try:
        os.remove(CONFIG_FILE)
    except OSError:
        pass
    os.rename(temp, CONFIG_FILE)

# Simple percent decode (ASCII and UTF-8 names)
def unquote(s):
    out = bytearray()
    if isinstance(s, str):
        s = s.encode()
    i = 0
    while i < len(s):
        if s[i] == 37 and i + 2 < len(s):
            try:
                out.append(int(s[i+1:i+3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.append(32 if s[i] == 43 else s[i])
        i += 1
    return out.decode('utf-8')

def params(path):
    result = {}
    if b'?' not in path:
        return result
    for pair in path.split(b'?', 1)[1].split(b'&'):
        if b'=' in pair:
            k, v = pair.split(b'=', 1)
            result[unquote(k)] = unquote(v)
    return result

def respond(client, body, ctype='application/json', status='200 OK'):
    if isinstance(body, str):
        body = body.encode('utf-8')
    header = ('HTTP/1.1 ' + status + '\r\nContent-Type: ' + ctype + '; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: ' + str(len(body)) + '\r\n\r\n').encode()
    client.write(header)
    for i in range(0, len(body), 768):
        client.write(body[i:i+768])

HTML = '''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover"><title>FLY-C3RX</title><style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#101827;color:white;font-family:Arial,sans-serif;touch-action:none;user-select:none}
#main{--gap:6px;--cell:min(calc((100vw - 28px)/3 * 1.5),calc((100dvh - 75px)/2.4));display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-template-rows:var(--cell) minmax(0,1fr) var(--cell);gap:var(--gap);width:100vw;height:100vh;height:100dvh;padding:38px 8px max(9px,env(safe-area-inset-bottom));min-height:0}
#main button{border:0;border-radius:12px;background:#34445c;color:white;font-size:clamp(25px,8vw,42px);touch-action:none;min-height:0;width:100%;height:100%}
#main button.on{background:#0284c7}
#main>button[data-key="5"]{grid-area:1/1}#main>button[data-key="1"]{grid-area:1/2}#main>button[data-key="7"]{grid-area:1/3}
#main>button[data-key="3"]{grid-area:2/1}#main>button[data-key="4"]{grid-area:2/3}
#main>button[data-key="6"]{grid-area:3/1}#main>button[data-key="2"]{grid-area:3/2}#main>button[data-key="8"]{grid-area:3/3}
#center{grid-area:2/2;display:flex;align-items:center;justify-content:center;flex-direction:column;min-width:0;min-height:0;gap:6px}
#label{white-space:nowrap;font-size:clamp(11px,3vw,15px);background:#101827bb;padding:2px 3px;border-radius:5px}
#track{flex:1;min-height:0;width:min(100%,90px);border-radius:55px;background:#34445c;border:2px solid #789;position:relative;touch-action:none}
#thumb{width:calc(100% - 12px);height:clamp(36px,9dvh,66px);position:absolute;left:6px;top:calc(100% - 76px);background:#39bdf8;color:#082032;border-radius:50px;display:grid;place-items:center;font-size:24px;font-weight:bold}
#status{position:absolute;top:5px;right:7px;font-size:11px;color:#facc15;background:#101827bb;padding:2px 4px;border-radius:4px;z-index:3;pointer-events:none}
@media(max-height:480px){#main{padding-top:32px;--cell:min(calc((100vw - 28px)/3 * 1.5),calc((100dvh - 60px)/2.5))}}
#settings{display:none;width:100vw;height:100dvh;overflow:auto;touch-action:pan-y;padding:32px 10px 12px;background:#101827}#fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}#fields label{display:flex;align-items:center;justify-content:space-between;gap:5px;background:#243247;border-radius:6px;padding:6px;font-size:12px}#fields input{width:75px;max-width:45%;padding:5px;color:white;background:#111827;border:1px solid #64748b;border-radius:5px;font-size:14px}#fields input[type=text]{width:115px;max-width:60%}#settings button{font-size:13px;padding:9px 12px;margin:6px 4px 0 0}.topbtn{position:fixed;top:3px;left:5px;z-index:5;font-size:12px;padding:5px 8px;background:#475569}#msg{font-size:12px;color:#93c5fd;padding:3px 4px}#status{right:6px;top:5px}</style></head><body><button id="tab" class="topbtn">⚙ 校正</button><span id="status">連線中</span><div id="main"><button data-key="5">↖</button><button data-key="1">↑</button><button data-key="7">↗</button><button data-key="3">←</button><div id="center"><div id="label">油門 <b id="n">0</b>/15</div><div id="track"><div id="thumb">0</div></div></div><button data-key="4">→</button><button data-key="6">↙</button><button data-key="2">↓</button><button data-key="8">↘</button></div><section id="settings"><div id="msg">讀取參數中…</div><div id="fields"></div><button id="reload">重新讀取</button><button id="save">儲存至 ESP32-C3</button><div style="font-size:11px;color:#a8b5c7">校正頁停止油門。修改後立即更新暫存設定，按儲存才寫入 Flash。變更名稱後，下次重新啟動使用新 SSID。</div></section><script>
let speed=0,key=0,requesting=false,fail=0,page='flight',configReady=false;const track=document.getElementById('track'),thumb=document.getElementById('thumb'),status=document.getElementById('status');function show(){let max=Math.max(0,track.clientHeight-thumb.clientHeight-12);thumb.style.top=(6+max*(1-speed/15))+'px';thumb.textContent=speed;document.getElementById('n').textContent=speed}function throttle(e){let r=track.getBoundingClientRect();let f=1-(e.clientY-r.top-thumb.clientHeight/2)/(r.height-thumb.clientHeight);speed=Math.max(0,Math.min(15,Math.round(f*15)));show()}track.addEventListener('pointerdown',e=>{e.preventDefault();track.setPointerCapture(e.pointerId);throttle(e)});track.addEventListener('pointermove',e=>{if(track.hasPointerCapture(e.pointerId))throttle(e)});document.querySelectorAll('button[data-key]').forEach(b=>{b.addEventListener('pointerdown',e=>{e.preventDefault();b.setPointerCapture(e.pointerId);key=Number(b.dataset.key);document.querySelectorAll('button[data-key]').forEach(x=>x.classList.toggle('on',x===b))});for(let event of ['pointerup','pointercancel','lostpointercapture'])b.addEventListener(event,()=>{if(key===Number(b.dataset.key))key=0;b.classList.remove('on')})});async function send(){if(requesting)return;requesting=true;const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),350);try{let response=await fetch('/control?s='+(page==='flight'?speed:0)+'&k='+(page==='flight'?key:0),{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error('HTTP');fail=0;status.textContent='已連線';status.style.color='#86efac'}catch(e){fail++;status.textContent='連線中斷';status.style.color='#fca5a5';if(fail>=3){speed=0;key=0;show();document.querySelectorAll('button[data-key]').forEach(b=>b.classList.remove('on'))}}finally{clearTimeout(timer);requesting=false}}setInterval(send,100);document.addEventListener('visibilitychange',()=>{if(document.hidden){speed=0;key=0;show()}});window.addEventListener('pagehide',()=>{speed=0;key=0});show();window.addEventListener('resize',show);

const names={left_center:'左翼基準角',right_center:'右翼基準角',up_angle:'上拍角度',down_angle:'下拍角度',min_hz:'最低拍頻 Hz',max_hz:'最高拍頻 Hz',k1_up:'K1 左Servo偏移',k1_down:'K1 右Servo偏移',k2_up:'K2 左Servo偏移',k2_down:'K2 右Servo偏移',k3_up:'K3 左Servo偏移',k3_down:'K3 右Servo偏移',k4_up:'K4 左Servo偏移',k4_down:'K4 右Servo偏移',device_name:'蝴蝶名稱'};
const msg=document.getElementById('msg'),fields=document.getElementById('fields');
async function api(url){let c=new AbortController(),t=setTimeout(()=>c.abort(),1600);try{let r=await fetch(url,{cache:'no-store',signal:c.signal});if(!r.ok)throw Error('HTTP '+r.status);return await r.json()}finally{clearTimeout(t)}}
async function loadConfig(){configReady=false;fields.innerHTML='';msg.textContent='正在讀取 ESP32-C3 參數…';try{let data=await api('/config');for(let k of Object.keys(names)){let label=document.createElement('label'),text=document.createElement('span'),input=document.createElement('input');text.textContent=names[k];input.type=k==='device_name'?'text':'number';input.step=k.indexOf('hz')>=0?'0.1':'1';input.value=data.config[k];input.addEventListener('change',async()=>{let v=input.value;try{let ret=await api('/set?key='+encodeURIComponent(k)+'&value='+encodeURIComponent(v));if(!ret.ok)throw Error('invalid');input.value=ret.value;msg.textContent='已修改暫存值（尚未儲存）'}catch(e){msg.textContent='修改失敗，請重新讀取';configReady=false}});label.append(text,input);fields.append(label)}configReady=true;msg.textContent='目前裝置：'+data.id+'；參數讀取成功'}catch(e){msg.textContent='讀取失敗：'+e.message+'（禁止儲存）'}}
document.getElementById('tab').onclick=async()=>{speed=0;key=0;show();document.querySelectorAll('button[data-key]').forEach(b=>b.classList.remove('on'));if(page==='flight'){page='settings';try{await api('/mode?value=settings')}catch(e){};document.getElementById('main').style.display='none';document.getElementById('settings').style.display='block';document.getElementById('tab').textContent='← 飛行';await loadConfig()}else{try{await api('/mode?value=flight')}catch(e){};page='flight';document.getElementById('main').style.display='grid';document.getElementById('settings').style.display='none';document.getElementById('tab').textContent='⚙ 校正';show();requestAnimationFrame(show)}};
document.getElementById('reload').onclick=loadConfig;
document.getElementById('save').onclick=async()=>{if(!configReady){msg.textContent='請先成功讀取參數';return}try{let r=await api('/save');msg.textContent=r.ok?'儲存成功。若更改名稱，下次重啟使用 Butterfly_新名稱':'儲存失敗'}catch(e){msg.textContent='儲存失敗：'+e.message}};
</script></body></html>'''

# ============================================================
# Dual-servo controller (angles in degrees)
# ============================================================
SL_PIN = 7
SR_PIN = 10
SERVO_PERIOD_US = 20000
SERVO_STEP_MS = 10
SERVO_SMOOTH_MS = 180.0
TAU = 2.0 * math.pi

sl = PWM(Pin(SL_PIN), freq=50)
sr = PWM(Pin(SR_PIN), freq=50)

def servo_write(pwm, angle):
    angle = max(0.0, min(180.0, angle))
    us = 500 + angle * 2000 / 180.0
    pwm.duty_u16(int(us * 65535 / SERVO_PERIOD_US))

def offsets_for_key(key):
    # Existing config keys are retained for compatibility.
    # _up = left-servo offset; _down = right-servo offset.
    def pair(n):
        return (config['k%d_up' % n], config['k%d_down' % n])
    if 1 <= key <= 4:
        return pair(key)
    # Diagonals: combine pitch and turn offsets.
    combo = {5: (1, 3), 6: (2, 3), 7: (1, 4), 8: (2, 4)}
    if key in combo:
        a, b = combo[key]
        al, ar = pair(a)
        bl, br = pair(b)
        return al + bl, ar + br
    return 0, 0

mode = 'flight'
rx_speed = 0
rx_key = 0
phase = 0.0
current_hz = 0.0
current_amp = 0.0
last_motion_ms = time.ticks_ms()
last_servo_ms = last_motion_ms

servo_write(sl, config['left_center'])
servo_write(sr, config['right_center'])

def update_motion():
    global phase, current_hz, current_amp, last_motion_ms, last_servo_ms
    now = time.ticks_ms()
    dt_ms = max(0, min(100, time.ticks_diff(now, last_motion_ms)))
    last_motion_ms = now
    if time.ticks_diff(now, last_servo_ms) < SERVO_STEP_MS:
        return
    last_servo_ms = now
    dt = dt_ms / 1000.0
    active = mode == 'flight' and time.ticks_diff(now, last_seen) <= TIMEOUT_MS
    speed = rx_speed if active else 0
    key = rx_key if active else 0
    target_hz = (config['min_hz'] + (config['max_hz'] - config['min_hz']) * (speed - 1) / 14.0) if speed else 0.0
    # Time-based exponential smoothing, stable under variable web-server load.
    alpha = 1.0 - math.exp(-dt_ms / SERVO_SMOOTH_MS)
    current_hz += (target_hz - current_hz) * alpha
    current_amp += ((1.0 if speed else 0.0) - current_amp) * alpha
    if current_amp < 0.001 and not speed:
        current_amp = 0.0
        current_hz = 0.0
        phase = 0.0
    else:
        phase = (phase + TAU * current_hz * dt) % TAU
    wave = math.sin(phase)
    flap = wave * (config['up_angle'] if wave >= 0 else config['down_angle']) * current_amp
    dl, dr = offsets_for_key(key)
    left = config['left_center'] + dl + flap
    right = config['right_center'] + dr - flap
    servo_write(sl, left)
    servo_write(sr, right)

ap = network.WLAN(network.AP_IF)
ap.active(False)
time.sleep_ms(800)
ssid = 'Butterfly_' + config['device_name']
# Preserve original SSID for the first run and use custom name only when saved.
if config['device_name'] == 'Test':
    ssid = 'Butterfly_Test'
ap.config(essid=ssid, authmode=0, channel=AP_CHANNEL, hidden=False)
ap.active(True)
time.sleep_ms(1200)
print('AP active:', ap.active())
print('SSID:', ap.config('essid'))
print('IP:', ap.ifconfig()[0])
print('Open http://192.168.4.1')

server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 80))
server.listen(2)
server.settimeout(0.01)

last_data = None
last_seen = time.ticks_ms()

def output(data, prefix='RX'):
    speed = (data >> 8) & 15
    keys = data & 255
    names = ['K%d' % (i + 1) for i in range(8) if keys & (1 << i)]
    label = '+'.join(names) if names else 'K33'
    bits = ''.join('1' if speed & (1 << i) else '0' for i in (3, 2, 1, 0))
    print('%s: %-4s speed=%2d bits=%s data=0x%03X' % (prefix, label, speed, bits, data))

print('Web server running...')
while True:
    update_motion()
    now = time.ticks_ms()
    if last_data is not None and last_data != 0 and time.ticks_diff(now, last_seen) > TIMEOUT_MS:
        last_data = 0
        rx_speed = 0
        rx_key = 0
        output(0, 'TIMEOUT')
    try:
        client, addr = server.accept()
    except OSError:
        continue
    try:
        client.settimeout(0.5)
        raw = client.recv(1024)
        if not raw:
            continue
        line = raw.split(b'\r\n', 1)[0]
        parts = line.split(b' ')
        if len(parts) < 2:
            continue
        path = parts[1]
        if path.startswith(b'/control?'):
            q = params(path)
            speed = max(0, min(15, int(q.get('s', '0'))))
            key = max(0, min(8, int(q.get('k', '0'))))
            data = (speed << 8) | ((1 << (key - 1)) if key else 0)
            last_seen = time.ticks_ms()
            if mode == 'flight':
                rx_speed, rx_key = speed, key
            else:
                rx_speed, rx_key = 0, 0
            if data != last_data:
                last_data = data
                output(data)
            respond(client, 'OK', 'text/plain')
        elif path == b'/' or path.startswith(b'/?'):
            respond(client, HTML, 'text/html')
        elif path.startswith(b'/mode?'):
            new_mode = params(path).get('value', '')
            if new_mode not in ('flight', 'settings'):
                raise ValueError('invalid mode')
            mode = new_mode
            rx_speed = 0
            rx_key = 0
            current_hz = 0.0
            current_amp = 0.0
            phase = 0.0
            respond(client, json.dumps({'ok': True, 'mode': mode}))
        elif path == b'/config':
            respond(client, json.dumps({'id': ssid, 'config': config}))
        elif path.startswith(b'/set?'):
            q = params(path)
            key = q.get('key', '')
            value = valid(key, q.get('value', ''))
            candidate = config.copy()
            candidate[key] = value
            check_config(candidate)
            config[key] = value
            if key in ('left_center', 'right_center') and mode == 'settings':
                servo_write(sl, config['left_center'])
                servo_write(sr, config['right_center'])
            respond(client, json.dumps({'ok': True, 'value': value}))
        elif path == b'/save':
            save_config()
            respond(client, json.dumps({'ok': True}))
            print('Config saved to', CONFIG_FILE)
        else:
            respond(client, 'Not found', 'text/plain', '404 Not Found')
    except Exception as e:
        print('Request error:', e)
        try:
            respond(client, json.dumps({'ok': False, 'error': str(e)}), status='400 Bad Request')
        except Exception:
            pass
    finally:
        try:
            client.close()
        except Exception:
            pass
        # Avoid forced garbage collection on every 100-ms control request.
        if gc.mem_free() < 12000:
            gc.collect()
