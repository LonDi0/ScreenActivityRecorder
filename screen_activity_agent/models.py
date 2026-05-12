from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from screen_activity_agent.classification import UNKNOWN_PRIMARY, normalize_category
from screen_activity_agent.privacy import sanitize_record_fields


@dataclass(frozen=True)
class ActivityRecord:
    timestamp: str
    app: str
    window_title: str
    screen_content: str
    category: list[str]
    event: str
    is_continuation: bool
    confidence: float
    privacy_risk: bool

    @classmethod
    def failure_record(cls, *, timestamp: str, stage: str) -> "ActivityRecord":
        failure_stage = stage.strip() or "API 访问失败"
        return cls(
            timestamp=timestamp,
            app=UNKNOWN_PRIMARY,
            window_title=UNKNOWN_PRIMARY,
            screen_content=f"{failure_stage}，等待重试",
            category=[UNKNOWN_PRIMARY, failure_stage],
            event=failure_stage,
            is_continuation=True,
            confidence=0.0,
            privacy_risk=False,
        )

    @classmethod
    def from_model_json(
        cls,
        data: dict[str, Any],
        fallback_timestamp: str,
        *,
        privacy_protection_enabled: bool = True,
        sensitive_content_filter_enabled: bool = True,
    ) -> "ActivityRecord":
        raw_category = data.get("category")
        category = raw_category if isinstance(raw_category, list) else None
        normalized = normalize_category(category)

        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(max(confidence, 0.0), 1.0)

        privacy_risk = bool(data.get("privacy_risk", False))
        if privacy_protection_enabled or sensitive_content_filter_enabled:
            sanitized = sanitize_record_fields(
                app=data.get("app"),
                window_title=data.get("window_title"),
                screen_content=data.get("screen_content"),
                event=data.get("event"),
                category=normalized.to_list(),
                privacy_risk=privacy_risk if sensitive_content_filter_enabled else False,
            )
            app = sanitized.app
            window_title = sanitized.window_title
            screen_content = sanitized.screen_content
            event = sanitized.event
            category_list = sanitized.category.to_list()
            privacy_risk = sanitized.privacy_risk
        else:
            app = str(data.get("app") or "未知")
            window_title = str(data.get("window_title") or "未知")
            screen_content = str(data.get("screen_content") or "未知")
            event = str(data.get("event") or "未知活动")
            category_list = normalized.to_list()

        return cls(
            timestamp=str(data.get("timestamp") or fallback_timestamp),
            app=app,
            window_title=window_title,
            screen_content=screen_content,
            category=category_list,
            event=event,
            is_continuation=bool(data.get("is_continuation", False)),
            confidence=confidence,
            privacy_risk=privacy_risk,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "app": self.app,
            "window_title": self.window_title,
            "screen_content": self.screen_content,
            "category": self.category,
            "event": self.event,
            "is_continuation": self.is_continuation,
            "confidence": self.confidence,
            "privacy_risk": self.privacy_risk,
        }
