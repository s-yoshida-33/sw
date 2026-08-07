# MQTT Server - Stop
$host.UI.RawUI.WindowTitle = "Stop Server"
Write-Host "============================================================"
Write-Host " Switch System - Stop Server"
Write-Host "============================================================"
Write-Host ""

Write-Host "[INFO] Stopping mosquitto..."
Get-Process -Name "mosquitto" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if (Get-Process -Name "mosquitto" -ErrorAction SilentlyContinue) {
    Write-Host "[ERROR] Failed to stop mosquitto. Re-run this script as Administrator." -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[INFO] mosquitto stopped."

Write-Host ""
Write-Host "[INFO] All server processes stopped."
Write-Host ""
Read-Host "Press Enter to exit"
