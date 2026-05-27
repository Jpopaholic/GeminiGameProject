# 🌌 Gemini Game Stream Engine (吉米尼萬用實況助理引擎)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Gemini 2.5](https://img.shields.io/badge/Model-Gemini%202.5%20Flash-purple.svg)](https://deepmind.google/technologies/gemini/)

一個專為實況主（Streamer）設計的**高互動性、低延遲、具備視覺與聽覺能力**的 AI 萬用實況助理引擎。透過整合 Google Gemini 的原生多模態能力，本助理能即時看見實況畫面、聆聽實況主與觀眾的聲音，並以流暢的 Native Audio 語音進行極具個性化的即時互動與吐槽！

---

## 🌟 核心特色 (Core Features)

### 1. 👁️ OBS 眼睛 (OBS Visual Eye)
* **WebSocket v5 整合**：原生支援 OBS WebSocket v5，能以高效能、低延遲的方式即時擷取實況畫面。
* **480p 賽博壓制**：自動對擷取畫面進行壓縮優化，確保在保留關鍵畫面資訊的同時，極大化節省傳輸頻寬與 API Token 消耗。
* **雙重降級備份機制**：若 OBS 未開啟，會自動降級至系統級螢幕截圖（`mss`），或讀取靜態示範畫面（`test_gameplay.jpg`），確保系統不中斷。

### 2. 👂 雙通道聽覺系統 (Dual Ears Listener)
* **環路音訊監聽**：支援虛擬音訊裝置（如 `BlackHole 2ch`），可即時監聽遊戲大音量或特定背景音效。
* **麥克風語音辨識**：利用 `speech_recognition` 與 `PyAudio` 捕捉實況主的語音，並在背景以非阻塞非同步執行緒進行精準辨識。

### 3. 🛡️ 1M TPM 流量安全防護罩
* **智慧額度監控**：內建 TPM（Tokens Per Minute）追蹤器，當每分鐘 Token 消耗量逼近 **850,000** 的警告水位時，會自動觸發警告。
* **安全下班機制**：若達到 **1,000,000** 安全極限，助理會透過語音向觀眾與實況主大合照告別，並啟動安全保護自動關機下班，完美防止 API 額度超支。

### 4. 🧠 靈魂設定與實況日記記憶 (Personality & Memories)
* **繁體中文角色扮演**：依照 `brain_profile/identity.txt` 塑造專屬靈魂——一個懂網路梗、動漫 ACG、富有趣味與親和力的語音助理。
* **記憶提煉存檔**：下播或結束時，會自動將本次實況的精彩瞬間、吐槽次數、甚至是實況主的趣味數值累積，提煉並永久存檔至 `session_memories/`，作為下次開播的背景記憶。

### 5. 🎮 跨遊戲與情境專案切換
* 原生支援動態專案切換：
  * **激戰 2 (Guild Wars 2, `gw2`)**：提供世界戰場藍標指揮官、市場交易與副本機制的常識庫與即時輔助。
  * **數獨專案 (Sudoku Kotlin, `vibe_coding`)**：陪伴實況主進行 Android 數獨專案的 Vibe Coding，隨時提供代碼吐槽與加油打氣。

### 6. 🌌 Gemini Cyber Glow 實況 Logo 掛件 (OBS Overlay)
* **雙星 Logo 呼吸與發光**：整合精緻向量雙四角星標（Gemini 經典圖示），空閒時溫馨呼吸，助理發言時瞬間擴大 1.15 倍，亮起耀眼霓虹漸層光環！
* **Canvas 粒子噴湧**：說話時即時爆發噴射出無數微小彩光霓虹粒子，順風緩緩上升淡出，為直播增添華麗氣氛！
* **毛玻璃字幕 bubble**：自帶 `backdrop-filter` 磨砂毛玻璃框，實時滑動淡入顯示助理回答文字，並在說完話 4 秒後自動淡出，保持畫面簡潔。
* **發言狀態/音量雙模式**：支援讀取 `speaking_state.json` 發言狀態，或使用 Web Audio API 自動感應麥克風/音訊振幅，隨聲音即時跳動！

---

## 📂 專案架構 (Project Structure)

