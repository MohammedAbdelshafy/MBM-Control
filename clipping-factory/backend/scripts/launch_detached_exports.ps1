$ErrorActionPreference = 'Stop'
$backend = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = Join-Path $backend '.venv\Scripts\python.exe'
$script = Join-Path $backend 'scripts\export_clipping_sessions.py'
$sessions = Join-Path $backend 'sessions'
New-Item -ItemType Directory -Force -Path $sessions | Out-Null

$platforms = @('whop', 'clipping_net', 'vyro', 'reach_cat', 'clip_affiliates', 'muslim_clippers', 'halalclipping')

foreach ($plat in $platforms) {
    Get-ChildItem -Path $sessions -Filter "$plat.json" -ErrorAction SilentlyContinue | Remove-Item -Force
    $cmd = "cmd /c set AUTO_CAPTURE_SECONDS=7200&& `"$py`" `"$script`" $plat"
    $create = ([wmiclass]'Win32_Process').Create($cmd)
    if ($create.ReturnValue -eq 0) {
        Write-Output "launched $plat (pid $($create.ProcessId))"
    } else {
        Write-Output "FAILED $plat (return $($create.ReturnValue))"
    }
}
Write-Output 'ALL LAUNCHED'
