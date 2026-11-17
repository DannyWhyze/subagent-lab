$ErrorActionPreference = "Stop"

# Resolve project root dynamically regardless of working directory
$ProjectRoot = $PSScriptRoot

$serverCmd = "Set-Location -LiteralPath '$ProjectRoot'; Write-Host 'Starting Subagent Lab Dev Server...' -ForegroundColor Cyan; Write-Host 'URL: http://127.0.0.1:8000' -ForegroundColor Green; uv run python -m src.main"

Write-Host "Launching Subagent Lab dev server in a dedicated console window..." -ForegroundColor Cyan
Start-Process powershell.exe -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $serverCmd
