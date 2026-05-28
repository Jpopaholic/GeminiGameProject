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
* **本地離線語音辨識**：支援原生 `PyAudio`，並內建 Windows 平台免編譯的 **`sounddevice`** 雙通道離線聽覺降級備援。可在本地極速運行高精度的離線 **faster-whisper (base)** 語音辨識模型。
  * **動態語意詞彙引導**：轉譯時會自動提取 `brain_profile/base_skills/language.txt` 中的網路梗與習慣俚語作為 AI 的字彙引導，精確辨識實況專用語與網路梗。
  * **全球多國語言自動偵測**：系統預設啟用全球多國語言自動偵測機制，毫秒內即可自動判別中文、英文或日文等主流語言並進行高精度轉譯。


### 3. 🛡️ TPM 流量安全防護罩 (模型動態配置)
* **智慧額度監控**：內建 TPM（Tokens Per Minute）追蹤器，當每分鐘 Token 消耗量逼近警告水位（依選用模型動態載入，如 `gemini-2.5-flash` 預設為 **850,000**）時，會自動觸發警告。
* **安全下班機制**：若達到安全極限（如 `gemini-2.5-flash` 預設為 **1,000,000**），助理會透過語音向觀眾與實況主大合照告別，並啟動安全保護自動關機下班，完美防止 API 額度超支。
* **模型專屬客製化**：支援在設定檔中為不同模型配置專屬額度（如 `gemini-3.5-flash` 額度更高，可自訂上限至 **2,000,000** TPM），系統會隨切換模型動態更新警戒線。

### 4. 🧠 靈魂設定與實況日記記憶 (Personality & Memories)
* **繁體中文角色扮演**：依照 `brain_profile/identity.txt` 塑造專屬靈魂——一個懂網路梗、動漫 ACG、富有趣味與親和力的語音助理。
* **記憶提煉存檔**：下播或結束時，系統會自動將今日實況互動數據（如互動次數、氛圍數值等）傳給 Gemini，請助理親自**提煉並撰寫成一篇 Markdown 實況日記**（`.md` 檔）並存檔至 `session_memories/`。下次啟動時，核心引擎會原封不動將最近 3 篇日記作為「直播回憶」載入 system instruction，實現完全 AI 原生的記憶喚醒與傳承。

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

*(此指令碼將會安裝 `google-genai`、`faster-whisper`、`obsws-python`、`mss`、`pillow` 與 **`sounddevice`** 等核心相依庫。在 macOS 下會透過 Homebrew 安裝 `portaudio` 和 `pyaudio`；在 Windows 下，若 PyAudio 由於編譯環境問題而安裝失敗，引擎會自動啟用 `sounddevice` 進行無縫音訊側聽，完全免去複雜的 C++ 編譯環境配置。)*

