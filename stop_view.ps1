# Display Viewer - Stop
$host.UI.RawUI.WindowTitle = "Stop View"
Write-Host "============================================================"
Write-Host " Switch System - Stop View"
Write-Host "============================================================"
Write-Host ""

Write-Host "[INFO] Stopping view.py..."
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*view.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

$remaining = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*view.py*" }
if ($remaining) {
    Write-Host "[ERROR] Failed to stop view.py. Re-run this script as Administrator." -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[INFO] view.py stopped."

Write-Host ""
Write-Host "[INFO] Display process stopped."
Write-Host ""
Read-Host "Press Enter to exit"
