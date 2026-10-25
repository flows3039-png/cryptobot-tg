@echo off
chcp 65001 > nul
title mechnik-osint Server
echo [mechnik-osint] Запуск локального сервера...
start http://localhost:8080
python server.py
pause
