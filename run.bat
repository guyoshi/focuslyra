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
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, requests, google.auth, googleapiclient, google_auth_oauthlib" >nul 2>nul
if errorlevel 1 (
  echo [Focuslyra] A required package is missing. Repairing the local environment...
  call setup.bat
  if errorlevel 1 goto :setup_failed
)

echo [Focuslyra] Starting local server...
echo [Focuslyra] URL: http://127.0.0.1:8765
echo [Focuslyra] Log: %LOG_FILE%
echo.

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765'" >nul 2>nul

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [ERROR] Focuslyra stopped with exit code %EXIT_CODE%.
  echo Copy the error shown above if you need help.
  goto :failed
)

goto :eof

:setup_failed
echo.
echo [ERROR] Setup failed, so Focuslyra cannot start yet.
goto :failed

:failed
echo.
echo The window will stay open so the error is visible.
pause
exit /b 1
