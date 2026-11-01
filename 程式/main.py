import ble_remote
import machine
import time
import math


# ============================================================
# BLE
# ============================================================

remote = ble_remote.RemoteReceiver()


# ============================================================
# Servo 腳位
# ============================================================

SL_PIN = 7
SR_PIN = 20

_servo_data = {}


# ============================================================
# Servo 獨立校正基準
#
# 左右 Servo 可個別調整
#
# 例如：
# SL_BASE_ANGLE = 93.0
# SR_BASE_ANGLE = 87.0
#
# 校正完成後，所有撲翼與動作
# 都以這兩個角度為各自基準
# ============================================================

SL_BASE_ANGLE = 84.0
SR_BASE_ANGLE = 83.0


# ============================================================
# 撲翼角度
#
# 以各自校正基準為中心
#
# 上拍 +20°
# 下拍 -40°
# ============================================================

UP_ANGLE = 70.0
DOWN_ANGLE = 50.0


# ============================================================
# 動作偏移
# ============================================================

ACTION_OFFSET = 10.0


# ============================================================
# 拍頻
#
# speed 0  = 停止
# speed 1  = 0.5 Hz
# speed 15 = 4 Hz
# ============================================================

MIN_HZ = 1
MAX_HZ = 3.5


# ============================================================
# 拍頻平滑
# ============================================================

HZ_SMOOTH = 0.08


# ============================================================
# 無訊號保護
# ============================================================

SIGNAL_TIMEOUT_MS = 500


# ============================================================
# 更新週期
# ============================================================

LOOP_DELAY_MS = 5


# ============================================================
# Servo 函式
# ============================================================

def servo_us_to_duty(us):

    if us < 500:
        us = 500

    if us > 2500:
        us = 2500

    return int(
        us * 65535 / 20000
    )


def servo_angle_to_us(angle):

    if angle < 0:
        angle = 0

    if angle > 180:
        angle = 180

    return int(
        500
        + angle * 2000 / 180
    )


def servo_write_angle(pwm, angle):

    pwm.duty_u16(
        servo_us_to_duty(
            servo_angle_to_us(angle)
        )
    )


def servo_setup(name, pin):

    pwm = machine.PWM(
        machine.Pin(pin),
        freq=50
    )

    pwm.duty_u16(0)

    _servo_data[name] = pwm


# ============================================================
# Speed → Hz
# ============================================================

def speed_to_hz(speed):

    if speed <= 0:
        return 0.0

    if speed > 15:
        speed = 15

    return (
        MIN_HZ
        +
        (MAX_HZ - MIN_HZ)
        * (speed - 1)
        / 14
    )


# ============================================================
# 角度限制
# ============================================================

def limit_angle(angle):

    if angle < 0:
        return 0.0

    if angle > 180:
        return 180.0

    return angle


# ============================================================
# 依按鍵取得左右 Servo 基準
#
# 注意：
# 不再使用固定 90°
#
# 而是：
# 左 Servo → SL_BASE_ANGLE
# 右 Servo → SR_BASE_ANGLE
#
#
# NORMAL
# L = SL_BASE
# R = SR_BASE
#
# UP
# L = SL_BASE + 10
# R = SR_BASE - 10
#
# DOWN
# L = SL_BASE - 10
# R = SR_BASE + 10
#
# LEFT
# L = SL_BASE - 10
# R = SR_BASE - 10
#
# RIGHT
# L = SL_BASE + 10
# R = SR_BASE + 10
# ============================================================

def get_base_angles(
    head_up,
    head_down,
    turn_left,
    turn_right
):

    base_l = SL_BASE_ANGLE
    base_r = SR_BASE_ANGLE


    # K1 抬頭
    if head_up:

        base_l = (
            SL_BASE_ANGLE
            + ACTION_OFFSET
        )

        base_r = (
            SR_BASE_ANGLE
            - ACTION_OFFSET
        )


    # K2 低頭
    elif head_down:

        base_l = (
            SL_BASE_ANGLE
            - ACTION_OFFSET
        )

        base_r = (
            SR_BASE_ANGLE
            + ACTION_OFFSET
        )


    # K3 左轉
    elif turn_left:

        base_l = (
            SL_BASE_ANGLE
            - ACTION_OFFSET
        )

        base_r = (
            SR_BASE_ANGLE
            - ACTION_OFFSET
        )


    # K4 右轉
    elif turn_right:

        base_l = (
            SL_BASE_ANGLE
            + ACTION_OFFSET
        )

        base_r = (
            SR_BASE_ANGLE
            + ACTION_OFFSET
        )


    return base_l, base_r


# ============================================================
# Servo 初始化
# ============================================================

servo_setup(
    "SL",
    SL_PIN
)

servo_setup(
    "SR",
    SR_PIN
)


# ============================================================
# 開機直接進入各自校正基準
# ============================================================

servo_write_angle(
    _servo_data["SL"],
    SL_BASE_ANGLE
)

