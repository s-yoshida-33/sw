# MQTT Server - Scheduled Task registration and launch
$ErrorActionPreference = "Stop"
$host.UI.RawUI.WindowTitle = "MQTT Server"

$MosquittoPath = "C:\Program Files (x86)\mosquitto\mosquitto.exe"
$MosquittoConf = "C:\sw\config\mosquitto.conf"
$PythonPath    = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python310\python.exe"
$SignalLogger  = "C:\sw\server\signal_logger.py"

# --- Disable the Windows service registered by the Mosquitto installer ---
# (it auto-starts with the default config and duplicates the process started below via config\mosquitto.conf)
$MosquittoService = Get-Service -Name "mosquitto" -ErrorAction SilentlyContinue
if ($MosquittoService -and $MosquittoService.StartType -ne "Disabled") {
    Write-Host "[INFO] Disabling default 'mosquitto' Windows service..."
    Stop-Service -Name "mosquitto" -ErrorAction SilentlyContinue
    Set-Service -Name "mosquitto" -StartupType Disabled
}

# --- Scheduled task registration ---
# Every task below is re-registered with -Force on every run, even if a task of
# that name already exists. A task's registered action is a snapshot taken at
# registration time; if this script later changes what a task should launch,
# a plain "skip if it already exists" check would leave already-deployed
# servers permanently running the stale, previously-registered action.
function Register-SwTask {
    param($Name, $Action, $Trigger, $Settings = $null)
    if (-not (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue)) {
        Write-Host "[INFO] Registering scheduled task '$Name'..."
    } else {
        Write-Host "[INFO] Updating scheduled task '$Name'..."
    }
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    if ($Settings) {
        $task = New-ScheduledTask -Action $Action -Trigger $Trigger -Principal $principal -Settings $Settings
    } else {
        $task = New-ScheduledTask -Action $Action -Trigger $Trigger -Principal $principal
    }
    $task.Author = "$env:USERDOMAIN\$env:USERNAME"
    Register-ScheduledTask -TaskName $Name -InputObject $task -Force | Out-Null
}

$AtStartupSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Mosquitto (system boot, no interactive logon needed)
Register-SwTask -Name "MosquittoAutoStart" `
    -Action (New-ScheduledTaskAction -Execute $MosquittoPath -Argument "-c `"$MosquittoConf`"") `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Settings $AtStartupSettings

# Daily restart (3:00 AM)
Register-SwTask -Name "SrvDailyRestart" `
    -Action (New-ScheduledTaskAction -Execute "shutdown.exe" -Argument "/r /f /t 0") `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "03:00")

# Signal logger (system boot)
Register-SwTask -Name "SignalLoggerAutoStart" `
    -Action (New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$SignalLogger`"") `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Settings $AtStartupSettings

# Start Mosquitto and the signal logger in background now (logs configured in mosquitto.conf / signal_logger.py)
Write-Host "[INFO] Starting Mosquitto..."
Start-Process -FilePath $MosquittoPath -ArgumentList "-c `"$MosquittoConf`""
Write-Host "[INFO] Starting Signal Logger..."
Start-Process -FilePath $PythonPath -ArgumentList "`"$SignalLogger`"" -WindowStyle Minimized
