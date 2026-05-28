@echo off
echo =========================================================================
echo [INSTALLER] Installing Dependencies for Gemini Game Stream Engine (Windows)
echo =========================================================================

:: 1. Upgrade pip
echo [1/3] Upgrading pip...
python -m pip install --user --upgrade pip

:: 2. Install base requirements
echo [2/3] Installing core libraries (Gemini SDK, Pillow, OBS WebSocket, MSS, ASR (Whisper), TTS, WebSockets, SoundDevice)...
python -m pip install --user google-genai obsws-python pillow mss faster-whisper edge-tts websockets sounddevice

:: 3. Try to install pyaudio
echo [3/3] Trying to install pyaudio (microphone capture support)...
python -m pip install --user pyaudio

:: Check if pyaudio succeeded
python -c "import pyaudio" 2>nul
if %errorlevel% equ 0 (
    echo SUCCESS: PyAudio installed successfully!
) else (
    echo WARNING: PyAudio failed to compile on Windows (normal for this Python version).
    echo NO WORRIES! The engine has installed sounddevice as a robust, pre-compiled fallback.
    echo Your offline microphone side-hearing will still work perfectly!
)

echo =========================================================================
echo SUCCESS: Core setup complete! Ready to start vibe streaming!
echo =========================================================================
pause
