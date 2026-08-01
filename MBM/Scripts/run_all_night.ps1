# run_all_night.ps1
# Runs the MBM Daily Revenue Daemon and the Wolf Closer Agent in the background indefinitely.

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $baseDir

$revenueDaemon = Join-Path $rootDir "LeadEngine\run_daily_revenue_daemon.py"
$wolfCloser = Join-Path $rootDir "LeadEngine\wolf_closer_agent.py"

Write-Host "================================================="
Write-Host "🐺 MBM OVERNIGHT MONETIZATION & CLOSING SUITE 💰"
Write-Host "================================================="
Write-Host "Starting Revenue Daemon (15-min cycles)..."
Start-Process "python" -ArgumentList $revenueDaemon -WindowStyle Hidden

Write-Host "Starting Wolf Closer Agent (5-min cycles)..."
Start-Process "python" -ArgumentList $wolfCloser -WindowStyle Hidden

Write-Host "Both systems are now running in the background."
Write-Host "Keep this machine on. They will handle everything automatically."
Write-Host "Check Telegram for updates!"
