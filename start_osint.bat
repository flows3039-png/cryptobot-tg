@echo off
chcp 65001 > nul
cd /d "%~dp0\mechnik-osint"
title mechnik-osint

echo [mechnik-osint] запуск сервера...
start http://localhost:8080
python server.py
pause
