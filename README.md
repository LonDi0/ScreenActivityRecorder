# 屏幕活动记录 Agent

本项目是一个本地运行的屏幕活动记录 Agent。首版提供 PySide6 最小 GUI，支持手动识别一次、按间隔持续记录、暂停、查看日志、原始记录落盘和连续活动合并。

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

## 打包 EXE

```powershell
cd E:\myProject\recordAgent
.\build_exe.ps1
```

生成文件：

```text
E:\myProject\recordAgent\dist\ScreenActivityAgent\ScreenActivityAgent.exe
```

运行 `.exe` 后会打开图形界面。如果同目录 `.env` 缺少 API Key、URL 或模型，程序会先进入“配置”页；配置完整后会进入正常界面。配置页可随时修改 API Key、URL、模型和截图间隔。

配置页支持保存多套 API 配置：

- 页面会显示当前正在应用的配置名称。
- 点击“添加配置”会打开子页面，填写配置名称、API Key、URL、模型后点击“保存”。
- 新增配置时配置名称不能重复，配置名称、API Key、URL 和模型都不能为空。
- 点击每行的“修改”可以在原配置基础上编辑名称、API Key、URL 和模型；名称可以保持为当前配置名，但不能和其它配置重复。
- 在配置列表里点击某套配置后的“应用”即可切换；当前配置会显示为绿色“已应用”。
- “删除”只删除保存的配置档案，不删除历史记录。

多配置档案保存在 `.env` 同目录的 `api_profiles.json`。

修改 API Key、URL 或模型只影响后续识别请求，不会删除历史记录。历史数据默认保存在 `.env` 所在目录下的 `data/`，也可以通过 `SCREEN_AGENT_DATA_DIR` 固定到指定目录。

如果你想把程序移动到别的文件夹，请移动整个目录：

```text
E:\myProject\recordAgent\dist\ScreenActivityAgent\
```

不要只移动单独的 `.exe`，因为 PyInstaller 目录模式还需要旁边的 `_internal` 运行库。配置文件和记录数据会保存在 `.exe` 所在目录下。

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
