<#
.SYNOPSIS
  MBM Task Scheduler Installer
  Registers 3 Windows Scheduled Tasks for the never-stop lead engine.
  Run as Administrator.

.NOTES
  Tasks:
    1. MBM_LeadEngine_4HR  — Full pipeline every 4 hours
    2. MBM_DailyLeadPack   — Daily lead pack + email at 6 AM
    3. MBM_Watchdog         — Health check every 30 minutes
    4. MBM_DailyDigest      — Telegram digest at 9 AM
#>

$ScriptsDir = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Scripts"
$Python     = "C:\Users\omare\AppData\Local\Programs\Python\Python312\python.exe"
$PS         = "powershell.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MBM NEVER-STOP LEAD ENGINE — Task Scheduler Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Common settings ─────────────────────────────────────────
$Settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -DontStopOnIdleEnd `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -RestartInterval (New-TimeSpan -Minutes 5) `
  -RestartCount 3 `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$Principal = New-ScheduledTaskPrincipal `
  -UserId "omare" `
  -LogonType S4U `
  -RunLevel Limited

# ── Task 1: Lead Engine (every 4 hours) ─────────────────────
Write-Host "[1/4] Registering MBM_LeadEngine_4HR..." -ForegroundColor Yellow

$existingTask = Get-ScheduledTask -TaskName "MBM_LeadEngine_4HR" -ErrorAction SilentlyContinue
if ($existingTask) {
  Unregister-ScheduledTask -TaskName "MBM_LeadEngine_4HR" -Confirm:$false
  Write-Host "  Removed existing task."
}

$Action1 = New-ScheduledTaskAction `
  -Execute $PS `
  -Argument "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$ScriptsDir\lead_engine_forever.ps1`"" `
  -WorkingDirectory $ScriptsDir

# Trigger: every 4 hours, repeating indefinitely
$Trigger1 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
  -RepetitionInterval (New-TimeSpan -Hours 4) `
  -RepetitionDuration (New-TimeSpan -Days 3650)

Register-ScheduledTask `
  -TaskName "MBM_LeadEngine_4HR" `
  -Action $Action1 `
  -Trigger $Trigger1 `
  -Settings $Settings `
  -Principal $Principal `
  -Description "MBM Lead Engine: Full pipeline every 4 hours with retry, Telegram delivery, and heartbeat."

Write-Host "  [OK] MBM_LeadEngine_4HR registered (every 4 hours)" -ForegroundColor Green

# ── Task 2: Daily Lead Pack (6 AM) ──────────────────────────
Write-Host "[2/4] Registering MBM_DailyLeadPack..." -ForegroundColor Yellow

$existingTask = Get-ScheduledTask -TaskName "MBM_DailyLeadPack" -ErrorAction SilentlyContinue
if ($existingTask) {
  Unregister-ScheduledTask -TaskName "MBM_DailyLeadPack" -Confirm:$false
  Write-Host "  Removed existing (broken) task."
}

$Action2 = New-ScheduledTaskAction `
  -Execute $Python `
  -Argument "`"$ScriptsDir\daily_lead_pack.py`"" `
  -WorkingDirectory $ScriptsDir

$Trigger2 = New-ScheduledTaskTrigger -Daily -At "6:00AM"

Register-ScheduledTask `
  -TaskName "MBM_DailyLeadPack" `
  -Action $Action2 `
  -Trigger $Trigger2 `
  -Settings $Settings `
  -Principal $Principal `
  -Description "MBM Daily Lead Pack: Collects leads from free sources and emails wholesalers at 6 AM."

Write-Host "  [OK] MBM_DailyLeadPack registered (daily 6:00 AM)" -ForegroundColor Green

# ── Task 3: Watchdog (every 30 minutes) ─────────────────────
Write-Host "[3/4] Registering MBM_Watchdog..." -ForegroundColor Yellow

$existingTask = Get-ScheduledTask -TaskName "MBM_Watchdog" -ErrorAction SilentlyContinue
if ($existingTask) {
  Unregister-ScheduledTask -TaskName "MBM_Watchdog" -Confirm:$false
  Write-Host "  Removed existing task."
}

