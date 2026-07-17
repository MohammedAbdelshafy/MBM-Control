<#
.SYNOPSIS
  MBM Watchdog — Monitors the Lead Engine heartbeat.
  If the engine hasn't reported in > 5 hours, sends a Telegram alert and
  optionally force-starts a new run.

.NOTES
  Runs via Windows Task Scheduler every 30 minutes.
#>

param(
  [string]$ConfigDir   = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Config",
  [string]$ScriptsDir  = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Scripts",
  [string]$LogDir      = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Logs",
  [int]$MaxStalenessHours = 5
)

$Python = "C:\Users\omare\AppData\Local\Programs\Python\Python312\python.exe"
$HeartbeatFile = "$ConfigDir\heartbeat.json"
$NotifyPy = "$ScriptsDir\telegram_notify.py"
$WatchdogLog = "$LogDir\watchdog.log"
$EngineScript = "$ScriptsDir\lead_engine_forever.ps1"

function WLog {
  param([string]$Msg)
  $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Msg"
  Add-Content -Path $WatchdogLog -Value $line -Encoding utf8
}

function TelegramAlert {
  param([string]$Text)
  try {
    & $Python -c @"
import sys; sys.path.insert(0, r'$ScriptsDir')
from telegram_notify import send_message
send_message(r'''$($Text -replace "'","")''')
"@ 2>&1 | Out-Null
  } catch {}
}

# ── Check heartbeat ─────────────────────────────────────────
WLog "Watchdog check started"

if (-not (Test-Path $HeartbeatFile)) {
  WLog "No heartbeat file found — engine may have never run."
  TelegramAlert "*MBM Watchdog* `u26a0`ufe0f`nNo heartbeat file found. The lead engine may have never started.`nForce-starting now..."

  # Force-start the engine
  Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$EngineScript`"" -WindowStyle Hidden
  WLog "Force-started engine."
  exit 0
}

# Parse heartbeat
try {
  $hb = Get-Content $HeartbeatFile -Raw | ConvertFrom-Json
  $lastBeat = [DateTime]::Parse($hb.timestamp)
  $ageMins = [math]::Round(((Get-Date) - $lastBeat).TotalMinutes, 1)
  $ageHours = [math]::Round($ageMins / 60, 1)

  WLog "Heartbeat age: ${ageHours}h | Status: $($hb.status) | Leads: $($hb.leads_found)"

  if ($ageMins -gt ($MaxStalenessHours * 60)) {
    # Engine is stale — alert and restart
    WLog "STALE heartbeat (${ageHours}h > ${MaxStalenessHours}h). Restarting engine."

    $alertMsg = @"
*MBM Watchdog ALERT* `u{1F6A8}

Engine heartbeat is *${ageHours} hours old* (max: ${MaxStalenessHours}h).
Last status: $($hb.status)
Last leads found: $($hb.leads_found)
Last error: $($hb.error)

*Auto-restarting the engine now...*
"@
    TelegramAlert $alertMsg

    # Kill any stuck engine processes
    Get-Process -Name "python" -ErrorAction SilentlyContinue |
      Where-Object { $_.StartTime -lt (Get-Date).AddHours(-4) } |
      Stop-Process -Force -ErrorAction SilentlyContinue

    # Force-start new run
    Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$EngineScript`"" -WindowStyle Hidden
    WLog "Force-started new engine run."
  }
  elseif ($hb.status -eq "running") {
    # Engine is currently running — check if it's stuck
    if ($ageMins -gt 120) {
      WLog "Engine has been 'running' for ${ageHours}h — may be stuck."
      TelegramAlert "*MBM Watchdog* `u26a0`ufe0f`nEngine has been in 'running' state for ${ageHours}h. May be stuck. Will restart if it doesn't finish within ${MaxStalenessHours}h."
    } else {
      WLog "Engine is currently running (${ageMins}min). Normal."
    }
  }
  else {
    WLog "Engine healthy. Next check in 30 min."
  }
} catch {
  WLog "Error parsing heartbeat: $_"
  TelegramAlert "*MBM Watchdog ERROR*`nCould not parse heartbeat file: $_"
}

# ── Clean old watchdog logs (keep 7 days of entries) ────────
if (Test-Path $WatchdogLog) {
  $lines = Get-Content $WatchdogLog
  if ($lines.Count -gt 2000) {
    $lines[-1000..-1] | Set-Content $WatchdogLog -Encoding utf8
    WLog "Trimmed watchdog log to last 1000 entries."
  }
}

WLog "Watchdog check complete."
