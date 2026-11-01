FLY-C3RX Wi-Fi / BLE 共用核心 V1（2026-10-27）
================================================

本套件依照原有 Wi-Fi V3.2 與 BLE V12 的程式架構整理。
注意：這是新的共用核心測試版，不是已完成實機驗證的正式版。
原本可運作的 Wi-Fi V3.2 與 BLE V11 請先備份。

檔案：
main.py             啟動入口，選擇 TRANSPORT = "wifi" 或 "ble"
calibration.py      15 項共用參數、合法範圍、首次開機建立 JSON、儲存
flight_control.py   GPIO7/GPIO10、50Hz PWM、正弦拍翼、K1~K8、逾時保護
communication.py    統一指令介面
wifi_server.py      Wi-Fi AP、HTTP API
ble_server.py       BLE GATT UUID 0x1234 / 0x5678
wifi_page.html      Wi-Fi 手機控制頁（內嵌在 ESP32-C3 檔案系統）
phone_ble.html      BLE 手機控制頁（上傳 GitHub Pages）

使用步驟：
1. 在 Thonny 先備份原有 main.py、butterfly_cfg.json。
2. 將 main.py、calibration.py、flight_control.py、communication.py、
   wifi_server.py、ble_server.py、wifi_page.html 全部上傳到 ESP32-C3 根目錄。
3. 只用 Wi-Fi 時，main.py 設 TRANSPORT = "wifi"。
   只用 BLE 時，main.py 設 TRANSPORT = "ble"。
   修改後需重新啟動 ESP32-C3。這個版本一次只啟動一種通訊。
4. Wi-Fi：手機連上 Butterfly_Test，瀏覽 http://192.168.4.1。
5. BLE：把 phone_ble.html 放到 GitHub 的 butterfly 專案並命名為 phone_ble.html，
   用 Android Chrome 網址列直接開啟：
   https://wt500706.github.io/butterfly/phone_ble.html
   不要在 ChatGPT 預覽或 App 內嵌瀏覽器開啟。
6. 校正前先確認讀到 15 筆參數，數值與 C3 的 JSON 一致，
   未核對前不要儲存。

共用參數索引（重要）：
0 device_name
1 left_center
2 right_center
3 up_angle
4 down_angle
5 min_hz
6 max_hz
7 k1_up
8 k1_down
9 k2_up
10 k2_down
11 k3_up
12 k3_down
13 k4_up
14 k4_down

預設值：Test / 90 / 90 / 40 / 55 / 0.5 / 2.5 /
        10 / -10 / -10 / 10 / -10 / -10 / 10 / 10
注意：Wi-Fi/BLE 兩者使用同一 butterfly_cfg.json。
切換通訊方式不會重設校正設定。
更改名稱後需重啟才更新 Wi-Fi SSID 或 BLE 廣播名稱。

安全：
- 進入校正模式立即停止拍翼，返回飛行模式油門維持 0。
- 無控制訊號超過 500ms，拍翼平滑停止。
- BLE 斷線時立即歸零。
- 首次缺少 butterfly_cfg.json 才建立預設檔。
- 不會自動覆寫現有的設定檔。
- 實機測試請先拆下翅膀，確認伺服方向與角度。

測試建議：
A. Wi-Fi：油門 0 / 5 / 15、K1~K8、校正、儲存、重開機。
B. BLE：連線、油門 0 / 5 / 15、K1~K8、G 收 15 筆、M,1/M,0、
   校正、儲存、重開機。
C. 檢查兩者同一校正數值是否產生相同角度/拍頻。
