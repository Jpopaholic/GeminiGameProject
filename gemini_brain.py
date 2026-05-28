#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Stream Engine - Brain Component (吉米尼實況助理大腦/推理模組)
"""

import os
import sys
import json
import time
import glob
import random
import asyncio
import base64
from datetime import datetime

from gemini_shared import (
    HAS_GEMINI_SDK, HAS_PYAUDIO, TPMTracker,
    CYAN, YELLOW, GREEN, RED, MAGENTA, BG_RED, BG_BLACK_FG_YELLOW, BOLD, UNDERLINE, RESET
)

if HAS_GEMINI_SDK:
    from google import genai
    from google.genai import types
    from google.genai.types import GenerateContentConfig, LiveConnectConfig, Part, Content
if HAS_PYAUDIO:
    import pyaudio

class GeminiBrainMixin:
    """智慧大腦推理 Mixin，提供常規內容生成、Live 連線、狀態提煉與專案熱切換"""

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
                print(f"\n{BG_RED}{BOLD}[🚨 TPM LIMIT BURST 🚨] 偵測到 {self.tpm_tracker.limit:,} TPM 警戒線已安全超載！啟動自動流量守護防線！{RESET}")
                await asyncio.sleep(0.5)
                print(f"\n{MAGENTA}{BOLD}Gemini：{RESET}")
                warning_exit_msg = (
                    f"『哎呀{self.streamer_name}！我們今天的實況互動真的太熱烈了，TPM 已經達到安全上限 {self.tpm_tracker.limit:,} 囉！(〃∀〃)』\n"
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
                print(f"\n{BG_BLACK_FG_YELLOW}[⚠️ TPM WARNING] 當前 TPM 達 {self.tpm_tracker.current_tpm:,}，已逼近 {self.tpm_tracker.warning_threshold:,} 限額！防護罩隨時可能開啟！{RESET}")

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
            game_tools_path = os.path.join(self.base_dir, "game_tools")
            available_plugins = []
            if os.path.exists(game_tools_path):
                for d in os.listdir(game_tools_path):
                    plugin_dir = os.path.join(game_tools_path, d)
                    has_skills = os.path.isdir(os.path.join(plugin_dir, "skills"))
                    if os.path.isdir(plugin_dir) and has_skills:
                        available_plugins.append(d)
                    elif os.path.isdir(plugin_dir):
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
        
        # 決定回應模態 (若有 PyAudio則開啟語音，否則為純文字)
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
