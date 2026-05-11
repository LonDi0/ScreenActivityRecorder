# ScreenActivityRecorder v0.1.0

ScreenActivityRecorder is a local Windows desktop app that periodically analyzes your screen and builds an objective activity timeline. It helps users review what they spent time on by category, timeline, and statistics.

This project is useful for personal time review, lightweight work logs, learning logs, and activity statistics. It is not an anti-procrastination tool: it does not judge, warn, block apps, or interfere with user behavior.

## What It Does

ScreenActivityRecorder works by:

1. Taking screenshots at a configured interval.
2. Sending temporary image data to a GPT-compatible vision model.
3. Converting the model response into structured local records.
4. Merging continuous similar activities into timeline blocks.
5. Showing timelines, statistics, and records in a desktop GUI.

Example output:

```text
2026-05-11 09:12-09:47 - Study / Programming - Watched a Python tutorial and practiced code
2026-05-11 13:41-14:35 - Games / Wuthering Waves - Played Wuthering Waves
```

## Download And Run

For normal Windows users:

1. Open the GitHub Releases page.
2. Download `ScreenActivityRecorder-v0.1.0-windows.zip`.
3. Extract the entire zip file.
4. Double-click `ScreenActivityAgent.exe`.
5. On first launch, open Settings and add an API profile.

Keep the whole extracted folder together. Do not move only the `.exe`, because the app also needs the `_internal` runtime directory.

## First-Time Setup

In the app's Settings page, add an API profile:

- `OPENAI_API_KEY`: your GPT-compatible API key.
- `API Base URL`: the API endpoint. The default project target is `https://apiport.cc.cd/v1`.
- `Model`: a vision-capable model name supported by your provider.

After saving a profile, click `Apply`, then return to the dashboard and click `Start Recording` or `Manual Recognize Once`.

## Main Features

- Start, pause, and manually run screen recognition.
- Save multiple API profiles and switch between them.
- Mask API keys in the UI and copy the full key when needed.
- Dashboard with today's recorded duration and category share.
- Daily timeline page.
- Day, week, month, last 7 days, and last 30 days statistics.
- Record management with filters, details, editing, deletion, and JSON/CSV export.
- Privacy protection and sensitive content filtering.
- Optional raw screenshot saving.
- Optional Windows startup launch.

## Local Data And Privacy

Runtime records are stored locally after users run the app. By default, data is saved in:

```text
data/
  raw/
    YYYY-MM-DD.jsonl
  events/
    YYYY-MM-DD.json
```

The repository and release package do not include development data, `.env`, `api_profiles.json`, or `data/`.

ScreenActivityRecorder asks the model to summarize activities without saving sensitive text. The code also applies privacy-oriented normalization before records are written.

The app should not record raw passwords, verification codes, API keys, tokens, cookies, private chat transcripts, bank card numbers, ID numbers, home addresses, or medical private details. When sensitive content is detected, records should keep only a general description.

## Build From Source

Install [uv](https://docs.astral.sh/uv/) first, then run:

```powershell
uv sync
uv run screen-agent-gui
```

Useful commands:

```powershell
uv run screen-agent-once
uv run screen-agent-diagnose
uv run screen-agent-report 2026-05-11 --period day
uv run screen-agent-report 2026-05-11 --period week
uv run screen-agent-report 2026-05-11 --period month
uv run screen-agent-report 2026-05-11 --period last7
uv run screen-agent-report 2026-05-11 --period last30
```

## Build Windows EXE

From the repository root:

```powershell
.\build_exe.ps1
```

The build output is:

```text
dist/ScreenActivityAgent/ScreenActivityAgent.exe
```

To distribute it, zip the whole `dist/ScreenActivityAgent/` folder, not just the exe.

## Configuration Variables

The GUI is the recommended way to configure the app. Advanced users can also use environment variables or a local `.env` file:

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

Legacy-compatible names `OPENAI_BASE_URL` and `MODEL_ID` are also supported.

## Project Status

This is an early Windows desktop version. Current storage uses local JSON/JSONL files. Future versions may add a stronger background service model, tray mode, database storage, richer charts, and improved installers.
