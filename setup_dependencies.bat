@echo off
echo =========================================================================
echo [INSTALLER] Installing Dependencies for Gemini Game Stream Engine (Windows)
echo =========================================================================

:: 1. Upgrade pip
echo [1/3] Upgrading pip...
python -m pip install --user --upgrade pip

:: 2. Install base requirements
echo [2/3] Installing core libraries (Gemini SDK, Pillow, OBS WebSocket, MSS, Speech, TTS, WebSockets)...
python -m pip install --user google-genai obsws-python pillow mss SpeechRecognition edge-tts websockets

:: 3. Try to install pyaudio
echo [3/3] Trying to install pyaudio (microphone capture support)...
python -m pip install --user pyaudio

:: Check if pyaudio succeeded
python -c "import pyaudio" 2>nul
if %errorlevel% equ 0 (
    echo SUCCESS: PyAudio installed successfully!
) else (
    echo WARNING: PyAudio failed to install.
    echo Note: PyAudio compilation failed on Windows due to missing portaudio headers.
    echo This is NORMAL. The stream engine will gracefully downgrade to keyboard mode.
)

echo =========================================================================
echo SUCCESS: Core setup complete! Ready to start vibe streaming!
echo =========================================================================
pause
