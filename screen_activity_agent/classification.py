from __future__ import annotations

from dataclasses import dataclass


PRIMARY_CATEGORIES = [
    "工作",
    "学习",
    "编程",
    "写作",
    "阅读",
    "沟通",
    "会议",
    "娱乐",
    "游戏",
    "音乐",
    "购物",
    "生活事务",
    "系统操作",
    "空闲",
    "未知",
]

VIDEO_CONTENT_MAP = {
    "编程": "学习",
    "语言": "学习",
    "课程": "学习",
    "论文": "学习",
    "考试": "学习",
    "培训": "工作",
    "会议": "会议",
    "演示": "工作",
    "动画": "娱乐",
    "电影": "娱乐",
    "综艺": "娱乐",
    "直播": "娱乐",
    "实况": "娱乐",
    "音乐": "音乐",
    "演唱会": "音乐",
    "mv": "音乐",
}

UNKNOWN_PRIMARY = "未知"
SENSITIVE_PRIMARY = "隐私内容"
SENSITIVE_SECONDARY = "敏感页面"
SENSITIVE_EVENT = "用户正在查看包含敏感信息的页面"


@dataclass(frozen=True)
class NormalizedCategory:
    primary: str
    secondary: str
    tertiary: str = ""

    def to_list(self) -> list[str]:
        items = [self.primary, self.secondary]
        if self.tertiary:
            items.append(self.tertiary)
        return items


def normalize_primary_category(value: str | None) -> str:
    if not value:
        return UNKNOWN_PRIMARY
    candidate = str(value).strip()
    if candidate in PRIMARY_CATEGORIES:
        return candidate
    for allowed in PRIMARY_CATEGORIES:
        if allowed in candidate:
            return allowed
    return UNKNOWN_PRIMARY


def normalize_category(raw: list[str] | tuple[str, ...] | None) -> NormalizedCategory:
    if not raw:
        return NormalizedCategory(UNKNOWN_PRIMARY, UNKNOWN_PRIMARY)

    items = [str(item).strip() for item in raw if str(item).strip()]
    if not items:
        return NormalizedCategory(UNKNOWN_PRIMARY, UNKNOWN_PRIMARY)

    primary = normalize_primary_category(items[0])
    secondary = items[1] if len(items) > 1 and items[1] else UNKNOWN_PRIMARY
    tertiary = items[2] if len(items) > 2 else ""
    if primary == UNKNOWN_PRIMARY and secondary == "视频":
        secondary = UNKNOWN_PRIMARY
    return NormalizedCategory(primary=primary, secondary=secondary or UNKNOWN_PRIMARY, tertiary=tertiary)


def classify_video_content(text: str) -> str:
    lowered = text.lower()
    for keyword, category in VIDEO_CONTENT_MAP.items():
        if keyword.lower() in lowered:
            return category
    return UNKNOWN_PRIMARY


def is_sensitive_primary(primary: str) -> bool:
    return primary == SENSITIVE_PRIMARY
