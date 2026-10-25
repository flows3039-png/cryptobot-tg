@echo off
chcp 65001 > nul
cd /d "%~dp0\mechnik-osint"
title mechnik-osint

echo [mechnik-osint] освобождение порта 8080 при необходимости...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo [mechnik-osint] запуск сервера...
start http://localhost:8080
python server.py
pause
