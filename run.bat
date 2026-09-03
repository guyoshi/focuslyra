@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  call setup.bat
)

call .venv\Scripts\activate.bat
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8765"

echo [Focuslyra] Starting at http://127.0.0.1:8765
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
endlocal
