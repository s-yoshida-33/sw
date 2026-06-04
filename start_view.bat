@echo off
REM Display Viewer - Startup registration and launch
title Display Viewer

REM --- Startup registration ---
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "BATCH_PATH=%~f0"

if not exist "%STARTUP_DIR%\%~nx0" (
    echo [INFO] First run: registering this batch in Startup...
    copy "%BATCH_PATH%" "%STARTUP_DIR%" >nul
) else (
    echo [INFO] Startup registration already exists
)

REM Start Python view.py in new window with logging
set "PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
set "VIEW_PATH=C:\sw\view\view.py"

echo [INFO] Starting View...
start "Display Viewer" /min "%PYTHON_PATH%" "%VIEW_PATH%"
