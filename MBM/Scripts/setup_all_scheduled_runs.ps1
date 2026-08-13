# Master Scheduled Tasks Installer for JARVIS OS & MBM Subsystems
# Registers and updates all background automated runs with explicit paths and virtual environments.

$ProjectDir  = "C:\Users\omare\OneDrive\Desktop\AI"
$ScriptsDir  = "$ProjectDir\MBM\Scripts"
$MCDir       = "$ProjectDir\MissionControl"
$SocialDir   = "$ProjectDir\clipping-factory\MBM-Social"
$VenvPython  = "$ProjectDir\.venv\Scripts\python.exe"
$SysPython   = "C:\Users\omare\AppData\Local\Programs\Python\Python312\python.exe"
$PythonExe   = if (Test-Path $VenvPython) { $VenvPython } else { $SysPython }
$PS          = "powershell.exe"
$Cmd         = "cmd.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  JARVIS OS & MBM - MASTER TASK SCHEDULER INSTALLER" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Using Python Executable: $PythonExe" -ForegroundColor Green

# Common task settings
$Settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -DontStopOnIdleEnd `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -MultipleInstances IgnoreNew `
  -RestartInterval (New-TimeSpan -Minutes 5) `
  -RestartCount 3 `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$Principal = New-ScheduledTaskPrincipal `
  -UserId $env:USERNAME `
  -LogonType Interactive `
  -RunLevel Limited

# Helper to register task safely
function Register-Or-Update-Task {
    param(
        [string]$TaskName,
        [object]$Action,
        [object]$Trigger,
        [string]$Description
    )
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    Register-ScheduledTask `
      -TaskName $TaskName `
      -Action $Action `
      -Trigger $Trigger `
      -Settings $Settings `
      -Principal $Principal `
      -Description $Description | Out-Null
    Write-Host "  [OK] $TaskName registered successfully." -ForegroundColor Green
}

# 1. LeadsRunner5Daily (Fixed path & executable)
Write-Host "`n[1/8] Updating LeadsRunner5Daily (Runs 5x daily)..." -ForegroundColor Yellow
$Action1 = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$MCDir\leads_runner.py`"" -WorkingDirectory $MCDir
$Trigger1 = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 3) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-Or-Update-Task -TaskName "LeadsRunner5Daily" -Action $Action1 -Trigger $Trigger1 -Description "Dispatch find-leads Revenue Agent runs."

# 2. LeadsDailyCycle (Daily lead processing & packs)
Write-Host "`n[2/8] Updating LeadsDailyCycle (Daily at 9 PM)..." -ForegroundColor Yellow
$Action2 = New-ScheduledTaskAction -Execute $Cmd -Argument "/c `"$MCDir\leads_daily_cycle.cmd`"" -WorkingDirectory $MCDir
$Trigger2 = New-ScheduledTaskTrigger -Daily -At "9:00PM"
Register-Or-Update-Task -TaskName "LeadsDailyCycle" -Action $Action2 -Trigger $Trigger2 -Description "Daily leads execution and pack distributor."

# 3. JarvisOS_15Min_VideoAgentFactory (15-Minute Video Factory + Verified Publisher)
Write-Host "`n[3/8] Registering JarvisOS_15Min_VideoAgentFactory (Every 15 min)..." -ForegroundColor Yellow
$Action3 = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$SocialDir\publish_cycle.py`"" -WorkingDirectory $SocialDir
$Trigger3 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-Or-Update-Task -TaskName "JarvisOS_15Min_VideoAgentFactory" -Action $Action3 -Trigger $Trigger3 -Description "Autonomous 15-min content factory + verified multi-platform publishing (post_orchestrator)."

# 4. MBM_LeadEngine_4HR (Full pipeline every 4 hours)
Write-Host "`n[4/8] Registering MBM_LeadEngine_4HR (Every 4 hours)..." -ForegroundColor Yellow
$Action4 = New-ScheduledTaskAction -Execute $PS -Argument "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$ScriptsDir\lead_engine_forever.ps1`"" -WorkingDirectory $ScriptsDir
$Trigger4 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 4) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-Or-Update-Task -TaskName "MBM_LeadEngine_4HR" -Action $Action4 -Trigger $Trigger4 -Description "MBM Lead Engine full pipeline."

# 4b. JarvisOS_15Min_LeadsSkiptrace (Skip-trace + dispatch to dialer every 15 min)
Write-Host "`n[4b/8] Registering JarvisOS_15Min_LeadsSkiptrace (Every 15 min)..." -ForegroundColor Yellow
$Action4b = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptsDir\leads_15min_run.py`"" -WorkingDirectory $ScriptsDir
$Trigger4b = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(3) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-Or-Update-Task -TaskName "JarvisOS_15Min_LeadsSkiptrace" -Action $Action4b -Trigger $Trigger4b -Description "15-min skip-trace + dispatch verified leads to live dialer."

# 5. MBM_Watchdog (Health check & Auto-restart every 25 min)
Write-Host "`n[5/8] Registering MBM_Watchdog (Every 25 min)..." -ForegroundColor Yellow
$Action5 = New-ScheduledTaskAction -Execute $PS -Argument "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$ScriptsDir\watchdog.ps1`"" -WorkingDirectory $ScriptsDir
$Trigger5 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 25) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-Or-Update-Task -TaskName "MBM_Watchdog" -Action $Action5 -Trigger $Trigger5 -Description "MBM Watchdog: Checks engine heartbeat every 25 min, auto-restarts if dead."

