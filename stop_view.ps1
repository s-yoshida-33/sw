# Display Viewer - Stop
$host.UI.RawUI.WindowTitle = "Stop View"
Write-Host "============================================================"
Write-Host " Switch System - Stop View"
Write-Host "============================================================"
Write-Host ""

Write-Host "[INFO] Stopping view.py..."
# pythonw.exe since view.py v2.4; python.exe is still matched for STBs launched before that.
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*view.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

$remaining = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
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
