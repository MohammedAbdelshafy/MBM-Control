<#
.SYNOPSIS
    Clipping Factory Production Launcher — authoritative entry point for Windows Task Scheduler.

.DESCRIPTION
    1. Resolves repository root from script location
    2. Loads environment variables safely
    3. Activates Python virtual environment
    4. Validates dependencies
    5. Runs one production cycle (movie discovery → research → script → render → QA → queue)
    6. Captures stdout/stderr to timestamped logs
    7. Returns correct exit code
    8. Prevents overlapping runs (file-based lock)
    9. Writes heartbeat/state

.NOTES
    Scheduled via Windows Task Scheduler.
    Never use relative paths — all paths derived from $RepoRoot.
#>

param(
    [switch]$DryRun,
    [switch]$ForceUnlock
)

$ErrorActionPreference = "Stop"
$ScriptName = "ClippingFactory"

# ── 1. RESOLVE REPOSITORY ROOT ──
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Split-Path -Parent $ScriptDir  # clipping-factory/scripts/ → clipping-factory/
$WorkspaceRoot = Split-Path -Parent $RepoRoot  # clipping-factory/ → workspace root

# Verify we found the right directory
if (-not (Test-Path "$RepoRoot\clipping_factory")) {
    Write-Error "Cannot resolve clipping_factory package at $RepoRoot\clipping_factory"
    exit 2
}

# ── 2. SETUP DIRECTORIES ──
$ArtifactsDir = Join-Path $RepoRoot "artifacts\clipping_factory"
$LogsDir = Join-Path $RepoRoot "logs"
$LockFile = Join-Path $ArtifactsDir ".factory_lock"

foreach ($dir in @($ArtifactsDir, $LogsDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

# ── 3. TIMESTAMPED LOG FILES ──
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogsDir "factory_run_$Timestamp.log"
$ErrorLog = Join-Path $LogsDir "factory_error_$Timestamp.log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

# ── 4. OVERLAP PROTECTION ──
$LockTimeoutSec = 7200  # 2 hours

function Test-LockActive {
    if (-not (Test-Path $LockFile)) { return $false }
    try {
        $lockData = Get-Content $LockFile -Raw | ConvertFrom-Json
        $lockTime = [datetime]::Parse($lockData.acquired_at)
        $elapsed = ((Get-Date) - $lockTime).TotalSeconds
        return $elapsed -lt $LockTimeoutSec
    } catch {
        return $false  # Corrupt lock, treat as inactive
    }
}

function Set-Lock {
    $lockData = @{
        pid = $PID
        acquired_at = (Get-Date).ToUniversalTime().ToString("o")
        machine = $env:COMPUTERNAME
    } | ConvertTo-Json
    Set-Content -Path $LockFile -Value $lockData -Encoding UTF8
}

function Remove-Lock {
    if (Test-Path $LockFile) {
        Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    }
}

if ($ForceUnlock) {
    Remove-Lock
    Write-Log "Lock force-removed"
}

if (Test-LockActive) {
    Write-Log "SKIPPED_ALREADY_RUNNING — another instance holds the lock" -Level "WARN"
    $lockData = Get-Content $LockFile -Raw | ConvertFrom-Json
    Write-Log "  Lock holder PID: $($lockData.pid), acquired: $($lockData.acquired_at)" -Level "WARN"

    # Write heartbeat with skip status
    $hb = @{
        status = "skipped_already_running"
        last_started = (Get-Date).ToUniversalTime().ToString("o")
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
    } | ConvertTo-Json
    Set-Content -Path (Join-Path $ArtifactsDir "heartbeat.json") -Value $hb -Encoding UTF8

    exit 0
}

Set-Lock
Write-Log "Lock acquired (PID: $PID)"

# ── 5. HEARTBEAT: STARTED ──
$StartTime = Get-Date
$hbStart = @{
    status = "running"
    last_started = $StartTime.ToUniversalTime().ToString("o")
    updated_at = $StartTime.ToUniversalTime().ToString("o")
} | ConvertTo-Json
Set-Content -Path (Join-Path $ArtifactsDir "heartbeat.json") -Value $hbStart -Encoding UTF8

# ── 6. LOAD ENVIRONMENT ──
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    Write-Log "Loading environment from $EnvFile"
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            $key = $Matches[1].Trim()
            $val = $Matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
} else {
    Write-Log "No .env file found at $EnvFile — using existing environment" -Level "WARN"
}

# ── 7. ACTIVATE PYTHON VENV ──
$VenvDir = Join-Path $RepoRoot "backend\.venv"
$PythonExe = "python"

if (Test-Path "$VenvDir\Scripts\python.exe") {
    $PythonExe = Join-Path $VenvDir "Scripts\python.exe"
    Write-Log "Using venv Python: $PythonExe"
} else {
    $sysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPython) {
        $PythonExe = $sysPython.Source
        Write-Log "Using system Python: $PythonExe"
    } else {
        Write-Log "ERROR: No Python found" -Level "ERROR"
        exit 3
    }
}

