@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Focuslyra Free Audio Setup

echo ==================================================
echo  Focuslyra - Free Local Audio Setup
echo ==================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [Focuslyra] Python environment is missing. Running setup first...
  call setup.bat
  if errorlevel 1 goto :failed
)

echo [Focuslyra] Installing local speech transcription...
".venv\Scripts\python.exe" -m pip install -r requirements-audio.txt
if errorlevel 1 goto :failed

if not exist ".env" copy ".env.example" ".env" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env'; $c=Get-Content $p -Raw; $pairs=@{'WHISPER_MODEL'='small';'WHISPER_DEVICE'='cpu';'WHISPER_COMPUTE_TYPE'='int8'}; foreach($k in $pairs.Keys){$v=$pairs[$k]; if($c -match ('(?m)^'+[regex]::Escape($k)+'=.*$')){$c=[regex]::Replace($c,'(?m)^'+[regex]::Escape($k)+'=.*$',($k+'='+$v))}else{$c += [Environment]::NewLine+$k+'='+$v+[Environment]::NewLine}}; Set-Content $p $c -Encoding UTF8"

echo.
echo [Focuslyra] Preloading Whisper 'small' locally.
echo [Focuslyra] This first download can take a few minutes and uses no paid API.
".venv\Scripts\python.exe" -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('[Focuslyra] Whisper small is ready.')"
if errorlevel 1 goto :failed

echo.
echo ==================================================
echo [Focuslyra] Free local audio is ready.
echo Recording: browser microphone
echo Transcription: Whisper small, local
echo Generated voice: browser TTS, free
echo Paid audio APIs: not required
echo ==================================================
echo.
pause
exit /b 0

:failed
echo.
echo [ERROR] Free audio setup did not finish.
echo Check the error above and run this file again.
pause
exit /b 1
