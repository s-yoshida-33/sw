# MQTT Server - Stop
$host.UI.RawUI.WindowTitle = "Stop Server"
Write-Host "============================================================"
Write-Host " Switch System - Stop Server"
Write-Host "============================================================"
Write-Host ""

Write-Host "[INFO] Stopping mosquitto..."
Get-Process -Name "mosquitto" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "[INFO] mosquitto stopped."

Write-Host ""
Write-Host "[INFO] All server processes stopped."
Write-Host ""
Read-Host "Press Enter to exit"
