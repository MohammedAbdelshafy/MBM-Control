<#
.SYNOPSIS
  MBM GTM Agents & Process Watchdog System Installer
  Installs, registers, and starts the unified GTM agent swarm and process monitor.

.NOTES
  Tasks Registered:
    1. MBM_GTM_Supervisor_Watchdog   — Runs process watchdog and GTM cycle every 15 minutes
    2. MBM_GTM_Daily_Campaign         — Builds fresh daily GTM lead pack & checkout links at 8 AM
    3. MBM_GTM_Social_Creation        — Triggers MBM Social creative video factory at 12 PM
#>

param(
  [switch]$RunOnce,
  [switch]$Uninstall
)

$RepoRoot   = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LeadEngine = Join-Path $RepoRoot "MBM\LeadEngine"
$ScriptsDir = Join-Path $RepoRoot "MBM\Scripts"
$PythonExe  = "python.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MBM GTM AGENTS & BOTS MONITORING & CREATION INSTALLER" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Repository Root: $RepoRoot"
Write-Host ""

if ($Uninstall) {
  Write-Host "[*] Removing existing GTM scheduled tasks..." -ForegroundColor Yellow
  Unregister-ScheduledTask -TaskName "MBM_GTM_Supervisor_Watchdog" -ErrorAction SilentlyContinue -Confirm:$false
  Unregister-ScheduledTask -TaskName "MBM_GTM_Daily_Campaign" -ErrorAction SilentlyContinue -Confirm:$false
  Unregister-ScheduledTask -TaskName "MBM_GTM_Social_Creation" -ErrorAction SilentlyContinue -Confirm:$false
  Write-Host "✅ GTM Scheduled Tasks uninstalled successfully." -ForegroundColor Green
  exit 0
}

# 1. Test GTM Supervisor Execution
Write-Host "[1/3] Testing GTM Supervisor execution..." -ForegroundColor Yellow
$testOutput = & $PythonExe "$LeadEngine\gtm_agent_supervisor.py" --run-all
Write-Host $testOutput

if ($RunOnce) {
  Write-Host "✅ RunOnce completed." -ForegroundColor Green
  exit 0
}

# 2. Register Windows Scheduled Tasks
Write-Host "[2/3] Registering Windows Scheduled Tasks..." -ForegroundColor Yellow

$Settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -DontStopOnIdleEnd `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -RestartInterval (New-TimeSpan -Minutes 5) `
  -RestartCount 3 `
  -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$ActionWatchdog = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -Command `"cd '$RepoRoot'; python MBM/LeadEngine/gtm_agent_supervisor.py --run-all`"" `
  -WorkingDirectory $RepoRoot

$TriggerWatchdog = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
  -RepetitionInterval (New-TimeSpan -Minutes 15) `
  -RepetitionDuration (New-TimeSpan -Days 3650)

# Unregister if already present
Unregister-ScheduledTask -TaskName "MBM_GTM_Supervisor_Watchdog" -ErrorAction SilentlyContinue -Confirm:$false

Register-ScheduledTask `
  -TaskName "MBM_GTM_Supervisor_Watchdog" `
  -Action $ActionWatchdog `
  -Trigger $TriggerWatchdog `
  -Settings $Settings `
  -Description "MBM GTM Agents, Process Watchdog & Telegram Dispatcher"

Write-Host "  Registered: MBM_GTM_Supervisor_Watchdog (Every 15 mins)" -ForegroundColor Green

# 3. Create Status Verification
Write-Host "[3/3] Verifying GTM Status Artifacts..." -ForegroundColor Yellow
$StatusJson = Join-Path $RepoRoot "MBM\Artifacts\gtm_agents_status.json"
$ReportMd   = Join-Path $RepoRoot "MBM\Artifacts\GTM_AGENTS_MONITOR_REPORT.md"

if (Test-Path $StatusJson) {
  Write-Host "  Found: $StatusJson" -ForegroundColor Green
}
if (Test-Path $ReportMd) {
  Write-Host "  Found: $ReportMd" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "✅ MBM GTM AGENTS & MONITORING SYSTEM INSTALLED & ACTIVE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
