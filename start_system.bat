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

REM Start Mosquitto in background (logs configured in mosquitto.conf)
REM Adjust path if necessary
set "MOSQUITTO_PATH=C:\Program Files (x86)\mosquitto\mosquitto.exe"
set "MOSQUITTO_CONF=C:\sw\config\mosquitto.conf"

start "" "%MOSQUITTO_PATH%" -c "%MOSQUITTO_CONF%"

REM Wait a few seconds to ensure Mosquitto starts
timeout /t 2 /nobreak >nul

REM Start Python server in same window
REM Adjust Python path if necessary
set "PYTHON_PATH=C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
set "SRV_PATH=C:\sw\server\srv.py"

echo [INFO] Starting MQTT Server...
cmd /k "%PYTHON_PATH% %SRV_PATH%"
