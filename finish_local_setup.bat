@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Focuslyra - Finish Local Setup

echo ==================================================
echo  Focuslyra - Complete Free Local Learning Stack
echo ==================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [Focuslyra] Python environment is missing. Running setup first...
  call setup.bat
  if errorlevel 1 goto :failed
)

echo [1/5] Checking Ollama + Qwen...
where ollama >nul 2>nul
if errorlevel 1 (
  echo [Focuslyra] Ollama is not installed. Run configure_free_ai.bat once, then run this file again.
  goto :failed
)

ollama list >nul 2>nul
if errorlevel 1 (
  echo [Focuslyra] Starting Ollama locally...
  start "" /B ollama serve >nul 2>nul
  timeout /t 3 /nobreak >nul
)

ollama list | findstr /i "qwen3:4b" >nul
if errorlevel 1 (
  echo [Focuslyra] Downloading qwen3:4b...
  ollama pull qwen3:4b
  if errorlevel 1 goto :failed
) else (
  echo [Focuslyra] qwen3:4b already present.
)

echo.
echo [2/5] Installing local speech-to-text packages...
".venv\Scripts\python.exe" -m pip install -r requirements-audio.txt
if errorlevel 1 goto :failed

echo [Focuslyra] Preloading Whisper model. First run may take a while...
".venv\Scripts\python.exe" -c "import os; from faster_whisper import WhisperModel; m=os.getenv('WHISPER_MODEL','small'); WhisperModel(m, device=os.getenv('WHISPER_DEVICE','cpu'), compute_type=os.getenv('WHISPER_COMPUTE_TYPE','int8')); print('[Focuslyra] Whisper',m,'ready.')"
if errorlevel 1 goto :failed

echo.
echo [3/5] Installing local Kokoro TTS...
".venv\Scripts\python.exe" -m pip install -r requirements-tts.txt
if errorlevel 1 goto :failed
if not exist "models\tts\kokoro" mkdir "models\tts\kokoro"
set "MODEL=models\tts\kokoro\kokoro-v1.0.onnx"
set "VOICES=models\tts\kokoro\voices-v1.0.bin"
if not exist "%MODEL%" (
  echo [Focuslyra] Downloading Kokoro model...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx' -OutFile '%MODEL%'"
  if errorlevel 1 goto :failed
)
if not exist "%VOICES%" (
  echo [Focuslyra] Downloading Kokoro voices...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile '%VOICES%'"
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -c "from app.tts_service import synthesise; r=synthesise('Focuslyra local voice is ready.', 'en-GB', purpose='reference'); print('[Focuslyra] Kokoro test WAV:',r['relative_audio_path'])"
if errorlevel 1 goto :failed

echo.
echo [4/5] Installing pronunciation analysis...
".venv\Scripts\python.exe" -m pip install -r requirements-pronunciation.txt
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -c "import parselmouth, soundfile, av, numpy; from app.pronunciation_service import pronunciation_status; print('[Focuslyra]',pronunciation_status()['note'])"
if errorlevel 1 goto :failed

echo.
echo [5/5] Verifying Focuslyra local engines...
".venv\Scripts\python.exe" -c "from app.providers import get_provider_statuses; from app.audio_service import audio_status; from app.tts_service import tts_status; from app.pronunciation_service import pronunciation_status; print('AI:',next((p['note'] for p in get_provider_statuses() if p['id']=='ollama'),'missing')); print('Whisper:',audio_status()['note']); print('TTS:',tts_status()['note']); print('Pronunciation:',pronunciation_status()['note'])"
if errorlevel 1 goto :failed

echo.
echo ==================================================
echo [Focuslyra] FREE LOCAL STACK READY
echo   Qwen       : local text intelligence
echo   Whisper    : local speech transcription
echo   Kokoro     : local persistent speech generation
echo   Praat      : local pronunciation/acoustic analysis
echo   Paid API   : not required
echo ==================================================
echo.
echo You can now start Focuslyra with run.bat
pause
exit /b 0

:failed
echo.
echo ==================================================
echo [ERROR] Focuslyra local setup did not finish.
echo Copy or screenshot the error above and send it to Iris.
echo ==================================================
echo.
pause
exit /b 1
