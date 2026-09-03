@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Focuslyra Pronunciation Setup

echo ==================================================
echo  Focuslyra - Pronunciation Engine Setup
echo ==================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [Focuslyra] Python environment is missing. Running setup first...
  call setup.bat
  if errorlevel 1 goto :failed
)

echo [Focuslyra] Installing local acoustic-analysis tools...
".venv\Scripts\python.exe" -m pip install -r requirements-pronunciation.txt
if errorlevel 1 goto :failed

echo [Focuslyra] Verifying Praat/Parselmouth...
".venv\Scripts\python.exe" -c "import parselmouth, numpy, av, soundfile; print('[Focuslyra] Pronunciation acoustic dependencies OK')"
if errorlevel 1 goto :failed

for /f "tokens=*" %%H in ('certutil -hashfile requirements-pronunciation.txt SHA256 ^| findstr /v /i "hash certutil"') do set "REQ_HASH=%%H"
if not exist ".venv\focuslyra" mkdir ".venv\focuslyra"
> ".venv\focuslyra\requirements-pronunciation.sha256" echo %REQ_HASH: =%

echo.
echo ==================================================
echo [Focuslyra] Acoustic pronunciation analysis is ready.
echo This stage measures the real signal locally.
echo It does NOT pretend to score individual phonemes yet.
echo Target-specific phoneme alignment/calibration comes next.
echo Cost: 0 EUR
echo ==================================================
echo.
pause
exit /b 0

:failed
echo.
echo [ERROR] Pronunciation setup did not finish.
echo Copy the error above if you need help.
pause
exit /b 1
