@echo off
title Stop Server
echo ============================================================
echo  Switch System - Stop Server
echo ============================================================
echo.

REM Stop srv.py
echo [INFO] Stopping srv.py...
wmic process where "name='python.exe' and CommandLine like '%%srv.py%%'" delete >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq MQTT Server" >nul 2>&1
echo [INFO] srv.py stopped.

REM Stop mosquitto
echo [INFO] Stopping mosquitto...
taskkill /f /im mosquitto.exe >nul 2>&1
echo [INFO] mosquitto stopped.

echo.
echo [INFO] All server processes stopped.
echo.
pause
