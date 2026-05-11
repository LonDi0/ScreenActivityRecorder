from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from screen_activity_agent.config import DEFAULT_MERGE_GAP_SECONDS, load_settings
from screen_activity_agent.models import ActivityRecord
from screen_activity_agent.storage import ActivityStorage


def _load_raw_records(data_dir: Path, day: str) -> list[dict]:
    path = data_dir / "raw" / f"{day}.jsonl"
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    records.sort(key=lambda item: str(item.get("timestamp", "")))
    return records


def _record_from_dict(item: dict) -> ActivityRecord:
    return ActivityRecord(
        timestamp=str(item.get("timestamp") or ""),
        app=str(item.get("app") or "未知"),
        window_title=str(item.get("window_title") or "未知"),
        screen_content=str(item.get("screen_content") or "未知"),
        category=[str(part) for part in item.get("category", ["未知", "未知"]) if str(part).strip()],
        event=str(item.get("event") or "未知活动"),
        is_continuation=bool(item.get("is_continuation", False)),
        confidence=float(item.get("confidence", 0.0) or 0.0),
        privacy_risk=bool(item.get("privacy_risk", False)),
    )


def rebuild_day(data_dir: Path, day: str, merge_gap_seconds: int, *, backup: bool = True) -> Path:
    records = _load_raw_records(data_dir, day)
    if not records:
        raise SystemExit(f"No raw records found for {day}.")

    events_path = data_dir / "events" / f"{day}.json"
    if backup and events_path.exists():
        backup_path = events_path.with_suffix(".json.bak")
        shutil.copy2(events_path, backup_path)

    if events_path.exists():
        events_path.unlink()
    storage = ActivityStorage(data_dir, merge_gap_seconds)
    for item in records:
        storage._merge_event(_record_from_dict(item))
    return events_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild merged event JSON from raw JSONL records.")
    parser.add_argument("date", help="Date to rebuild, in YYYY-MM-DD format.")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--merge-gap-seconds", type=int, default=None)
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    settings = load_settings(Path.cwd())
    data_dir = Path(args.data_dir) if args.data_dir else settings.data_dir
    merge_gap = args.merge_gap_seconds or settings.merge_gap_seconds or DEFAULT_MERGE_GAP_SECONDS
    path = rebuild_day(data_dir, args.date, merge_gap, backup=not args.no_backup)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