```bash
├── main.py                    # 實況主互動主控台 CLI (雙模輸入、非同步事件循環)
├── gemini_engine.py           # 萬用實況助理核心引擎 (視覺/聽覺/安全防護/語音輸出)
├── test_engine.py             # 引擎自主功能驗證與測試指令碼
├── setup_dependencies.sh      # 系統環境與相依性套件一鍵安裝指令碼
├── player_profile/
│   ├── config.template.json   # 核心系統設定模板 (複製為 config.json 使用)
│   ├── host_info.template.txt # 實況主背景設定模板 (複製為 host_info.txt 使用)
│   └── .gitignore 排除檔案     # config.json 與 host_info.txt 已被 git 忽略，保護隱私
├── brain_profile/
│   ├── identity.txt           # AI 助理的靈魂人格設定
│   └── base_skills/           # 基礎常識與語言風格庫
├── stream_overlay/
│   └── index.html             # OBS 實況發光 Logo 掛件 (整合粒子與磨砂字幕框)
└── game_tools/                # 專案情境專屬技能庫
    ├── gw2/                   # 激戰 2 專用技能 (市場、機制等)
    └── vibe_coding/           # Vibe Coding 專用技能 (Kotlin 規則等)
```

---

## 🚀 快速開始 (Quick Start)

### 1. 安裝環境相依性
本專案支援 macOS 與 Windows。在 macOS 下可直接執行一鍵安裝指令碼：
```bash
chmod +x setup_dependencies.sh
./setup_dependencies.sh
```

*(此指令碼將會透過 Homebrew 安裝 `portaudio`，並藉由 `pip` 安裝 `pyaudio`、`google-genai`、`speechrecognition`、`obsws-python`、`mss` 與 `pillow` 等核心相依庫。)*

### 2. 進行設定
請複製 [player_profile/config.template.json](file:///Users/jpopaholic/Documents/GeminiGameProject/player_profile/config.template.json) 並命名為 `config.json`，同樣將 [player_profile/host_info.template.txt](file:///Users/jpopaholic/Documents/GeminiGameProject/player_profile/host_info.template.txt) 複製並命名為 `host_info.txt`：
```json
{
  "active_project": "vibe_coding",
  "obs_websocket": {
    "host": "localhost",
    "port": 4455,
    "password": "您的OBS_WS密碼",
    "enabled": false
  },
  "game_audio_device": "BlackHole 2ch",
  "tpm_safety_limit": 1000000,
  "streamer_name": "您的名字",
  "gemini_api_key": "您的_GEMINI_API_KEY",
  "gemini_voice": "Aoede"
}
```

### 3. 驗證引擎功能
在正式開播前，可使用以下指令碼驗證引擎的視覺擷取降級備份、語音 Instruction 組合等功能是否完全正常：
```bash
python3 test_engine.py
```

### 4. 啟動主控台
直接執行主控制台即可開始與吉米尼助理互動：
```bash
python3 main.py
```
* 支援**雙模輸入**：可直接在終端機鍵盤輸入，或對著麥克風直接說話。
* 輸入 `status`：查看當前安全額度消耗、專案與 OBS 連線狀態。
* 輸入 `switch vibe_coding` 或 `switch gw2`：動態切換實況主題。
* 輸入 `exit`：安全提煉記憶並存檔收播。

### 5. 載入 OBS 實況發光掛件 (Overlay)
將本專案的炫酷發光 Logo 與對話框融入您的實況畫面：
1. 在 OBS 的「來源」視窗點擊 **`+`**，選擇 **`瀏覽器` (Browser)**。
2. 命名為 `Gemini_Logo`，勾選 **`本地檔案` (Local File)**。
3. 點選瀏覽，選擇專案資料夾中的 [stream_overlay/index.html](file:///Users/jpopaholic/Documents/GeminiGameProject/stream_overlay/index.html)。
4. 設定寬度為 **`500`**，高度為 **`500`**，點擊確定。
5. （選擇性）若需要以實體麥克風/音響聲量感應（而非引擎輪詢），可點擊 OBS 來源視窗的「互動」按鈕，並點擊最上方的「模式切換」或雙擊 Logo 進行效果測試。

---

## 🎨 設計美學與開發哲學

* **完全解耦**：控制台介面與底層多模態 API 完全解耦，相容 Windows 與 macOS 雙系統。
* **防禦性程式設計**：無處不在的 `try-except` 與優雅降級備份，保證實況中絕不因周邊設備異常而崩潰。
* **低延遲響應**：採用非阻塞的語音輸出方式（macOS 原生 `say` 語音與 Gemini Native Audio 雙規並行），即使在大流量實況環境中依然能保持絲滑流暢的對答。

---

## 📄 開源授權

本專案採用 [MIT License](LICENSE) 授權。歡迎自由修改與二次開發！
