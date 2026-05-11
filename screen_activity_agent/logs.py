from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ALL_CATEGORIES_LABEL = "全部"


def _category_parts(category: Any) -> list[str]:
    if not isinstance(category, list):
        return ["未知"]
    parts = [str(item).strip() for item in category if str(item).strip()]
    return parts or ["未知"]


def category_label(category: Any) -> str:
    return " / ".join(_category_parts(category))


def _matches_category(item: dict[str, Any], category_filter: str) -> bool:
    if not category_filter or category_filter == ALL_CATEGORIES_LABEL:
        return True
    label = category_label(item.get("category"))
    primary = _category_parts(item.get("category"))[0]
    return label == category_filter or label.startswith(f"{category_filter} /") or primary == category_filter


def _json_load(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def load_events(data_dir: Path, date_text: str) -> list[dict[str, Any]]:
    data = _json_load(data_dir / "events" / f"{date_text}.json", [])
    return data if isinstance(data, list) else []


def save_events(data_dir: Path, date_text: str, events: list[dict[str, Any]]) -> None:
    path = data_dir / "events" / f"{date_text}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_raw_records(data_dir: Path, date_text: str) -> list[dict[str, Any]]:
    path = data_dir / "raw" / f"{date_text}.jsonl"
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def save_raw_records(data_dir: Path, date_text: str, records: list[dict[str, Any]]) -> None:
    path = data_dir / "raw" / f"{date_text}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    path.write_text(text, encoding="utf-8")


def filter_items_by_category(items: list[dict[str, Any]], category_filter: str) -> list[dict[str, Any]]:
    return [item for item in items if _matches_category(item, category_filter)]


def category_options(data_dir: Path, date_text: str) -> list[str]:
    labels: set[str] = set()
    primary_labels: set[str] = set()
    for item in [*load_events(data_dir, date_text), *load_raw_records(data_dir, date_text)]:
        parts = _category_parts(item.get("category"))
        primary_labels.add(parts[0])
        labels.add(" / ".join(parts))
    options = sorted(primary_labels | labels)
    return [item for item in options if item and item != "未知"]


def _minutes(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def format_minutes(minutes: int) -> str:
    minutes = max(0, int(minutes))
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} 小时 {rest} 分钟"
    if hours:
        return f"{hours} 小时"
    return f"{rest} 分钟"


def today_summary(data_dir: Path, date_text: str) -> tuple[str, str]:
    events = load_events(data_dir, date_text)
    totals: Counter[str] = Counter()
    total_minutes = 0
    for event in events:
        primary = _category_parts(event.get("category"))[0]
        minutes = _minutes(event.get("duration_minutes"))
        if minutes <= 0:
            continue
        total_minutes += minutes
        totals[primary] += minutes
    if not totals or total_minutes <= 0:
        return "0 分钟", "暂无记录"
    parts = [f"{name} {minutes * 100 / total_minutes:.1f}%" for name, minutes in totals.most_common(5)]
    return format_minutes(total_minutes), "；".join(parts)


def record_summary(data_dir: Path, date_text: str, category_filter: str = ALL_CATEGORIES_LABEL) -> tuple[str, str]:
    events = filter_items_by_category(load_events(data_dir, date_text), category_filter)
    totals: Counter[str] = Counter()
    total_minutes = 0
    for event in events:
        primary = _category_parts(event.get("category"))[0]
        minutes = _minutes(event.get("duration_minutes"))
        if minutes <= 0:
            continue
        total_minutes += minutes
        totals[primary] += minutes
    summary = "；".join(f"{name} {format_minutes(minutes)}" for name, minutes in totals.most_common(3))
    return format_minutes(total_minutes), summary or "暂无记录"


def format_timeline(data_dir: Path, date_text: str, category_filter: str = ALL_CATEGORIES_LABEL) -> str:
    events = filter_items_by_category(load_events(data_dir, date_text), category_filter)
    lines: list[str] = [f"{date_text} 时间线", ""]
    if not events:
        lines.append("暂无合并事件。")
    else:
        for event in events:
            lines.append(
                f"{event.get('start', '--:--')}-{event.get('end', '--:--')} —— "
                f"{category_label(event.get('category'))} —— {event.get('event', '未知活动')}"
            )
    return "\n".join(lines)


def format_day_timeline(data_dir: Path, date_text: str, category_filter: str = ALL_CATEGORIES_LABEL) -> str:
    return format_timeline(data_dir, date_text, category_filter)


def format_records(data_dir: Path, date_text: str, category_filter: str = ALL_CATEGORIES_LABEL) -> str:
    events = filter_items_by_category(load_events(data_dir, date_text), category_filter)
    raw_records = filter_items_by_category(load_raw_records(data_dir, date_text), category_filter)
    lines: list[str] = [f"{date_text} 记录管理", ""]

    lines.append("合并事件")
    if not events:
        lines.append("暂无合并事件。")
    else:
        for index, event in enumerate(events, start=1):
            lines.append(
                f"{index}. {event.get('start', '--:--')}-{event.get('end', '--:--')} —— "
                f"{category_label(event.get('category'))} —— {event.get('event', '未知活动')} "
                f"({format_minutes(_minutes(event.get('duration_minutes')))})"
            )

    lines.extend(["", "原始识别记录"])
    if not raw_records:
        lines.append("暂无原始记录。")
    else:
        for index, record in enumerate(raw_records, start=1):
            lines.append(
                f"{index}. {record.get('timestamp', '未知时间')} —— "
                f"{category_label(record.get('category'))} —— {record.get('event', '未知活动')} —— "
                f"App: {record.get('app', '未知')} —— 置信度 {record.get('confidence', 0)}"
            )

    return "\n".join(lines)


def format_day_log(data_dir: Path, date_text: str) -> str:
    return format_records(data_dir, date_text)


def export_items_to_json(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_items_to_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "date",
        "start",
        "end",
        "category",
        "event",
        "duration_minutes",
        "app",
        "window_title",
        "confidence",
        "privacy_risk",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            row = {key: item.get(key, "") for key in fieldnames}
            row["category"] = category_label(item.get("category"))
            writer.writerow(row)
