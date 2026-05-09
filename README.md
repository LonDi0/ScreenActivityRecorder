# 屏幕活动记录 Agent

本项目是一个本地运行的屏幕活动记录 Agent。首版提供 PySide6 最小 GUI，支持手动识别一次、按间隔持续记录、暂停/停止、原始记录落盘和连续活动合并。

## 环境变量

不要把 API Key 写入代码。运行前设置：

```powershell
$env:OPENAI_API_KEY="你的 API Key"
```

可选配置：

```powershell
$env:SCREEN_AGENT_BASE_URL="https://apiport.cc.cd"
$env:SCREEN_AGENT_MODEL="gpt-4o-mini"
$env:SCREEN_AGENT_SCREENSHOT_MAX_WIDTH="1280"
$env:SCREEN_AGENT_ALL_SCREENS="false"
$env:SCREEN_AGENT_IMAGE_FORMAT="jpeg"
$env:SCREEN_AGENT_JPEG_QUALITY="70"
```

项目也会读取本地 `.env`，并兼容 `OPENAI_BASE_URL` 与 `MODEL_ID`。

如果点击“开始”后模型服务返回 `Your request was blocked.`，优先尝试：

```powershell
$env:SCREEN_AGENT_MODEL="gpt-4o-mini"
$env:SCREEN_AGENT_SCREENSHOT_MAX_WIDTH="960"
$env:SCREEN_AGENT_ALL_SCREENS="false"
$env:SCREEN_AGENT_IMAGE_FORMAT="jpeg"
.\run_gui.ps1
```

这会改用更常见的视觉模型名，并缩小截图请求体。

## Windows 运行

```powershell
uv sync
uv run screen-agent-gui
```

如果 C 盘空间紧张，建议在项目目录使用 E 盘缓存：

```powershell
$env:UV_CACHE_DIR="E:\myProject\recordAgent\.uv-cache"
uv sync
```

命令行单次识别：

```powershell
uv run screen-agent-once
```

API 诊断：

```powershell
uv run screen-agent-diagnose
```

如果系统还没有安装 `uv`，可在 PowerShell 中安装后重新打开终端：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

也可以直接使用项目脚本：

```powershell
.\run_gui.ps1
.\run_once.ps1
```

Windows 控制台如果显示中文乱码，先切换 UTF-8：

```powershell
chcp 65001
Get-Content .\data\events\2026-05-09.json -Encoding UTF8
```

或直接使用：

```powershell
.\view_today.ps1
.\view_today.ps1 2026-05-09
```

## 数据目录

```text
data/
  raw/
    YYYY-MM-DD.jsonl
  events/
    YYYY-MM-DD.json
```
