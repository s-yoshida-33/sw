@echo off
REM MQTT Server - Startup registration and launch
title MQTT Server

REM --- Startup registration ---
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "BATCH_PATH=%~f0"

if not exist "%STARTUP_DIR%\%~nx0" (
    echo [INFO] First run: registering this batch in Startup...
    copy "%BATCH_PATH%" "%STARTUP_DIR%" >nul
) else (
    echo [INFO] Startup registration already exists
)

REM --- Daily restart task registration (3:00 AM) ---
schtasks /query /tn "SrvDailyRestart" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Registering daily restart task at 03:00...
    schtasks /create /tn "SrvDailyRestart" /tr "shutdown /r /f /t 0" /sc daily /st 03:00:00 /rl highest /f >nul
) else (
    echo [INFO] Daily restart task already registered
)

REM Start Mosquitto in background (logs configured in mosquitto.conf)
REM Adjust path if necessary
set "MOSQUITTO_PATH=C:\Program Files (x86)\mosquitto\mosquitto.exe"
set "MOSQUITTO_CONF=C:\sw\config\mosquitto.conf"

start "" "%MOSQUITTO_PATH%" -c "%MOSQUITTO_CONF%"
