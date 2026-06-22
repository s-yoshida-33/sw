@echo off
REM Display Viewer - Startup registration and launch
title Display Viewer

REM --- Startup registration (always overwrite to keep latest version) ---
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "BATCH_PATH=%~f0"
copy /Y "%BATCH_PATH%" "%STARTUP_DIR%" >nul
echo [INFO] Startup registration updated

REM --- Resolve Python path ---
set "VIEW_PATH=C:\sw\view\view.py"
set "PYTHON_PATH="

REM 1. Per-user install (LocalAppData)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto :launch
)

REM 2. System-wide install (Program Files)
if exist "C:\Program Files\Python310\python.exe" (
    set "PYTHON_PATH=C:\Program Files\Python310\python.exe"
    goto :launch
)

REM 3. Windows Python Launcher (py.exe)
where py >nul 2>&1
if %errorlevel% == 0 (
    set "PYTHON_PATH=py"
    goto :launch
)

REM 4. python in PATH
where python >nul 2>&1
if %errorlevel% == 0 (
    set "PYTHON_PATH=python"
    goto :launch
)

echo [ERROR] Python not found. Install Python 3.10 and try again.
pause
exit /b 1

:launch
echo [INFO] Python: %PYTHON_PATH%
echo [INFO] Starting View...
start "Display Viewer" /min "%PYTHON_PATH%" "%VIEW_PATH%"