servo_write_angle(
    _servo_data["SR"],
    SR_BASE_ANGLE
)


# ============================================================
# 狀態
# ============================================================

speed = 0

head_up = False
head_down = False
turn_left = False
turn_right = False


# ============================================================
# 拍頻狀態
# ============================================================

target_hz = 0.0
current_hz = 0.0


# ============================================================
# SIN
# ============================================================

phase = 0.0

last_phase_time = time.ticks_ms()


# ============================================================
# BLE
# ============================================================

last_packet_time = time.ticks_ms()

last_data = None


# ============================================================
# BLE 啟動
# ============================================================

remote.start()

time.sleep(1)

print("Butterfly Ready")

print(
    "Servo Base |",
    "L:{:.1f}".format(SL_BASE_ANGLE),
    "R:{:.1f}".format(SR_BASE_ANGLE)
)


# ============================================================
# 主迴圈
# ============================================================

while True:

    now = time.ticks_ms()


    # ========================================================
    # BLE 接收
    # ========================================================

    if remote.is_connected_now():

        data = remote.get_value()

        if isinstance(data, int):

            last_packet_time = now


            # =================================================
            # K1 ~ K4
            # =================================================

            head_up = bool(
                data & 0x01
            )

            head_down = bool(
                data & 0x02
            )

            turn_left = bool(
                data & 0x04
            )

            turn_right = bool(
                data & 0x08
            )


            # =================================================
            # K9 ~ K12
            #
            # speed = 0 ~ 15
            # =================================================

            speed = (
                (data >> 8)
                & 0x0F
            )


            target_hz = speed_to_hz(
                speed
            )


            # =================================================
            # 狀態改變才印
            # =================================================

            if data != last_data:

                if head_up:
                    action = "UP"

                elif head_down:
                    action = "DOWN"

                elif turn_left:
                    action = "LEFT"

                elif turn_right:
                    action = "RIGHT"

                else:
                    action = "NORMAL"


                print(
                    "Hz:{:.2f}".format(
                        target_hz
                    ),
                    "|",
                    action
                )


                last_data = data


    # ========================================================
    # 無訊號保護
    # ========================================================

    if time.ticks_diff(
        now,
        last_packet_time
    ) > SIGNAL_TIMEOUT_MS:

        speed = 0
        target_hz = 0.0

        head_up = False
        head_down = False
        turn_left = False
        turn_right = False


    # ========================================================
    # dt
    # ========================================================

    dt_ms = time.ticks_diff(
        now,
        last_phase_time
    )

    last_phase_time = now


    if dt_ms < 0:
        dt_ms = 0

    if dt_ms > 100:
        dt_ms = 100


    dt = (
        dt_ms / 1000.0
    )


    # ========================================================
    # 拍頻平滑
    # ========================================================

    current_hz += (
        target_hz - current_hz
    ) * HZ_SMOOTH


    # ========================================================
    # 依校正值計算目前動作基準
    # ========================================================

    base_l, base_r = get_base_angles(
        head_up,
        head_down,
        turn_left,
        turn_right
    )


    # ========================================================
    # 拍頻 = 0
    #
    # 不撲翼
    # 仍依按鍵移動到對應基準角度
    # ========================================================

    if target_hz == 0.0:

        if current_hz < 0.05:

            current_hz = 0.0

            servo_write_angle(
                _servo_data["SL"],
                base_l
            )

            servo_write_angle(
                _servo_data["SR"],
                base_r
            )

            time.sleep_ms(
                LOOP_DELAY_MS
            )

            continue


    # ========================================================
    # SIN 相位
    # ========================================================

    phase += (
        2.0
        * math.pi
        * current_hz
        * dt
    )


    if phase >= (
        2.0 * math.pi
    ):

        phase %= (
            2.0 * math.pi
        )


    wave = math.sin(
        phase
    )


    # ========================================================
    # 不對稱撲翼
    #
    # 正半波：往上 +40°
    # 負半波：往下 -55°
    # ========================================================

    if wave >= 0:

        wing_offset = (
            wave
            * UP_ANGLE
        )

    else:

        wing_offset = (
            wave
            * DOWN_ANGLE
        )


    # ========================================================
    # 以左右各自校正後的基準撲翼
    #
    # 左 Servo：
    # base_l + wing_offset
    #
    # 右 Servo：
    # base_r - wing_offset
    # ========================================================

    servo_l_angle = (
        base_l
        + wing_offset
    )

    servo_r_angle = (
        base_r
        - wing_offset
    )


    # ========================================================
    # 限制 0 ~ 180°
    # ========================================================

    servo_l_angle = limit_angle(
        servo_l_angle
    )

    servo_r_angle = limit_angle(
        servo_r_angle
    )


    # ========================================================
    # Servo 輸出
    # ========================================================

    servo_write_angle(
        _servo_data["SL"],
        servo_l_angle
    )

    servo_write_angle(
        _servo_data["SR"],
        servo_r_angle
    )


    time.sleep_ms(
        LOOP_DELAY_MS
    )