@echo off
rem Double-click to talk: opens in the repo root (stc talk needs data\ relative to it).
rem Extra arguments pass through, e.g. a shortcut to: talk.bat --mein-tag
chcp 65001 >nul
cd /d "%~dp0.."
if not exist ".venv\Scripts\stc.exe" (
    echo .venv fehlt. Setup im README: python -m venv .venv, dann pip install -e ".[dev]"
    pause
    exit /b 1
)
.venv\Scripts\stc.exe talk %*
echo.
pause
