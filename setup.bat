@echo off
setlocal
cd /d "%~dp0"

echo [Focuslyra] Creating local Python environment...
if not exist .venv (
  py -m venv .venv 2>nul || python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist .env (
  copy .env.example .env >nul
  echo [Focuslyra] Created .env from safe defaults.
)

if not exist media\recordings mkdir media\recordings
if not exist sources mkdir sources
if not exist indexes mkdir indexes

echo.
echo [Focuslyra] Setup complete.
echo Paid AI remains OFF unless you explicitly change ALLOW_PAID_AI in .env.
endlocal
