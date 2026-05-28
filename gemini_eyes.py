#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Stream Engine - Eyes Component (吉米尼實況助理視覺/眼睛模組)
"""

import os
import base64
import io
from gemini_shared import (
    HAS_OBS, HAS_MSS, HAS_PILLOW,
    YELLOW, GREEN, RED, RESET
)

if HAS_PILLOW:
    from PIL import Image
if HAS_OBS:
    import obsws_python as obs
if HAS_MSS:
    import mss

class GeminiEyesMixin:
    """視覺處理 Mixin，提供直播畫面截圖、OBS 串接與降級防線"""
    
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
