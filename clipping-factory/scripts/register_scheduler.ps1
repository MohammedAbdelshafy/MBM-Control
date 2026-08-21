<#
.SYNOPSIS
    Registers the Clipping Factory production task in Windows Task Scheduler.

.DESCRIPTION
    Creates a scheduled task that runs the factory production cycle.
    - Morning: 8:00 AM — Discovery + research
    - Midday: 1:00 PM — Production batch
    - Evening: 7:00 PM — Production + publishing

.PARAMETER Uninstall
    Remove the scheduled task instead of creating it.

.EXAMPLE
    .\register_scheduler.ps1
    .\register_scheduler.ps1 -Uninstall
#>

param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "ClippingFactory_Production"
$ScriptPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) "run_clipping_factory.ps1"

# Verify the launcher script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Launcher script not found at: $ScriptPath"
    exit 1
}

# Uninstall mode
if ($Uninstall) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "REMOVED: Task '$TaskName' has been unregistered." -ForegroundColor Yellow
    } else {
        Write-Host "Task '$TaskName' does not exist. Nothing to remove." -ForegroundColor Gray
    }
    exit 0
}

# Check for existing task
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Task '$TaskName' already exists. Updating..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the task action
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory (Split-Path -Parent $ScriptPath)

# Create three triggers: Morning 8AM, Midday 1PM, Evening 7PM
$TriggerMorning = New-ScheduledTaskTrigger -Daily -At "08:00"
$TriggerMidday = New-ScheduledTaskTrigger -Daily -At "13:00"
$TriggerEvening = New-ScheduledTaskTrigger -Daily -At "19:00"

# Create settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

# Register the task
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger @($TriggerMorning, $TriggerMidday, $TriggerEvening) `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Clipping Factory production cycle: discovery, script, render, QA, publish. Runs 3x daily." `
    -Force

# Verify
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Write-Host ""
    Write-Host "SUCCESS: Task '$TaskName' registered." -ForegroundColor Green
    Write-Host "  Triggers: Daily at 8:00 AM, 1:00 PM, 7:00 PM"
    Write-Host "  Script: $ScriptPath"
    Write-Host "  Run level: Highest"
    Write-Host "  Multiple instances: IgnoreNew (overlap protection)"
    Write-Host ""
    Write-Host "To test manually: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Cyan
    Write-Host "To uninstall: .\register_scheduler.ps1 -Uninstall" -ForegroundColor Cyan
} else {
    Write-Error "Task registration failed."
    exit 1
}
