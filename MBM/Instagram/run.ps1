# Launch an authenticated Chrome with remote debugging, then run the IG intel pipeline.
# Prerequisite: you must be logged into Instagram in the profile used below.
$ErrorActionPreference = "Stop"

$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $ChromePath)) {
    $ChromePath = (Get-Command chrome -ErrorAction SilentlyContinue).Source
}
if (-not $ChromePath) { Write-Error "Chrome not found. Install Chrome or set \$ChromePath." }

$ProfileDir = "$env:USERPROFILE\AppData\Local\Chrome-IG-Profile"
$Port = 9222

Write-Host "Starting Chrome with remote debugging on port $Port ..."
Start-Process -FilePath $ChromePath -ArgumentList @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$ProfileDir",
    "https://www.instagram.com/"
) -PassThru | Out-Null

Start-Sleep -Seconds 4
Write-Host "Open Instagram and confirm you are logged in, then press ENTER to run the pipeline."
Read-Host | Out-Null

Set-Location $PSScriptRoot
& ".\.venv\Scripts\python.exe" -m ig_intel run --config config.local.yaml
