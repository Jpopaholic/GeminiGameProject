#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Game Stream Engine - Streamer CLI Console (吉米尼實況主互動主控台)
專注於終端機交互、VAD 文字流/語音聽覺讀取與實況同步響應
"""

import sys
import asyncio
import subprocess
from gemini_engine import GeminiStreamEngine

# ANSI 色彩與特效定義
MAGENTA = '\033[95m'
BOLD = '\033[1m'
RESET = '\033[0m'
YELLOW = '\033[93m'
GREEN = '\033[92m'

async def main():
    # 載入核心解耦引擎
    engine = GeminiStreamEngine()
    engine.print_splash()
    
    # 啟動 WebSocket 語音側聽伺服器 (賽博耳朵) - 只在 input_mode 為 voice 或 both 時啟動
    if engine.input_mode in ["voice", "both"] and hasattr(engine, 'start_ears_server'):
        await engine.start_ears_server()
    # 呼叫 Gemini 動態生成開場歡迎詞
    welcome_prompt = (
        f"請為實況主「{engine.streamer_name}」生成一個親切、活潑且帶有你傲嬌又溫馨性格的開台歡迎問候詞！\n"
        "你可以提到要一起優化寫代碼或是玩遊戲，字數大約 80-150 字，直接輸出對話即可，絕對不要有任何前置或後置的解釋文字。"
    )
    print(f"{MAGENTA}{BOLD}Gemini 正在載入賽博魂魄，思考開場白中...{RESET}\n")
    
    welcome_msg = (
        f"大家安安！哈囉，你上線啦，{engine.streamer_name}！(〃∀〃) 今天我們也是開開心心一起努力喔！"
    )
    audio_bytes = None
    
    if engine.client:
        try:
            # ⚡ 增加超時防線至 8.0 秒，避免冷啟動 DNS/SSL 握手延遲導致直接觸發備援開場白
            welcome_msg, audio_bytes = await asyncio.wait_for(
                engine.generate_gemini_real_response(welcome_prompt, is_visual=False),
                timeout=8.0
            )
        except Exception as e:
            # 超時或出錯自動啟動備用防線
            welcome_msg = f"大家安安！哈囉，你上線啦，{engine.streamer_name}！今天我們也要開開心心一起寫扣和實況互動喔！"
            audio_bytes = None
            
    # 如果生成的開場白為 None，自動啟用預設開場白
    if welcome_msg is None:
        welcome_msg = f"大家安安！哈囉，你上線啦，{engine.streamer_name}！今天我們也要開開心心一起寫扣和實況互動喔！"
            
    print(f"{MAGENTA}{BOLD}Gemini：{RESET}")
    print(welcome_msg + "\n")
    
    # 播放開場親切語音 (優先使用 Native Audio，若無則自動使用本地 TTS)
    # 同步麮起 OBS Overlay Logo 動畫
    engine.set_speaking_state(True, welcome_msg)
    if audio_bytes:
        duration = engine.get_wav_duration(audio_bytes)
        engine.play_native_audio(audio_bytes)
        # 等待語音播畢
        if duration > 0:
            await asyncio.sleep(duration + 0.3)
    else:
        tts_handle = engine.speak_tts(welcome_msg)
        if tts_handle is not None:
            loop = asyncio.get_event_loop()
            try:
                if hasattr(tts_handle, 'join'):
                    await loop.run_in_executor(None, tts_handle.join)
                elif hasattr(tts_handle, 'wait'):
                    await loop.run_in_executor(None, tts_handle.wait)
            except Exception:
                pass
    engine.set_speaking_state(False)

    # 建立非同步使用者輸入佇列
    user_input_queue = asyncio.Queue()
    
    # 啟動雙向 WebSocket Live Session 核心
    live_task = asyncio.create_task(engine.run_live_session(user_input_queue))
    
    # 啟動非同步鍵盤讀取任務
    try:
        await keyboard_input_loop(engine, user_input_queue)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await engine.distill_and_archive_memory()
    except Exception as e:
        print(f"\033[91m[CONSOLES ERROR] {e}\033[RESET]")


async def keyboard_input_loop(engine, user_input_queue):
    """非同步非阻塞讀取鍵盤輸入，並送入實時發送佇列"""
    while True:
        try:
            # 非同步讀取鍵盤終端機輸入 (保留鍵盤操作，作為雙模輸入)
            loop = asyncio.get_event_loop()
            user_input = await loop.run_in_executor(None, lambda: input(f"{BOLD}{engine.streamer_name} (或觀眾) >>> {RESET}"))
            
            user_input = user_input.strip()
            if not user_input:
                continue
                
            # 當大腦額度或流量爆表（限流保護中），鎖定鍵盤對答輸入以確保使用者體驗與頻寬安全
            if getattr(engine, 'is_quota_warning', False) and user_input.lower() not in ["exit", "quit", "status"] and not user_input.lower().startswith("switch "):
                print(f"\n{RED}[⚠️ 額度保護中] Gemini 的大腦額度已耗盡或處於頻寬限流狀態！輸入暫時鎖定，請稍候或修改設定檔切換模型！{RESET}")
                continue
                
            # 當助理正在發言（且非管理控制指令），鎖定鍵盤對答輸入以確保使用者體驗
            if getattr(engine, 'is_speaking', False) and user_input.lower() not in ["exit", "quit", "status"] and not user_input.lower().startswith("switch "):
                print(f"\n{YELLOW}[⚠️ 助理發言中] Gemini 正在回答中，輸入已鎖定。請等她說完再發問喔！{RESET}")
                continue
                
            # pyrefly: ignore [parse-error]
            if user_input.lower() in ["exit", "quit"]:
                await engine.distill_and_archive_memory()
                break
                
            elif user_input.lower() == "status":
                engine.display_status()
                continue
                
            elif user_input.lower().startswith("switch "):
                parts = user_input.split(" ")
                if len(parts) >= 2:
                    await engine.switch_project(parts[1])
                continue
                
            # 💡 核心修正：直接調用 execute_query，繞過會崩潰的 Live WebSocket
            # 這會自動判斷關鍵字、驅動 OBS 截圖、並呼叫 generate_gemini_real_response 播放原生 WAV 語音
            await engine.execute_query(user_input)
            
        except KeyboardInterrupt:
            await engine.distill_and_archive_memory()
            break
        except Exception as e:
            print(f"\n\033[91m[CONSOLES ERROR] {e}\033[0m")


if __name__ == "__main__":
    if sys.platform.startswith('win'):
        # 解決 Windows 下的 asyncio 迴圈相容問題
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
