from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    def from_model_json(cls, data: dict[str, Any], fallback_timestamp: str) -> "ActivityRecord":
        category = data.get("category")
        if not isinstance(category, list):
            category = ["未知", "未知"]
        category = [str(item).strip() for item in category if str(item).strip()]
        if not category:
            category = ["未知", "未知"]
        if len(category) == 1:
            category.append("未知")

        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(max(confidence, 0.0), 1.0)

        return cls(
            timestamp=str(data.get("timestamp") or fallback_timestamp),
            app=str(data.get("app") or "未知"),
            window_title=str(data.get("window_title") or "未知"),
            screen_content=str(data.get("screen_content") or "未知"),
            category=category[:3],
            event=str(data.get("event") or "未知活动"),
            is_continuation=bool(data.get("is_continuation", False)),
            confidence=confidence,
            privacy_risk=bool(data.get("privacy_risk", False)),
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