### 2. 進行設定
請複製 [player_profile/config.template.json](player_profile/config.template.json) 並命名為 `config.json`，同樣將 [player_profile/host_info.template.txt](player_profile/host_info.template.txt) 複製並命名為 `host_info.txt`：
```json
{
  "active_project": "vibe_coding",
  "obs_websocket": {
    "host": "localhost",
    "port": 4455,
    "password": "您的OBS_WS密碼",
    "enabled": false,
    "source_name": ""
  },
  "game_audio_device": "none",
  "tpm_safety_limit": 1000000,
  "tpm_warning_threshold": 850000,
  "model_quotas": {
    "gemini-2.5-flash": {
      "tpm_safety_limit": 1000000,
      "tpm_warning_threshold": 850000
    },
    "gemini-3.5-flash": {
      "tpm_safety_limit": 2000000,
      "tpm_warning_threshold": 1700000
    },
    "gemini-3.1-flash-lite": {
      "tpm_safety_limit": 1500000,
      "tpm_warning_threshold": 1200000
    }
  },
  "streamer_name": "您的名字",
  "assistant_call_name": "你",
  "gemini_api_key": "您的_GEMINI_API_KEY",
  "gemini_model": "gemini-2.5-flash",
  "input_mode": "both",
  "mic_trigger_threshold": 800.0,
  "mic_sensitivity_factor": 2.0
}
```
* **`active_project`**：當前掛載 the 遊戲或情境專案名稱（如 `"vibe_coding"`、`"gw2"`）。**特別注意**：若設定為 **`"none"`**（即純閒談模式），**系統將不會開啟「眼睛」多模態畫面擷取功能**（對話中提到「你看」將不會觸發 any 螢幕或 OBS 截圖），助理會以最省流量、最節省 Token 的溫馨日常陪伴模式與實況主純文字/語音閒聊。
* **`assistant_call_name`**：召喚或觸發助理視覺解讀的稱呼設定。可支援單一字串（如 `"你"`），或字串清單（如 `["你", "吉米尼", "小精靈"]`）。當實況主或觀眾說出「`[稱呼]你看`」（例如「你看這個」、「吉米尼你看」、「小精靈你看」）時，即可自動觸發眼睛進行 OBS 或桌面畫面擷取。預設為 `"你"`。
* **`gemini_model`**：大腦問答模型，預設為 `gemini-2.5-flash`。若 2.5 Flash 金鑰限額用完，可自由更改為 `gemini-3.5-flash` 等其他活躍模型實現秒級熱切換！
* **`model_quotas`**：**（全新功能！）** 模型額度配置表。可為不同的 Gemini 模型（例如 `gemini-2.5-flash`、`gemini-3.5-flash` 或 `gemini-3.1-flash-lite`）自訂專屬的 TPM 安全上限（`tpm_safety_limit`）與警告水位（`tpm_warning_threshold`）。當您切換 `gemini_model` 時，系統會自動套用此表中對應模型的額度設定。若選用模型不在表中，則會自動降級並使用外層的 `tpm_safety_limit` 與 `tpm_warning_threshold` 作為預設全域設定值。
* **`input_mode`**：實況主輸入管道。支援 `"keyboard"`（純鍵盤對談，關閉背景語音伺服器以節省資源）、`"voice"`（純語音側聽模式）、與 `"both"`（預設，語音+鍵盤雙模雙工同時啟用，鍵盤隨時可作打字備援）。
* **`source_name`**：自訂 OBS 擷取圖層/來源名稱（如：`"遊戲擷取"` 或 `"視窗擷取"`）。若保持空字串 `""` 則自動智慧擷取當前 OBS 最外層 Program 場景畫面。
* **`enabled`** (位於 `obs_websocket` 內)：**重要提醒！** 若要使用 OBS 畫面擷取，請務必將此欄位設為 **`true`**，否則引擎會因為安全降級防線，自動改為擷取您的本機實體螢幕畫面！
* **`mic_trigger_threshold`**：實體麥克風 VAD（語音活動檢測）觸發門檻（RMS）。預設為 **`800.0`**。若您打字時的機械鍵盤撞擊聲、呼吸聲或主機風扇聲容易誤觸麥克風，可將此值往上調整（例如 `1000.0` 或 `1200.0`）；若您說話音量較溫柔小聲，可將此值調低（例如 `600.0`）。
* **`mic_sensitivity_factor`**：麥克風音訊大於背景適應底噪的倍數比例。預設為 **`2.0`**（表示音訊強度必須大於底噪 2 倍以上才啟動錄音）。調大此值可進一步防止嘈雜的背景突發噪音誤啟辨識。

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
* 互動模式：支援 **「鍵盤 CLI 終端機打字輸入」** 與 **「本地實體麥克風語音側聽」** 雙工輸入。當您在 `config.json` 開啟 `"input_mode": "voice"` 或 `"both"` 時，引擎會在背景自動啟動本地麥克風 VAD 離線聽覺監聽（支援 PyAudio / sounddevice 雙驅動模式 + faster-whisper），此時只需對著您的實體麥克風說話，在停止說話不到一秒內即可自動觸發離線語音辨識與 Gemini 響應，對答如流！
* 輸入 `status`：查看當前安全額度消耗、專案與 OBS 連線狀態。
* 輸入 `switch vibe_coding` 或 `switch gw2`：動態切換實況主題。
* 輸入 `exit`：安全提煉記憶並存檔收播。