# 6. MBM_DailyLeadPack (Daily at 6 AM)
Write-Host "`n[6/8] Registering MBM_DailyLeadPack (Daily 6 AM)..." -ForegroundColor Yellow
$Action6 = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptsDir\daily_lead_pack.py`"" -WorkingDirectory $ScriptsDir
$Trigger6 = New-ScheduledTaskTrigger -Daily -At "6:00AM"
Register-Or-Update-Task -TaskName "MBM_DailyLeadPack" -Action $Action6 -Trigger $Trigger6 -Description "MBM Daily Lead Pack & email."

# 7. MBM_DailyDigest (Daily at 9 AM)
Write-Host "`n[7/8] Registering MBM_DailyDigest (Daily 9 AM)..." -ForegroundColor Yellow
$Action7 = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ScriptsDir\telegram_notify.py`" daily_digest" -WorkingDirectory $ScriptsDir
$Trigger7 = New-ScheduledTaskTrigger -Daily -At "9:00AM"
Register-Or-Update-Task -TaskName "MBM_DailyDigest" -Action $Action7 -Trigger $Trigger7 -Description "Telegram 24hr summary digest."

# 8. MBM-HUNTER-Daily (Outreach daily cycles)
Write-Host "`n[8/8] Registering MBM-HUNTER-Daily (Daily 9AM, 12PM, 3PM, 6PM)..." -ForegroundColor Yellow
$Action8 = New-ScheduledTaskAction -Execute $PS -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptsDir\run_hunter_daily.ps1`"" -WorkingDirectory $ScriptsDir
$Trigger8 = @(
    New-ScheduledTaskTrigger -Daily -At "9:00AM"
    New-ScheduledTaskTrigger -Daily -At "12:00PM"
    New-ScheduledTaskTrigger -Daily -At "3:00PM"
    New-ScheduledTaskTrigger -Daily -At "6:00PM"
)
Register-Or-Update-Task -TaskName "MBM-HUNTER-Daily" -Action $Action8 -Trigger $Trigger8 -Description "HUNTER outreach daily cycles."

# -------------------------------------------------------------------------
# 11) JarvisOS_DatabaseAndLogsCleanup (Weekly)
# -------------------------------------------------------------------------
try {
    $Action11  = New-ScheduledTaskAction -Execute $PS -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -Command `"& '$ScriptsDir\cleanup_logs_and_db.ps1'`"" -WorkingDirectory $ProjectDir
    $Trigger11 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3:00AM
    Register-ScheduledTask -TaskName "JarvisOS_DatabaseAndLogsCleanup" -Action $Action11 -Trigger $Trigger11 -Principal $Principal -Settings $Settings -Description "Weekly database maintenance and log cleanup" -Force | Out-Null
    Write-Host "[+] Registered Task: JarvisOS_DatabaseAndLogsCleanup (Weekly Sun 3AM)" -ForegroundColor Green
} catch {
    Write-Host "[-] Failed to register Task: JarvisOS_DatabaseAndLogsCleanup - $_" -ForegroundColor Red
}

# -------------------------------------------------------------------------
# 12) JarvisOS_MasterOnlineRevenueEngine (Every 6 Hours)
# -------------------------------------------------------------------------
try {
    $Action12  = New-ScheduledTaskAction -Execute $PS -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -Command `"& '$ScriptsDir\run_master_online_revenue_workflow.ps1'`"" -WorkingDirectory $ProjectDir
    $Trigger12 = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 6)
    Register-ScheduledTask -TaskName "JarvisOS_MasterOnlineRevenueEngine" -Action $Action12 -Trigger $Trigger12 -Principal $Principal -Settings $Settings -Description "Master Automated Online Revenue Workflow (Bidding, Audits, Deal Matching)" -Force | Out-Null
    Write-Host "[+] Registered Task: JarvisOS_MasterOnlineRevenueEngine (Every 6 Hours)" -ForegroundColor Green
} catch {
    Write-Host "[-] Failed to register Task: JarvisOS_MasterOnlineRevenueEngine - $_" -ForegroundColor Red
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Get-ScheduledTask | Where-Object { $_.TaskName -like "MBM*" -or $_.TaskName -like "*Lead*" -or $_.TaskName -like "JarvisOS*" } | Format-Table TaskName, State -AutoSize
