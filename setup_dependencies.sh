#!/usr/bin/env bash
# -*- coding: utf-8 -*-

echo -e "\033[96m=========================================================================\033[0m"
echo -e "\033[96m🤖 Installing Dependencies for Gemini Game Stream Engine 🤖\033[0m"
echo -e "\033[96m=========================================================================\033[0m"

# 1. Upgrade pip
echo -e "\033[93m[1/3] Upgrading pip...\033[0m"
python3 -m pip install --user --upgrade pip

# 2. Install base requirements
echo -e "\033[93m[2/3] Installing core libraries (Gemini SDK, Pillow, OBS WebSocket, MSS)...\033[0m"
python3 -m pip install --user google-genai obsws-python pillow mss SpeechRecognition

# 3. Try to install pyaudio
echo -e "\033[93m[3/3] Trying to install pyaudio (microphone capture support)...\033[0m"
python3 -m pip install --user pyaudio

# Check if pyaudio succeeded
if python3 -c "import pyaudio" &> /dev/null; then
    echo -e "\033[92m✔ PyAudio installed successfully!\033[0m"
else
    echo -e "\033[91m⚠️  PyAudio failed to install.\033[0m"
    echo -e "\033[93m💡 提示：在 macOS 上，PyAudio 需要系統的 PortAudio 函式庫。"
    echo -e "若要啟用「麥克風耳朵」功能，請在終端機安裝 Homebrew PortAudio，接著再執行本腳本一次："
    echo -e "   1) brew install portaudio"
    echo -e "   2) python3 -m pip install --user pyaudio"
    echo -e "別擔心！即使沒有 PyAudio，我們的實況助理依然會自動流暢降級為「鍵盤輸入」模式，不會崩潰！\033[0m"
fi

echo -e "\033[96m=========================================================================\033[0m"
echo -e "\033[92m🎉 Core setup complete! Ready to start vibe streaming! 🎉\033[0m"
echo -e "\033[96m=========================================================================\033[0m"
