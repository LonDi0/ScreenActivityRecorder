# ScreenActivityRecorder v0.1.0

这是 ScreenActivityRecorder 的首个 Windows 桌面版本。

ScreenActivityRecorder 是一个本地屏幕活动记录工具。它会定时识别屏幕内容，生成结构化记录，并把连续相似活动合并成时间线，帮助用户回顾当天活动、查看分类占比和管理历史记录。

它不是反拖延工具，不会提醒、批评、阻止或干预用户操作，只做客观记录和统计。

## 下载和运行

1. 在 [release](https://github.com/LonDi0/ScreenActivityRecorder/releases/tag/v0.1.0) 中下载 `ScreenActivityRecorder-v0.1.0-windows.zip`。
2. 解压整个压缩包。
3. 双击 `ScreenActivityAgent.exe`。
4. 首次启动后，在“配置”页面添加 API 配置。

不要只移动单独的 `.exe` 文件。请保留解压后的完整目录，包括 `_internal` 文件夹。

## 首次配置

在“配置”页面添加：

- `OPENAI_API_KEY`：你的 GPT 兼容 API Key。
- `API Base URL`：API 地址，默认目标是 `https://api.openai.com/v1`。
- `Model`：服务商支持的视觉模型名称。

保存配置后点击“应用”，再回到首页点击“开始记录”或“手动识别一次”。

## 主要功能

- 开始、暂停、手动识别一次。
- 保存和切换多套 API 配置。
- API Key 掩码显示，并支持复制完整 Key。
- 首页展示今日记录时长和分类占比。
- 独立时间线页面。
- 日、周、月、近 7 天、近 30 天统计。
- 记录管理：筛选、详情、编辑、删除、导出 JSON/CSV。
- 隐私保护和敏感内容过滤。
- 可选保存原始截图。
- 可选 Windows 开机自启。

## 本地数据

发布包不包含开发数据、`.env`、`api_profiles.json` 或 `data/`。

运行后，用户自己的配置和记录会保存在本地。
