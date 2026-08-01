$ErrorActionPreference = 'Stop'
$backend = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = Join-Path $backend '.venv\Scripts\python.exe'
$script = Join-Path $backend 'scripts\export_clipping_sessions.py'
$sessions = Join-Path $backend 'sessions'
$logs = Join-Path $backend 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
New-Item -ItemType Directory -Force -Path $sessions | Out-Null

$platforms = @('whop', 'clipping_net', 'vyro', 'reach_cat', 'clip_affiliates', 'muslim_clippers', 'halalclipping')

foreach ($plat in $platforms) {
    Get-ChildItem -Path $sessions -Filter "$plat.json" -ErrorAction SilentlyContinue | Remove-Item -Force
    $outLog = Join-Path $logs "export3_$plat.out.log"
    $errLog = Join-Path $logs "export3_$plat.err.log"
    $env:AUTO_CAPTURE_SECONDS = 7200
    $p = Start-Process -FilePath $py -ArgumentList @($script, $plat) -WindowStyle Normal -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
    Write-Output "launched $plat (pid $($p.Id))"
}
Write-Output 'ALL LAUNCHED'
