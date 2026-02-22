@echo off
chcp 65001 >nul 2>&1
title Opium - Install
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       OPIUM - Installation           ║
echo  ╚══════════════════════════════════════╝
echo.

REM ─── Check Python ───────────────────────────────────
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found! Install Python 3.11+ and add to PATH.
    echo  https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo  Found Python %%v

REM ─── Check Node.js ─────────────────────────────────
echo.
echo [2/4] Checking Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Node.js not found! Install Node.js 18+ and add to PATH.
    echo  https://nodejs.org/
    pause
    exit /b 1
)
for /f %%v in ('node --version 2^>^&1') do echo  Found Node.js %%v

REM ─── Create venv + install Python deps ─────────────
echo.
echo [3/4] Setting up Python virtual environment...
if not exist ".venv" (
    echo  Creating .venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo  .venv created.
) else (
    echo  .venv already exists, skipping creation.
)

echo  Installing Python dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)
echo  Python dependencies installed.

REM ─── Install frontend deps ─────────────────────────
echo.
echo [4/4] Installing frontend dependencies...
cd frontend
call npm install --silent 2>nul
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install frontend dependencies.
    cd ..
    pause
    exit /b 1
)
echo  Frontend dependencies installed.

REM ─── Build frontend for production ─────────────────
echo.
echo  Building frontend...
call npm run build --silent 2>nul
if %errorlevel% neq 0 (
    echo  [WARN] Frontend build failed. You can still run in dev mode.
) else (
    echo  Frontend built successfully.
)
cd ..

echo.
echo  ╔══════════════════════════════════════╗
echo  ║     Installation complete!           ║
echo  ║                                      ║
echo  ║  1. Configure .env file              ║
echo  ║  2. Run start.bat to launch          ║
echo  ╚══════════════════════════════════════╝
echo.
pause
