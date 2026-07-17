<#
.SYNOPSIS
  MBM Lead Engine — Never-Stop Edition
  Runs the full lead pipeline, retries on failure, sends findings via Telegram.
  Designed to be triggered by Windows Task Scheduler every 4 hours.

.NOTES
  - Each invocation runs ONE full cycle (not a loop) — the scheduler handles recurrence.
  - Auto-retries failed steps up to 3 times with exponential backoff.
  - Writes a heartbeat file so the watchdog can verify liveness.
  - Sends Telegram summary + CSV attachments after every run.
#>

param(
  [string]$ScriptsDir  = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Scripts",
  [string]$LogDir      = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Logs",
  [string]$ArtifactsDir= "C:\Users\omare\OneDrive\Desktop\AI\MBM\Artifacts",
  [string]$ConfigDir   = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Config",
  [string]$PacksDir    = "C:\Users\omare\OneDrive\Desktop\AI\MBM\LeadPacks",
  [int]$MaxRetries     = 3,
  [int]$RetryDelaySec  = 60
)

$Python = "C:\Users\omare\AppData\Local\Programs\Python\Python312\python.exe"
$NotifyPy = "$ScriptsDir\telegram_notify.py"
$HeartbeatFile = "$ConfigDir\heartbeat.json"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "$LogDir\engine_$timestamp.log"
$start = Get-Date

