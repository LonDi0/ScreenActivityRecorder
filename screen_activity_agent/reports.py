from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from screen_activity_agent.logs import load_events
from screen_activity_agent.timeutil import local_tz


@dataclass(frozen=True)
class EventItem:
    day: date
    start: str
    end: str
    category: list[str]
    event: str
    duration_minutes: int
    privacy_risk: bool

    @property
    def primary(self) -> str:
        if self.category and self.category[0].strip():
            return self.category[0].strip()
        return "未知"

    @property
    def secondary(self) -> str:
        if len(self.category) > 1 and self.category[1].strip():
            return self.category[1].strip()
        return "未知"

    @property
    def label(self) -> str:
        return f"{self.primary} / {self.secondary}"


@dataclass
class ReportAggregate:
    events: list[EventItem]
    total_minutes: int
    unknown_minutes: int
    primary_totals: Counter[str]
    secondary_totals: Counter[str]
    daily_totals: dict[date, int]
    daily_primary: dict[date, Counter[str]]
    weekly_totals: dict[date, int]
    weekly_primary: dict[date, Counter[str]]


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _iter_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _week_bounds(anchor: date) -> tuple[date, date]:
    start = anchor - timedelta(days=anchor.weekday())
    end = start + timedelta(days=6)
    return start, end


def _month_bounds(anchor: date) -> tuple[date, date]:
    start = anchor.replace(day=1)
    if anchor.month == 12:
        end = date(anchor.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(anchor.year, anchor.month + 1, 1) - timedelta(days=1)
    return start, end


def _rolling_bounds(anchor: date, days: int) -> tuple[date, date]:
    return anchor - timedelta(days=days - 1), anchor


def _period_bounds(anchor: date, period: str) -> tuple[date, date]:
    if period == "day":
        return anchor, anchor
    if period == "week":
        return _week_bounds(anchor)
    if period == "month":
        return _month_bounds(anchor)
    if period == "last7":
        return _rolling_bounds(anchor, 7)
    if period == "last30":
        return _rolling_bounds(anchor, 30)
    raise ValueError(f"Unsupported period: {period}")


def _format_minutes(minutes: int) -> str:
    minutes = max(0, int(minutes))
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} 小时 {rest} 分钟"
    if hours:
        return f"{hours} 小时"
    return f"{rest} 分钟"


