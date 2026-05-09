from __future__ import annotations

from collections import deque
from typing import Any

from screen_activity_agent.config import Settings
from screen_activity_agent.models import ActivityRecord
from screen_activity_agent.screenshot import capture_data_url
from screen_activity_agent.storage import ActivityStorage
from screen_activity_agent.timeutil import now_local
from screen_activity_agent.vision_client import VisionClient


class ScreenActivityAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = ActivityStorage(settings.data_dir, settings.merge_gap_seconds)
        self.memory: deque[dict[str, Any]] = deque(maxlen=5)

    def analyze_once(self) -> ActivityRecord:
        if not self.settings.has_api_key:
            raise ValueError("OPENAI_API_KEY 未配置。")

        timestamp = now_local().isoformat()
        image_data_url = capture_data_url(
            max_width=self.settings.screenshot_max_width,
            all_screens=self.settings.screenshot_all_screens,
            image_format=self.settings.image_format,
            jpeg_quality=self.settings.jpeg_quality,
        )
        client = VisionClient(self.settings)
        record = client.analyze(
            image_data_url=image_data_url,
            timestamp=timestamp,
            recent_records=list(self.memory),
        )
        self.storage.save_record(record)
        self.memory.append(record.to_dict())
        return record
