@echo off
chcp 65001 > nul
cd /d "%~dp0"
title mechnik-osint

echo [mechnik-osint] проверка зависимостей...
python -c "import aiohttp" 2>nul
if errorlevel 1 (
    echo [mechnik-osint] установка aiohttp...
    pip install aiohttp
)

echo [mechnik-osint] запуск сервера на http://localhost:8080
start http://localhost:8080
python server.py
pause
