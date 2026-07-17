while ($true) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path "C:\Users\omare\OneDrive\Desktop\AI\MBM\Logs\autorun.log" -Value "[$ts] Starting pipeline run..."
  powershell -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File "C:\Users\omare\OneDrive\Desktop\AI\MBM\Scripts\pipeline_runner.ps1"
  Start-Sleep -Seconds 14400
}
