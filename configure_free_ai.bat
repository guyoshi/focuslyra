@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Focuslyra Free AI Setup

echo ==================================================
echo  Focuslyra - Free AI Setup
echo ==================================================
echo.
echo This will install Ollama locally if needed and download
echo the multilingual qwen3:4b model (about 2.5 GB).
echo No paid API is enabled.
echo.

set "OLLAMA_EXE="
call :find_ollama
if defined OLLAMA_EXE goto :ollama_ready

echo [Focuslyra] Ollama was not found. Installing it automatically...
where winget >nul 2>nul
if errorlevel 1 goto :no_winget

winget install --id Ollama.Ollama -e --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :install_failed

call :find_ollama
if not defined OLLAMA_EXE (
  echo.
  echo [Focuslyra] Ollama appears to be installed, but this terminal cannot see it yet.
  echo Close this window and run configure_free_ai.bat again.
  goto :failed
)

:ollama_ready
echo [Focuslyra] Ollama found: %OLLAMA_EXE%
echo [Focuslyra] Starting local Ollama service if needed...
start "" /min "%OLLAMA_EXE%" serve >nul 2>nul

rem Give the local service a moment to start.
powershell -NoProfile -Command "Start-Sleep -Seconds 3" >nul 2>nul

echo [Focuslyra] Downloading multilingual model qwen3:4b...
echo [Focuslyra] This is a one-time download of roughly 2.5 GB.
"%OLLAMA_EXE%" pull qwen3:4b
if errorlevel 1 goto :pull_failed

if not exist ".env" copy ".env.example" ".env" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env'; $c=Get-Content $p -Raw; if($c -match '(?m)^OLLAMA_MODEL=.*$'){ $c=[regex]::Replace($c,'(?m)^OLLAMA_MODEL=.*$','OLLAMA_MODEL=qwen3:4b') } else { $c += [Environment]::NewLine + 'OLLAMA_MODEL=qwen3:4b' + [Environment]::NewLine }; if($c -match '(?m)^ALLOW_PAID_AI=.*$'){ $c=[regex]::Replace($c,'(?m)^ALLOW_PAID_AI=.*$','ALLOW_PAID_AI=false') }; Set-Content $p $c -Encoding UTF8"

echo.
echo ==================================================
echo [Focuslyra] Free local AI is ready.
echo [Focuslyra] Model: qwen3:4b
echo [Focuslyra] Paid AI: OFF
echo ==================================================
echo.
echo If Focuslyra is already open, restart run.bat and open the AI page.
pause
exit /b 0

:find_ollama
set "OLLAMA_EXE="
for /f "delims=" %%I in ('where ollama 2^>nul') do (
  if not defined OLLAMA_EXE set "OLLAMA_EXE=%%I"
)
if defined OLLAMA_EXE exit /b 0

if exist "%LocalAppData%\Programs\Ollama\ollama.exe" (
  set "OLLAMA_EXE=%LocalAppData%\Programs\Ollama\ollama.exe"
  exit /b 0
)
exit /b 1

:no_winget
echo [ERROR] winget is not available, so Ollama cannot be installed automatically.
echo Install Ollama from https://ollama.com/download/windows and run this file again.
goto :failed

:install_failed
echo [ERROR] Ollama installation failed.
goto :failed

:pull_failed
echo [ERROR] The qwen3:4b model could not be downloaded.
echo Check your internet connection and available disk space, then run this file again.
goto :failed

:failed
echo.
pause
exit /b 1
