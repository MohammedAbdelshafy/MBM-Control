# Install HUNTER daily scheduled task
# NOTE: Run PowerShell AS ADMINISTRATOR for this to work
# Or run: npm run hunter:schedule-admin (opens admin prompt)

$taskName = "MBM-HUNTER-Daily"
$projectDir = Resolve-Path "$PSScriptRoot\..\.."
$runnerScript = "$PSScriptRoot\run_hunter_daily.ps1"

# Create runner script
@"
`$projectDir = "$projectDir"
Set-Location `$projectDir
`$env:NODE_ENV = "production"
`$logDir = Join-Path `$projectDir "logs"
New-Item -ItemType Directory -Path `$logDir -Force | Out-Null
`$logFile = Join-Path `$logDir "hunter_daily.log"
`$date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$date] Starting HUNTER outreach..." | Out-File -FilePath `$logFile -Append
npm run hunter:send 2>&1 | ForEach-Object { Add-Content -Path `$logFile -Value `$_ }
"[$date] Complete." | Out-File -FilePath `$logFile -Append
"---" | Out-File -FilePath `$logFile -Append
"@ | Out-File -FilePath $runnerScript -Encoding utf8 -Force

# Ensure log directory
New-Item -ItemType Directory -Path "$projectDir\logs" -Force | Out-Null

# Try to register as admin; if fails, show manual instructions
try {
  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runnerScript`""
  $triggers = @(
    New-ScheduledTaskTrigger -Daily -At 09:00am
    New-ScheduledTaskTrigger -Daily -At 12:00pm
    New-ScheduledTaskTrigger -Daily -At 03:00pm
    New-ScheduledTaskTrigger -Daily -At 06:00pm
  )
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Force
  Write-Host "✅ Scheduled task '$taskName' installed. Runs daily at 9AM, 12PM, 3PM, 6PM."
} catch {
  Write-Host "⚠️  Could not register task (run PowerShell as Admin)."
  Write-Host ""
  Write-Host "Manual setup:"
  Write-Host "  1. Open Task Scheduler as Administrator"
  Write-Host "  2. Create Task:"
  Write-Host "     - Name: $taskName"
  Write-Host "     - Trigger: Daily at 9AM, 12PM, 3PM, 6PM"
  Write-Host "     - Action: Start a program"
  Write-Host "       Program: powershell.exe"
  Write-Host "       Args: -NoProfile -ExecutionPolicy Bypass -File `"$runnerScript`""
  Write-Host "     - Start in: $projectDir"
  Write-Host ""
  Write-Host "  Or run this script AS ADMINISTRATOR to auto-setup."
}
Write-Host "Logs: $projectDir\logs\hunter_daily.log"
