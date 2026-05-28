@echo off
title Stop View
echo ============================================================
echo  Switch System - Stop View
echo ============================================================
echo.

REM Stop view.py
echo [INFO] Stopping view.py...
wmic process where "name='python.exe' and CommandLine like '%%view.py%%'" delete >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Display Viewer" >nul 2>&1
echo [INFO] view.py stopped.

echo.
echo [INFO] Display process stopped.
echo.
pause
