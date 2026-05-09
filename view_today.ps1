$ErrorActionPreference = "Stop"

chcp 65001 | Out-Null
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()

$date = Get-Date -Format "yyyy-MM-dd"
if ($args.Count -gt 0) {
    $date = $args[0]
}

$eventsPath = Join-Path $PSScriptRoot "data\events\$date.json"
$rawPath = Join-Path $PSScriptRoot "data\raw\$date.jsonl"

Write-Host "$date 合并事件"
if (Test-Path -LiteralPath $eventsPath) {
    Get-Content -LiteralPath $eventsPath -Encoding UTF8
} else {
    Write-Host "未找到 $eventsPath"
}

Write-Host ""
Write-Host "$date 原始记录"
if (Test-Path -LiteralPath $rawPath) {
    Get-Content -LiteralPath $rawPath -Encoding UTF8
} else {
    Write-Host "未找到 $rawPath"
}
