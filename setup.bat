@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Focuslyra Setup

echo ==================================================
echo  Focuslyra Setup
echo ==================================================
echo.

call :find_python
if defined PY_EXE goto :python_ready

echo [Focuslyra] Python 3.11+ was not found.
echo [Focuslyra] Trying to install Python 3.12 automatically...
echo.

where winget >nul 2>nul
if errorlevel 1 goto :no_winget

winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :python_install_failed

call :find_python
if defined PY_EXE goto :python_ready

echo [Focuslyra] Python appears to have been installed, but Focuslyra
echo [Focuslyra] cannot locate python.exe yet. Close this window and run run.bat again.
goto :failed

:python_ready
echo [Focuslyra] Using Python: %PY_EXE% %PY_ARGS%
"%PY_EXE%" %PY_ARGS% -c "import sys; print('[Focuslyra] Python', sys.version.split()[0]); raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo [ERROR] Focuslyra requires Python 3.11 or newer.
  goto :failed
)

if not exist ".venv\Scripts\python.exe" (
  echo [Focuslyra] Creating local Python environment...
  "%PY_EXE%" %PY_ARGS% -m venv .venv
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

echo [Focuslyra] Installing/updating core dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :pip_failed

rem Verify the imports that currently prevent the application from starting if absent.
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, requests, google.auth, googleapiclient, google_auth_oauthlib; print('[Focuslyra] Core dependency check OK')"
if errorlevel 1 goto :pip_failed

rem Store the dependency-file hash. run.bat compares this on every launch so future
rem Git updates can install new packages automatically without recreating the venv.
powershell -NoProfile -Command "(Get-FileHash 'requirements.txt' -Algorithm SHA256).Hash | Set-Content '.venv\.focuslyra_requirements_hash' -Encoding ascii"
if errorlevel 1 (
  echo [WARN] Could not save dependency hash. Focuslyra will still work, but may re-check packages next launch.
)

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

:find_python
set "PY_EXE="
set "PY_ARGS="

py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PY_EXE=py"
  set "PY_ARGS=-3.12"
  exit /b 0
)

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PY_EXE=py"
  set "PY_ARGS=-3"
  exit /b 0
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PY_EXE=python"
  exit /b 0
)

for %%V in (314 313 312 311) do (
  if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" (
    set "PY_EXE=%LocalAppData%\Programs\Python\Python%%V\python.exe"
    set "PY_ARGS="
    exit /b 0
  )
)
exit /b 1

:no_winget
echo [ERROR] Windows Package Manager (winget) is not available.
echo [ERROR] Python could not be installed automatically.
echo.
echo Install Python 3.12 from https://www.python.org/downloads/windows/
echo Then run run.bat again.
goto :failed

:python_install_failed
echo.
echo [ERROR] Automatic Python installation failed.
echo If Windows showed a permission prompt, allow it and run run.bat again.
goto :failed

:pip_failed
echo.
echo [ERROR] Python dependencies could not be installed or verified.
echo Check your internet connection and the error above.
goto :failed

:failed
echo.
echo The window will stay open so the error is visible.
pause
exit /b 1
