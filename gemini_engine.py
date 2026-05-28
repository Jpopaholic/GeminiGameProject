#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Game Stream Engine - Core Infrastructure (吉米尼萬用實況助理核心引擎)
專注於真實 API 串接、OBS 眼睛、多通道耳朵與原生 Native Audio 語音輸出
"""

import os
import sys
import json
import time
import glob

# Import shared resources
from gemini_shared import (
    HAS_GEMINI_SDK, HAS_PILLOW, HAS_OBS, HAS_MSS, HAS_WHISPER, HAS_PYAUDIO, HAS_SPEECH,
    CYAN, MAGENTA, YELLOW, GREEN, RED, BOLD, UNDERLINE, RESET, BG_RED, BG_BLACK_FG_YELLOW,
    TPMTracker
)

# Import sub-modules mixins
from gemini_eyes import GeminiEyesMixin
from gemini_mouth import GeminiMouthMixin
from gemini_ears import GeminiEarsMixin
from gemini_brain import GeminiBrainMixin

# Windows console output Unicode compatibility fix
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass

# Import actual libraries if available to preserve HAS_* variables checks for submodules and clients
if HAS_GEMINI_SDK:
    from google import genai

if HAS_WHISPER:
    from faster_whisper import WhisperModel

class GeminiStreamEngine(GeminiBrainMixin, GeminiEyesMixin, GeminiEarsMixin, GeminiMouthMixin):
    """吉米尼萬用實況助理核心引擎，整合大腦、眼睛、耳朵與嘴巴元件"""

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.active_project = "vibe_coding"
        self.streamer_name = "風子"
        
        # 載入核心設定
        self.load_config()
        self.tpm_tracker = TPMTracker(
            limit=self.tpm_safety_limit,
            warning_threshold=self.tpm_warning_threshold
        )
        
        # 互動歷程計數器 (供動態更新與日記提煉)
        self.session_logs = []
        self.roast_count = 0          # 本日對話次數 (動態統計)
        self.vibe_score = 90          # 動態氣氛分數 (通用實況氣氛)
        self.api_exhausted = False    # 標記 API 額度是否耗盡
        self.is_speaking = False      # 標記助理當前是否正在發言（用於防回音防重複觸發）
        self.is_quota_warning = False  # 標記是否正處於額度用完/限流警告狀態
        
        # 載入設定與插件
        self.reload_profiles()

        # 初始化真實 Gemini API 客戶端
        self.client = None
        self.live_client = None
        self.chat_history = []  # 對話上下文
        
        if HAS_GEMINI_SDK and self.api_key and self.api_key != "YOUR_GEMINI_API_KEY_HERE" and len(self.api_key) > 10:
            try:
                # 建立標準對答客戶端（使用預設穩定版本，完美支援 gemini-3.5-flash 等最新 GA 模型）
                self.client = genai.Client(api_key=self.api_key)
                # 建立 WebSocket Live 專用客戶端（使用 v1alpha，完美支援 2.0 Live bidi 串流）
                self.live_client = genai.Client(api_key=self.api_key, http_options={'api_version': 'v1alpha'})
            except Exception as e:
                print(f"{RED}[SDK ERROR] 初始化 Gemini 聯網客戶端失敗: {e}{RESET}")
                
        # 雙通道聽覺音訊屬性
        self.recognizer = None
        self.mic = None
        self.mic_stop_listening = None
        self.game_audio_active = False
        self.game_thread = None
        
        # 初始化發言狀態
        self.speaking_state_file = os.path.join(self.base_dir, "player_profile", "speaking_state.json")
        self.set_speaking_state(False)
        self.live_session_active = False

        # 初始化本地 faster-whisper 大腦模型 (全面離線、低延遲 ASR 轉譯通道)
        self.whisper_model = None
        if HAS_WHISPER:
            try:
                # 預設使用 "base" 模型，在 CPU 與 INT8 量化下兼顧速度與 Traditional Chinese 準確度
                print(f"{YELLOW}[🔊 WHISPER] 正在載入本地離線 ASR 模型 (base)...{RESET}")
                self.whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
                print(f"{GREEN}[🔊 WHISPER] faster-whisper 離線大腦載入成功！{RESET}")
            except Exception as e:
                print(f"{RED}[🔊 WHISPER ERROR] 載入 faster-whisper 失敗: {e}{RESET}")

    def load_config(self):
        config_path = os.path.join(self.base_dir, "player_profile", "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
                self.active_project = self.config.get("active_project", "vibe_coding")
                if not self.active_project or self.active_project.lower() == "none":
                    self.active_project = "none"
                self.streamer_name = self.config.get("streamer_name", "風子")
        else:
            self.config = {
                "active_project": "vibe_coding",
                "tpm_safety_limit": 1000000,
                "tpm_warning_threshold": 850000,
                "streamer_name": "風子"
            }
        # API 金鑰與模型加載安全通道 (環境變數優先，其次是 config.json)
        self.api_key = os.environ.get("GEMINI_API_KEY") or self.config.get("gemini_api_key", "")
        self.gemini_model = self.config.get("gemini_model", "gemini-2.5-flash")
        self.input_mode = self.config.get("input_mode", "both")
        
        # 根據模型動態解析 TPM 安全限制與警告閾值
        model_quotas = self.config.get("model_quotas", {})
        current_model = self.gemini_model
        
        if current_model in model_quotas:
            self.tpm_safety_limit = model_quotas[current_model].get("tpm_safety_limit", 1000000)
            self.tpm_warning_threshold = model_quotas[current_model].get("tpm_warning_threshold", 850000)
        else:
            self.tpm_safety_limit = self.config.get("tpm_safety_limit", 1000000)
            self.tpm_warning_threshold = self.config.get("tpm_warning_threshold", 850000)
            
        # 動態更新 TPM 追蹤器的限制
        if hasattr(self, 'tpm_tracker') and self.tpm_tracker:
            self.tpm_tracker.limit = self.tpm_safety_limit
            self.tpm_tracker.warning_threshold = self.tpm_warning_threshold
        
        # 麥克風 VAD 靈敏度與觸發設定 (預設 800 RMS 門檻，底噪 2.0 倍以上)
        self.mic_trigger_threshold = self.config.get("mic_trigger_threshold", 800.0)
        self.mic_sensitivity_factor = self.config.get("mic_sensitivity_factor", 2.0)
        
        # 載入助理稱呼召喚詞，可支援單一字串，或字串清單
        call_name_cfg = self.config.get("assistant_call_name", "你")
        if isinstance(call_name_cfg, list):
            self.assistant_call_names = [str(name).lower() for name in call_name_cfg]
        else:
            self.assistant_call_names = [str(call_name_cfg).lower()]

    def save_config(self):
        config_path = os.path.join(self.base_dir, "player_profile", "config.json")
        self.config["active_project"] = self.active_project
        self.config["gemini_model"] = self.gemini_model
        self.config["input_mode"] = self.input_mode
        self.config["mic_trigger_threshold"] = self.mic_trigger_threshold
        self.config["mic_sensitivity_factor"] = self.mic_sensitivity_factor
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def set_speaking_state(self, speaking, text=""):
        """寫入助理當前的發言狀態，供 OBS 網頁 Logo Overlay 即時讀取亮起
        同時輸出 speaking_state.js 供本機 file:// 開啟 index.html 時繞過 CORS 跨域限制
        """
        self.is_speaking = speaking
        try:
            # 確保父目錄存在
            os.makedirs(os.path.dirname(self.speaking_state_file), exist_ok=True)
            state_data = {"speaking": speaking, "text": text, "timestamp": time.time()}
            # 寫入 JSON（供 HTTP 伺服器環境的 fetch 輪詢使用）
            with open(self.speaking_state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, ensure_ascii=False)
            # 同時輸出 JS 腳本（供本機 file:// 協議環境繞過 CORS 使用）
            js_path = os.path.join(os.path.dirname(self.speaking_state_file), "speaking_state.js")
            js_content = f"window.speakingState = {json.dumps(state_data, ensure_ascii=False)};"
            with open(js_path, "w", encoding="utf-8") as f:
                f.write(js_content)
        except Exception:
            pass

    def reload_profiles(self):
        """核心載入模組：載入大腦靈魂、主人設定、歷史回憶與項目插件配置"""
        self.api_exhausted = False  # 重新載入時重置 API 額度狀態
        # 1. 讀取主人背景
        self.host_info = self._read_file("player_profile", "host_info.txt")
        
        # 2. 讀取大腦靈魂調性與通用技能
        self.identity = self._read_file("brain_profile", "identity.txt")
        self.base_skill_general = self._read_file("brain_profile", "base_skills", "general.txt")
        self.base_skill_language = self._read_file("brain_profile", "base_skills", "language.txt")
        
        # 3. 讀取遊戲/項目插件配置 (plugin_config.json) 與專屬技能常識庫
        self.game_skills = {}
        self.plugin_config = {}
        
        is_casual_mode = not self.active_project or self.active_project.lower() == "none"
        plugin_config_path = os.path.join(self.base_dir, "game_tools", self.active_project, "plugin_config.json")
        if not is_casual_mode and os.path.exists(plugin_config_path):
            try:
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    self.plugin_config = json.load(f)
            except Exception as e:
                print(f"{YELLOW}[WARN] 讀取 plugin_config.json 失敗: {e}，將降級使用通用配置。{RESET}")
                self.plugin_config = {}
        else:
            self.plugin_config = {}

        # 讀取專屬技能 txt
        if is_casual_mode:
            self.game_skills = {"info.txt": "當前處於閒談模式，暫停加載遊戲專屬技能常識庫。"}
        else:
            game_skills_path = os.path.join(self.base_dir, "game_tools", self.active_project, "skills")
            if os.path.exists(game_skills_path):
                for skill_file in glob.glob(os.path.join(game_skills_path, "*.txt")):
                    basename = os.path.basename(skill_file)
                    with open(skill_file, "r", encoding="utf-8") as f:
                        self.game_skills[basename] = f.read()
            else:
                self.game_skills = {"info.txt": f"目前尚無 {self.active_project} 模組的技能檔案。"}

        # 4. 撈取近期日記 (動態讀取最近 3 場，改為 Markdown 格式)
        self.loaded_memories = []
        memory_pattern = os.path.join(self.base_dir, "session_memories", "memory_*.md")
        memory_files = glob.glob(memory_pattern)
        memory_files.sort(reverse=True)
        for mem_file in memory_files[:3]:
            try:
                with open(mem_file, "r", encoding="utf-8") as f:
                    self.loaded_memories.append(f.read())
            except Exception as e:
                pass

    def _read_file(self, *paths):
        full_path = os.path.join(self.base_dir, *paths)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        return f"[未找到檔案: {'/'.join(paths)}]"

    def print_splash(self):
        """炫酷的 CLI 啟動介面"""
        os.system('clear' if os.name == 'posix' else 'cls')
        display_name = self.plugin_config.get("project_display_name", self.active_project.upper())
        print(f"{CYAN}{BOLD}========================================================================={RESET}")
        print(f"{CYAN}{BOLD}     🤖  GEMINI GAME STREAM ENGINE (吉米尼萬用實況助理引擎)  v2.0  🤖{RESET}")
        print(f"{CYAN}{BOLD}========================================================================={RESET}")
        print(f"{BOLD} 【實況主人背景】{RESET} {GREEN}已載入 ({self.streamer_name}){RESET}")
        print(f"{BOLD} 【大腦靈魂設定】{RESET} {GREEN}已載入 (Gemini / 實況助理核心){RESET}")
        print(f"{BOLD} 【雙向聽覺系統】{RESET} {GREEN if HAS_SPEECH else YELLOW}已配置 (OBS Web 麥克風側聽伺服器){RESET}")
        print(f"{BOLD} 【當前插件外掛】{RESET} {YELLOW}{BOLD}{display_name}{RESET} {GREEN}已載入 ({len(self.game_skills)} 個常識庫檔案){RESET}")
        print(f"{BOLD} 【近期日記記憶】{RESET} {GREEN}已喚醒最近 {len(self.loaded_memories)} 場直播記憶日記{RESET}")
        
        # 顯示輸入模式狀態
        mode_str = "雙模並存 (鍵盤打字 + OBS Web 語音側聽)"
        if self.input_mode == "keyboard":
            mode_str = "純鍵盤模式 (語音監聽已停用)"
        elif self.input_mode == "voice":
            mode_str = "純語音模式 (鍵盤作為備援)"
        print(f"{BOLD} 【實況輸入模式】{RESET} {GREEN if self.input_mode != 'keyboard' else YELLOW}{mode_str}{RESET}")
        
        # 顯示 API Key 加載與客戶端狀態
        if self.client:
            print(f"{BOLD} 【雲端語音大腦】{RESET} {GREEN}連線成功 (真實 Gemini API | 模型: {self.gemini_model}){RESET}")
        else:
            print(f"{BOLD} 【雲端語音大腦】{RESET} {RED}未加載 (使用「本地模擬引擎」。請在 config.json 填入有效的 gemini_api_key){RESET}")
            
        # 顯示 OBS 眼睛狀態
        obs_cfg = self.config.get("obs_websocket", {})
        if obs_cfg.get("enabled", False):
            print(f"{BOLD} 【實體實況眼睛】{RESET} {GREEN if HAS_OBS else YELLOW}OBS WebSocket 啟用 ({obs_cfg.get('host')}:{obs_cfg.get('port')}){RESET}")
        else:
            print(f"{BOLD} 【實體實況眼睛】{RESET} {YELLOW}已停用 (將降級使用系統螢幕截圖 / test_gameplay.jpg){RESET}")
        
        print(f"{CYAN}========================================================================={RESET}")
        print(f"{YELLOW}💡 雙通道聽覺監聽模式準備就緒...{RESET}")
        is_casual_mode = not self.active_project or self.active_project.lower() == "none"
        if is_casual_mode:
            print(f"👉 當前處於閒談模式，不進行畫面截圖。輸入或對話中提到「{CYAN}Gemini{RESET}」即可與助理進行一般日常對話！")
        else:
            print(f"👉 說話或輸入「{CYAN}gemini你看{RESET}」即可觸發 OBS / 桌面的 480p 畫面多模態視覺解讀！")
        
        # 動態顯示關鍵字提示，如果 plugin_config 內有配置 triggers
        triggers = self.plugin_config.get("triggers", [])
        if triggers:
            kws = []
            for t in triggers:
                kws.extend(t.get("keywords", []))
            if kws:
                print(f"👉 本地觸發關鍵字: {', '.join(f'「{CYAN}{kw}{RESET}」' for kw in kws[:5])}")
                
        print(f"👉 特殊指令: {BOLD}switch <project_name>{RESET} (熱切換遊戲), {BOLD}status{RESET} (監測 TPM), {BOLD}exit{RESET} (提煉日記並收播)")
        print(f"{CYAN}========================================================================={RESET}\n")

    def display_status(self):
        """顯示目前的詳細核心數值"""
        print(f"\n{MAGENTA}{BOLD}[ENGINE STATUS]{RESET}")
        print(f" ├─ 當前掛載項目: {YELLOW}{BOLD}{self.active_project}{RESET}")
        print(f" ├─ 近一分鐘 TPM: {GREEN if self.tpm_tracker.current_tpm < self.tpm_tracker.warning_threshold else RED}{self.tpm_tracker.current_tpm:,} / {self.tpm_tracker.limit:,}{RESET}")
        print(f" ├─ 今日互動次數: {CYAN}{self.roast_count} 次{RESET}")
        print(f" └─ 當前實況氛圍: {GREEN}{self.vibe_score}% Vibe{RESET}\n")
