# Mosquitto Launcher - rotates the previous day's log out of the fixed
# 'mqtt.log' filename Mosquitto writes to, archives past months into a zip,
# drops archives older than the retention window, then starts Mosquitto.
$MosquittoPath      = "C:\Program Files (x86)\mosquitto\mosquitto.exe"
$MosquittoConf      = "C:\sw\config\mosquitto.conf"
$LogDir             = "C:\sw\logs"
$CurrentLog         = Join-Path $LogDir "mqtt.log"
$ZipRetentionMonths = 12

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# --- Rotate mqtt.log to a dated file (its content predates this boot) ---
if (Test-Path $CurrentLog) {
    $dateStamp = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
    $dest = Join-Path $LogDir "mqtt-$dateStamp.log"
    if (Test-Path $dest) {
        Get-Content $CurrentLog | Add-Content -Path $dest
        Remove-Item $CurrentLog -Force
    } else {
        Move-Item -Path $CurrentLog -Destination $dest -Force
    }
}

# --- Archive daily logs from months other than the current one ---
$currentMonth = (Get-Date).ToString("yyyy-MM")
$months = Get-ChildItem -Path $LogDir -Filter "mqtt-*.log" | ForEach-Object {
    if ($_.Name -match '^mqtt-(\d{4}-\d{2})-\d{2}\.log$' -and $Matches[1] -ne $currentMonth) {
        $Matches[1]
    }
} | Select-Object -Unique

foreach ($month in $months) {
    $zipPath = Join-Path $LogDir "mqtt-$month.zip"
    $files = Get-ChildItem -Path $LogDir -Filter "mqtt-$month-*.log"
    if ($files) {
        Compress-Archive -Path $files.FullName -DestinationPath $zipPath -Update
        $files | Remove-Item -Force
    }
}

# --- Delete archives older than the retention window ---
$nowIndex = (Get-Date).Year * 12 + (Get-Date).Month
Get-ChildItem -Path $LogDir -Filter "mqtt-*.zip" | ForEach-Object {
    if ($_.Name -match '^mqtt-(\d{4})-(\d{2})\.zip$') {
        $zipIndex = [int]$Matches[1] * 12 + [int]$Matches[2]
        if ($nowIndex - $zipIndex -ge $ZipRetentionMonths) {
            Remove-Item $_.FullName -Force
        }
    }
}

# --- Start Mosquitto ---
Start-Process -FilePath $MosquittoPath -ArgumentList "-c `"$MosquittoConf`""
