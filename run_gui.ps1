$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed or not in PATH. Install it with: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
}

$env:UV_CACHE_DIR = Join-Path $PSScriptRoot ".uv-cache"
uv sync
uv run screen-agent-gui
