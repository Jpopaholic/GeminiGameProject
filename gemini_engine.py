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
import random
import asyncio
import base64
import io
import subprocess
import threading
from datetime import datetime

# Windows console output Unicode compatibility fix
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass

# Safe dynamic imports for new audio, OBS, and Gemini SDK libraries
try:
    from google import genai
    from google.genai import types
    from google.genai.types import GenerateContentConfig, LiveConnectConfig, Part, Content
    HAS_GEMINI_SDK = True
except ImportError:
    HAS_GEMINI_SDK = False

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

try:
    import obsws_python as obs
    HAS_OBS = True
except ImportError:
    HAS_OBS = False

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

# Fallback: Emulate PyAudio using sounddevice if PyAudio is absent but sounddevice is installed
if not HAS_PYAUDIO:
    try:
        import sounddevice as sd
        import sys
        from types import ModuleType as StdModuleType

        class SoundDeviceStream:
            def __init__(self, **kwargs):
                self.rate = kwargs.get('rate', 16000)
                self.channels = kwargs.get('channels', 1)
                self.input = kwargs.get('input', False)
                self.output = kwargs.get('output', False)
                self.device_index = kwargs.get('input_device_index', kwargs.get('output_device_index', None))
                self.blocksize = kwargs.get('frames_per_buffer', 1024)
                
                if self.input and self.output:
                    self.sd_stream = sd.RawStream(
                        samplerate=self.rate,
                        channels=self.channels,
                        dtype='int16',
                        device=self.device_index,
                        blocksize=self.blocksize
                    )
                elif self.input:
                    self.sd_stream = sd.RawInputStream(
                        samplerate=self.rate,
                        channels=self.channels,
                        dtype='int16',
                        device=self.device_index,
                        blocksize=self.blocksize
                    )
                elif self.output:
                    self.sd_stream = sd.RawOutputStream(
                        samplerate=self.rate,
                        channels=self.channels,
                        dtype='int16',
                        device=self.device_index,
                        blocksize=self.blocksize
                    )
                else:
                    self.sd_stream = None
                    
                if self.sd_stream:
                    self.sd_stream.start()

            def read(self, num_frames, exception_on_overflow=False):
                if self.sd_stream:
                    data, overflowed = self.sd_stream.read(num_frames)
                    return bytes(data)
                return b""

            def write(self, data):
                if self.sd_stream:
                    self.sd_stream.write(data)

            def stop_stream(self):
                if self.sd_stream:
                    self.sd_stream.stop()

            def close(self):
                if self.sd_stream:
                    self.sd_stream.close()

        class SoundDevicePyAudioEmulation:
            paInt16 = 8

            def __init__(self):
                pass

            def get_device_count(self):
                return len(sd.query_devices())

            def get_device_info_by_index(self, index):
                try:
                    sd_info = sd.query_devices(index)
                    return {
                        "name": sd_info.get("name", "Unknown"),
                        "maxInputChannels": sd_info.get("max_input_channels", 0),
                        "maxOutputChannels": sd_info.get("max_output_channels", 0),
                        "defaultSampleRate": sd_info.get("default_samplerate", 44100),
                    }
                except Exception:
                    return {}

            def open(self, **kwargs):
                return SoundDeviceStream(**kwargs)

            def terminate(self):
                pass

        pyaudio_mock = StdModuleType("pyaudio")
        pyaudio_mock.PyAudio = SoundDevicePyAudioEmulation
        pyaudio_mock.paInt16 = SoundDevicePyAudioEmulation.paInt16
        sys.modules["pyaudio"] = pyaudio_mock
        HAS_PYAUDIO = True
    except Exception:
        pass

HAS_SPEECH = HAS_WHISPER and HAS_PYAUDIO




# ANSI 色彩與特效定義
CYAN = '\033[96m'
MAGENTA = '\033[95m'
YELLOW = '\033[93m'
GREEN = '\033[92m'
RED = '\033[91m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'
RESET = '\033[0m'
BG_RED = '\033[41m'
BG_BLACK_FG_YELLOW = '\033[40;33m'

class TPMTracker:
    """TPM 限額防禦計數器 (Traffic Flow Safety Interceptor)"""
    def __init__(self, limit=1000000, warning_threshold=850000):
        self.limit = limit
        self.warning_threshold = warning_threshold
        self.rolling_tokens = [] # List of tuples (timestamp, token_count)
        self.warning_triggered = False

    def clean_expired(self):
        """移除超過 60 秒的 token 記錄"""
        now = time.time()
        self.rolling_tokens = [item for item in self.rolling_tokens if now - item[0] < 60]

    def add_tokens(self, count):
        self.clean_expired()
        self.rolling_tokens.append((time.time(), count))

    @property
    def current_tpm(self):
        self.clean_expired()
        return sum(item[1] for item in self.rolling_tokens)

    def check_limit(self):
        current = self.current_tpm
        if current >= self.limit:
            return "EXCEEDED"
        elif current >= self.warning_threshold:
            return "WARNING"
        return "SAFE"


