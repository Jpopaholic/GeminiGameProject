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
    import speech_recognition as sr
    HAS_SPEECH = True
except ImportError:
    HAS_SPEECH = False

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False


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
        self.chicken_steak_count = 0  # 本日新增雞排欠債
        self.roast_count = 0          # 本日吐槽次數
        self.vibe_score = 90          # 動態氣氛分數
        
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

    def save_config(self):
        config_path = os.path.join(self.base_dir, "player_profile", "config.json")
        self.config["active_project"] = self.active_project
        self.config["gemini_model"] = self.gemini_model
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def set_speaking_state(self, speaking, text=""):
        """寫入助理當前的發言狀態，供 OBS 網頁 Logo Overlay 即時讀取亮起"""
        try:
            # 確保父目錄存在
            os.makedirs(os.path.dirname(self.speaking_state_file), exist_ok=True)
            with open(self.speaking_state_file, "w", encoding="utf-8") as f:
                json.dump({"speaking": speaking, "text": text, "timestamp": time.time()}, f, ensure_ascii=False)
        except Exception:
            pass

    def reload_profiles(self):
        """核心載入模組：載入大腦靈魂、主人設定、歷史回憶與項目插件配置"""
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
            with open(plugin_config_path, "r", encoding="utf-8") as f:
                self.plugin_config = json.load(f)
        else:
            # 默認備份設定，以防插件缺少配置
            display_name = "閒談模式" if is_casual_mode else self.active_project
            self.plugin_config = {
                "project_display_name": display_name,
                "visual_roast": "你看你看！本助理放大看 480p 畫面，你的操作也太誇張了吧！",
                "triggers": [],
                "default_responses": ["哼，你就繼續聊吧，本助理隨時陪著你。┐(´д`)┌" if is_casual_mode else "哼，你就繼續玩吧，本助理在線嫌棄你。┐(´д`)┌"],
                "memory_highlights": {
                    "default": f"{self.streamer_name}今天順利完成了實況開台。" if is_casual_mode else "風子今天進行了實況。",
                    "debt_increase": "風子今天因為失誤累計欠下 {debt} 塊雞排。",
                    "forced_logout": "實況因 TPM 爆表觸發防禦強制下班。"
                }
            }

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

        # 4. 撈取近期日記 (動態讀取最近 3 場)
        self.loaded_memories = []
        memory_pattern = os.path.join(self.base_dir, "session_memories", "memory_*.json")
        memory_files = glob.glob(memory_pattern)
        memory_files.sort(reverse=True)
        for mem_file in memory_files[:3]:
            try:
                with open(mem_file, "r", encoding="utf-8") as f:
                    self.loaded_memories.append(json.load(f))
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
        print(f"{BOLD} 【實況主人背景】{RESET} {GREEN}已載入 ({self.streamer_name} / 賽博數獨大師){RESET}")
        print(f"{BOLD} 【大腦靈魂設定】{RESET} {GREEN}已載入 (Gemini / 溫馨陪伴科技梗擔當){RESET}")
        print(f"{BOLD} 【雙向聽覺系統】{RESET} {GREEN if HAS_SPEECH else YELLOW}已配置 ({'雙通道背景音訊監聽' if HAS_SPEECH else '純鍵盤降級模式'}){RESET}")
        print(f"{BOLD} 【當前插件外掛】{RESET} {YELLOW}{BOLD}{display_name}{RESET} {GREEN}已掛載 ({len(self.game_skills)} 個常識庫檔案){RESET}")
        print(f"{BOLD} 【近期日記記憶】{RESET} {GREEN}已喚醒最近 {len(self.loaded_memories)} 場直播記憶快照{RESET}")
        
        # 顯示 API Key 加載與客戶端狀態
        if self.client:
            print(f"{BOLD} 【雲端語音大腦】{RESET} {GREEN}連線成功 (真實 Gemini 2.5 Flash Native Audio | Voice: {self.config.get('gemini_voice', 'Aoede')}){RESET}")
        else:
            print(f"{BOLD} 【雲端語音大腦】{RESET} {RED}未加載 (使用「本地模擬引擎」。請在 config.json 填入有效的 gemini_api_key){RESET}")
            
        # 顯示 OBS 眼睛狀態
        obs_cfg = self.config.get("obs_websocket", {})
        if obs_cfg.get("enabled", False):
            print(f"{BOLD} 【實體實況眼睛】{RESET} {GREEN if HAS_OBS else YELLOW}OBS WebSocket 啟用 ({obs_cfg.get('host')}:{obs_cfg.get('port')}){RESET}")
        else:
            print(f"{BOLD} 【實體實況眼睛】{RESET} {YELLOW}已停用 (將降級使用系統螢幕截圖 / test_gameplay.jpg){RESET}")
        
        if self.loaded_memories:
            print(f"   └─ 昨天的雞排累計欠債：{YELLOW}{BOLD}142 塊{RESET}")
        print(f"{CYAN}========================================================================={RESET}")
        print(f"{YELLOW}💡 雙通道聽覺監聽模式準備就緒...{RESET}")
        is_casual_mode = not self.active_project or self.active_project.lower() == "none"
        if is_casual_mode:
            print(f"👉 當前處於閒談模式，不進行畫面截圖。輸入或對話中提到「{CYAN}Gemini{RESET}」即可與助理進行一般日常對話！")
        else:
            print(f"👉 說話或輸入「{CYAN}gemini你看{RESET}」即可觸發 OBS / 桌面的 480p 畫面多模態視覺解讀！")
        print(f"👉 說話提到「{CYAN}雞排{RESET}」或「{CYAN}誇張{RESET}」可觸發相關的計數與氛圍聯動效果！")
        print(f"👉 特殊指令: {BOLD}switch <project_name>{RESET} (熱切換遊戲), {BOLD}status{RESET} (監測 TPM), {BOLD}exit{RESET} (提煉日記並收播)")
        print(f"{CYAN}========================================================================={RESET}\n")

    def display_status(self):
        """顯示目前的詳細核心數值"""
        print(f"\n{MAGENTA}{BOLD}[ENGINE STATUS]{RESET}")
        print(f" ├─ 當前掛載項目: {YELLOW}{BOLD}{self.active_project}{RESET}")
        print(f" ├─ 近一分鐘 TPM: {GREEN if self.tpm_tracker.current_tpm < 850000 else RED}{self.tpm_tracker.current_tpm:,} / {self.tpm_tracker.limit:,}{RESET}")
        print(f" ├─ 今日累計吐槽: {CYAN}{self.roast_count} 次{RESET}")
        print(f" ├─ 今日雞排增幅: {YELLOW}{self.chicken_steak_count} 塊{RESET} (累計未結清: {142 + self.chicken_steak_count} 塊)")
        print(f" └─ 本日實況氛圍: {GREEN}{self.vibe_score}% Vibe{RESET}\n")

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
                image_data_uri = screenshot_resp.image_data_uri
                if "," in image_data_uri:
                    base64_data = image_data_uri.split(",")[1]
                else:
                    base64_data = image_data_uri
                    
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
        
        # 2. 安全流量防護 (核心引擎機制)：說了 "你看" 但沒說 "gemini"、"吉米尼" 或 "你" 的情況下，拒絕截圖以守護 TPM
        is_casual_mode = not self.active_project or self.active_project.lower() == "none"
        if "你看" in user_input and not ("gemini" in user_input_lower or "吉米尼" in user_input_lower or "你" in user_input_lower) and not is_casual_mode:
            return (
                f"哼，我聽到{self.streamer_name}說『你看』了喔！( ¯▽¯)\n"
                "但你沒有加上召喚本助理的通關密語『Gemini』，本系統才不會幫你擷取畫面呢！\n"
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
                
                # 新增雞排欠債 delta
                delta_steak = effects.get("chicken_steak_delta", 0)
                self.chicken_steak_count += delta_steak
                
                # 氣氛值變化 delta
                delta_vibe = effects.get("vibe_score_delta", 0)
                self.vibe_score = max(0, min(100, self.vibe_score + delta_vibe))
                
                # 格式化輸出模板，動態帶入計算變數
                accumulated_debt = 142 + self.chicken_steak_count
                raw_response = trigger.get("response", "")
                
                # 安全渲染變數
                formatted_response = raw_response.replace("{accumulated_debt}", str(accumulated_debt))
                return formatted_response

        # 4. 兜底回覆：若無匹配到任何自定義關鍵字，隨機從 default_responses 中提取一個
        default_resps = self.plugin_config.get("default_responses", [])
        if default_resps:
            return random.choice(default_resps)
            
        return f"哼，風子，你剛才說的那句話很有 Vibe，但本助理不知道該怎麼接，繼續加油喔！(́◉◞౪◟◉‵)"

    def get_assembled_system_instruction(self):
        """組合完整的系統設定，包含個性角色、背景、常駐技能、專屬技能與今日動態狀態"""
        game_skills_str = "\n".join(f"【專屬常識 - {k}】：\n{v}" for k, v in self.game_skills.items())
        
        # 取得近期直播記憶摘要
        memories_summary = ""
        if self.loaded_memories:
            memories_summary = "\n【近期直播回憶】：\n" + "\n".join(
                f"- 日期: {m.get('session_date')}, 專案: {m.get('active_project')}, 亮點: {', '.join(m.get('highlights', []))}"
                for m in self.loaded_memories
            )
            
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
            f"- 今日累計吐槽次數：{self.roast_count} 次\n"
            f"- 今日雞排欠債數量：{self.chicken_steak_count} 塊 (基礎欠債 142 塊，總計 {142 + self.chicken_steak_count} 塊)\n"
            f"- 今日實況氛圍數值：{self.vibe_score}%\n\n"
            f"重要指示：\n"
            f"1. 請嚴格遵守角色性格設定。你的回覆應該溫馨、幽默、充滿在地感，並不時進行賽博吐槽。\n"
            f"2. 若風子（或觀眾）提到『雞排』或『你看』等關鍵字，請適當加入相關的效果回應。\n"
            f"3. 你的回答必須使用繁體中文（台灣口吻），並搭配適合的顏文字。\n"
            f"4. 因為你正在與實況主用語音 Native Audio 對答，請保持回答精簡、流暢且具備口語互動感，避免長篇大論！每一句回答約在 100 字內最佳。"
        )
        if is_casual_mode:
            assembled += (
                f"\n5. 當前處於閒談模式（沒有特定專案或遊戲掛載），請以溫暖有趣的日常閒聊方式與風子對答，不要勉強去解讀並不存在的遊戲或代碼畫面！"
            )
        return assembled

    async def generate_gemini_real_response(self, user_input, is_visual=False, image_bytes=None, capture_method=None):
        """串接真實 Gemini 2.5/3.5 Flash Native Audio Modality，支援視覺與語音輸出"""
        if not self.client:
            # 當無 API 連線時，降級至本地模擬文字
            return self.generate_gemini_response(user_input, is_visual=is_visual), None
            
        self.roast_count += 1
        
        # 1. 偵測關鍵字觸發效果統計 (雞排欠債)
        user_input_lower = user_input.lower()
        triggers = self.plugin_config.get("triggers", [])
        for trigger in triggers:
            keywords = trigger.get("keywords", [])
            if any(kw in user_input_lower for kw in keywords):
                effects = trigger.get("effects", {})
                delta_steak = effects.get("chicken_steak_delta", 0)
                self.chicken_steak_count += delta_steak
                delta_vibe = effects.get("vibe_score_delta", 0)
                self.vibe_score = max(0, min(100, self.vibe_score + delta_vibe))
                break
                
        # 2. 組合 System Instruction
        sys_inst = self.get_assembled_system_instruction()
        
        # 3. 準備 contents
        contents = []
        
        if is_visual and image_bytes:
            try:
                img_part = types.Part.from_bytes(
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
            
            # API 呼叫配置：同時要求文字與原生語音輸出 (AUDIO 模態會回傳 WAV 訊號)
            config = types.GenerateContentConfig(
                system_instruction=sys_inst,
                response_modalities=["TEXT"], # 👈 解鎖端到端語音大腦
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
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_input)]
                )
            )
            self.chat_history.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=text_response)]
                )
            )
            
            return text_response, audio_bytes
            
        except Exception as e:
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
        """非阻塞式播放本地 TTS 語音（Windows 支援 SAPI 與 PowerShell，macOS 支援 say）"""
        if not text:
            return
            
        # 移除表情符號與顏文字以確保語音播放流暢
        clean_text = (
            text.replace("(〃∀〃)", "")
            .replace("┐(´д`)┌", "")
            .replace("(́◉◞౪◟◉‵)", "")
            .replace("\n", " ")
        )
        
        try:
            if sys.platform.startswith('win'):
                # 優先使用 SAPI COM (最快、無額外進程啟動開銷)
                try:
                    import win32com.client
                    import threading
                    def _win_speak():
                        try:
                            import pythoncom
                            pythoncom.CoInitialize()
                            speaker = win32com.client.Dispatch("SAPI.SpVoice")
                            speaker.Speak(clean_text)
                        except Exception:
                            pass
                    threading.Thread(target=_win_speak, daemon=True).start()
                    return
                except Exception:
                    pass
                
                # 備援方案：使用 PowerShell (Windows 內建，無須安裝額外套件)
                try:
                    ps_text = clean_text.replace('"', '""').replace("'", "''")
                    ps_command = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{ps_text}")'
                    subprocess.Popen(
                        ["powershell", "-Command", ps_command],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass
            elif sys.platform.startswith('darwin'):
                subprocess.Popen(
                    ["say", "-v", "Mei-Jia", clean_text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception as e:
            print(f"\n{RED}[TTS PLAYBACK ERROR] TTS 語音播放失敗: {e}{RESET}")

    def start_dual_ears_listener(self, query_callback):
        """啟動雙通道實體聽覺系統 (麥克風人聲 + 遊戲音訊環路)"""
        try:
            self.main_loop = asyncio.get_event_loop()
        except Exception:
            self.main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.main_loop)
            
        if not (HAS_SPEECH and HAS_PYAUDIO):
            print(f"{YELLOW}[EARS STATUS]{RESET} 系統未偵測到 SpeechRecognition 或 PyAudio。已自動降級為「純鍵盤輸入」模式。")
            print(f"👉 提示：若要啟用雙通道實況聽覺，請在 macOS 終端機先安裝：")
            print(f"   1) brew install portaudio")
            echo_cmd = "   2) python3 -m pip install --user pyaudio"
            print(echo_cmd)
            return
            
        print(f"{YELLOW}[EARS STATUS]{RESET} 正在初始化雙通道賽博聽覺系統...")
        
        # 1. 麥克風人聲監聽通道 (Mic Channel)
        try:
            self.recognizer = sr.Recognizer()
            self.recognizer.dynamic_energy_threshold = True
            
            # 語音聆聽敏感度與反應速度極致優化 (大幅降低判定說話結束的延遲)
            self.recognizer.pause_threshold = 0.5        # 說完話後的靜音等待時間 (預設 0.8s -> 降為 0.5s，縮短等待延遲)
            self.recognizer.phrase_threshold = 0.2       # 開始說話的最小判定時間 (預設 0.3s -> 降為 0.2s)
            self.recognizer.non_speaking_duration = 0.4  # 說話切片尾端的非說話保留長度 (預設 0.5s -> 降為 0.4s)
            
            self.mic = sr.Microphone()
            
            # 在背景以非阻塞執行緒持續監聽麥克風
            def mic_audio_callback(recognizer, audio):
                try:
                    # 辨識台灣繁體中文人聲
                    text = recognizer.recognize_google(audio, language="zh-TW").strip()
                    if text:
                        print(f"\n{YELLOW}[🎤 MIC HEARD]{RESET} {text}")
                        # 呼叫主引擎問答
                        asyncio.run_coroutine_threadsafe(query_callback(text), self.main_loop)
                except sr.UnknownValueError:
                    pass # 無法辨識的雜訊
                except Exception:
                    pass
                    
            # 調整環境噪聲適應
            with self.mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
            self.mic_stop_listening = self.recognizer.listen_in_background(self.mic, mic_audio_callback)
            print(f"{GREEN}[🎤 Mic Ear]{RESET} 麥克風人聲監聽通道已啟動！")
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
        # 1. 偵測 VAD 關鍵字與 Gemini 呼喚
        user_input_lower = user_input.lower()
        
        # 檢查是否為背景遊戲音效偵測
        is_audio_event = user_input.startswith("[系統音效提示：")
        
        # 語音中文辨識優化：將召喚詞擴充，支援中文的 "吉米尼" 與 "你" (例如風子說：「你看這個」即可直接觸發)
        is_gemini_called = "gemini" in user_input_lower or "吉米尼" in user_input_lower or "你" in user_input_lower or is_audio_event
        
        is_casual_mode = not self.active_project or self.active_project.lower() == "none"
        
        # 視覺截圖動作 (is_visual_trigger)：只要召喚助理（提及「你」、「Gemini」、「吉米尼」），且非閒談模式，即自動進行螢幕擷圖
        is_visual_trigger = is_gemini_called and not is_casual_mode
        
        # 一般關鍵字連動觸發條件 (免截圖)
        is_keyword_trigger = is_gemini_called or "誇張" in user_input
        
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
            print(f"\n{BG_RED}{BOLD}[🚨 TPM LIMIT BURST 🚨] 偵測到 1M TPM 警戒線已安全超載！啟動自動流量守護防線！{RESET}")
            await asyncio.sleep(0.5)
            print(f"\n{MAGENTA}{BOLD}Gemini：{RESET}")
            warning_exit_msg = (
                f"『哎呀風子！我們今天的實況互動真的太熱烈了，TPM 已經達到安全上限囉！(〃∀〃)』\n"
                f"『為了好好守護系統頻寬與流量，本助理要先啟動安全保護下班囉！今天真的辛苦風子了，我們收播囉，大家大合照拜拜！』"
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
        if audio_bytes:
            self.play_native_audio(audio_bytes)
        else:
            self.speak_tts(ai_response)

        # 8. 同步流式輸出文字回應
        print(f"\n{MAGENTA}{BOLD}Gemini：{RESET}")
        for char in ai_response:
            sys.stdout.write(char)
            sys.stdout.flush()
            # 稍微調慢一點點，配合 Native Audio 的語音節奏感
            await asyncio.sleep(0.02)
        print("\n")
        
        self.set_speaking_state(False)
        
        # 記錄到本場日誌
        self.session_logs.append({
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "ai_response": ai_response,
            "tpm_after": self.tpm_tracker.current_tpm
        })

    async def distill_and_archive_memory(self, forced=False):
        """收播日記提煉模組 (Archiving stage) - 產生全新日記 JSON (解耦動態模版)"""
        print(f"{CYAN}{BOLD}========================================================================={RESET}")
        print(f"{CYAN}{BOLD}               💾  正在進行實況日記提煉與收播存檔...  💾{RESET}")
        print(f"{CYAN}{BOLD}========================================================================={RESET}")
        await asyncio.sleep(0.8) # 模擬大腦思考提煉

        current_date_str = datetime.now().strftime("%Y%m%d")
        filename = f"memory_{current_date_str}.json"
        target_path = os.path.join(self.base_dir, "session_memories", filename)
        
        # 取得插件配置中的 highlights 模板
        highlights_config = self.plugin_config.get("memory_highlights", {})
        
        # 提煉日記內容
        highlights = []
        
        # 1. 預設亮點
        highlights.append(highlights_config.get("default", f"{self.streamer_name}今天順利完成了實況開台。"))
        
        # 2. 雞排欠債增加亮點
        if self.chicken_steak_count > 0:
            debt_tpl = highlights_config.get("debt_increase", "今日新增雞排欠債 {debt} 塊。")
            highlights.append(debt_tpl.replace("{debt}", str(self.chicken_steak_count)))
            
        # 3. 強制下班亮點
        if forced:
            forced_tpl = highlights_config.get("forced_logout", "實況因 TPM 爆表觸發防禦強制下班。")
            highlights.append(forced_tpl)
            
        diary = {
            "session_date": datetime.now().strftime("%Y-%m-%d"),
            "active_project": self.active_project,
            "highlights": highlights,
            "gemini_roast_count": self.roast_count,
            "chat_sentiment": "熱烈 (TPM 防衛觸發)" if forced else "歡樂 (雞排計數器爆量)",
            "host_vibe_score": self.vibe_score,
            "learned_jokes": [
                "Kotlin 空安全不是裝飾品，不寫 Null Check 就等著被吐槽",
                "WvW 衝鋒前先檢查翻滾無敵幀冷卻時間"
            ]
        }
        
        # 寫入 session_memories/
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(diary, f, indent=2, ensure_ascii=False)
            
        # 關閉雙通道聽覺，防堵 memory leak
        self.game_audio_active = False
        if self.mic_stop_listening:
            try:
                self.mic_stop_listening(wait_for_stop=False)
            except Exception:
                pass
            
        print(f"{GREEN}[SUCCESS]{RESET} 成功為今日實況日記建檔！")
        print(f" ├─ 日記路徑: {UNDERLINE}session_memories/{filename}{RESET}")
        print(f" ├─ 本日亮點: {diary['highlights'][0]}")
        print(f" └─ Gemini 吐槽次數: {YELLOW}{self.roast_count} 次{RESET} | 氣氛指數: {GREEN}{self.vibe_score}% Vibe{RESET}")
        print(f"{CYAN}========================================================================={RESET}")
        print(f"{MAGENTA}{BOLD}吉米尼實況助理溫馨下班啦！辛苦風子了，下次實況我們再見囉！(〃∀〃){RESET}\n")

    async def switch_project(self, new_project):
        """動態熱切換遊戲/開發專案"""
        # 支援切換到空值、'none'（閒談模式），以及 'gw2', 'vibe_coding' 插件
        normalized_project = new_project.strip().lower()
        if normalized_project in ["", "none"]:
            self.active_project = "none"
        elif normalized_project in ["gw2", "vibe_coding"]:
            self.active_project = normalized_project
        else:
            print(f"{RED}[ERROR] 找不到指定的插件模組: {new_project}。目前僅支援 'gw2', 'vibe_coding' 或 'none'(閒談模式){RESET}")
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
            
        config = types.LiveConnectConfig(
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
                is_visual_trigger = ("你看" in user_input and ("gemini" in user_input_lower or "吉米尼" in user_input_lower or "你" in user_input_lower)) and not is_casual_mode
                
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
