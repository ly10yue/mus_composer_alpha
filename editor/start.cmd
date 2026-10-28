@echo off
cd /d "%~dp0\.."
python editor\main.py %*
if errorlevel 1 pause
