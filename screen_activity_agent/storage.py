from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from screen_activity_agent.models import ActivityRecord
from screen_activity_agent.timeutil import date_key, local_iso_for_date_minute, minute_key, parse_iso


def _same_category(left: list[str], right: list[str]) -> bool:
    return len(left) >= 2 and len(right) >= 2 and left[0] == right[0] and left[1] == right[1]


def _event_similar(left: str, right: str) -> bool:
    left = "".join(left.split())
    right = "".join(right.split())
    if not left or not right:
        return False
    if left == right:
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.55


@dataclass
class ActivityStorage:
    data_dir: Path
    merge_gap_seconds: int

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def events_dir(self) -> Path:
        return self.data_dir / "events"

    def ensure_dirs(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def save_record(self, record: ActivityRecord) -> dict[str, Any]:
        self.ensure_dirs()
        record_dict = record.to_dict()
        timestamp = parse_iso(record.timestamp)
        day = date_key(timestamp)

        raw_path = self.raw_dir / f"{day}.jsonl"
        with raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record_dict, ensure_ascii=False) + "\n")

        self._merge_event(record)
        return record_dict

    def _events_path(self, day: str) -> Path:
        return self.events_dir / f"{day}.json"

    def _load_events(self, day: str) -> list[dict[str, Any]]:
        path = self._events_path(day)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []

    def _load_runtime_marks(self, day: str) -> list[dict[str, Any]]:
        path = self.data_dir / "runtime" / f"{day}.jsonl"
        if not path.exists():
            return []
        marks: list[dict[str, Any]] = []
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
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
                marks.append(item)
        return marks

    def _has_runtime_break(self, day: str, start_minute: str, end_minute: str) -> bool:
        start_ts = parse_iso(local_iso_for_date_minute(day, start_minute))
        end_ts = parse_iso(local_iso_for_date_minute(day, end_minute))
        for mark in self._load_runtime_marks(day):
            action = str(mark.get("action", "")).strip().lower()
            if action not in {"pause", "stop"}:
                continue
            try:
                mark_ts = parse_iso(str(mark.get("timestamp", "")))
            except ValueError:
                continue
            if start_ts <= mark_ts <= end_ts:
                return True
        return False

    def _save_events(self, day: str, events: list[dict[str, Any]]) -> None:
        path = self._events_path(day)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(events, handle, ensure_ascii=False, indent=2)

    def close_current_event(self, timestamp: str) -> None:
        ts = parse_iso(timestamp)
        day = date_key(ts)
        events = self._load_events(day)
        if not events:
            return
        current_minute = minute_key(ts)
        last = events[-1]
        if last.get("date") != day:
            return
        last_start = str(last.get("start", current_minute))
        current_ts = parse_iso(local_iso_for_date_minute(day, current_minute))
        last_start_ts = parse_iso(local_iso_for_date_minute(day, last_start))
        if current_ts < last_start_ts:
            return
        last["end"] = current_minute
        last["duration_minutes"] = self._duration_minutes(day, last_start, current_minute)
        self._save_events(day, events)

    def _merge_event(self, record: ActivityRecord) -> None:
        ts = parse_iso(record.timestamp)
        day = date_key(ts)
        events = self._load_events(day)
        current_minute = minute_key(ts)

        if events and self._can_merge(events[-1], record, ts):
            last = events[-1]
            last["end"] = current_minute
            if last.get("privacy_risk") or record.privacy_risk:
                last["event"] = "用户正在查看包含敏感信息的页面"
                last["category"] = ["隐私内容", "敏感页面"]
                last["privacy_risk"] = True
            else:
                last["event"] = record.event if len(record.event) > len(last.get("event", "")) else last.get("event", record.event)
                last["category"] = record.category
            last["confidence"] = round((float(last.get("confidence", 0.0)) + record.confidence) / 2, 3)
            last["duration_minutes"] = self._duration_minutes(last["date"], last["start"], last["end"])
            last["_last_seen"] = record.timestamp
        else:
            if events:
                last = events[-1]
                if last.get("date") == day:
                    last_end = str(last.get("end", last.get("start", current_minute)))
                    current_ts = parse_iso(local_iso_for_date_minute(day, current_minute))
                    last_end_ts = parse_iso(local_iso_for_date_minute(day, last_end))
                    if (
                        current_ts >= last_end_ts
                        and current_ts - last_end_ts <= timedelta(seconds=self.merge_gap_seconds)
                        and not self._has_runtime_break(day, last_end, current_minute)
                    ):
                        last["end"] = current_minute
                        last["duration_minutes"] = self._duration_minutes(last["date"], last["start"], last["end"])
            events.append(
                {
                    "date": day,
                    "start": current_minute,
                    "end": current_minute,
                    "category": record.category,
                    "event": record.event,
                    "duration_minutes": 0,
                    "confidence": record.confidence,
                    "privacy_risk": record.privacy_risk,
                    "_last_seen": record.timestamp,
                }
            )

        public_events = [{key: value for key, value in item.items() if key != "_last_seen"} for item in events]
        self._save_events(day, public_events)

    def _can_merge(self, event: dict[str, Any], record: ActivityRecord, current_ts) -> bool:
        if not record.is_continuation:
            return False
        if not _same_category(list(event.get("category", [])), record.category):
            return False
        if not _event_similar(str(event.get("event", "")), record.event):
            return False

        last_seen_raw = event.get("_last_seen")
        if last_seen_raw:
            last_seen = parse_iso(str(last_seen_raw))
        else:
            last_seen = parse_iso(local_iso_for_date_minute(event["date"], event.get("end", "00:00")))

        return current_ts - last_seen <= timedelta(seconds=self.merge_gap_seconds)

    @staticmethod
    def _duration_minutes(day: str, start: str, end: str) -> int:
        start_ts = parse_iso(local_iso_for_date_minute(day, start))
        end_ts = parse_iso(local_iso_for_date_minute(day, end))
        minutes = int((end_ts - start_ts).total_seconds() // 60)
        return max(0, minutes)
