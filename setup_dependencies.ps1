Write-Host '=========================================================================' -ForegroundColor Cyan
Write-Host '[INSTALLER] Installing Dependencies for Gemini Game Stream Engine' -ForegroundColor Cyan
Write-Host '=========================================================================' -ForegroundColor Cyan

# 1. Upgrade pip
Write-Host '[1/3] Upgrading pip...' -ForegroundColor Yellow
python -m pip install --user --upgrade pip

# 2. Install base requirements
Write-Host '[2/3] Installing core libraries (Gemini SDK, Pillow, OBS WebSocket, MSS, Speech, TTS)...' -ForegroundColor Yellow
python -m pip install --user google-genai obsws-python pillow mss SpeechRecognition edge-tts

# 3. Try to install pyaudio
Write-Host '[3/3] Trying to install pyaudio (microphone capture support)...' -ForegroundColor Yellow
python -m pip install --user pyaudio

# Check if pyaudio succeeded
$null = python -c "import pyaudio" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host 'SUCCESS: PyAudio installed successfully!' -ForegroundColor Green
}
else {
    Write-Host 'WARNING: PyAudio failed to install.' -ForegroundColor Red
    Write-Host 'Note: PyAudio compilation failed on Windows due to missing portaudio headers.' -ForegroundColor Yellow
    Write-Host 'This is NORMAL. The stream engine will gracefully downgrade to keyboard mode.' -ForegroundColor Yellow
}

Write-Host '=========================================================================' -ForegroundColor Cyan
Write-Host 'SUCCESS: Core setup complete! Ready to start vibe streaming!' -ForegroundColor Green
Write-Host '=========================================================================' -ForegroundColor Cyan