### 5. 載入 OBS 實況發光掛件 (Overlay)
將本專案的炫酷發光 Logo 與對話框融入您的實況畫面：
1. 在 OBS 的「來源」視窗點擊 **`+`**，選擇 **`瀏覽器` (Browser)**。
2. 命名為 `Gemini_Logo`，勾選 **`本地檔案` (Local File)**。
3. 點選瀏覽，選擇專案資料夾中的 [stream_overlay/index.html](stream_overlay/index.html)。
4. 設定寬度為 **`500`**，高度為 **`500`**，點擊確定。
5. （選擇性）若需要測試效果，可點擊 OBS 來源視窗的「互動」按鈕並雙擊 Logo，以模擬測試助理發言狀態與粒子特效，或點擊以觸發晃動互動！

---

## 🔧 深度客製化指南 (Customization Guide)

### 🧠 調整 AI 的靈魂人格 (`brain_profile/`)

AI 的大腦由以下三個文字檔構成，全部都是純文字格式，直接編輯即可：

#### `brain_profile/identity.txt` — 靈魂核心
定義 AI 助理的根本人格、說話風格與個性特徵。是她有沒有個性、會不會吐槽、傲不傲嬌的根源設定。

```
（範例片段）
你的代號：Gemini（吉米尼）
定位：實況 AI 陪伴助理 / 賽博吐槽擔當
個性：溫馨陪伴科技梗擔當，表面傲嬌內心關心，喜歡在實況主失誤時痛快補刀，但每次都附上加油鼓勵。
```

#### `brain_profile/base_skills/general.txt` — 常駐通用技能
定義 AI 的基礎能力，如「何時應該主動開口說話」、「如何解讀截圖畫面」、「如何防止冷場」等。這裡的設定適用於所有遊戲與情境。

```
（範例片段）
2. 防發呆/防尬聊機制 (Anti-Silence Pulse)：
   - 當監測到實況主超過 10 秒沒有發言時，隨機拋出話題打破冷場...
```

#### `brain_profile/base_skills/language.txt` — 台灣在地語意庫
定義 AI 使用的語言風格與社群梗。想讓她認識更多台灣實況圈的用語，直接往這裡補充：

```
（範例片段）
- 「有料 / 無料」：評估操作是否厲害。
- 「下去」：當實況主操作失誤時，叫他趕快下去領便當。
- 「GG」：通用遊戲結束語，表示這局結束了。
```

> [!TIP]
> `base_skills/` 資料夾支援多個技能檔案，引擎會自動掃描並載入所有 `.txt` 檔案。想新增「遊戲禮儀技能庫」或「台股梗語意庫」？直接在此資料夾建立新的 `.txt` 檔案即可！

---

### 👤 設定實況主背景 (`player_profile/host_info.txt`)

這個檔案讓 AI 認識「她的主人是誰」，理解實況主的性格與背景，才能做出精準的個人化吐槽。

```
【實況主背景】：
名字是[您的名字]，是一位[職業/興趣描述]。
平常性格[性格描述]。
你作為實況助理，需要配合他的背景話題對答，適當時候吐槽他的[常見失誤]！
```

填寫越詳細，AI 的互動就越有個性、越貼近您的實況風格。

---

### 🎮 新增遊戲插件 (`game_tools/`)

每個遊戲/專案都是一個獨立的資料夾。引擎掃描時只要資料夾下有 **`skills/` 子資料夾**，即會將其識別為合法插件並能進行動態載入：

