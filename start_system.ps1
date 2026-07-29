# MQTT Server - Scheduled Task registration and launch
$ErrorActionPreference = "Stop"
$host.UI.RawUI.WindowTitle = "MQTT Server"

$MosquittoPath = "C:\Program Files (x86)\mosquitto\mosquitto.exe"
$MosquittoConf = "C:\sw\config\mosquitto.conf"

# --- Mosquitto auto-start task registration (system boot, no interactive logon needed) ---
$MosquittoTaskName = "MosquittoAutoStart"
if (-not (Get-ScheduledTask -TaskName $MosquittoTaskName -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] Registering scheduled task '$MosquittoTaskName'..."
    $action    = New-ScheduledTaskAction -Execute $MosquittoPath -Argument "-c `"$MosquittoConf`""
    $trigger   = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $MosquittoTaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
} else {
    Write-Host "[INFO] Scheduled task '$MosquittoTaskName' already registered."
}

# --- Daily restart task registration (3:00 AM) ---
$RestartTaskName = "SrvDailyRestart"
if (-not (Get-ScheduledTask -TaskName $RestartTaskName -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] Registering daily restart task at 03:00..."
    $action    = New-ScheduledTaskAction -Execute "shutdown.exe" -Argument "/r /f /t 0"
    $trigger   = New-ScheduledTaskTrigger -Daily -At "03:00"
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName $RestartTaskName -Action $action -Trigger $trigger -Principal $principal | Out-Null
} else {
    Write-Host "[INFO] Daily restart task '$RestartTaskName' already registered."
}

# Start Mosquitto in background now (logs configured in mosquitto.conf)
Write-Host "[INFO] Starting Mosquitto..."
Start-Process -FilePath $MosquittoPath -ArgumentList "-c `"$MosquittoConf`""
