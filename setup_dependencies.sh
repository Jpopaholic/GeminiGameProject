#!/usr/bin/env bash
# -*- coding: utf-8 -*-

echo -e "\033[96m=========================================================================\033[0m"
echo -e "\033[96m[INSTALLER] Installing Dependencies for Gemini Game Stream Engine\033[0m"
echo -e "\033[96m=========================================================================\033[0m"

# 1. Upgrade pip
echo -e "\033[93m[1/3] Upgrading pip...\033[0m"
python3 -m pip install --user --upgrade pip

# 2. Install base requirements
echo -e "\033[93m[2/3] Installing core libraries (Gemini SDK, Pillow, OBS WebSocket, MSS, ASR (Whisper), TTS, WebSockets, SoundDevice)...\033[0m"
python3 -m pip install --user google-genai obsws-python pillow mss faster-whisper edge-tts websockets sounddevice

# 3. Try to install pyaudio
echo -e "\033[93m[3/3] Trying to install pyaudio (microphone capture support)...\033[0m"
python3 -m pip install --user pyaudio

# Check if pyaudio succeeded
if python3 -c "import pyaudio" &> /dev/null; then
    echo -e "\033[92mSUCCESS: PyAudio installed successfully!\033[0m"
else
    echo -e "\033[91mWARNING: PyAudio failed to install.\033[0m"
    echo -e "\033[93mNote: On macOS, PyAudio requires the system PortAudio library."
    echo -e "If you want microphone support, please install PortAudio via Homebrew first:"
    echo -e "   1) brew install portaudio"
    echo -e "   2) python3 -m pip install --user pyaudio"
    echo -e "No worries! The engine will gracefully downgrade to keyboard mode if PyAudio is absent.\033[0m"
fi

echo -e "\033[96m=========================================================================\033[0m"
echo -e "\033[92mSUCCESS: Core setup complete! Ready to start vibe streaming!\033[0m"
echo -e "\033[96m=========================================================================\033[0m"