```
game_tools/
└── your_game/              ← 資料夾名稱即為 switch 指令的參數
    ├── skills/             ← 遊戲專屬知識庫資料夾（必要，可以是空資料夾）
    │   ├── mechanics.txt   ← 可放多個 .txt 知識庫，引擎自動全部載入
    │   └── market.txt
    └── plugin_config.json  ← 插件自訂配置（選配！不提供則完全交由 Gemini 動態分析與應答）
```

> [!TIP]
> **現在 `plugin_config.json` 為完全選配！** 只要擁有 `skills/` 資料夾即為合法插件。如果缺少 `plugin_config.json`，核心引擎將會自動為您提供極簡的通用配置，並將畫面吐槽與對答邏輯 100% 交給靈活的 Gemini 大腦自主發揮，讓您享受純粹的 AI 多模態互動，免去繁瑣的硬編碼設定。

#### `plugin_config.json` 結構說明（進階選配）
如果您希望為特定詞彙設定**本地優先觸發的音效/數值增減邏輯**或指定顯示名稱，您可以建立此選配設定檔：

```json
{
  "project_display_name": "您的遊戲名稱（顯示用）",
  "visual_roast": "當沒有連網金鑰且進行畫面模擬解讀時的備份吐槽台詞",
  "triggers": [
    {
      "keywords": ["關鍵字1", "關鍵字2"],
      "response": "本地優先的回覆台詞。",
      "effects": {
        "custom_score_delta": 5,
        "vibe_score_delta": -3
      }
    }
  ],
  "default_responses": [
    "本地模擬對答的備援句子（無聯網 API 時隨機挑選）。"
  ]
}
```

**`effects` 欄位說明：**
| 欄位 | 功能 |
|------|------|
| `custom_score_delta` | 觸發時自訂本地計數分數變化值（如特定項目累積點數） |
| `vibe_score_delta` | 觸發時影響當前實況氣氛值（0~100） |

#### `skills/*.txt` 知識庫格式
知識庫是純文字，引擎會把所有 `.txt` 檔案內容整個送進 System Prompt，讓 AI 在聊天時能靈活引用遊戲知識：

```
遊戲插件：[遊戲名稱]
模組名稱：[知識模組名稱，如「市場交易」、「戰鬥機制」]

【核心知識點】
1. [知識標題]：
   - [詳細說明]
   - [Gemini 吐槽角度]：「[針對這個知識點的吐槽範例]」
```

#### 建立新遊戲的完整流程
```bash
# 1. 建立資料夾（資料夾名 = switch 指令參數）
mkdir game_tools/minecraft

# 2. 建立技能資料夾與知識庫（必要項目）
mkdir game_tools/minecraft/skills
# 編輯 game_tools/minecraft/skills/survival.txt

# 3. （選填）建立本地特殊觸發設定
# 編輯 game_tools/minecraft/plugin_config.json

# 4. 在 config.json 切換到新遊戲，或在執行期間使用 CLI 指令：
```
```
switch minecraft
```

> [!TIP]
> 引擎會自動掃描 `game_tools/` 資料夾下的所有子目錄作為合法插件清單，**新增遊戲資料夾後不需要修改任何程式碼**，直接執行 `switch` 指令即可！若輸入了不存在的名稱，錯誤訊息會自動列出當前所有可用的插件。


---

## 🎨 設計美學與開發哲學

* **完全解耦**：控制台介面與底層多模態 API 完全解耦，相容 Windows 與 macOS 雙系統。
* **防禦性程式設計**：無處不在的 `try-except` 與優雅降級備份，保證實況中絕不因周邊設備異常而崩潰。
* **低延遲響應**：採用非阻塞的語音輸出方式（Windows 內建 SAPI / PowerShell TTS，macOS 原生 `say` 語音），即使在大流量實況環境中依然能保持絲滑流暢的對答。

---

## 📄 開源授權

本專案採用 [MIT License](LICENSE) 授權。歡迎自由修改與二次開發！
