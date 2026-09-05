@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Focuslyra

if not exist logs mkdir logs
set "LOG_FILE=%CD%\logs\focuslyra.log"

echo ==================================================
echo  Focuslyra
echo ==================================================
echo.

rem Honour FOCUSLYRA_HOST/FOCUSLYRA_PORT from .env instead of hardcoding
rem 127.0.0.1:8765 everywhere, so a customised .env actually takes effect.
set "FOCUSLYRA_HOST=127.0.0.1"
set "FOCUSLYRA_PORT=8765"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /r /c:"FOCUSLYRA_HOST=" ".env"`) do if not "%%B"=="" set "FOCUSLYRA_HOST=%%B"
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /r /c:"FOCUSLYRA_PORT=" ".env"`) do if not "%%B"=="" set "FOCUSLYRA_PORT=%%B"
)

if not exist ".venv\Scripts\python.exe" (
  echo [Focuslyra] First run detected. Running setup...
  call setup.bat
  if errorlevel 1 goto :setup_failed
)

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] The Python virtual environment was not created.
  goto :failed
)

rem Compare the current requirements file with the one last installed into this venv.
set "REQ_HASH="
set "INSTALLED_HASH="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash 'requirements.txt' -Algorithm SHA256).Hash"`) do set "REQ_HASH=%%H"
if exist ".venv\.focuslyra_requirements_hash" set /p INSTALLED_HASH=<".venv\.focuslyra_requirements_hash"

if not defined REQ_HASH (
  echo [WARN] Could not calculate dependency hash. Verifying imports directly...
) else if /I not "%REQ_HASH%"=="%INSTALLED_HASH%" (
  echo [Focuslyra] Project dependencies changed since the last run.
  echo [Focuslyra] Updating local environment automatically...
  call setup.bat
  if errorlevel 1 goto :setup_failed
)

rem Final safety check. This also repairs old venvs created before dependency tracking existed.
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, requests, google.auth, googleapiclient, google_auth_oauthlib, pykakasi" >nul 2>nul
if errorlevel 1 (
  echo [Focuslyra] A required package is missing. Repairing the local environment...
  call setup.bat
  if errorlevel 1 goto :setup_failed
)

rem If local Kokoro was already configured, keep its optional dependencies in
rem sync too. This lets pronunciation fixes arrive with git pull + restart
rem instead of asking the learner to discover another setup script manually.
if exist "models\tts\kokoro\kokoro-v1.0.onnx" call :sync_tts_dependencies
if errorlevel 1 goto :setup_failed

echo [Focuslyra] Starting local server...
echo [Focuslyra] URL: http://%FOCUSLYRA_HOST%:%FOCUSLYRA_PORT%
echo [Focuslyra] Log: %LOG_FILE%
echo.

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://%FOCUSLYRA_HOST%:%FOCUSLYRA_PORT%'" >nul 2>nul

".venv\Scripts\python.exe" -m uvicorn app.main:app --host %FOCUSLYRA_HOST% --port %FOCUSLYRA_PORT% --reload 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [ERROR] Focuslyra stopped with exit code %EXIT_CODE%.
  echo Copy the error shown above if you need help.
  goto :failed
)

goto :eof

:sync_tts_dependencies
if not exist "requirements-tts.txt" exit /b 0
set "TTS_REQ_HASH="
set "TTS_INSTALLED_HASH="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash 'requirements-tts.txt' -Algorithm SHA256).Hash"`) do set "TTS_REQ_HASH=%%H"
if exist ".venv\focuslyra\requirements-tts.sha256" set /p TTS_INSTALLED_HASH=<".venv\focuslyra\requirements-tts.sha256"
if not defined TTS_REQ_HASH exit /b 0
if /I "%TTS_REQ_HASH%"=="%TTS_INSTALLED_HASH%" exit /b 0
echo [Focuslyra] Local voice dependencies changed. Updating them automatically...
".venv\Scripts\python.exe" -m pip install -r requirements-tts.txt
if errorlevel 1 exit /b 1
if not exist ".venv\focuslyra" mkdir ".venv\focuslyra"
> ".venv\focuslyra\requirements-tts.sha256" echo %TTS_REQ_HASH%
echo [Focuslyra] Local voice dependencies are up to date.
exit /b 0

:setup_failed
echo.
echo [ERROR] Setup failed, so Focuslyra cannot start yet.
goto :failed

:failed
echo.
echo The window will stay open so the error is visible.
pause
exit /b 1
