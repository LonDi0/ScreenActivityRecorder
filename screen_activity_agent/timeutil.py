from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ).replace(second=0, microsecond=0)


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def date_key(dt: datetime) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")


def minute_key(dt: datetime) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%H:%M")
