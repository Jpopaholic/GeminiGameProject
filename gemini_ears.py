#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Stream Engine - Ears Component (吉米尼實況助理聽覺/耳朵模組)
"""

import os
import sys
import time
import math
import struct
import io
import wave
import asyncio
import threading
import collections
from gemini_shared import (
    HAS_WHISPER, HAS_PYAUDIO, HAS_SPEECH,
    YELLOW, GREEN, RED, RESET
)

if HAS_PYAUDIO:
    import pyaudio
if HAS_WHISPER:
    from faster_whisper import WhisperModel

class GeminiEarsMixin:
    """音訊監聽與 ASR 語音轉譯 Mixin，提供麥克風人聲側聽與遊戲音效監控"""

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

    def _mic_listener_loop(self, query_callback):
        """背景實體麥克風側聽與 VAD 辨識迴圈 (PyAudio + faster-whisper)"""
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

            # 構建統一化 ASR 語氣引導 prompt ─ 結合語意設定 (language.txt)
            prompt = ""
            if hasattr(self, 'base_skill_language') and self.base_skill_language:
                clean_lang = self.base_skill_language[:200].replace("\n", " ").replace("-", " ").strip()
                prompt = f"以下是實況對話與常用詞習慣：{clean_lang}"
            else:
                prompt = "以下是台灣繁體中文的實況對話，包含一些網路梗跟口語。"

            # 執行離線轉譯 ─ 採用多國語言自動偵測 (language=None)，極致通用！
            segments, info = self.whisper_model.transcribe(
                wav_buf,
                beam_size=5,
                language=None,
                initial_prompt=prompt
            )

            text = "".join(segment.text for segment in segments).strip()
            return text if len(text) > 0 else None
        except Exception as e:
            print(f"{RED}[ASR ERROR] faster-whisper 辨識出錯: {e}{RESET}")
            return None