# Ensure directories exist
@($LogDir, $ArtifactsDir, $ConfigDir, $PacksDir) | ForEach-Object {
  if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# ── Logging ──────────────────────────────────────────────────
function Log {
  param([string]$Msg, [string]$Level = "INFO")
  $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Msg"
  Add-Content -Path $logFile -Value $line -Encoding utf8
  Write-Host $line
}

# ── Telegram helpers ─────────────────────────────────────────
function Telegram {
  param([string[]]$Args)
  try {
    & $Python $NotifyPy @Args 2>&1 | Out-Null
  } catch {
    Log "Telegram call failed: $_" "WARN"
  }
}

function TelegramMsg {
  param([string]$Text)
  try {
    & $Python -c @"
import sys; sys.path.insert(0, r'$ScriptsDir')
from telegram_notify import send_message
send_message('''$($Text -replace "'","\'")''')
"@ 2>&1 | Out-Null
  } catch {
    Log "Telegram message failed: $_" "WARN"
  }
}

function TelegramFile {
  param([string]$FilePath, [string]$Caption = "")
  try {
    & $Python $NotifyPy file $FilePath $Caption 2>&1 | Out-Null
  } catch {
    Log "Telegram file send failed: $_" "WARN"
  }
}

# ── Heartbeat ────────────────────────────────────────────────
function Write-Heartbeat {
  param([string]$Status, [int]$LeadsFound = 0, [string]$Error = "")
  $hb = @{
    timestamp    = (Get-Date -Format "o")
    status       = $Status
    leads_found  = $LeadsFound
    last_log     = $logFile
    error        = $Error
    pid          = $PID
  } | ConvertTo-Json
  Set-Content -Path $HeartbeatFile -Value $hb -Encoding utf8
}

# ── Run a step with retry ───────────────────────────────────
function RunStepWithRetry {
  param(
    [string]$Name,
    [string]$Script,
    [string]$Type = "python",
    [int]$Retries = $MaxRetries
  )

  for ($attempt = 1; $attempt -le $Retries; $attempt++) {
    Log ">>> [$Name] Attempt $attempt/$Retries starting..."
    $stepStart = Get-Date
    try {
      if ($Type -eq "python") {
        $result = & $Python "$ScriptsDir\$Script" 2>&1
      } else {
        $result = powershell -ExecutionPolicy Bypass -File "$Script" 2>&1
      }
      $exitCode = $LASTEXITCODE
      if ($null -eq $exitCode) { $exitCode = 0 }
    } catch {
      $result = $_.Exception.Message
      $exitCode = 1
    }

    $duration = [math]::Round(((Get-Date) - $stepStart).TotalSeconds, 1)

    if ($exitCode -eq 0) {
      Log "<<< [$Name] SUCCESS in ${duration}s"
      foreach ($line in $result) { Add-Content -Path $logFile -Value "    $line" -Encoding utf8 }
      return @{ Success = $true; Output = $result; Duration = $duration }
    }

    Log "<<< [$Name] FAILED (exit: $exitCode) in ${duration}s - attempt $attempt/$Retries" "ERROR"
    foreach ($line in $result) { Add-Content -Path $logFile -Value "    $line" -Encoding utf8 }

    if ($attempt -lt $Retries) {
      $delay = $RetryDelaySec * $attempt  # exponential-ish backoff
      Log "    Retrying in ${delay}s..." "WARN"
      Start-Sleep -Seconds $delay
    }
  }

  # All retries exhausted
  Log "!!! [$Name] FAILED after $Retries attempts" "ERROR"
  Telegram -Args @("notify_error", $Name, "Failed after $Retries attempts")
  return @{ Success = $false; Output = $result; Duration = 0 }
}

# ══════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════════════════════════
Log "============================================================"
Log "  MBM LEAD ENGINE — RUN STARTED"
Log "  Timestamp: $timestamp"
Log "============================================================"

Write-Heartbeat -Status "running"
Telegram -Args @("start")

$errors = @()
$stepResults = @{}

# Step 1: Evidence Collector (Dallas 311 API)
$r = RunStepWithRetry -Name "Evidence Collector" -Script "evidence_collector.py"
$stepResults["evidence"] = $r
if (-not $r.Success) { $errors += "Evidence Collector" }

# Step 2: Revenue Review
$r = RunStepWithRetry -Name "Revenue Review" -Script "revenue_review.py"
$stepResults["revenue"] = $r
if (-not $r.Success) { $errors += "Revenue Review" }

# Step 3: Skip Trace
$r = RunStepWithRetry -Name "Skip Trace" -Script "skip_trace_leads.py"
$stepResults["skip_trace"] = $r
if (-not $r.Success) { $errors += "Skip Trace" }

# Step 4: QA Round 1
$r = RunStepWithRetry -Name "QA Round 1" -Script "qa_001.py"
$stepResults["qa1"] = $r
if (-not $r.Success) { $errors += "QA Round 1" }

# Step 5: Lead Qualification
$r = RunStepWithRetry -Name "Lead Qualification" -Script "lead_qualification.py"
$stepResults["qualification"] = $r
if (-not $r.Success) { $errors += "Lead Qualification" }

# Step 6: QA Round 2
$r = RunStepWithRetry -Name "QA Round 2" -Script "qa_002_verification.py"
$stepResults["qa2"] = $r
if (-not $r.Success) { $errors += "QA Round 2" }

# Step 7: Free Lead Engine (code violations + OSM + web directories)
$r = RunStepWithRetry -Name "Free Lead Engine" -Script "free_lead_engine.py"
$stepResults["free_engine"] = $r
if (-not $r.Success) { $errors += "Free Lead Engine" }

# Step 7.1: Auction & REO Scraper
$r = RunStepWithRetry -Name "Auction Scraper" -Script "auction_scraper.py"
$stepResults["auction"] = $r
if (-not $r.Success) { $errors += "Auction Scraper" }

# Step 7.2: Tranchi AI Workflow Analyzer
$r = RunStepWithRetry -Name "Tranchi AI Analyzer" -Script "tranchi_workflow_analyzer.py"
$stepResults["tranchi_ai"] = $r
if (-not $r.Success) { $errors += "Tranchi AI Analyzer" }

# Step 8: Daily Lead Pack (builds packs + emails wholesalers)
$r = RunStepWithRetry -Name "Daily Lead Pack" -Script "daily_lead_pack.py"
$stepResults["daily_pack"] = $r
if (-not $r.Success) { $errors += "Daily Lead Pack" }

# Step 9: Matching Engine
$r = RunStepWithRetry -Name "Matching Engine" -Script "matching_engine.py"
$stepResults["matching"] = $r
if (-not $r.Success) { $errors += "Matching Engine" }

# Step 10: Lead Scorer
$r = RunStepWithRetry -Name "Lead Scorer" -Script "lead_scorer.py"
$stepResults["scorer"] = $r
if (-not $r.Success) { $errors += "Lead Scorer" }

# Step 11: Outreach Pipeline
$r = RunStepWithRetry -Name "Outreach Pipeline" -Script "outreach_pipeline.py"
$stepResults["outreach"] = $r
if (-not $r.Success) { $errors += "Outreach Pipeline" }

# Step 12: Pain Point Sales Pipeline
$r = RunStepWithRetry -Name "Pain Point Sales Pipeline" -Script "pain_point_sales_pipeline.py"
$stepResults["sales_pipeline"] = $r
if (-not $r.Success) { $errors += "Pain Point Sales Pipeline" }

# ══════════════════════════════════════════════════════════════
#  RESULTS SUMMARY + TELEGRAM DELIVERY
# ══════════════════════════════════════════════════════════════
$totalDuration = [math]::Round(((Get-Date) - $start).TotalMinutes, 1)
$successCount = ($stepResults.Values | Where-Object { $_.Success }).Count
$totalSteps = $stepResults.Count

Log "============================================================"
Log "  PIPELINE COMPLETE: $successCount/$totalSteps steps succeeded in ${totalDuration}min"
if ($errors.Count -gt 0) {
  Log "  FAILED STEPS: $($errors -join ', ')" "WARN"
}
Log "============================================================"

# ── Collect lead counts ──────────────────────────────────────
$totalLeads = 0
$buyerCount = 0
$sellerCount = 0
$matchCount = 0
$scoredCount = 0

# Check master CSV
$masterCsv = "$ArtifactsDir\all_leads_master.csv"
$buyerCsv = ""
$sellerCsv = ""

if (Test-Path $masterCsv) {
  $data = Import-Csv $masterCsv
  $totalLeads = $data.Count
  $buyerCount = ($data | Where-Object { $_.Lead_Type -eq 'Buyer Contact' -or $_.Lead_Type -eq 'Wholesaler/Buyer' }).Count
  $sellerCount = ($data | Where-Object { $_.Lead_Type -eq 'Distressed Property' -or $_.Lead_Type -eq 'Distressed Seller' }).Count

  # Export separate CSVs for Telegram delivery
  $buyerCsv = "$ArtifactsDir\buyer_contacts_$timestamp.csv"
  $sellerCsv = "$ArtifactsDir\distressed_sellers_$timestamp.csv"
  $data | Where-Object { $_.Lead_Type -eq 'Buyer Contact' -or $_.Lead_Type -eq 'Wholesaler/Buyer' } | Export-Csv -Path $buyerCsv -NoTypeInformation -Encoding utf8
  $data | Where-Object { $_.Lead_Type -eq 'Distressed Property' -or $_.Lead_Type -eq 'Distressed Seller' } | Export-Csv -Path $sellerCsv -NoTypeInformation -Encoding utf8
}

# Also check the latest free engine output
$freeLeadsCsv = Get-ChildItem "$ArtifactsDir\ALL_LEADS_FREE_*.csv" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($freeLeadsCsv -and -not (Test-Path $masterCsv)) {
  $data = Import-Csv $freeLeadsCsv.FullName
  $totalLeads = $data.Count
  $buyerCount = ($data | Where-Object { $_.Lead_Type -eq 'Wholesaler/Buyer' }).Count
  $sellerCount = ($data | Where-Object { $_.Lead_Type -eq 'Distressed Seller' }).Count
  $buyerCsv = $freeLeadsCsv.FullName
}

# Check for matched/scored
$matchedCsv = Get-ChildItem "$ArtifactsDir\matched_leads_*.csv" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$scoredCsv = Get-ChildItem "$ArtifactsDir\scored_leads_*.csv" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($matchedCsv) { $matchCount = (Import-Csv $matchedCsv.FullName).Count }
if ($scoredCsv) { $scoredCount = (Import-Csv $scoredCsv.FullName).Count }

# Check daily pack
$todayPack = Get-ChildItem "$PacksDir\Pack_*\FULL_PACK_*.csv" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($todayPack -and $totalLeads -eq 0) {
  $data = Import-Csv $todayPack.FullName
  $totalLeads = $data.Count
  $buyerCount = ($data | Where-Object { $_.Lead_Type -eq 'Wholesaler/Buyer' }).Count
  $sellerCount = ($data | Where-Object { $_.Lead_Type -eq 'Distressed Seller' }).Count
}

# ── Send Telegram summary ───────────────────────────────────
$statusIcon = if ($errors.Count -eq 0) { [char]0x2705 } else { [char]0x26A0 }
$summary = @"
*MBM Lead Engine Report* $statusIcon

*Steps:* $successCount/$totalSteps passed
*Duration:* ${totalDuration} min
*Total Leads:* $totalLeads
  - Buyers/Wholesalers: $buyerCount
  - Distressed Sellers: $sellerCount
  - Matched: $matchCount
  - Scored: $scoredCount
"@

if ($errors.Count -gt 0) {
  $summary += "`n`n*Failed Steps:* $($errors -join ', ')"
}

$summary += "`n`n_Next run in ~4 hours_"

# Send summary message
& $Python -c @"
import sys; sys.path.insert(0, r'$ScriptsDir')
from telegram_notify import send_message, send_file
send_message(r'''$($summary -replace "'","")''')
"@ 2>&1 | Out-Null

# Send CSV files
if ($buyerCsv -and (Test-Path $buyerCsv)) {
  TelegramFile -FilePath $buyerCsv -Caption "Buyer Contacts ($buyerCount)"
}
if ($sellerCsv -and (Test-Path $sellerCsv)) {
  TelegramFile -FilePath $sellerCsv -Caption "Distressed Sellers ($sellerCount)"
}
if ($matchedCsv -and (Test-Path $matchedCsv.FullName)) {
  TelegramFile -FilePath $matchedCsv.FullName -Caption "Matched Leads ($matchCount)"
}
if ($scoredCsv -and (Test-Path $scoredCsv.FullName)) {
  TelegramFile -FilePath $scoredCsv.FullName -Caption "Scored Leads ($scoredCount)"
}
if ($todayPack -and (Test-Path $todayPack.FullName)) {
  TelegramFile -FilePath $todayPack.FullName -Caption "Full Lead Pack"
}

# ── Write heartbeat ─────────────────────────────────────────
$hbStatus = if ($errors.Count -eq 0) { "healthy" } else { "degraded" }
Write-Heartbeat -Status $hbStatus -LeadsFound $totalLeads -Error ($errors -join ", ")

# ── Clean old logs (keep 30 days) ───────────────────────────
Get-ChildItem "$LogDir\engine_*.log" -ErrorAction SilentlyContinue |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
  Remove-Item -Force -ErrorAction SilentlyContinue

# Clean old timestamped CSVs (keep 7 days)
Get-ChildItem "$ArtifactsDir\*_20*.csv" -ErrorAction SilentlyContinue |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
  Remove-Item -Force -ErrorAction SilentlyContinue

Log "Engine run complete. Heartbeat written. Next run scheduled by Task Scheduler."
