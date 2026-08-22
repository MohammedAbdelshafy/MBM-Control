<#
.SYNOPSIS
    Twists Revealed flagship production cycle — ONE real movie recap end-to-end.

.DESCRIPTION
    discovery -> research -> REAL source acquisition (public-domain provenance)
    -> script -> TTS (edge-tts / SAPI fallback) -> vertical render from the real
    film -> burned captions -> loudness mix -> video+creative QA -> artifact
    package -> optional unlisted YouTube publish + verification.

    Designed to run from Task Scheduler with any working directory.
    Overlap protection via the shared factory lock (artifacts/clipping_factory/.factory_lock).

.PARAMETER Publish
    After a QA pass, upload ONE clip unlisted and verify the returned video id.

.PARAMETER Movies
    How many movies to attempt this run (default: channel daily_target).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File run_twists_revealed.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File run_twists_revealed.ps1 -Publish
#>

param(
    [switch]$Publish,
    [int]$Movies = 0,
    [switch]$ForceUnlock
)

$ErrorActionPreference = "Stop"

# 1. Resolve repo root from script location (scheduler-safe)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Split-Path -Parent $ScriptDir
if (-not (Test-Path (Join-Path $RepoRoot "clipping_factory"))) {
    Write-Error "Cannot resolve clipping_factory package at $RepoRoot"
    exit 2
}

$ArtifactsDir = Join-Path $RepoRoot "artifacts\twistsrevealed"
$LogsDir = Join-Path $RepoRoot "logs\autonomous"
foreach ($d in @($ArtifactsDir, $LogsDir)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogsDir "twists_run_$Timestamp.log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

# 2. Overlap pre-check (authoritative lock enforced inside Python as well)
$LockFile = Join-Path $RepoRoot "artifacts\clipping_factory\.factory_lock"
if ($ForceUnlock -and (Test-Path $LockFile)) {
    Remove-Item $LockFile -Force
    Write-Log "Stale lock removed (-ForceUnlock)"
}
if (Test-Path $LockFile) {
    try {
        $lock = Get-Content $LockFile -Raw | ConvertFrom-Json
        $age = ((Get-Date) - [datetime]::Parse($lock.acquired_at)).TotalSeconds
        if ($age -lt 7200) {
            Write-Log "SKIPPED_ALREADY_RUNNING — lock held by PID $($lock.pid) ($([math]::Round($age))s)" "WARN"
            exit 0
        }
        Write-Log "Stale lock detected (${age}s) — proceeding" "WARN"
    } catch { Write-Log "Corrupt lock file ignored" "WARN" }
}

# 3. Python resolution: workspace venv (has edge-tts) -> backend venv -> system
$PythonExe = $null
$candidates = @(
    (Join-Path (Split-Path -Parent $RepoRoot) ".venv\Scripts\python.exe"),
    (Join-Path $RepoRoot "backend\.venv\Scripts\python.exe")
)
foreach ($c in $candidates) {
    if (Test-Path $c) { $PythonExe = $c; break }
}
if (-not $PythonExe) {
    $sysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPython) { $PythonExe = $sysPython.Source }
}
if (-not $PythonExe) {
    Write-Log "FATAL: no Python interpreter found" "ERROR"
    exit 3
}
Write-Log "Python: $PythonExe"

# ffmpeg must be on PATH or beside the repo tooling
$ff = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
if (-not $ff) { Write-Log "FATAL: ffmpeg not on PATH" "ERROR"; exit 4 }

# 4. Run one production cycle
Write-Log "=== TWISTS REVEALED PRODUCTION CYCLE $Timestamp (publish=$Publish) ==="
$args = @("-m", "clipping_factory.full_cycle", "--movies", "$Movies")
if ($Publish) { $args += "--publish" }

$exitCode = 0
try {
    $output = & $PythonExe @args 2>&1
    $output | ForEach-Object { Write-Log "$_" }
    $exitCode = $LASTEXITCODE
} catch {
    Write-Log "RUNNER ERROR: $_" "ERROR"
    $_ | Out-File (Join-Path $LogsDir "twists_error_$Timestamp.log") -Encoding UTF8
    $exitCode = 1
}

Write-Log "=== CYCLE COMPLETE — ExitCode $exitCode ==="
exit $exitCode
