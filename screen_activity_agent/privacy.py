from __future__ import annotations

import re
from dataclasses import dataclass

from screen_activity_agent.classification import (
    SENSITIVE_EVENT,
    SENSITIVE_PRIMARY,
    SENSITIVE_SECONDARY,
    UNKNOWN_PRIMARY,
    NormalizedCategory,
    is_sensitive_primary,
    normalize_category,
)


SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b", re.IGNORECASE),
    re.compile(r"\bapi[_-]?key\b", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"\bcookie\b", re.IGNORECASE),
    re.compile(r"\bpass(word)?\b", re.IGNORECASE),
    re.compile(r"\b验证码\b"),
    re.compile(r"\b身份证\b"),
    re.compile(r"\b银行卡\b"),
    re.compile(r"\b住址\b"),
    re.compile(r"\b医疗\b"),
]


@dataclass(frozen=True)
class PrivacyOutcome:
    category: NormalizedCategory
    app: str
    window_title: str
    screen_content: str
    event: str
    privacy_risk: bool


def _sanitize_text(value: str | None) -> str:
    if not value:
        return "未知"
    text = str(value).strip()
    if not text:
        return "未知"
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        return "敏感信息"
    return text


def detect_privacy_risk(*parts: str | None) -> bool:
    for part in parts:
        if not part:
            continue
        text = str(part)
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            return True
    return False


def sanitize_record_fields(
    *,
    app: str | None,
    window_title: str | None,
    screen_content: str | None,
    event: str | None,
    category: list[str] | tuple[str, ...] | None,
    privacy_risk: bool,
) -> PrivacyOutcome:
    normalized_category = normalize_category(list(category) if category else None)
    detected_risk = privacy_risk or detect_privacy_risk(app, window_title, screen_content, event)

    if detected_risk or is_sensitive_primary(normalized_category.primary):
        return PrivacyOutcome(
            category=NormalizedCategory(SENSITIVE_PRIMARY, SENSITIVE_SECONDARY),
            app="敏感页面",
            window_title="敏感页面",
            screen_content="用户正在查看包含敏感信息的页面",
            event=SENSITIVE_EVENT,
            privacy_risk=True,
        )

    return PrivacyOutcome(
        category=normalized_category,
        app=_sanitize_text(app),
        window_title=_sanitize_text(window_title),
        screen_content=_sanitize_text(screen_content),
        event=_sanitize_text(event),
        privacy_risk=False,
    )
