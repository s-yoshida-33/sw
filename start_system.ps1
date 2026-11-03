# MQTT Server - Scheduled Task registration and launch
$ErrorActionPreference = "Stop"
$host.UI.RawUI.WindowTitle = "MQTT Server"

$MosquittoPath = "C:\Program Files (x86)\mosquitto\mosquitto.exe"
$MosquittoConf = "C:\sw\config\mosquitto.conf"
$MosquittoLog  = "C:\sw\logs\mqtt.log"   # must match log_dest in mosquitto.conf
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

# --- Mosquitto log file permissions ---
# Mosquitto creates its log file with an ACL for the creating account only (not
# inherited from C:\sw\logs). When this script used to start Mosquitto as the
# logged-on administrator, the log was created for that account only, and the
# SYSTEM-run MosquittoAutoStart task after the next reboot could not write it:
# Mosquitto keeps running silently and the log simply stops. Create the file if
# needed and reset it to the folder's inherited ACL (SYSTEM, Administrators,
# Users), which Mosquitto keeps when it opens an existing file.
$MosquittoLogDir = Split-Path $MosquittoLog
if (-not (Test-Path $MosquittoLogDir)) { New-Item -ItemType Directory -Path $MosquittoLogDir | Out-Null }
if (-not (Test-Path $MosquittoLog)) { New-Item -ItemType File -Path $MosquittoLog | Out-Null }
icacls $MosquittoLog /reset | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Could not reset permissions on $MosquittoLog (icacls exit code $LASTEXITCODE)"
}

# Start Mosquitto through its scheduled task, so it always runs as SYSTEM exactly as
# it does after a reboot. A Mosquitto already running (e.g. from an earlier run of
# this script) is stopped first: it holds port 1883, and it opened the log before
# the permission fix above. Connected clients reconnect on their own.
$running = Get-Process -Name "mosquitto" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "[INFO] Stopping running Mosquitto (PID $($running.Id -join ', '))..."
    $running | Stop-Process -Force
    $running | Wait-Process -Timeout 10 -ErrorAction SilentlyContinue
}
Write-Host "[INFO] Starting Mosquitto (scheduled task 'MosquittoAutoStart')..."
Start-ScheduledTask -TaskName "MosquittoAutoStart"
Start-Sleep -Seconds 2
if (-not (Get-Process -Name "mosquitto" -ErrorAction SilentlyContinue)) {
    Write-Host "[WARN] Mosquitto is not running. Check $MosquittoConf and $MosquittoLog"
}

# Start the signal logger in background now (log configured in signal_logger.py)
Write-Host "[INFO] Starting Signal Logger..."
Start-Process -FilePath $PythonPath -ArgumentList "`"$SignalLogger`"" -WindowStyle Minimized
