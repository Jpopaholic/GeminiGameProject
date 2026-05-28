# 吉米尼實況助理 ─ 遊戲與開發插件目錄 (Game & Project Tools Plugins)

這個目錄存放了各個實況項目或遊戲（例如：`vibe_coding`、`bunny_garden2`、`gw2`）的專屬插件、技能知識庫以及自定義觸發器設定。

## ⚠️ Git 追蹤說明

為了保護每位實況主的敏感配置、本機臨時除錯指令與自定義觸發回應，**除本說明文件 (`README.md`) 外，此目錄下的所有子目錄與設定檔案皆已透過 `.gitignore` 排除追蹤。**

---

## 📂 插件目錄結構規範

每個插件資料夾必須依循以下結構配置，才能被大腦動態讀取與切換：

```text
game_tools/
└── <project_name>/
    ├── plugin_config.json   # 包含 project_display_name、自定義 triggers 關鍵字與氣氛效果
    └── skills/
        ├── general.txt      # 專案通用基礎知識
        └── gameplay.txt     # 遊戲/開發玩法與技巧指南
```

### 1. `plugin_config.json` 範例

```json
{
  "project_display_name": "我的酷遊戲",
  "visual_roast": "你看你看！本助理放大看 480p 畫面，你的操作也太誇張了吧！",
  "triggers": [
    {
      "keywords": ["太難了", "不會玩"],
      "effects": {
        "vibe_score_delta": -5
      },
      "response": "哎呀！主人別氣餒，大腦運算發現多練習幾次一定能通關的！(〃∀〃)"
    }
  ],
  "default_responses": [
    "哼，主人剛才的操作很有 Vibe，繼續加油喔！(́◉◞౪◟◉‵)"
  ]
}
```

### 2. `skills/` 技能文字庫

在此目錄下放置任何以 `.txt` 結尾的檔案（例如 `knowledge.txt`），核心引擎將會自動在載入時：
- 動態掃描並拼接為系統指令（System Instruction）。
- 作為 Gemini 在對答時所應遵守的核心常識與技術背景。