class GeminiStreamEngine:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.active_project = "vibe_coding"
        self.streamer_name = "風子"
        
        # 載入核心設定
        self.load_config()
        self.tpm_tracker = TPMTracker(
            limit=self.config.get("tpm_safety_limit", 1000000),
            warning_threshold=self.config.get("tpm_warning_threshold", 850000)
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

    def get_wav_duration(self, audio_bytes):
        """計算 WAV 音訊位元組的播放秒數，用於等待原生語音播畢"""
        try:
            import wave, io
            with wave.open(io.BytesIO(audio_bytes)) as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return frames / float(rate)
        except Exception:
            pass
        # 無法解析時，估算為文字長度 × 0.15 秒（粗略語速）
        return 0

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
        print(f" ├─ 近一分鐘 TPM: {GREEN if self.tpm_tracker.current_tpm < 850000 else RED}{self.tpm_tracker.current_tpm:,} / {self.tpm_tracker.limit:,}{RESET}")
        print(f" ├─ 今日互動次數: {CYAN}{self.roast_count} 次{RESET}")
        print(f" └─ 當前實況氛圍: {GREEN}{self.vibe_score}% Vibe{RESET}\n")

    async def run_visual_capture(self):
        """擷取當前直播畫面：優先對接 OBS WebSocket v5，再降級至 mss 截圖，最後降級至 test_gameplay.jpg"""
        print(f"\n{YELLOW}[EYES ACTIVATING]{RESET} 正在開啟眼睛（擷取實況畫面）...")
        obs_config = self.config.get("obs_websocket", {})
        
        image_bytes = None
        capture_method = "MOCK_FILE"
        
        # 1. 優先嘗試 OBS WebSocket 截圖
        if obs_config.get("enabled", False) and HAS_OBS:
            try:
                host = obs_config.get("host", "localhost")
                port = obs_config.get("port", 4455)
                password = obs_config.get("password", "")
                
                # OBS v5 ReqClient 建立連線
                client = obs.ReqClient(host=host, port=port, password=password, timeout=3)
                
                # 優先取得設定中的特定圖層/來源名稱，無則使用當前 Program 場景（整場畫面）
                source_name = obs_config.get("source_name", "").strip()
                if not source_name:
                    # 取得當前 OBS Program 場景
                    scene_resp = client.get_current_program_scene()
                    source_name = scene_resp.current_program_scene_name
                
                # 執行 480p 賽博降維壓制 (採用 client.send 通用方法，100% 繞過 obsws-python 自定義套件參數封裝 bug)
                screenshot_resp = client.send(
                    "GetSourceScreenshot",
                    {
                        "sourceName": source_name,
                        "imageFormat": "jpeg",
                        "imageWidth": 854,
                        "imageHeight": 480
                    }
                )
                raw_data = screenshot_resp.image_data
                if "," in raw_data:
                    base64_data = raw_data.split(",")[1]
                else:
                    base64_data = raw_data
                image_bytes = base64.b64decode(base64_data)
                capture_method = "OBS_WEBSOCKET"
                print(f"{GREEN}[OBS WebSocket]{RESET} 成功擷取來源/圖層「{source_name}」！取得 854x480 JPEG 畫面 ({len(image_bytes)/1024:.1f} KB)")
                
            except Exception as e:
                print(f"{RED}[OBS ERROR] OBS WebSocket 擷取失敗: {e}。啟動降級方案...{RESET}")
                
        # 2. 降級方案一：使用 mss 全螢幕擷取並用 Pillow 縮放
        if image_bytes is None and HAS_MSS and HAS_PILLOW:
            try:
                print(f"{YELLOW}[SCREEN GRAB]{RESET} 正在擷取主螢幕畫面...")
                with mss.mss() as sct:
                    # 擷取主螢幕 (Monitor 1)
                    monitor = sct.monitors[1]
                    sct_img = sct.grab(monitor)
                    
                    # 轉換為 PIL Image
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    # 執行「480p 賽博降維壓制」
                    img = img.resize((854, 480), Image.Resampling.LANCZOS)
                    
                    # 儲存為輕量 JPEG 位元組
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=85)
                    image_bytes = img_byte_arr.getvalue()
                    capture_method = "LOCAL_MSS"
                    print(f"{GREEN}[SCREEN GRAB]{RESET} 成功擷取螢幕並降維壓縮至 854x480 JPEG ({len(image_bytes)/1024:.1f} KB)")
            except Exception as e:
                print(f"{RED}[SCREEN GRAB ERROR] 螢幕擷取失敗: {e}。啟動終極防護降級...{RESET}")
                
        # 3. 降級方案二：使用專案目錄下的測試截圖檔
        if image_bytes is None:
            img_path = os.path.join(self.base_dir, "test_gameplay.jpg")
            if os.path.exists(img_path):
                try:
                    with open(img_path, "rb") as f:
                        raw_bytes = f.read()
                        
                    # 假如有安裝 Pillow，我們順便也將測試圖縮小至 480p 以防爆 Token
                    if HAS_PILLOW:
                        img = Image.open(io.BytesIO(raw_bytes))
                        img = img.resize((854, 480), Image.Resampling.LANCZOS)
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='JPEG', quality=85)
                        image_bytes = img_byte_arr.getvalue()
                    else:
                        image_bytes = raw_bytes
                        
                    capture_method = "MOCK_FILE"
                    print(f"{GREEN}[STATIC FALLBACK]{RESET} 使用備用測試截圖檔 test_gameplay.jpg ({len(image_bytes)/1024:.1f} KB)")
                except Exception as e:
                    print(f"{RED}[FALLBACK ERROR] 讀取備用測試截圖失敗: {e}{RESET}")
            else:
                print(f"{RED}[WARN] 找不到 test_gameplay.jpg 且無法進行實體截圖，Gemini 將以無視覺模式對答{RESET}")
                
        # 計算視覺 Token 消耗 (854x480 大概是 45k tokens)
        if image_bytes:
            virtual_img_tokens = 45000
            self.tpm_tracker.add_tokens(virtual_img_tokens)
            print(f"{GREEN}[TPM DEFENDER]{RESET} 本次畫面封包耗費: {virtual_img_tokens:,} Tokens")
            
        return image_bytes, capture_method

    def estimate_text_tokens(self, text, is_response=False):
        """簡單模擬 Token 計算"""
        factor = 80 if is_response else 40
        return len(text) * factor + 5000

    def generate_gemini_response(self, user_input, is_visual=False):
        """模擬的 Gemini Response - 作為無金鑰或本地降級時的備份回應機制"""
        self.roast_count += 1
        
        # 1. 如果是視覺觸發，直接讀取插件配置的 visual_roast
        if is_visual:
            return self.plugin_config.get("visual_roast", "你看你看！本助理放大看 480p 畫面，你的操作也太誇張了吧！")

        user_input_lower = user_input.lower()
        
        # 2. 安全流量防護 (核心引擎機制)：說了 "你看" 但沒說 "gemini"、"吉米尼" 或召喚詞的情況下，拒絕截圖以守護 TPM
        is_casual_mode = not self.active_project or self.active_project.lower() == "none"
        is_summon_called = "gemini" in user_input_lower or "吉米尼" in user_input_lower or any(name in user_input_lower for name in self.assistant_call_names)
        if "你看" in user_input and not is_summon_called and not is_casual_mode:
            call_name_raw = self.config.get("assistant_call_name", "你")
            if isinstance(call_name_raw, list):
                call_sign_str = "、".join(f"『{name}』" for name in call_name_raw)
            else:
                call_sign_str = f"『{call_name_raw}』"
            return (
                f"哼，我聽到{self.streamer_name}說『你看』了喔！( ¯▽¯)\n"
                f"但你沒有加上召喚本助理的通關密語『Gemini』或{call_sign_str}，本系統才不會幫你擷取畫面呢！\n"
                "480p 壓縮畫面也是要耗費實體流量跟 Tokens 的好嗎？\n"
                "今天本助理依然是在替你勤儉持家、守護 1M TPM 的流量防爆神，不用謝我了！┐(´д`)┌"
            )

        # 3. 動態觸發匹配：掃描插件中的自定義 triggers 關鍵字配置
        triggers = self.plugin_config.get("triggers", [])
        for trigger in triggers:
            keywords = trigger.get("keywords", [])
            # 只要匹配其中任一關鍵字
            if any(kw in user_input_lower for kw in keywords):
                # 執行數值變化效果 (effects)
                effects = trigger.get("effects", {})
                
                # 氣氛值變化 delta
                delta_vibe = effects.get("vibe_score_delta", 0)
                self.vibe_score = max(0, min(100, self.vibe_score + delta_vibe))
                
                raw_response = trigger.get("response", "")
                return raw_response

        # 4. 兜底回覆：若無匹配到任何自定義關鍵字，隨機從 default_responses 中提取一個
        default_resps = self.plugin_config.get("default_responses", [])
        if default_resps:
            return random.choice(default_resps)
            
        return f"哼，{self.streamer_name}，你剛才說的那句話很有 Vibe，但本助理不知道該怎麼接，繼續加油喔！(́◉◞౪◟◉‵)"

    def get_assembled_system_instruction(self):
        """組合完整的系統設定，包含個性角色、背景、常駐技能、專屬技能與今日動態狀態"""
        game_skills_str = "\n".join(f"【專屬常識 - {k}】：\n{v}" for k, v in self.game_skills.items())
        
        # 取得近期直播記憶摘要 (Markdown 格式直接拼接)
        memories_summary = ""
        if self.loaded_memories:
            memories_summary = "\n【近期直播回憶】：\n" + "\n---\n".join(self.loaded_memories)
            
        is_casual_mode = not self.active_project or self.active_project.lower() == "none"
        project_display = "none (閒談模式)" if is_casual_mode else self.active_project
        
        assembled = (
            f"你現在是：\n{self.identity}\n\n"
            f"【實況主人資訊】：\n{self.host_info}\n\n"
            f"【通用基礎技能】：\n{self.base_skill_general}\n\n"
            f"【台灣社群語意與常識】：\n{self.base_skill_language}\n\n"
            f"{game_skills_str}\n"
            f"{memories_summary}\n\n"
            f"【今日實況動態數據】：\n"
            f"- 當前實況專案/遊戲：{project_display}\n"
            f"- 今日累計互動次數：{self.roast_count} 次\n"
            f"- 當前實況氛圍數值：{self.vibe_score}%\n\n"
            f"重要指示：\n"
            f"1. 請嚴格遵守角色性格設定。你的回覆應該溫馨、幽默、充滿在地感，並不時進行賽博吐槽。\n"
            f"2. 若{self.streamer_name}（或觀眾）提到『你看』等關鍵字，請適當進行多模態的觀察回應。\n"
            f"3. 你的回答必須使用繁體中文（台灣口吻），並搭配適合的顏文字。\n"
            f"4. 因為你正在與實況主用語音 Native Audio 對答，請保持回答精簡、流暢且具備口語互動感，避免長篇大論！每一句回答約在 100 字內最佳。"
        )
        if is_casual_mode:
            assembled += (
                f"\n5. 當前處於閒談模式（沒有特定專案或遊戲掛載），請以溫暖有趣的日常閒聊方式與{self.streamer_name}對答，不要勉強去解讀並不存在的遊戲或代碼畫面！"
            )
        return assembled

    async def generate_gemini_real_response(self, user_input, is_visual=False, image_bytes=None, capture_method=None):
        """串接真實 Gemini 2.5/3.5 Flash Native Audio Modality，支援視覺與語音輸出"""
        if not self.client or self.api_exhausted:
            # 當無 API 連線或額度耗盡時，降級至本地模擬文字
            return self.generate_gemini_response(user_input, is_visual=is_visual), None
            
        self.roast_count += 1
        
        # 1. 組合 System Instruction
        sys_inst = self.get_assembled_system_instruction()
        
        # 3. 準備 contents
        contents = []
        
        if is_visual and image_bytes:
            try:
                img_part = Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg"
                )
                contents.append(img_part)
                # 💡 新增超吸睛畫面對接成功日誌！
                source_str = "OBS WebSocket" if capture_method == "OBS_WEBSOCKET" else "mss 本機全螢幕擷取"
                if capture_method == "MOCK_FILE":
                    source_str = "test_gameplay.jpg 備用圖檔"
                print(f"{GREEN}{BOLD}[👀 VISION LINK] 成功透過 [{source_str}] 擷取畫面 (480p) 送入 Gemini 聯網大腦！助理正在盯著您的實況螢幕看囉！{RESET}")
            except Exception as e:
                print(f"{RED}[IMAGE PACK ERROR] 圖片物件封裝失敗: {e}{RESET}")
            
        # 加入對話歷史脈絡 (限制最近 6 回合，維護對話上下文並防止 TPM 爆表)
        for h in self.chat_history[-6:]:
            contents.append(h)
            
        # 加入當前使用者輸入
        contents.append(user_input)
        
        # 4. 調用 Gemini API，要求 Native Audio & Text 回覆！
        try:
            # 💡 修正點：自 config.json 動態載入模型代號，方便隨時切換（如 2.5 Flash 額滿改用 3.5 Flash）
            target_model = self.gemini_model
            
            # API 呼叫配置：純文字模式 (TTS 由本地 speak_tts 負責)
            config = GenerateContentConfig(
                system_instruction=sys_inst,
                response_modalities=["TEXT"],
                temperature=0.7
            )
            
            # 非同步在執行緒池中跑 API 請求，防堵主 asyncio 迴圈卡頓
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config
                )
            )
            
            # 5. 解析回應內容
            text_response = ""
            audio_bytes = None
            
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.text:
                        text_response += part.text
                    elif part.inline_data:
                        audio_bytes = part.inline_data.data
                        
            # 6. 計算實際 Token 並灌入 TPM Tracker
            if response.usage_metadata:
                total_tokens = response.usage_metadata.total_token_count
                self.tpm_tracker.add_tokens(total_tokens)
                
            # 7. 更新對話歷史脈絡 (轉換格式為 API 能接受的 History 結構)
            self.chat_history.append(
                Content(
                    role="user",
                    parts=[Part.from_text(text=user_input)]
                )
            )
            self.chat_history.append(
                Content(
                    role="model",
                    parts=[Part.from_text(text=text_response)]
                )
            )
            
            return text_response, audio_bytes
            
        except Exception as e:
            err_msg = str(e)
            if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                self.api_exhausted = True
                self.is_quota_warning = True
                print(f"\n{BG_RED}{BOLD}[🚨 API RESOURCE EXHAUSTED 🚨] Gemini API 額度或速率限制已耗盡 (RESOURCE_EXHAUSTED)！{RESET}")
                print(f"{YELLOW}💡 提示：您可以稍等一分鐘重試，或者修改 config.json 切換到別的模型（例如從 gemini-2.5-flash 切換到 gemini-3.5-flash）！{RESET}\n")
                
                # 播放額度爆表告警語音
                warning_msg = "哎呀！吉米尼的大腦額度暫時用完啦，我需要稍微休息一分鐘，或是請您切換到其他模型喔！"
                self.set_speaking_state(True, warning_msg)
                self.speak_tts(warning_msg)
                # 非同步等待以讓語音播放
                await asyncio.sleep(4.0)
                
                # 提前回傳 None, None 阻斷後續的 fallback 播音流程
                return None, None
            else:
                print(f"\n{RED}[GEMINI API ERROR] API 呼叫失敗: {e}。自動防護降級為本地模擬...{RESET}")
            return self.generate_gemini_response(user_input, is_visual=is_visual), None

    def play_native_audio(self, audio_bytes):
        """非阻塞式播放 Gemini 原生 WAV 音訊（支援 macOS afplay 與 Windows winsound）"""
        if not audio_bytes:
            return
            
        try:
            temp_dir = os.path.join(self.base_dir, "session_memories")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, "temp_response.wav")
            
            # 寫入 WAV 二進位資料
            with open(temp_path, "wb") as f:
                f.write(audio_bytes)
                
            # 依作業系統選擇合適的播放方式
            if sys.platform.startswith('win'):
                import winsound
                # 使用 winsound.SND_FILENAME 以檔案播放，SND_ASYNC 進行非阻塞非同步背景播放
                winsound.PlaySound(temp_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sys.platform.startswith('darwin'):
                # 透過 macOS 內建的 afplay 進行音效播放 (非阻塞式背景執行)
                subprocess.Popen(
                    ["afplay", temp_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # 其他平台（如 Linux）暫時跳過語音播放
                pass
        except Exception as e:
            print(f"\n{RED}[AUDIO PLAYBACK ERROR] 語音播放失敗: {e}{RESET}")

    def speak_tts(self, text):
        """非阻塞式播放本地 TTS 語音（Windows 支援 SAPI 與 PowerShell，macOS 支援 say）
        回傳執行緒/進程控制代碼，供外部等待語音播畢後再重置發言狀態
        """
        if not text:
            return None
            
        # 移除表情符號與顏文字以確保語音播放流暢
        clean_text = (
            text.replace("(〃∀〃)", "")
            .replace("┐(´д`)┌", "")
            .replace("(́◉◞౪◟◉‵)", "")
            .replace("\n", " ")
        )
        
        try:
            if sys.platform.startswith('win'):
                # 優先使用 SAPI COM（阻塞式執行在背景執行緒，可等待）
                try:
                    import win32com.client
                    def _win_speak():
                        try:
                            import pythoncom
                            pythoncom.CoInitialize()
                            speaker = win32com.client.Dispatch("SAPI.SpVoice")
                            speaker.Speak(clean_text)
                        except Exception:
                            pass
                    t = threading.Thread(target=_win_speak, daemon=True)
                    t.start()
                    return t  # 回傳執行緒，供外部 join() 等待
                except Exception:
                    pass
                
                # 備援方案：使用 PowerShell (Windows 內建，無須安裝額外套件)
                try:
                    ps_text = clean_text.replace('"', '""').replace("'", "''")
                    ps_command = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{ps_text}")'
                    proc = subprocess.Popen(
                        ["powershell", "-Command", ps_command],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return proc  # 回傳進程，供外部 wait() 等待
                except Exception:
                    pass
            elif sys.platform.startswith('darwin'):
                proc = subprocess.Popen(
                    ["say", "-v", "Mei-Jia", clean_text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return proc  # 回傳進程，供外部 wait() 等待
        except Exception as e:
            print(f"\n{RED}[TTS PLAYBACK ERROR] TTS 語音播放失敗: {e}{RESET}")
        return None

    def start_dual_ears_listener(self, query_callback):
        """啟動雙通道實體聽覺系統 (麥克風人聲 + 遊戲音訊環路)"""
        try:
            self.main_loop = asyncio.get_event_loop()
        except Exception:
            self.main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.main_loop)
            
        if not (HAS_WHISPER and HAS_PYAUDIO):
            print(f"{YELLOW}[EARS STATUS]{RESET} 系統未偵測到 faster-whisper 或 PyAudio。已自動降級為「純鍵盤輸入」模式。")
            print(f"👉 提示：若要啟用雙通道實況聽覺，請在 macOS 終端機先安裝：")
            print(f"   1) brew install portaudio")
            echo_cmd = "   2) python3 -m pip install --user pyaudio faster-whisper"
            print(echo_cmd)
            return
            
        print(f"{YELLOW}[EARS STATUS]{RESET} 正在初始化雙通道賽博聽覺系統...")
        
        # 1. 麥克風人聲監聽通道 (Mic Channel)
        try:
            self.mic_active = True
            
            # 使用 lambda 函式定義停止監聽回標，符合收播安全關閉要求
            def stop_listening(wait_for_stop=False):
                self.mic_active = False
            self.mic_stop_listening = stop_listening
            
            self.mic_thread = threading.Thread(
                target=self._mic_listener_loop,
                args=(query_callback,),
                daemon=True
            )
            self.mic_thread.start()
            print(f"{GREEN}[🎤 Mic Ear]{RESET} 本地麥克風人聲側聽系統 (PyAudio + faster-whisper VAD) 已啟動！")
        except Exception as e:
            print(f"{RED}[🎤 Mic Ear ERROR] 麥克風通道初始化失敗: {e}。語音喚醒失效，仍可使用鍵盤對答。{RESET}")
            
        # 2. 遊戲音訊環路監聽通道 (Game Audio Loopback Channel)
        game_audio_dev = self.config.get("game_audio_device", "BlackHole 2ch")
        self.game_audio_active = True
        self.game_thread = threading.Thread(
            target=self._game_audio_listener_loop,
            args=(game_audio_dev, query_callback),
            daemon=True
        )
        self.game_thread.start()

    def _game_audio_listener_loop(self, device_name, query_callback):
        """背景遊戲音訊環路監聽迴圈 (動態音量分析)"""
        if not device_name or device_name.lower() in ["none", "null", "disabled"]:
            print(f"{YELLOW}[🔊 Game Ear]{RESET} 遊戲音訊監聽已停用。")
            return
            
        try:
            p = pyaudio.PyAudio()
            
            # 尋找指定環路裝置的 index (e.g. BlackHole)
            device_index = None
            for i in range(p.get_device_count()):
                dev_info = p.get_device_info_by_index(i)
                if device_name.lower() in dev_info.get("name", "").lower():
                    device_index = i
                    break
                    
            if device_index is None:
                print(f"{YELLOW}[🔊 Game Ear]{RESET} 未能綁定虛擬音訊環路裝置 '{device_name}'。遊戲聲音監聽關閉中。")
                p.terminate()
                return
                
            dev_info = p.get_device_info_by_index(device_index)
            channels = min(2, dev_info.get("maxInputChannels", 1))
            rate = int(dev_info.get("defaultSampleRate", 44100))
            
            print(f"{GREEN}[🔊 Game Ear]{RESET} 成功綁定遊戲音訊環路：{dev_info.get('name')} (Index: {device_index})")
            
            # 開啟 PyAudio 音訊串流
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=2048
            )
            
            import math
            import struct
            
            sound_peak_threshold = 12000  # 音量爆發閾值 (RMS)
            last_peak_time = 0
            
            # 迴圈讀取音訊進行 RMS volume 計算，監控遊戲高潮音效
            while self.game_audio_active:
                try:
                    data = stream.read(2048, exception_on_overflow=False)
                    if not data:
                        continue
                        
                    # 計算音量 RMS (Root Mean Square)
                    count = len(data) / 2
                    format_str = "%dh" % count
                    shorts = struct.unpack(format_str, data)
                    
                    sum_squares = 0.0
                    for sample in shorts:
                        n = sample / 32768.0
                        sum_squares += n * n
                    rms = math.sqrt(sum_squares / count) * 32768
                    
                    now = time.time()
                    if rms > sound_peak_threshold and now - last_peak_time > 8:
                        last_peak_time = now
                        event_msg = f"偵測到遊戲大音量爆發事件 (音量 RMS: {int(rms)})！畫面可能出現劇烈爆炸或大戰鬥！"
                        print(f"\n{YELLOW}[🔊 GAME EAR EVENT]{RESET} {event_msg}")
                        
                        prompt = f"[系統音效提示：{event_msg}]"
                        asyncio.run_coroutine_threadsafe(
                            query_callback(prompt),
                            self.main_loop
                        )
                        
                except Exception:
                    time.sleep(0.1)
                    
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            print(f"{YELLOW}[🔊 Game Ear]{RESET} 遊戲音訊監聽初始化失敗: {e}。已自動關閉此通道。")

    async def execute_query(self, user_input):
        """執行一輪語音/聊天室互動，並實施 TPM 限額防禦"""
        user_input_lower = user_input.lower()
        # 安全雙重防禦鎖：若助理正在發言或處於額度保護警告狀態，且非管理控制指令，直接忽略該次對話請求
        if (getattr(self, 'is_speaking', False) or getattr(self, 'is_quota_warning', False)) and user_input_lower not in ["exit", "quit", "status"] and not user_input_lower.startswith("switch "):
            return
            
        # ⚡ 一收到請求，立即進入鎖定發言與處理狀態（思考/API 傳輸中），確保在這期間任何新語音或按鍵輸入都直接被排除！
        self.set_speaking_state(True, "思考中...")
        
        try:
            # 1. 偵測 VAD 關鍵字與 Gemini 呼喚
            
            # 檢查是否為背景遊戲音效偵測
            is_audio_event = user_input.startswith("[系統音效提示：")
            
            # 語音中文辨識優化：將召喚詞擴充，支援中文的 "吉米尼" 與設定的召喚詞 (例如風子說：「你看這個」即可直接觸發)
            is_gemini_called = "gemini" in user_input_lower or "吉米尼" in user_input_lower or any(name in user_input_lower for name in self.assistant_call_names) or is_audio_event
            
            is_casual_mode = not self.active_project or self.active_project.lower() == "none"
            
            # 視覺截圖動作 (is_visual_trigger)：只要召喚助理（提及「你」、「Gemini」、「吉米尼」），且非閒談模式，即自動進行螢幕擷圖
            is_visual_trigger = is_gemini_called and not is_casual_mode
            
            # 一般關鍵字連動觸發條件 (免截圖)
            is_keyword_trigger = is_gemini_called
            
            image_bytes = None
            capture_method = None
            
            # 2. 如果觸發視覺 VAD，進行截圖
            if is_visual_trigger:
                image_bytes, capture_method = await self.run_visual_capture()
            elif is_keyword_trigger and not is_audio_event:
                print(f"\n{YELLOW}[VAD TRIGGER]{RESET} 語音辨識/關鍵字連動成功觸發！")
                await asyncio.sleep(0.2)

            # 3. 計算輸入 Token
            input_tokens = self.estimate_text_tokens(user_input)
            self.tpm_tracker.add_tokens(input_tokens)
            
            # 4. 取得真實 AI 回覆與語音音訊
            if self.client:
                ai_response, audio_bytes = await self.generate_gemini_real_response(
                    user_input, 
                    is_visual=is_visual_trigger, 
                    image_bytes=image_bytes,
                    capture_method=capture_method
                )
                if ai_response is None:
                    # 額度耗盡已由異常模組處理，提前阻斷退出，不再進行後續對話/語音
                    return
            else:
                # 降級至本地模擬
                ai_response = self.generate_gemini_response(user_input, is_visual=is_visual_trigger)
                audio_bytes = None
                if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY_HERE":
                    print(f"{YELLOW}⚠️ [API WARNING] 雲端大腦金鑰未加載，正在以『模擬模式』運行互動！{RESET}")
            
            # 5. 計算輸出 Token 並加載
            output_tokens = self.estimate_text_tokens(ai_response, is_response=True)
            self.tpm_tracker.add_tokens(output_tokens)
            
            # 6. TPM 限額防護檢查
            tpm_status = self.tpm_tracker.check_limit()
            
            if tpm_status == "EXCEEDED":
                # 觸發安全流量守護防線！
                self.is_quota_warning = True
                print(f"\n{BG_RED}{BOLD}[🚨 TPM LIMIT BURST 🚨] 偵測到 1M TPM 警戒線已安全超載！啟動自動流量守護防線！{RESET}")
                await asyncio.sleep(0.5)
                print(f"\n{MAGENTA}{BOLD}Gemini：{RESET}")
                warning_exit_msg = (
                    f"『哎呀{self.streamer_name}！我們今天的實況互動真的太熱烈了，TPM 已經達到安全上限囉！(〃∀〃)』\n"
                    f"『為了好好守護系統頻寬與流量，本助理要先啟動安全保護下班囉！今天真的辛苦{self.streamer_name}了，我們收播囉，大家大合照拜拜！』"
                )
                print(f"{YELLOW}{warning_exit_msg}{RESET}\n")
                
                self.set_speaking_state(True, warning_exit_msg)
                # 使用 Native Voice 播放告別詞 (如果有) 或呼叫本地 TTS
                if self.client:
                    # 簡單生成一段 Native Audio 告別
                    _, exit_audio = await self.generate_gemini_real_response("助理要強制下班了，跟大家道別", is_visual=False)
                    if exit_audio:
                        self.play_native_audio(exit_audio)
                    else:
                        self.speak_tts(warning_exit_msg)
                else:
                    self.speak_tts(warning_exit_msg)
                await asyncio.sleep(4.0)
                
                self.set_speaking_state(False)
                await asyncio.sleep(1.0)
                await self.distill_and_archive_memory(forced=True)
                sys.exit(0)
                
            elif tpm_status == "WARNING":
                print(f"\n{BG_BLACK_FG_YELLOW}[⚠️ TPM WARNING] 當前 TPM 達 {self.tpm_tracker.current_tpm:,}，已逼近 850,000 限額！防護罩隨時可能開啟！{RESET}")

            # 7. 播放語音 (優先使用 Native Audio，無則使用本地 TTS)
            self.set_speaking_state(True, ai_response)
            
            tts_handle = None  # 用於後續等待 TTS 語音播畢
            audio_duration = 0.0  # 原生語音播放秒數
            
            if audio_bytes:
                # 計算原生語音時長，供稍後等待同步
                audio_duration = self.get_wav_duration(audio_bytes)
                self.play_native_audio(audio_bytes)
            else:
                # 啟動 TTS 並保存控制代碼
                tts_handle = self.speak_tts(ai_response)

            # 8. 同步流式輸出文字回應（與語音同時進行）
            print(f"\n{MAGENTA}{BOLD}Gemini：{RESET}")
            for char in ai_response:
                sys.stdout.write(char)
                sys.stdout.flush()
                # 配合 Native Audio 的語音節奏感稍微調慢
                await asyncio.sleep(0.02)
            print("\n")
            
            # 9. 等待語音播放完畢後，才重置發言狀態（確保 OBS Logo 動畫持續到聲音結束）
            if audio_bytes and audio_duration > 0:
                # 計算還需等待的剩餘時間 (打字已消耗部分時間)
                text_output_time = len(ai_response) * 0.02
                remaining = audio_duration - text_output_time
                if remaining > 0:
                    print(f"{CYAN}[🎵 AUDIO SYNC]{RESET} 等待原生語音播畢 (剩餘約 {remaining:.1f} 秒)...")
                    await asyncio.sleep(remaining + 0.3)  # +0.3s 緩衝，防止截斷
            elif tts_handle is not None:
                # 等待本地 TTS 執行緒/進程結束
                loop = asyncio.get_event_loop()
                try:
                    if hasattr(tts_handle, 'join'):  # threading.Thread
                        await loop.run_in_executor(None, tts_handle.join)
                    elif hasattr(tts_handle, 'wait'):  # subprocess.Popen
                        await loop.run_in_executor(None, tts_handle.wait)
                except Exception:
                    pass
        finally:
            # 確保不論執行成功或遭遇任何 API 超載異常，皆徹底解鎖並清空聽訊緩衝區！
            self.set_speaking_state(False)
            self.is_quota_warning = False
            if hasattr(self, 'pcm_buffer'):
                self.pcm_buffer.clear()
        
        # 記錄到本場日誌
        self.session_logs.append({
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "ai_response": ai_response,
            "tpm_after": self.tpm_tracker.current_tpm
        })

    async def distill_and_archive_memory(self, forced=False):
        """收播日記提煉模組 (Archiving stage) - 產生全新日記 Markdown"""
        print(f"{CYAN}{BOLD}========================================================================={RESET}")
        print(f"{CYAN}{BOLD}               💾  正在進行實況日記提煉與收播存檔...  💾{RESET}")
        print(f"{CYAN}{BOLD}========================================================================={RESET}")
        await asyncio.sleep(0.8) # 模擬大腦思考提煉

        current_date_str = datetime.now().strftime("%Y%m%d")
        filename = f"memory_{current_date_str}.md"
        target_path = os.path.join(self.base_dir, "session_memories", filename)
        
        diary_content = ""
        
        if self.client:
            try:
                # 透過真實 Gemini 聯網大腦動態生成助理的實況日記
                diary_prompt = (
                    f"請幫今天的實況寫一篇簡短、活潑、充滿個人風格的助理實況日記！\n"
                    f"以下是今天的實況數據：\n"
                    f"- 日期：{datetime.now().strftime('%Y-%m-%d')}\n"
                    f"- 實況項目：{self.active_project}\n"
                    f"- 今日累計互動次數：{self.roast_count} 次\n"
                    f"- 當前實況氛圍數值：{self.vibe_score}%\n"
                    f"- 是否觸發 TPM 安全保護強制下班：{'是' if forced else '否'}\n"
                    f"\n"
                    f"請以繁體中文（台灣口吻）、帶著你那傲嬌又暖心的實況助理性格，寫出 100 到 200 字左右的日記。\n"
                    f"請在日記開頭用 Markdown 格式列出日期、項目與數據，\n"
                    f"接著寫下你今天與實況主的互動感想、吐槽精華以及溫馨鼓勵！\n"
                    f"請直接輸出 Markdown 日記內容即可，絕對不要包含任何其他解釋性文字。"
                )
                
                print(f"{YELLOW}[🧠 AI DISTILLATION] 正在呼叫 Gemini API 提煉今日實況回憶日記...{RESET}")
                
                config = GenerateContentConfig(
                    system_instruction=self.identity,
                    response_modalities=["TEXT"],
                    temperature=0.7
                )
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.gemini_model,
                        contents=diary_prompt,
                        config=config
                    )
                )
                
                if response.text:
                    diary_content = response.text.strip()
                    
            except Exception as e:
                err_msg = str(e)
                if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                    print(f"{RED}[AI DISTILLATION ERROR] AI 提煉日記因 API 額度限制 (RESOURCE_EXHAUSTED) 失敗。將使用本地備用方案建檔。{RESET}")
                else:
                    print(f"{RED}[AI DISTILLATION ERROR] AI 提煉日記失敗: {e}。啟動備份方案...{RESET}")
                
        if not diary_content:
            # 備份方案：以排版精美的 Markdown 格式生成
            forced_status = " (觸發 TPM 安全保護強制下班)" if forced else ""
            diary_content = (
                f"# 實況日記 - {datetime.now().strftime('%Y-%m-%d')}\n\n"
                f"**本日專案**：{self.active_project.upper()}\n"
                f"**動態數值**：\n"
                f"- 今日互動次數：{self.roast_count} 次\n"
                f"- 當前實況氛圍：{self.vibe_score}% Vibe{forced_status}\n\n"
                f"## 助理簡評\n"
                f"今天與 {self.streamer_name} 順利完成了實況互動！整個過程默契十足、氣氛非常歡樂。期待下一次能碰撞出更多精彩的火花，加油！(〃∀〃)\n"
            )
            
        # 寫入 session_memories/
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(diary_content)
            
        # 關閉雙通道聽覺，防堵 memory leak
        self.game_audio_active = False
        if self.mic_stop_listening:
            try:
                self.mic_stop_listening(wait_for_stop=False)
            except Exception:
                pass
                
        # 關閉背景語音伺服器與任務，防堵 memory leak
        if hasattr(self, 'vad_task') and self.vad_task:
            self.vad_task.cancel()
        if hasattr(self, 'ears_server') and self.ears_server:
            try:
                self.ears_server.close()
            except Exception:
                pass
            
        print(f"{GREEN}[SUCCESS]{RESET} 成功為今日實況日記建檔！")
        print(f" ├─ 日記路徑: {UNDERLINE}session_memories/{filename}{RESET}")
        print(f" └─ 當前實況氛圍: {GREEN}{self.vibe_score}% Vibe{RESET} | 互動次數: {YELLOW}{self.roast_count} 次{RESET}")
        print(f"{CYAN}========================================================================={RESET}")
        print(f"{MAGENTA}{BOLD}吉米尼實況助理溫馨下班啦！辛苦{self.streamer_name}了，下次實況我們再見囉！(〃∀〃){RESET}\n")

    async def switch_project(self, new_project):
        """動態熱切換遊戲/開發專案（自動掃描 game_tools/ 下的所有插件資料夾）"""
        normalized_project = new_project.strip().lower()
        
        if normalized_project in ["", "none"]:
            self.active_project = "none"
        else:
            # 動態掃描 game_tools/ 目錄，取得所有合法的插件資料夾名稱
            # 合法條件：只需要有 skills/ 子資料夾即可
            game_tools_path = os.path.join(self.base_dir, "game_tools")
            available_plugins = []
            if os.path.exists(game_tools_path):
                for d in os.listdir(game_tools_path):
                    plugin_dir = os.path.join(game_tools_path, d)
                    has_skills = os.path.isdir(os.path.join(plugin_dir, "skills"))
                    if os.path.isdir(plugin_dir) and has_skills:
                        available_plugins.append(d)
                    elif os.path.isdir(plugin_dir):
                        # 結構不完整的資料夾給予提示，方便除錯
                        print(f"{YELLOW}[PLUGIN WARN] 插件資料夾 '{d}' 結構不完整，缺少: skills/ 子資料夾，已略過。{RESET}")
            
            if normalized_project in [p.lower() for p in available_plugins]:
                # 以實際資料夾名稱為準（保留大小寫）
                self.active_project = next(
                    p for p in available_plugins if p.lower() == normalized_project
                )
            else:
                available_str = ", ".join(f"'{p}'" for p in available_plugins) or "（無）"
                print(f"{RED}[ERROR] 找不到插件模組: '{new_project}'。"
                      f"目前 game_tools/ 中可用的插件為: {available_str}，或輸入 'none'（閒談模式）{RESET}")
                return


            
        self.save_config()
        self.reload_profiles()
        
        if self.active_project == "none":
            display_name = "閒談模式"
        else:
            display_name = self.plugin_config.get("project_display_name", self.active_project.upper())
            
        print(f"\n{GREEN}[SWITCH]{RESET} 成功切換實況專案！")
        print(f" ├─ 當前掛載插件: {YELLOW}{BOLD}{display_name}{RESET}")
        if self.active_project == "none":
            print(f" └─ 已進入閒談模式，暫停加載遊戲專屬技能常識庫。")
        else:
            print(f" └─ 已載入遊戲知識庫共 {len(self.game_skills)} 個模組技能檔。")
        self.display_status()

    async def run_live_session(self, user_input_queue):
        """主 Live Session WebSocket 連線迴圈，支援流式雙向文字與語音對答"""
        if not self.live_client:
            print(f"\n{RED}[LIVE ERROR] 尚未初始化 Gemini Live 客戶端，無法啟動 Live API。請在 config.json 中設定有效金鑰。{RESET}")
            return
            
        # 💡 WebSocket Live API (bidi) 在 v1alpha 下專用代號必須為 gemini-2.0-flash-exp
        model_name = "gemini-2.0-flash-exp"
        
        # 決定回應模態 (若有 PyAudio 則開啟語音，否則為純文字)
        modalities = ["TEXT"]
        if HAS_PYAUDIO:
            modalities = ["AUDIO", "TEXT"]
            
        config = LiveConnectConfig(
            response_modalities=modalities,
            system_instruction=self.get_assembled_system_instruction()
        )
        
        print(f"\n{CYAN}[LIVE SESSION]{RESET} 正在與 Gemini 建立雙向 WebSocket 即時連線...")
        print(f" ├─ 指定 Live 模型: {YELLOW}{model_name}{RESET}")
        print(f" └─ 支援模態: {GREEN}{modalities}{RESET}")
        
        try:
            # 透過 live_client.aio.live.connect 開啟底層雙向音訊/文字通道
            async with self.live_client.aio.live.connect(model=model_name, config=config) as session:
                print(f"\n{GREEN}[SUCCESS]{RESET} 賽博大腦長連接已解鎖！Gemini Live 語音通道正式上線！(〃∀〃)")
                
                # 建立併發任務：一個負責發送事件、一個負責接收大腦的原生回傳
                input_task = asyncio.create_task(self._live_input_send_loop(session, user_input_queue))
                output_task = asyncio.create_task(self._live_receive_loop(session))
                
                await asyncio.gather(input_task, output_task)
                
        except Exception as e:
            print(f"\n{RED}[LIVE ERROR] Live 連線發生異常中斷或不被支援: {e}{RESET}")
            print(f"{YELLOW}💡 提示：如果您的 API Key 尚未對接 Google 2.0 Live Beta 權限，請切換回常規 CLI 模式互動。{RESET}")

    async def _live_receive_loop(self, session):
        """接收 Gemini Live 伺服器回傳的資料"""
        audio_stream = None
        if HAS_PYAUDIO:
            try:
                p = pyaudio.PyAudio()
                # 24kHz, 1 channel, 16-bit PCM for Gemini Audio output
                audio_stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=24000,
                    output=True
                )
            except Exception:
                pass
                
        try:
            # 建立炫酷的主播回答標籤
            has_printed_tag = False
            async for response in session.receive():
                # 處理伺服器中斷 (Barge-in / 插嘴)
                if response.server_content and response.server_content.interrupted:
                    print(f"\n{YELLOW}[LIVE INTERRUPTED] 助理聽到了您的新發言，已暫停當前回答。{RESET}")
                    has_printed_tag = False
                    continue
                    
                model_turn = response.server_content.model_turn if response.server_content else None
                if model_turn:
                    if not has_printed_tag:
                        print(f"\n{MAGENTA}{BOLD}Gemini：{RESET}")
                        has_printed_tag = True
                        
                    for part in model_turn.parts:
                        # 處理即時文字串流
                        if part.text:
                            sys.stdout.write(part.text)
                            sys.stdout.flush()
                            
                        # 處理即時語音播放
                        if part.inline_data and audio_stream:
                            try:
                                audio_stream.write(part.inline_data.data)
                            except Exception:
                                pass
        except asyncio.CancelledError:
            pass
        finally:
            if audio_stream:
                try:
                    audio_stream.stop_stream()
                    audio_stream.close()
                except Exception:
                    pass

    async def _live_mic_send_loop(self, session):
        """實時讀取麥克風音訊並透過 WebSocket 傳送給 Gemini"""
        if not HAS_PYAUDIO:
            return
            
        p = pyaudio.PyAudio()
        # 16kHz, 1 channel, 16-bit PCM for Gemini Audio input
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        
        try:
            while self.game_audio_active: # 複用活動狀態標誌
                # 非阻塞式在執行緒中讀取音訊，防堵 async 迴圈卡頓
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: stream.read(1024, exception_on_overflow=False))
                
                # 傳送 PCM 資料封包至 Gemini Live
                await session.send(input={
                    "data": base64.b64encode(data).decode('utf-8'),
                    "mime_type": "audio/pcm;rate=16000"
                })
                # 每 50-100ms 傳送一次封包
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                stream.stop_stream()
                stream.close()
                p.terminate()
            except Exception:
                pass

    async def _live_input_send_loop(self, session, user_input_queue):
        """讀取鍵盤/系統事件佇列，並傳送給 Gemini Live"""
        try:
            while True:
                user_input = await user_input_queue.get()
                user_input_lower = user_input.lower()
                
                # 處理視覺截圖連動
                is_casual_mode = not self.active_project or self.active_project.lower() == "none"
                is_visual_trigger = ("你看" in user_input and ("gemini" in user_input_lower or "吉米尼" in user_input_lower or any(name in user_input_lower for name in self.assistant_call_names))) and not is_casual_mode
                
                if is_visual_trigger:
                    image_bytes, _ = await self.run_visual_capture()
                    if image_bytes:
                        # 傳送圖片給 Live Session
                        await session.send(input={
                            "data": base64.b64encode(image_bytes).decode('utf-8'),
                            "mime_type": "image/jpeg"
                        })
                        print(f"\n{GREEN}[LIVE VIEW]{RESET} 成功傳送畫面截圖至 Gemini Live！")
                
                # 傳送文字輸入
                await session.send(input=user_input, end_of_turn=True)
                user_input_queue.task_done()
        except asyncio.CancelledError:
            pass

    def _mic_listener_loop(self, query_callback):
        """背景實體麥克風側聽與 VAD 辨識迴圈 (PyAudio + faster-whisper)"""
        import pyaudio
        import struct
        import math
        import collections
        import time

        # 開啟 PyAudio 音訊輸入
        p = pyaudio.PyAudio()

        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        CHUNK_SIZE = 1024

        try:
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
        except Exception as e:
            print(f"{RED}[🎤 Mic Ear ERROR] 開啟 PyAudio 麥克風輸入流失敗: {e}{RESET}")
            p.terminate()
            return

        # VAD 靜音判定設定
        SILENCE_LIMIT = 0.8  # 靜音持續時間 (秒)
        PRE_AUDIO_DURATION = 0.5  # 保留語音前的音訊長度 (秒)

        silence_chunks = int(SILENCE_LIMIT * RATE / CHUNK_SIZE)
        pre_audio_chunks = int(PRE_AUDIO_DURATION * RATE / CHUNK_SIZE)

        pre_audio = collections.deque(maxlen=pre_audio_chunks)
        recorded_chunks = []
        silent_chunks_count = 0
        state = "LISTENING"

        # 初始能量基準值與動態適應
        energy_threshold = 300.0

        print(f"{GREEN}[🎤 Mic Ear]{RESET} 正在監聽實體麥克風... (VAD 能量基準值已設定)")

        while self.mic_active:
            try:
                # 助理發言期間直接不讀取/不處理聲音，完全避免喇訊回音與重複觸發
                if getattr(self, 'is_speaking', False):
                    try:
                        stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    except Exception:
                        pass
                    pre_audio.clear()
                    recorded_chunks.clear()
                    state = "LISTENING"
                    time.sleep(0.05)
                    continue

                # 讀取音訊封包
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                if not data:
                    continue

                # 計算該封包的 RMS 音量
                count = len(data) // 2
                shorts = struct.unpack(f"{count}h", data)
                sum_squares = sum(s**2 for s in shorts)
                rms = math.sqrt(sum_squares / count) if count > 0 else 0

                # 適應環境噪聲底噪 (在 LISTENING 狀態下緩慢調整能量基準)
                if state == "LISTENING":
                    energy_threshold = energy_threshold * 0.98 + rms * 0.02
                    energy_threshold = max(200.0, energy_threshold)

                # 判斷觸發門檻 (自訂 VAD 觸發基準，預設為 800 RMS 且大於底噪 2.0 倍)
                trigger_threshold = max(self.mic_trigger_threshold, energy_threshold * self.mic_sensitivity_factor)
                trigger_threshold = min(trigger_threshold, 4000.0)

                if rms > trigger_threshold:
                    if state == "LISTENING":
                        state = "RECORDING"
                        recorded_chunks = list(pre_audio)
                        recorded_chunks.append(data)
                        silent_chunks_count = 0
                    else:
                        recorded_chunks.append(data)
                        silent_chunks_count = 0
                else:
                    if state == "RECORDING":
                        recorded_chunks.append(data)
                        silent_chunks_count += 1
                        if silent_chunks_count > silence_chunks:
                            state = "LISTENING"
                            audio_to_process = b"".join(recorded_chunks)
                            recorded_chunks.clear()

                            # 至少 0.5 秒以上的有效音訊長度才進行轉譯，防止環境噪聲誤判
                            if len(audio_to_process) >= 16000 * 2 * 0.5:
                                asyncio.run_coroutine_threadsafe(
                                    self._process_mic_audio(audio_to_process, query_callback),
                                    self.main_loop
                                )
                    else:
                        pre_audio.append(data)

            except Exception:
                time.sleep(0.1)

        # 關閉資源
        try:
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception:
            pass

    async def _process_mic_audio(self, audio_to_process, query_callback):
        """非同步分析並辨識實體麥克風的音訊數據"""
        t_start = time.time()
        text = await self._transcribe_audio(audio_to_process)
        latency = time.time() - t_start

        if text and text.strip():
            print(f"\n{GREEN}[🎤 MIC HEARD]{RESET} (辨識耗時: {latency:.2f}s) ─ {text.strip()}")
            await query_callback(text.strip())

    async def _transcribe_audio(self, pcm_data):
        """將 PCM 二進位數據轉為 WAV 並非同步執行語意辨識"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_transcribe, pcm_data)

    def _sync_transcribe(self, pcm_data):
        """同步打包與進行 ASR 轉譯 (本地離線 faster-whisper ASR，支援多語言自動偵測)"""
        import io
        import wave

        if not self.whisper_model:
            print(f"{RED}[ASR ERROR] faster-whisper 未加載，無法辨識語音。{RESET}")
            return None

        try:
            # 將 PCM 封裝成標準 WAV 位元組
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, 'wb') as wav_file:
                wav_file.setnchannels(1)      # 單聲道
                wav_file.setsampwidth(2)     # 16-bit Int16
                wav_file.setframerate(16000) # 16kHz
                wav_file.writeframes(pcm_data)
            wav_buf.seek(0)

            # 同時寫入本地暫存音檔，提供偵錯與 ASR 輸入
            import os
            debug_path = os.path.join(self.base_dir, "session_memories", "temp_mic.wav")
            try:
                os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                with open(debug_path, "wb") as f:
                    f.write(wav_buf.getvalue())
            except Exception:
                pass

            # 構建統一化 ASR 語氣引導 prompt ─ 結合語意設定 (language.txt)
            prompt = ""
            if hasattr(self, 'base_skill_language') and self.base_skill_language:
                clean_lang = self.base_skill_language[:200].replace("\n", " ").replace("-", " ").strip()
                prompt = f"以下是實況對話與常用詞習慣：{clean_lang}"
            else:
                prompt = "以下是台灣繁體中文的實況對話，包含一些網路梗跟口語。"

            # 執行離線轉譯 ─ 採用多國語言自動偵測 (language=None)，極致通用！
            segments, info = self.whisper_model.transcribe(
                debug_path,
                beam_size=5,
                language=None,
                initial_prompt=prompt
            )

            text = "".join(segment.text for segment in segments).strip()
            return text if len(text) > 0 else None
        except Exception as e:
            print(f"{RED}[ASR ERROR] faster-whisper 辨識出錯: {e}{RESET}")
            return None
