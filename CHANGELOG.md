# 更新日志

本文档记录每次功能添加、修改、删除的内容。后续开发必须在同一次变更中同步更新本文件。

## 2026-05-09

### 添加

- 初始化 Python / uv 项目结构，加入 `openai`、`pillow`、`pyside6`、`python-dotenv`、`tzdata` 等运行依赖。
- 添加屏幕截图与图片编码能力，支持 Windows 桌面截图、图片缩放、JPEG/PNG data URL 输出。
- 添加 GPT 兼容视觉模型调用，支持 `OPENAI_API_KEY`、API Base URL、模型名配置，并要求返回结构化 JSON。
- 添加活动识别 Prompt，包含分类体系、视频分类规则、隐私脱敏规则、未知处理规则和禁止评价用户行为规则。
- 添加最近 5 条活动记忆，用于辅助判断当前活动是否延续。
- 添加本地数据存储：原始记录写入 `data/raw/YYYY-MM-DD.jsonl`，合并事件写入 `data/events/YYYY-MM-DD.json`。
- 添加连续活动合并逻辑，按分类、事件相似度、时间间隔和 `is_continuation` 判断是否合并。
- 添加命令行单次识别入口 `screen-agent-once`。
- 添加 API 诊断入口 `screen-agent-diagnose`，用于测试文本调用、图片调用和截图图片调用。
- 添加 PySide6 图形界面，包含控制台、日志、配置三个页面。
- 添加控制台操作：开始记录、暂停、手动识别一次、查看最近识别结果。
- 添加日志页面，支持按日期查看合并事件和原始识别记录。
- 添加配置页面，支持编辑 API Key、API Base URL、模型名和截图间隔。
- 添加配置完整性检查：如果 API Key、URL 或模型未配置，启动后自动进入配置页面。
- 添加多套 API 配置管理：保存配置、应用配置、删除配置。
- 添加 `api_profiles.json`，用于保存多套 API 配置档案。
- 添加 Windows PowerShell 启动脚本 `run_gui.ps1`、`run_once.ps1`、`view_today.ps1`。
- 添加 PyInstaller 打包脚本 `build_exe.ps1`。
- 生成 Windows 图形界面可执行文件 `dist/ScreenActivityAgent/ScreenActivityAgent.exe`。

### 修改

- 将默认运行环境明确为 Windows 本地桌面。
- 将默认 API Base URL 规范化为 `https://apiport.cc.cd/v1`。
- 将默认模型调整为 `gpt-5.5`，同时保留通过环境变量覆盖的能力。
- 优化截图请求体，默认使用 JPEG、宽度压缩和单屏截图，降低模型网关拦截概率。
- 配置读取改为自动查找 `.env`，便于 exe 目录和项目根目录之间复用配置。
- GUI 状态语义改为“已暂停 / 运行中”，关闭窗口时会停止后台 worker。
- 控制台页移除“修改配置”按钮，配置切换统一通过顶部“配置”页进入。
- 配置页改为显示当前应用配置名称，并通过“添加配置”子页面新增 API 配置。
- 配置列表新增“修改”按钮，支持在原配置基础上编辑名称、API Key、URL 和模型，并允许名称保持为当前配置名。
- 配置列表改为每行直接显示“应用 / 已应用”状态，当前应用配置使用绿色“已应用”按钮区分。
- Windows 打包从全量收集 PySide6 改为只收集实际需要的模块和 `tzdata`，减少构建时间和产物体积。
- README 补充 Windows 运行、诊断、打包、多配置和日志查看说明。

### 删除

- 移除“只能通过命令行查看记录”的限制，改为 GUI 日志页可直接查看。
- 打包流程不再全量收集 PySide6 所有模块，避免构建过慢和产物过大。
