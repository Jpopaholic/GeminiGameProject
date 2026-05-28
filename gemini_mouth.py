#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Stream Engine - Mouth Component (吉米尼實況助理語音輸出/嘴巴模組)
"""

import os
import sys
import subprocess
import threading
from gemini_shared import (
    CYAN, YELLOW, GREEN, RED, RESET
)

class GeminiMouthMixin:
    """語音與聲音合成輸出 Mixin，提供本地 TTS 與原生音訊播放"""

    def get_wav_duration(self, audio_bytes):
        """計算 WAV 音訊位元組的播放秒數，用於等待原生語音播畢"""
        try:
            import wave
            import io
            with wave.open(io.BytesIO(audio_bytes)) as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return frames / float(rate)
        except Exception:
            pass
        # 無法解析時，估算為文字長度 × 0.15 秒（粗略語速）
        return 0

    def play_native_audio(self, audio_bytes):
        """非阻塞式播放 Gemini 原生 WAV 音訊（支援 macOS afplay 與 Windows winsound）"""
        if not audio_bytes:
            return
            
        try:
            # 依作業系統選擇合適的播放方式
            if sys.platform.startswith('win'):
                import winsound
                # Windows 支援直接從記憶體播放二進位 WAV 資料，完美避開實體檔案寫入與 Git 追蹤問題
                winsound.PlaySound(audio_bytes, winsound.SND_MEMORY | winsound.SND_ASYNC)
            elif sys.platform.startswith('darwin'):
                import tempfile
                # macOS 等外部播放器需要實體路徑，將檔案寫入系統暫存目錄（避免污染專案 Git）
                temp_path = os.path.join(tempfile.gettempdir(), "temp_response.wav")
                with open(temp_path, "wb") as f:
                    f.write(audio_bytes)
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
