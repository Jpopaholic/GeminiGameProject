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
    # 呼叫 Gemini 動態生成開場歡迎詞
    welcome_prompt = (
        "請為實況主「風子」生成一個親切、活潑且帶有你傲嬌又溫馨性格的開台歡迎問候詞！\n"
        "你可以提到要一起優化寫代碼或是玩遊戲，字數大約 80-150 字，直接輸出對話即可，絕對不要有任何前置或後置的解釋文字。"
    )
    print(f"{MAGENTA}{BOLD}Gemini 正在載入賽博魂魄，思考開場白中...{RESET}\n")
    
    welcome_msg = (
        "大家安安！哈囉，你上線啦，風子！(〃∀〃) 今天我們也是開開心心一起努力喔！"
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
            welcome_msg = "大家安安！哈囉，你上線啦，風子！今天我們也要開開心心一起寫扣和實況互動喔！"
            audio_bytes = None
            
    print(f"{MAGENTA}{BOLD}Gemini：{RESET}")
    print(welcome_msg + "\n")
    
    # 播放開場親切語音 (優先使用 Native Audio，若無則自動使用本地 TTS)
    if audio_bytes:
        engine.play_native_audio(audio_bytes)
    else:
        engine.speak_tts(welcome_msg)

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
            user_input = await loop.run_in_executor(None, lambda: input(f"{BOLD}風子 (或觀眾) >>> {RESET}"))
            
            user_input = user_input.strip()
            if not user_input:
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
