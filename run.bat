@echo off
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

echo [Focuslyra] Starting local server...
echo [Focuslyra] URL: http://127.0.0.1:8765
echo [Focuslyra] Log: %LOG_FILE%
echo.

rem Open the browser a moment after Uvicorn starts.
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
