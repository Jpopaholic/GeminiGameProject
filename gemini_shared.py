#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini Stream Engine - Shared Infrastructure & Utilities (吉米尼萬用實況助理核心共享庫)
"""

import os
import sys
import time

# Windows console output Unicode compatibility fix
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass

# Safe dynamic imports for dependencies
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
