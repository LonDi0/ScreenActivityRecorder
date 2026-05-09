from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_BASE_URL = "https://apiport.cc.cd/v1"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_MERGE_GAP_SECONDS = 180
DEFAULT_SCREENSHOT_MAX_WIDTH = 1280
DEFAULT_IMAGE_FORMAT = "jpeg"
DEFAULT_JPEG_QUALITY = 70


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str
    model: str
    interval_seconds: int
    merge_gap_seconds: int
    screenshot_max_width: int
    screenshot_all_screens: bool
    image_format: str
    jpeg_quality: int
    data_dir: Path

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized == "https://apiport.cc.cd":
        return "https://apiport.cc.cd/v1"
    return normalized


def _select_model(base_url: str) -> str:
    model = os.getenv("SCREEN_AGENT_MODEL") or os.getenv("MODEL_ID") or DEFAULT_MODEL
    fallback_model = os.getenv("MODEL_ID") or DEFAULT_MODEL
    if base_url == "https://apiport.cc.cd/v1" and model == "gpt-4o-mini":
        return fallback_model
    return model


def load_settings(project_root: Path | None = None) -> Settings:
    root = project_root or Path.cwd()
    load_dotenv(root / ".env")

    data_dir = Path(os.getenv("SCREEN_AGENT_DATA_DIR", root / "data"))
    base_url = _normalize_base_url(
        os.getenv("SCREEN_AGENT_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or DEFAULT_BASE_URL
    )
    model = _select_model(base_url)
    image_format = (os.getenv("SCREEN_AGENT_IMAGE_FORMAT") or DEFAULT_IMAGE_FORMAT).strip().lower()
    if image_format not in {"jpeg", "png"}:
        image_format = DEFAULT_IMAGE_FORMAT

    return Settings(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=base_url,
        model=model,
        interval_seconds=_int_env("SCREEN_AGENT_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS),
        merge_gap_seconds=_int_env("SCREEN_AGENT_MERGE_GAP_SECONDS", DEFAULT_MERGE_GAP_SECONDS),
        screenshot_max_width=_int_env("SCREEN_AGENT_SCREENSHOT_MAX_WIDTH", DEFAULT_SCREENSHOT_MAX_WIDTH),
        screenshot_all_screens=_bool_env("SCREEN_AGENT_ALL_SCREENS", False),
        image_format=image_format,
        jpeg_quality=min(max(_int_env("SCREEN_AGENT_JPEG_QUALITY", DEFAULT_JPEG_QUALITY), 1), 95),
        data_dir=data_dir,
    )
