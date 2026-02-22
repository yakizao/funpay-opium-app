@echo off
chcp 65001 >nul 2>&1
title Opium - Restarting
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       OPIUM - Restarting...          ║
echo  ╚══════════════════════════════════════╝
echo.

call "%~dp0stop.bat"
timeout /t 2 /nobreak >nul
call "%~dp0start.bat"