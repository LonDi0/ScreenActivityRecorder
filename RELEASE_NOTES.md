# ScreenActivityRecorder Release Notes

## v0.1.0

首个 Windows 桌面版本，提供屏幕活动记录 Agent 的图形界面和本地 JSON/JSONL 存储。

### 使用方式

1. 下载 `ScreenActivityRecorder-v0.1.0-windows.zip`。
2. 解压整个压缩包。
3. 双击 `ScreenActivityAgent.exe`。
4. 首次启动时在“配置”页面添加 API Key、API Base URL 和模型名称。

不要只移动单独的 `.exe` 文件；请保留解压后的完整目录，因为程序依赖同目录下的 `_internal` 运行库。

### 主要功能

- 开始、暂停和手动识别屏幕活动。
- 多套 API 配置保存、切换、修改和删除。
- API Key 掩码显示，并支持复制完整 Key。
- 首页展示今日记录时长和主要分类占比。
- 独立时间线页面。
- 日、周、月、近 7 天和近 30 天统计。
- 记录管理页面支持筛选、详情、编辑、删除和导出 JSON/CSV。
- 隐私保护和敏感内容过滤。
- 可选保存原始截图。
- Windows 开机自启开关。

### 本地数据

程序会在本地保存配置和活动记录。发布包不包含开发过程数据、`.env`、`api_profiles.json` 或 `data/`。
