from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_events(data_dir: Path, date_text: str) -> list[dict[str, Any]]:
    path = data_dir / "events" / f"{date_text}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def load_raw_records(data_dir: Path, date_text: str) -> list[dict[str, Any]]:
    path = data_dir / "raw" / f"{date_text}.jsonl"
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def format_day_log(data_dir: Path, date_text: str) -> str:
    events = load_events(data_dir, date_text)
    raw_records = load_raw_records(data_dir, date_text)
    lines: list[str] = [f"{date_text} 活动日志", ""]

    lines.append("合并事件")
    if not events:
        lines.append("暂无合并事件。")
    else:
        for event in events:
            category = " / ".join(str(item) for item in event.get("category", ["未知"]))
            lines.append(
                f"{event.get('start', '--:--')}-{event.get('end', '--:--')} —— "
                f"{category} —— {event.get('event', '未知活动')} "
                f"({event.get('duration_minutes', 0)} 分钟)"
            )

    lines.extend(["", "原始识别记录"])
    if not raw_records:
        lines.append("暂无原始记录。")
    else:
        for record in raw_records:
            category = " / ".join(str(item) for item in record.get("category", ["未知"]))
            lines.append(
                f"{record.get('timestamp', '未知时间')} —— {category} —— "
                f"{record.get('event', '未知活动')} —— 置信度 {record.get('confidence', 0)}"
            )

    return "\n".join(lines)
