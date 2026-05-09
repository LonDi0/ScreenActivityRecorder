$ErrorActionPreference = "Stop"

chcp 65001 | Out-Null
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed or not in PATH. Install it with: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
}

$env:UV_CACHE_DIR = Join-Path $PSScriptRoot ".uv-cache"
uv sync --group dev
uv run pyinstaller --noconfirm --clean --windowed --name ScreenActivityAgent --collect-all tzdata screen_activity_agent\gui.py

Write-Host ""
Write-Host "EXE created:"
Write-Host (Join-Path $PSScriptRoot "dist\ScreenActivityAgent\ScreenActivityAgent.exe")
