# GPT-OSS local bootstrap for Windows / PowerShell.
# Installs/uses Ollama, pulls gpt-oss:20b, configures the user environment,
# and performs a local OpenAI-compatible smoke test.
$ErrorActionPreference = 'Stop'

$model = if ($env:GPT_OSS_MODEL) { $env:GPT_OSS_MODEL } else { "gpt-oss:20b" }
$base = if ($env:GPT_OSS_BASE_URL) { $env:GPT_OSS_BASE_URL } else { "http://localhost:11434" }

Write-Host "== GPT-OSS bootstrap =="

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama was not found."
    Write-Host "Install Ollama from https://ollama.com/download/windows, then rerun this script."
    exit 2
}

$env:GPT_OSS_MODEL = $model
$env:GPT_OSS_BASE_URL = $base
[Environment]::SetEnvironmentVariable("GPT_OSS_MODEL", $model, "User")
[Environment]::SetEnvironmentVariable("GPT_OSS_BASE_URL", $base, "User")

Write-Host "Checking Ollama..."
try {
    $tags = Invoke-RestMethod -Uri "$base/api/tags" -Method Get -TimeoutSec 10
} catch {
    Write-Host "Ollama API is not reachable at $base"
    Write-Host "Start Ollama and rerun this script."
    exit 3
}

$exists = $tags.models | Where-Object { $_.name -eq $model }
if (-not $exists) {
    Write-Host "Pulling $model..."
    & ollama pull $model
    if ($LASTEXITCODE -ne 0) { throw "ollama pull failed with exit code $LASTEXITCODE" }
}

Write-Host "Running local chat-completions smoke test..."
$body = @{
    model = $model
    messages = @(
        @{ role = "user"; content = "Reply with exactly: GPT-OSS_OK" }
    )
    temperature = 0
    max_tokens = 16
} | ConvertTo-Json -Depth 5

try {
    $response = Invoke-RestMethod -Uri "$base/v1/chat/completions" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 180
} catch {
    Write-Host "GPT-OSS OpenAI-compatible endpoint failed at $base/v1/chat/completions"
    throw
}

$content = $response.choices[0].message.content
if (-not $content) { throw "GPT-OSS returned no assistant content." }

Write-Host "GPT-OSS endpoint is responding."
Write-Host "Model: $model"
Write-Host "Response: $content"
Write-Host ""
Write-Host "MBM-Social environment configured for this Windows user."