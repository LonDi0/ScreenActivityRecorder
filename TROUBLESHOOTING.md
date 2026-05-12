# 排障记录

本文档用于记录项目开发、打包、发布、网络、认证、Windows 环境等问题的排查结论。

当遇到已经解决过、未来可能再次出现的问题时，应把问题现象、原因、验证方式和解决办法记录在这里，避免新的聊天上下文或新的维护者重复从头排查。

## 记录模板

```text
## YYYY-MM-DD 问题标题

### 现象

- 用户或维护者看到的错误、异常行为或失败命令。

### 判断

- 明确说明问题发生在哪一层：项目代码、打包产物、GitHub、网络、认证、Windows TLS、Codex 审批层等。
- 如果排除了某些原因，也记录排除依据。

### 验证

- 列出用于确认问题的命令、返回状态或关键日志。
- 不记录 API Key、Token、Cookie 等敏感值。

### 处理

- 写清楚最终可行的处理步骤。
- 如果有推荐的替代路径，也一起记录。
```

## 2026-05-12 GitHub Release 上传失败但 Token 未必失效

### 现象

- 使用 PowerShell / `Invoke-RestMethod` 上传 GitHub Release 资产时，命令在执行前被 Codex 审批层拒绝，并显示 `503 Service Unavailable`。
- 使用 `curl.exe` 或 `git ls-remote` 访问 GitHub HTTPS 时，Windows TLS 路径报错：

```text
schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS (0x8009030E)
```

### 判断

- `503 Service Unavailable` 来自 Codex 命令审批链路，不是 GitHub 返回的认证失败。
- `SEC_E_NO_CREDENTIALS` 来自 Windows Schannel/TLS 路径，不等价于 GitHub Token 过期。
- 如果 Token 失效，GitHub API 通常会返回 `401 Unauthorized` 或 `403 Forbidden`。

### 验证

- PowerShell / curl / git 的 HTTPS 路径失败。
- 项目虚拟环境中的 Python `httpx` 可以正常访问 GitHub API，返回 `200`：

```powershell
@'
import httpx
resp = httpx.get("https://api.github.com/", headers={"User-Agent": "codex-test"}, timeout=20.0)
print(resp.status_code)
print(resp.headers.get("content-type"))
'@ | .\.venv\Scripts\python.exe -
```

### 处理

- 不要优先判断为 Token 过期，应先区分失败发生在审批层、Windows TLS 层还是 GitHub API 层。
- 如果 `git` / `curl` / PowerShell 因 Schannel 失败，但 Python `httpx` 能访问 GitHub，则可使用 `.venv` 中的 Python 通过 GitHub REST API 上传 Release 资产。
- 上传 Release 资产时建议采用稳妥流程：
  1. 先上传临时名称的新资产。
  2. 上传成功后删除旧的正式资产。
  3. 将新资产重命名为正式文件名。
- 不要在文档、日志、命令输出或提交中记录真实 Token。

## 2026-05-12 API 失败区间被误并入正常活动

### 现象

- 当 12:41-12:50 期间 API 一直没有正常返回，而 12:51 恢复正常且屏幕仍在学习时，旧逻辑会把 12:41-12:50 直接并入前后的学习时间，导致整段时间都显示为学习。

### 判断

- 问题不在分类识别本身，而在记录缺口没有被单独落盘。
- 旧逻辑会优先延长上一条正常事件，导致失败期间没有独立的“未知 / API 访问失败”事件。

### 验证

- 连续 API 失败时，如果没有独立失败记录，后续正常记录会延长前一个正常事件。
- 修复后，失败时会落一条 `未知 / API 访问失败` 的原始记录和合并事件，连续失败可继续合并成独立区间。

### 处理

- API 失败、截图失败或截图保存失败时，先写入一条独立失败记录，再抛出异常给 GUI 或 CLI。
- 合并逻辑只在“类别相同、事件相近、且确实满足延续条件”时才延长上一事件，不再用失败后的成功记录反向吞掉失败区间。
