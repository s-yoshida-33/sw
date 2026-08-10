# MQTT Server - Scheduled Task registration and launch
$ErrorActionPreference = "Stop"
$host.UI.RawUI.WindowTitle = "MQTT Server"

$MosquittoPath = "C:\Program Files (x86)\mosquitto\mosquitto.exe"
$MosquittoConf = "C:\sw\config\mosquitto.conf"
$WrapperPath   = "C:\sw\run_mosquitto.ps1"

# --- Disable the Windows service registered by the Mosquitto installer ---
# (it auto-starts with the default config and duplicates the process started below via config\mosquitto.conf)
$MosquittoService = Get-Service -Name "mosquitto" -ErrorAction SilentlyContinue
if ($MosquittoService -and $MosquittoService.StartType -ne "Disabled") {
    Write-Host "[INFO] Disabling default 'mosquitto' Windows service..."
    Stop-Service -Name "mosquitto" -ErrorAction SilentlyContinue
    Set-Service -Name "mosquitto" -StartupType Disabled
}

# --- Mosquitto auto-start task registration (system boot, no interactive logon needed) ---
# Launches via run_mosquitto.ps1 (log rotation) rather than mosquitto.exe directly; re-registered
# with -Force on every run so existing servers pick up wrapper-script changes without manual steps.
$MosquittoTaskName = "MosquittoAutoStart"
if (-not (Get-ScheduledTask -TaskName $MosquittoTaskName -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] Registering scheduled task '$MosquittoTaskName'..."
} else {
    Write-Host "[INFO] Updating scheduled task '$MosquittoTaskName'..."
}
$action    = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$WrapperPath`""
$trigger   = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings
$task.Author = "$env:USERDOMAIN\$env:USERNAME"
Register-ScheduledTask -TaskName $MosquittoTaskName -InputObject $task -Force | Out-Null

# --- Daily restart task registration (3:00 AM) ---
$RestartTaskName = "SrvDailyRestart"
if (-not (Get-ScheduledTask -TaskName $RestartTaskName -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] Registering daily restart task at 03:00..."
    $action    = New-ScheduledTaskAction -Execute "shutdown.exe" -Argument "/r /f /t 0"
    $trigger   = New-ScheduledTaskTrigger -Daily -At "03:00"
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal
    $task.Author = "$env:USERDOMAIN\$env:USERNAME"
    Register-ScheduledTask -TaskName $RestartTaskName -InputObject $task | Out-Null
} else {
    Write-Host "[INFO] Daily restart task '$RestartTaskName' already registered."
}

# Start Mosquitto in background now, via the same wrapper the scheduled task uses
Write-Host "[INFO] Starting Mosquitto..."
powershell.exe -ExecutionPolicy Bypass -File $WrapperPath
