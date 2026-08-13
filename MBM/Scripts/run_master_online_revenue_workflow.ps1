<#
.SYNOPSIS
Wrapper script to execute the Master Automated Online Revenue Workflow via Task Scheduler.
#>

$BasePath = "C:\Users\omare\OneDrive\Desktop\AI"
Set-Location -Path $BasePath

Write-Host "=========================================================="
Write-Host " STARTING MASTER AUTOMATED ONLINE REVENUE WORKFLOW"
Write-Host " Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "=========================================================="

try {
    # We use python directly to run the orchestrator script
    & python MBM/LeadEngine/master_online_revenue_workflow.py
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "[+] Master Workflow completed successfully."
    } else {
        Write-Host "[-] Master Workflow failed with exit code $exitCode."
        exit $exitCode
    }
}
catch {
    Write-Host "[-] FATAL ERROR executing Master Workflow: $_"
    exit 1
}
