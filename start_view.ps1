# Display Viewer - Scheduled Task registration and launch
$ErrorActionPreference = "Stop"
$host.UI.RawUI.WindowTitle = "Display Viewer"

$SwRoot     = "C:\sw"
$PythonPath = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python310\python.exe"
$ViewPath   = Join-Path $SwRoot "view\view.py"
$TaskName   = "DisplayViewerAutoStart"

if (-not (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] Registering scheduled task '$TaskName'..."
} else {
    Write-Host "[INFO] Updating scheduled task '$TaskName'..."
}
# Delay app launch after logon so the server's MQTT broker (started at boot) is
# reliably up before view.py's first connection attempt.
$action    = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$ViewPath`""
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = "PT90S"
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings
$task.Author = "$env:USERDOMAIN\$env:USERNAME"
Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null

Write-Host "[INFO] Starting View..."
Start-Process -FilePath $PythonPath -ArgumentList "`"$ViewPath`"" -WindowStyle Minimized
