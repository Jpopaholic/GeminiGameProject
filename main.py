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
    
    # 模擬開場親切問候
    welcome_msg = (
        f"哈囉，你上線啦，風子！(〃∀〃) \n"
        f"今天我們是要一起優化那個精細雕琢三年的 Android 數獨專案，\n"
        f"還是要開《激戰 2》到世界戰場展現藍標指揮官的衝鋒風采呢？\n"
        f"不論風子今天想玩哪一個，我都已經準備好全程陪伴你、為你加油打氣囉！助理 Gemini 全程在線，我們出發吧！"
    )
    print(f"{MAGENTA}{BOLD}Gemini：{RESET}")
    print(welcome_msg + "\n")
    
    # 開場親切語音問候 (非阻塞式 macOS say 語音)
    try:
        # 清除顏文字以確保語音發音流暢
        clean_welcome = welcome_msg.replace("(〃∀〃)", "").replace("┐(´д`)┌", "").replace("\n", " ")
        subprocess.Popen(
            ["say", "-v", "Mei-Jia", clean_welcome],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

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
            loop = asyncio.get_event_loop()
            user_input = await loop.run_in_executor(None, lambda: input(f"{BOLD}風子 (或觀眾) >>> {RESET}"))
            
            user_input = user_input.strip()
            if not user_input:
                continue
                
            if user_input.lower() in ["exit", "quit"]:
                await engine.distill_and_archive_memory()
                sys.exit(0)
                
            elif user_input.lower() == "status":
                engine.display_status()
                continue
                
            elif user_input.lower().startswith("switch "):
                parts = user_input.split(" ")
                if len(parts) >= 2:
                    await engine.switch_project(parts[1])
                continue
                
            # 將輸入發送給 Live Session 佇列處理
            await user_input_queue.put(user_input)
            # 給予一點緩衝時間讓回應能完整輸出
            await asyncio.sleep(0.1)
            
        except (asyncio.CancelledError, KeyboardInterrupt):
            break
        except Exception as e:
            print(f"\033[91m[KEYBOARD ERROR] {e}\033[RESET]")


if __name__ == "__main__":
    if sys.platform.startswith('win'):
        # 解決 Windows 下的 asyncio 迴圈相容問題
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
