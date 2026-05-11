# ScreenActivityRecorder

ScreenActivityRecorder 是一个在 Windows 本地运行的屏幕活动记录工具。它会按设定间隔识别当前屏幕内容，生成结构化记录，并把连续相似活动合并成时间线，帮助用户回顾一天中做了什么、各类活动占用了多少时间。

它不是反拖延工具，不会提醒、批评、阻止或干预用户操作，只做客观记录和统计。

## 项目能做什么

ScreenActivityRecorder 可以帮助你回答这些问题：

- 今天主要把时间花在了哪些事情上？
- 某一天从几点到几点在做什么？
- 工作、学习、编程、娱乐、游戏、沟通等活动分别占多少时间？
- 最近 7 天或最近 30 天的活动趋势如何？

基本流程是：

1. 定时截图。
2. 将截图临时发送给 GPT 兼容视觉模型识别。
3. 将模型返回结果整理为结构化 JSON 记录。
4. 自动合并连续相似活动。
5. 在图形界面中展示首页、时间线、统计、记录管理和配置。

记录示例：

```text
2026-05-11 09:12-09:47 - 学习 / 编程 - 观看 Python 教程并练习代码
2026-05-11 13:41-14:35 - 游戏 / 鸣潮 - 游玩《鸣潮》
```

## 主要功能

- 开始、暂停、手动识别一次。
- 首页展示今日已记录时长和主要分类占比。
- 独立时间线页面，支持按日期和分类筛选。
- 统计页面支持日、周、月、近 7 天、近 30 天。
- 记录管理页面支持筛选、查看详情、编辑、删除、导出 JSON/CSV。
- 支持保存多套 API 配置并自由切换。
- API Key 在界面中掩码显示，并支持复制完整 Key。
- 支持隐私保护和敏感内容过滤。
- 可选保存原始截图。
- 可选 Windows 开机自启。

## 下载和运行

普通用户建议直接下载 Release 包，不需要安装 Python。

1. 打开 GitHub 的 [Releases 页面](https://github.com/LonDi0/ScreenActivityRecorder/releases/tag/v0.1.0)。
2. 下载 `ScreenActivityRecorder-v0.1.0-windows.zip`。
3. 解压整个压缩包。
4. 双击 `ScreenActivityAgent.exe`。
5. 第一次启动后，在“配置”页面添加 API 配置。

不要只移动单独的 `.exe` 文件。请保留解压后的完整目录，包括 `_internal` 文件夹，因为程序运行依赖这些文件。

## 首次配置

在“配置”页面添加 API 配置：

- `OPENAI_API_KEY`：你的 GPT 兼容 API Key。
- `API Base URL`：API 地址，项目默认目标是 `https://apiport.cc.cd/v1`。
- `Model`：你的服务商支持的视觉模型名称。

保存配置后点击“应用”，回到首页点击“开始记录”或“手动识别一次”。

## 本地数据和隐私

运行时数据默认保存在本地：

```text
data/
  raw/
    YYYY-MM-DD.jsonl
  events/
    YYYY-MM-DD.json
```

仓库和发布包不会包含开发过程数据、`.env`、`api_profiles.json` 或 `data/`。

程序会要求模型只概括活动，不保存敏感原文。代码层也会在落盘前做隐私保护处理。它不应记录密码、验证码、API Key、Token、Cookie、私密聊天全文、银行卡号、身份证号、家庭住址或医疗隐私等原文。

## 从源码运行

先安装 [uv](https://docs.astral.sh/uv/)，然后在项目根目录执行：

```powershell
uv sync
uv run screen-agent-gui
```

其它命令：

```powershell
uv run screen-agent-once
uv run screen-agent-diagnose
uv run screen-agent-report 2026-05-11 --period day
uv run screen-agent-report 2026-05-11 --period week
uv run screen-agent-report 2026-05-11 --period month
uv run screen-agent-report 2026-05-11 --period last7
uv run screen-agent-report 2026-05-11 --period last30
```

## 打包 Windows EXE

在项目根目录执行：

```powershell
.\build_exe.ps1
```

输出目录：

```text
dist/ScreenActivityAgent/
```

发布时应压缩整个 `dist/ScreenActivityAgent/` 目录，而不是只压缩单独的 exe。

## 配置项

推荐通过 GUI 配置。高级用户也可以使用环境变量或本地 `.env`：

```text
OPENAI_API_KEY
SCREEN_AGENT_BASE_URL
SCREEN_AGENT_MODEL
SCREEN_AGENT_INTERVAL_SECONDS
SCREEN_AGENT_DATA_DIR
SCREEN_AGENT_SAVE_RAW_SCREENSHOT
SCREEN_AGENT_PRIVACY_PROTECTION
SCREEN_AGENT_SENSITIVE_CONTENT_FILTER
SCREEN_AGENT_AUTOSTART
```

兼容 `OPENAI_BASE_URL` 和 `MODEL_ID`。

## 项目状态

当前是早期 Windows 桌面版本，数据存储使用本地 JSON/JSONL。后续可以继续完善托盘后台运行、数据库存储、更丰富的图表、安装包和自动更新。
