from __future__ import annotations

from openai import BadRequestError, OpenAI

from screen_activity_agent.config import Settings
from screen_activity_agent.jsonutil import parse_json_object
from screen_activity_agent.models import ActivityRecord
from screen_activity_agent.prompts import build_system_prompt, build_user_prompt


class VisionClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.has_api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.api_timeout_seconds,
            max_retries=0,
        )

    def analyze(
        self,
        *,
        image_data_url: str,
        timestamp: str,
        recent_records: list[dict],
    ) -> ActivityRecord:
        messages = [
                {"role": "system", "content": build_system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": build_user_prompt(timestamp, recent_records)},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ]
        try:
            response = self.client.chat.completions.create(
                model=self.settings.model,
                response_format={"type": "json_object"},
                messages=messages,
            )
        except BadRequestError:
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
            )
        content = response.choices[0].message.content or "{}"
        data = parse_json_object(content)
        return ActivityRecord.from_model_json(
            data,
            timestamp,
            privacy_protection_enabled=self.settings.privacy_protection_enabled,
            sensitive_content_filter_enabled=self.settings.sensitive_content_filter_enabled,
        )
