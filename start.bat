@echo off
chcp 65001 >nul 2>&1
title Opium - Running
cd /d "%~dp0"

REM ─── Check venv ────────────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] .venv not found. Run install.bat first.
    pause
    exit /b 1
)

echo.
echo  ╔══════════════════════════════════════╗
echo  ║        OPIUM - Starting...           ║
echo  ╚══════════════════════════════════════╝
echo.

REM ─── Start Backend ─────────────────────────────────
echo [1/2] Starting backend...
start "Opium Backend" cmd /c "cd /d %~dp0 && call .venv\Scripts\activate.bat && python main.py"

timeout /t 3 /nobreak >nul

REM ─── Start Frontend (dev) ──────────────────────────
echo [2/2] Starting frontend (dev)...
start "Opium Frontend" cmd /c "cd /d %~dp0\frontend && npm run dev"

echo.
echo  Backend:  http://localhost:8000
echo  API Docs: http://localhost:8000/docs
echo  Frontend: http://localhost:3000
echo.
echo  To stop: run stop.bat
echo.