$Action3 = New-ScheduledTaskAction `
  -Execute $PS `
  -Argument "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$ScriptsDir\watchdog.ps1`"" `
  -WorkingDirectory $ScriptsDir

$Trigger3 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
  -RepetitionInterval (New-TimeSpan -Minutes 30) `
  -RepetitionDuration (New-TimeSpan -Days 3650)

Register-ScheduledTask `
  -TaskName "MBM_Watchdog" `
  -Action $Action3 `
  -Trigger $Trigger3 `
  -Settings $Settings `
  -Principal $Principal `
  -Description "MBM Watchdog: Checks engine heartbeat every 30 min, auto-restarts if dead."

Write-Host "  [OK] MBM_Watchdog registered (every 30 minutes)" -ForegroundColor Green

# ── Task 4: Daily Digest (9 AM) ─────────────────────────────
Write-Host "[4/4] Registering MBM_DailyDigest..." -ForegroundColor Yellow

$existingTask = Get-ScheduledTask -TaskName "MBM_DailyDigest" -ErrorAction SilentlyContinue
if ($existingTask) {
  Unregister-ScheduledTask -TaskName "MBM_DailyDigest" -Confirm:$false
  Write-Host "  Removed existing task."
}

$Action4 = New-ScheduledTaskAction `
  -Execute $Python `
  -Argument "`"$ScriptsDir\telegram_notify.py`" daily_digest" `
  -WorkingDirectory $ScriptsDir

$Trigger4 = New-ScheduledTaskTrigger -Daily -At "9:00AM"

Register-ScheduledTask `
  -TaskName "MBM_DailyDigest" `
  -Action $Action4 `
  -Trigger $Trigger4 `
  -Settings $Settings `
  -Principal $Principal `
  -Description "MBM Daily Digest: Sends Telegram summary of all runs from the past 24 hours at 9 AM."

Write-Host "  [OK] MBM_DailyDigest registered (daily 9:00 AM)" -ForegroundColor Green

# ── Task 5: Telegram Listener (Startup) ─────────────────────
Write-Host "[5/5] Registering MBM_TelegramListener..." -ForegroundColor Yellow

$existingTask = Get-ScheduledTask -TaskName "MBM_TelegramListener" -ErrorAction SilentlyContinue
if ($existingTask) {
  Unregister-ScheduledTask -TaskName "MBM_TelegramListener" -Confirm:$false
  Write-Host "  Removed existing task."
}

$Action5 = New-ScheduledTaskAction `
  -Execute $Python `
  -Argument "`"$ScriptsDir\telegram_listener.py`"" `
  -WorkingDirectory $ScriptsDir

$Trigger5 = New-ScheduledTaskTrigger -AtLogOn

Register-ScheduledTask `
  -TaskName "MBM_TelegramListener" `
  -Action $Action5 `
  -Trigger $Trigger5 `
  -Settings $Settings `
  -Principal $Principal `
  -Description "MBM Telegram Listener: Runs continuously on startup to handle commands."

Write-Host "  [OK] MBM_TelegramListener registered (at login)" -ForegroundColor Green

# ── Summary ──────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ALL 5 TASKS REGISTERED SUCCESSFULLY" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  MBM_LeadEngine_4HR  -> Every 4 hours (full pipeline + Telegram)" -ForegroundColor White
Write-Host "  MBM_DailyLeadPack   -> Daily 6:00 AM (lead packs + email)" -ForegroundColor White
Write-Host "  MBM_Watchdog        -> Every 30 min (health check + auto-restart)" -ForegroundColor White
Write-Host "  MBM_DailyDigest     -> Daily 9:00 AM (Telegram overnight summary)" -ForegroundColor White
Write-Host "  MBM_TelegramListener -> Login (continuous listener)" -ForegroundColor White
Write-Host ""
Write-Host "  The lead engine will NEVER stop. If it dies, the watchdog" -ForegroundColor Yellow
Write-Host "  restarts it and alerts you on Telegram." -ForegroundColor Yellow
Write-Host ""

# Show registered tasks
Get-ScheduledTask | Where-Object { $_.TaskName -like 'MBM_*' } | Format-Table TaskName, State -AutoSize