def _format_percent(part: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{part * 100 / total:.1f}%"


def _top_name(counter: Counter[str]) -> str:
    if not counter:
        return "无"
    return counter.most_common(1)[0][0]


def _load_event_items(data_dir: Path, start: date, end: date) -> list[EventItem]:
    items: list[EventItem] = []
    for current in _iter_dates(start, end):
        for raw in load_events(data_dir, current.isoformat()):
            category = raw.get("category")
            if not isinstance(category, list):
                category = ["未知", "未知"]
            category = [str(item).strip() for item in category if str(item).strip()]
            if not category:
                category = ["未知", "未知"]
            if len(category) == 1:
                category.append("未知")
            try:
                duration = int(raw.get("duration_minutes", 0))
            except (TypeError, ValueError):
                duration = 0
            items.append(
                EventItem(
                    day=current,
                    start=str(raw.get("start", "--:--")),
                    end=str(raw.get("end", "--:--")),
                    category=category[:3],
                    event=str(raw.get("event", "未知活动")),
                    duration_minutes=max(0, duration),
                    privacy_risk=bool(raw.get("privacy_risk", False)),
                )
            )
    items.sort(key=lambda item: (item.day, item.start, item.end, item.event))
    return items


def _aggregate_events(events: list[EventItem]) -> ReportAggregate:
    primary_totals: Counter[str] = Counter()
    secondary_totals: Counter[str] = Counter()
    daily_totals: dict[date, int] = defaultdict(int)
    daily_primary: dict[date, Counter[str]] = defaultdict(Counter)
    weekly_totals: dict[date, int] = defaultdict(int)
    weekly_primary: dict[date, Counter[str]] = defaultdict(Counter)
    total_minutes = 0
    unknown_minutes = 0

    for event in events:
        minutes = max(0, int(event.duration_minutes))
        total_minutes += minutes
        primary = event.primary
        secondary = event.secondary
        primary_totals[primary] += minutes
        secondary_totals[f"{primary} / {secondary}"] += minutes
        daily_totals[event.day] += minutes
        daily_primary[event.day][primary] += minutes
        week_start = event.day - timedelta(days=event.day.weekday())
        weekly_totals[week_start] += minutes
        weekly_primary[week_start][primary] += minutes
        if primary == "未知":
            unknown_minutes += minutes

    return ReportAggregate(
        events=events,
        total_minutes=total_minutes,
        unknown_minutes=unknown_minutes,
        primary_totals=primary_totals,
        secondary_totals=secondary_totals,
        daily_totals=dict(daily_totals),
        daily_primary={key: Counter(value) for key, value in daily_primary.items()},
        weekly_totals=dict(weekly_totals),
        weekly_primary={key: Counter(value) for key, value in weekly_primary.items()},
    )


def _format_share_lines(counter: Counter[str], total_minutes: int, limit: int | None = None) -> list[str]:
    if not counter:
        return ["暂无记录。"]
    lines: list[str] = []
    items = counter.most_common(limit)
    for name, minutes in items:
        lines.append(f"{name}：{_format_minutes(minutes)}，{_format_percent(minutes, total_minutes)}")
    return lines


def _format_timeline(events: list[EventItem]) -> list[str]:
    lines: list[str] = []
    if not events:
        return ["暂无合并事件。"]
    for event in events:
        lines.append(f"{event.start}-{event.end} —— {event.label} —— {event.event}")
    return lines


def _format_day_report(data_dir: Path, anchor: date) -> str:
    start, end = anchor, anchor
    events = _load_event_items(data_dir, start, end)
    aggregate = _aggregate_events(events)

    lines = [f"{anchor.isoformat()} 活动记录", "", "时间线"]
    lines.extend(_format_timeline(events))
    lines.extend(["", "总记录时长：{}".format(_format_minutes(aggregate.total_minutes))])
    lines.append("一级分类时间占比：")
    lines.extend(_format_share_lines(aggregate.primary_totals, aggregate.total_minutes))
    lines.append(f"未知时间占比：{_format_minutes(aggregate.unknown_minutes)}，{_format_percent(aggregate.unknown_minutes, aggregate.total_minutes)}")
    lines.append("")
    lines.append("二级分类时间占比：")
    lines.extend(_format_share_lines(aggregate.secondary_totals, aggregate.total_minutes))
    return "\n".join(lines)


def _format_week_report(data_dir: Path, anchor: date) -> str:
    start, end = _week_bounds(anchor)
    events = _load_event_items(data_dir, start, end)
    aggregate = _aggregate_events(events)

    lines = [f"{start.isoformat()} 至 {end.isoformat()} 周报", "", f"总记录时长：{_format_minutes(aggregate.total_minutes)}", ""]
    lines.append("一级分类时间占比：")
    lines.extend(_format_share_lines(aggregate.primary_totals, aggregate.total_minutes))
    lines.append(f"未知时间占比：{_format_minutes(aggregate.unknown_minutes)}，{_format_percent(aggregate.unknown_minutes, aggregate.total_minutes)}")
    lines.append("")
    lines.append("主要活动：")
    lines.extend(
        [
            f"{index + 1}. {name}：{_format_minutes(minutes)}"
            for index, (name, minutes) in enumerate(aggregate.secondary_totals.most_common(5))
        ]
        or ["暂无记录。"]
    )
    lines.append("")
    lines.append("每日趋势：")
    if not aggregate.daily_totals:
        lines.append("暂无记录。")
    else:
        for current in _iter_dates(start, end):
            total = aggregate.daily_totals.get(current, 0)
            top = _top_name(aggregate.daily_primary.get(current, Counter()))
            lines.append(f"{current.isoformat()}：{_format_minutes(total)}，主要活动：{top}")
    return "\n".join(lines)


def _format_month_report(data_dir: Path, anchor: date) -> str:
    start, end = _month_bounds(anchor)
    events = _load_event_items(data_dir, start, end)
    aggregate = _aggregate_events(events)

    lines = [f"{anchor.year} 年 {anchor.month} 月活动月报", "", f"总记录时长：{_format_minutes(aggregate.total_minutes)}", ""]
    lines.append("一级分类时间占比：")
    lines.extend(_format_share_lines(aggregate.primary_totals, aggregate.total_minutes))
    lines.append(f"未知时间占比：{_format_minutes(aggregate.unknown_minutes)}，{_format_percent(aggregate.unknown_minutes, aggregate.total_minutes)}")
    lines.append("")
    lines.append("Top 活动：")
    lines.extend(
        [
            f"{index + 1}. {name}：{_format_minutes(minutes)}"
            for index, (name, minutes) in enumerate(aggregate.secondary_totals.most_common(5))
        ]
        or ["暂无记录。"]
    )
    lines.append("")
    lines.append("每周趋势：")
    if not aggregate.weekly_totals:
        lines.append("暂无记录。")
    else:
        week_starts = sorted(aggregate.weekly_totals)
        for week_start in week_starts:
            week_end = week_start + timedelta(days=6)
            total = aggregate.weekly_totals.get(week_start, 0)
            top = _top_name(aggregate.weekly_primary.get(week_start, Counter()))
            lines.append(
                f"{week_start.isoformat()} 至 {week_end.isoformat()}：{_format_minutes(total)}，主要活动：{top}"
            )
    return "\n".join(lines)


def _format_rolling_report(data_dir: Path, anchor: date, days: int) -> str:
    start, end = _rolling_bounds(anchor, days)
    events = _load_event_items(data_dir, start, end)
    aggregate = _aggregate_events(events)

    lines = [
        f"{start.isoformat()} 至 {end.isoformat()} 近 {days} 天活动统计",
        "",
        f"总记录时长：{_format_minutes(aggregate.total_minutes)}",
        "",
    ]
    lines.append("一级分类时间占比：")
    lines.extend(_format_share_lines(aggregate.primary_totals, aggregate.total_minutes))
    lines.append(f"未知时间占比：{_format_minutes(aggregate.unknown_minutes)}，{_format_percent(aggregate.unknown_minutes, aggregate.total_minutes)}")
    lines.append("")
    lines.append("Top 活动：")
    lines.extend(
        [
            f"{index + 1}. {name}：{_format_minutes(minutes)}"
            for index, (name, minutes) in enumerate(aggregate.secondary_totals.most_common(5))
        ]
        or ["暂无记录。"]
    )
    lines.append("")
    lines.append("每日趋势：")
    if not aggregate.daily_totals:
        lines.append("暂无记录。")
    else:
        for current in _iter_dates(start, end):
            total = aggregate.daily_totals.get(current, 0)
            top = _top_name(aggregate.daily_primary.get(current, Counter()))
            lines.append(f"{current.isoformat()}：{_format_minutes(total)}，主要活动：{top}")
    return "\n".join(lines)


def render_report_text(data_dir: Path, anchor_date: date, period: str) -> str:
    period = period.lower().strip()
    if period == "day":
        return _format_day_report(data_dir, anchor_date)
    if period == "week":
        return _format_week_report(data_dir, anchor_date)
    if period == "month":
        return _format_month_report(data_dir, anchor_date)
    if period == "last7":
        return _format_rolling_report(data_dir, anchor_date, 7)
    if period == "last30":
        return _format_rolling_report(data_dir, anchor_date, 30)
    raise ValueError(f"Unsupported period: {period}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate activity reports.")
    parser.add_argument("date", nargs="?", default=date.today().isoformat(), help="Anchor date in YYYY-MM-DD format.")
    parser.add_argument("--period", choices=["day", "week", "month", "last7", "last30"], default="day")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args(argv)

    anchor = _parse_date(args.date)
    text = render_report_text(Path(args.data_dir), anchor, args.period)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
