param(
  [string]$LogDir = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Logs",
  [string]$ScriptsDir = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Scripts",
  [string]$ArtifactsDir = "C:\Users\omare\OneDrive\Desktop\AI\MBM\Artifacts"
)

$NotifyPy = "$ScriptsDir\telegram_notify.py"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "$LogDir\pipeline_$timestamp.log"
$start = Get-Date

function Log {
  param([string]$Msg)
  $line = "[$(Get-Date -Format 'HH:mm:ss')] $Msg"
  Add-Content -Path $logFile -Value $line
  Write-Host $line
}

function Telegram {
  param([string]$Cmd, [string]$Arg1 = "", [string]$Arg2 = "", [string]$Arg3 = "")
  python $NotifyPy $Cmd $Arg1 $Arg2 $Arg3 2>&1 | Out-Null
}

function RunStep {
  param(
    [string]$Name,
    [string]$Script,
    [string]$Type = "python"
  )
  Log ">>> [$Name] Starting..."
  $stepStart = Get-Date
  try {
    if ($Type -eq "python") {
      $result = python "$ScriptsDir\$Script" 2>&1
    } else {
      $result = powershell -ExecutionPolicy Bypass -File "$Script" 2>&1
    }
    $exitCode = $LASTEXITCODE
  } catch {
    $result = $_.Exception.Message
    $exitCode = 1
  }
  $duration = [math]::Round(((Get-Date) - $stepStart).TotalSeconds, 1)
  if ($exitCode -ne 0) {
    Log "<<< [$Name] FAILED in ${duration}s (exit: $exitCode)"
    Telegram -Cmd "notify_error" -Arg1 $Name -Arg2 ($result -join ' ')
  } else {
    Log "<<< [$Name] Finished in ${duration}s (exit: $exitCode)"
  }
  foreach ($line in $result) { Add-Content -Path $logFile -Value "  $line" }
  return $exitCode
}

# Notify start
Log "=== PIPELINE RUN STARTED ==="
Telegram -Cmd "start"

# Step 1: Collect raw evidence (Dallas 311 API)
RunStep -Name "Evidence Collector" -Script "evidence_collector.py"

# Step 2: Revenue review - process raw 311 into client batches
RunStep -Name "Revenue Review" -Script "revenue_review.py"

# Step 3: Skip trace - enrich with owner names/phones
RunStep -Name "Skip Trace" -Script "skip_trace_leads.py"

# Step 4: QA Round 1 - website/email verification
RunStep -Name "QA Round 1" -Script "qa_001.py"

# Step 5: Lead qualification with MX records
RunStep -Name "Lead Qualification" -Script "lead_qualification.py"

# Step 6: QA Round 2 - final verification
RunStep -Name "QA Round 2" -Script "qa_002_verification.py"

# Step 7: Merge all into master CSVs
RunStep -Name "Merge Master CSVs" -Script "$ArtifactsDir\merge_master_csvs.ps1" -Type "powershell"

# Step 8: Property-Buyer Matching Engine
RunStep -Name "Matching Engine" -Script "matching_engine.py"

# Step 9: Lead Scoring & Prioritization
RunStep -Name "Lead Scorer" -Script "lead_scorer.py"

# Step 10: Automated Outreach (logged, sends if GMAIL_APP_PASSWORD is set)
RunStep -Name "Outreach Pipeline" -Script "outreach_pipeline.py"

$total = [math]::Round(((Get-Date) - $start).TotalSeconds, 1)
Log "=== PIPELINE RUN COMPLETED in ${total}s ==="
Log "Log saved to: $logFile"

# Count results and notify (sends 2 separate CSVs: buyers + sellers)
$masterCsv = "$ArtifactsDir\all_leads_master.csv"
$matchedCsv = Get-ChildItem "$ArtifactsDir\matched_leads_*.csv" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$scoredCsv = Get-ChildItem "$ArtifactsDir\scored_leads_*.csv" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (Test-Path $masterCsv) {
  $data = Import-Csv $masterCsv
  $buyersCount = ($data | Where-Object { $_.Lead_Type -eq 'Buyer Contact' }).Count
  $propsCount = ($data | Where-Object { $_.Lead_Type -eq 'Distressed Property' }).Count

  # Export separate buyer and seller CSVs
  $buyerCsv = "$ArtifactsDir\buyer_contacts.csv"
  $sellerCsv = "$ArtifactsDir\distressed_sellers.csv"
  $data | Where-Object { $_.Lead_Type -eq 'Buyer Contact' } | Export-Csv -Path $buyerCsv -NoTypeInformation -Encoding utf8
  $data | Where-Object { $_.Lead_Type -eq 'Distressed Property' } | Export-Csv -Path $sellerCsv -NoTypeInformation -Encoding utf8

  $matchCount = if ($matchedCsv) { (Import-Csv $matchedCsv.FullName).Count } else { 0 }
  $scoredCount = if ($scoredCsv) { (Import-Csv $scoredCsv.FullName).Count } else { 0 }
  python $NotifyPy notify_result $logFile $buyersCount $propsCount $matchCount $scoredCount $buyerCsv $sellerCsv
} else {
  python $NotifyPy notify_result $logFile 0 0
}
