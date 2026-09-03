@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Focuslyra Local TTS Setup

echo ==================================================
echo  Focuslyra - Local Voice Setup
echo ==================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [Focuslyra] Python environment is missing. Running setup first...
  call setup.bat
  if errorlevel 1 goto :failed
)

echo [Focuslyra] Installing lightweight Kokoro ONNX TTS...
".venv\Scripts\python.exe" -m pip install -r requirements-tts.txt
if errorlevel 1 goto :failed

if not exist "models\tts\kokoro" mkdir "models\tts\kokoro"
set "MODEL=models\tts\kokoro\kokoro-v1.0.onnx"
set "VOICES=models\tts\kokoro\voices-v1.0.bin"

if not exist "%MODEL%" (
  echo [Focuslyra] Downloading Kokoro model...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx' -OutFile '%MODEL%'"
  if errorlevel 1 goto :failed
) else (
  echo [Focuslyra] Kokoro model already present.
)

if not exist "%VOICES%" (
  echo [Focuslyra] Downloading Kokoro voice pack...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile '%VOICES%'"
  if errorlevel 1 goto :failed
) else (
  echo [Focuslyra] Kokoro voice pack already present.
)

echo [Focuslyra] Verifying local British voice generation...
".venv\Scripts\python.exe" -c "from app.tts_service import synthesise; r=synthesise('Focuslyra local voice is ready.', 'en-GB', 'bm_george'); print('[Focuslyra] Test WAV:', r['relative_audio_path'])"
if errorlevel 1 goto :failed

for /f "tokens=*" %%H in ('certutil -hashfile requirements-tts.txt SHA256 ^| findstr /v /i "hash certutil"') do set "REQ_HASH=%%H"
if not exist ".venv\focuslyra" mkdir ".venv\focuslyra"
> ".venv\focuslyra\requirements-tts.sha256" echo %REQ_HASH: =%

echo.
echo ==================================================
echo [Focuslyra] Local Kokoro TTS is ready.
echo Generated audio is cached under media\generated\
echo British voices are candidates only until RP calibration.
echo Cost per generated clip: 0 EUR
echo ==================================================
echo.
pause
exit /b 0

:failed
echo.
echo [ERROR] Local TTS setup did not finish.
echo Copy the error above if you need help.
pause
exit /b 1
