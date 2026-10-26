@echo off
chcp 65001 >nul
title MRKT SNIPER // MODRIX EDITION
color 0a
cd /d "%~dp0"
python sniper.py
pause
