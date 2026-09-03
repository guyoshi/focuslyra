@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Focuslyra Setup

echo ==================================================
echo  Focuslyra Setup
echo ==================================================
echo.

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py"

if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
  echo [ERROR] Python was not found on this PC.
  echo Install Python 3.11 or newer from https://www.python.org/downloads/
  echo IMPORTANT: enable "Add python.exe to PATH" during installation.
  goto :failed
)

echo [Focuslyra] Using Python launcher: %PY_CMD%
%PY_CMD% -c "import sys; print('[Focuslyra] Python', sys.version.split()[0]); raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo [ERROR] Focuslyra requires Python 3.11 or newer.
  goto :failed
)

if not exist ".venv\Scripts\python.exe" (
  echo [Focuslyra] Creating local Python environment...
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Could not create the virtual environment.
    goto :failed
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment is incomplete.
  goto :failed
)

echo [Focuslyra] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :pip_failed

echo [Focuslyra] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :pip_failed

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo [Focuslyra] Created .env from safe defaults.
)

if not exist "media\recordings" mkdir "media\recordings"
if not exist "sources" mkdir "sources"
if not exist "indexes" mkdir "indexes"
if not exist "logs" mkdir "logs"

echo.
echo [Focuslyra] Setup complete.
echo [Focuslyra] Paid AI remains OFF unless you explicitly enable it in .env.
exit /b 0

:pip_failed
echo.
echo [ERROR] Python dependencies could not be installed.
echo Check your internet connection and the error above.
goto :failed

:failed
echo.
echo The window will stay open so the error is visible.
pause
exit /b 1
