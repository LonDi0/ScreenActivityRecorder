from __future__ import annotations

from datetime import datetime


def local_tz():
    return datetime.now().astimezone().tzinfo


def now_local() -> datetime:
    return datetime.now().astimezone().replace(second=0, microsecond=0)


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def date_key(dt: datetime) -> str:
    return dt.astimezone(local_tz()).strftime("%Y-%m-%d")


def minute_key(dt: datetime) -> str:
    return dt.astimezone(local_tz()).strftime("%H:%M")


def local_iso_for_date_minute(day: str, minute: str) -> str:
    offset = now_local().strftime("%z")
    offset_text = f"{offset[:3]}:{offset[3:]}" if offset else ""
    return f"{day}T{minute}:00{offset_text}"
