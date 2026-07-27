@echo off
title Stop Server
echo ============================================================
echo  Switch System - Stop Server
echo ============================================================
echo.

REM Stop mosquitto
echo [INFO] Stopping mosquitto...
taskkill /f /im mosquitto.exe >nul 2>&1
echo [INFO] mosquitto stopped.

echo.
echo [INFO] All server processes stopped.
echo.
pause
