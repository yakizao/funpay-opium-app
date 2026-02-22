@echo off
chcp 65001 >nul 2>&1
title Opium - Stopping
cd /d "%~dp0"

echo.
echo  Stopping Opium...
echo.

REM ─── Kill backend (uvicorn on port 8000) ───────────
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM ─── Kill frontend (vite on port 3000) ─────────────
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM ─── Close named windows ───────────────────────────
taskkill /FI "WINDOWTITLE eq Opium Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Opium Frontend*" /F >nul 2>&1

echo  Opium stopped.
echo.