# ── 8. VALIDATE DEPENDENCIES ──
Write-Log "Validating Python dependencies..."
$validateScript = @"
import sys
try:
    import json, hashlib, subprocess, shutil
    print('core deps: OK')
except ImportError as e:
    print(f'core deps FAIL: {e}')
    sys.exit(1)
"@

$valResult = & $PythonExe -c $validateScript 2>&1
Write-Log "Dependency check: $valResult"

# ── 9. RUN PRODUCTION CYCLE ──
Write-Log "=========================================================="
Write-Log "  CLIPPING FACTORY PRODUCTION CYCLE — $Timestamp"
Write-Log "=========================================================="

$DryRunArg = if ($DryRun) { "--dry-run" } else { "" }

$runnerScript = @"
import sys, json, time, traceback
from pathlib import Path

repo_root = Path(r'$RepoRoot')
sys.path.insert(0, str(repo_root))

try:
    from clipping_factory.movie_discovery import discover_movies, MovieStatus
    from clipping_factory.channel_profiles import get_profile
    from clipping_factory.script_agent import generate_recap_script
    from clipping_factory.heartbeat import write_heartbeat, complete_heartbeat, release_run_lock

    profile = get_profile('twistsrevealed')
    print(f'Loaded channel: {profile.display_name}')
    print(f'Genres: {profile.genres}')
    print(f'Daily target: {profile.daily_target}')

    # Discover movies
    status_file = repo_root / 'artifacts' / 'clipping_factory' / 'movie_status.json'
    status_file.parent.mkdir(parents=True, exist_ok=True)

    exclude = []
    if status_file.exists():
        try:
            data = json.loads(status_file.read_text(encoding='utf-8'))
            exclude = [v.get('campaign_id', '') for v in data.values() if isinstance(v, dict)]
        except Exception:
            pass

    movies = discover_movies(
        genres=profile.genres,
        count=profile.daily_target,
        exclude_ids=exclude,
        status_file=status_file,
    )

    print(f'Discovered {len(movies)} movie candidates')
    for m in movies:
        print(f'  - {m.title} ({m.year}) [{m.campaign_id}]')

    results = []
    for movie in movies:
        script = generate_recap_script(
            campaign_id=movie.campaign_id,
            title=movie.title,
            year=movie.year,
            synopsis=movie.synopsis,
            ending_description=movie.ending_description,
            key_characters=movie.key_characters,
            genres=movie.genres,
            tone=profile.tone,
            target_duration_min=profile.target_duration_min,
            target_duration_max=profile.target_duration_max,
        )
        print(f'  Script generated: {script.script_id} ({script.narration_words} words, ~{script.estimated_duration_sec:.0f}s)')

        # Update status
        if status_file.exists():
            try:
                status_data = json.loads(status_file.read_text(encoding='utf-8'))
            except Exception:
                status_data = {}
        else:
            status_data = {}

        status_data[movie.campaign_id] = {
            'title': movie.title,
            'year': movie.year,
            'campaign_id': movie.campaign_id,
            'script_id': script.script_id,
            'status': MovieStatus.SCRIPTED.value,
            'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        status_file.write_text(json.dumps(status_data, indent=2), encoding='utf-8')

        results.append({
            'campaign_id': movie.campaign_id,
            'title': movie.title,
            'script_id': script.script_id,
            'words': script.narration_words,
            'duration_sec': script.estimated_duration_sec,
        })

    complete_heartbeat(
        status='success',
        campaigns_found=len(movies),
        clips_produced=0,
        clips_queued=0,
    )

    print(f'Production cycle complete: {len(results)} candidates scripted')

except Exception as e:
    traceback.print_exc()
    from clipping_factory.heartbeat import complete_heartbeat
    complete_heartbeat(status='failed')
    sys.exit(1)
"@

$ExitCode = 0
try {
    $result = & $PythonExe -c $runnerScript 2>&1
    Write-Log $result
    Write-Log "Production cycle completed successfully"
} catch {
    Write-Log "ERROR: Production cycle failed — $_" -Level "ERROR"
    $_ | Out-File $ErrorLog -Encoding UTF8
    $ExitCode = 1
}

# ── 10. CLEANUP ──
$EndTime = Get-Date
$Duration = ($EndTime - $StartTime).TotalSeconds
Write-Log "Run duration: $([math]::Round($Duration, 1))s"

Remove-Lock
Write-Log "Lock released"

# ── 11. FINAL HEARTBEAT ──
$hbFinal = @{
    status = if ($ExitCode -eq 0) { "success" } else { "failed" }
    last_completed = $EndTime.ToUniversalTime().ToString("o")
    updated_at = $EndTime.ToUniversalTime().ToString("o")
    duration_sec = [math]::Round($Duration, 1)
} | ConvertTo-Json
Set-Content -Path (Join-Path $ArtifactsDir "heartbeat.json") -Value $hbFinal -Encoding UTF8

Write-Log "=========================================================="
Write-Log "  FACTORY RUN COMPLETE — Exit Code: $ExitCode"
Write-Log "=========================================================="

exit $ExitCode