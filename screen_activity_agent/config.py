from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

if sys.platform == "win32":
    import winreg


DEFAULT_BASE_URL = "https://apiport.cc.cd/v1"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_MERGE_GAP_SECONDS = 180
DEFAULT_SCREENSHOT_MAX_WIDTH = 1280
DEFAULT_IMAGE_FORMAT = "jpeg"
DEFAULT_JPEG_QUALITY = 70
PROFILES_FILE = "api_profiles.json"
AUTOSTART_REGISTRY_NAME = "ScreenActivityAgent"


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
    save_raw_screenshot: bool
    privacy_protection_enabled: bool
    sensitive_content_filter_enabled: bool
    autostart_enabled: bool
    env_path: Path
    has_base_url_config: bool
    has_model_config: bool

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    @property
    def is_complete(self) -> bool:
        return self.has_api_key and self.has_base_url_config and self.has_model_config


@dataclass(frozen=True)
class ApiProfile:
    name: str
    api_key: str
    base_url: str
    model: str


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def find_env_path(root: Path) -> Path:
    candidates: list[Path] = []
    for base in (root, Path.cwd()):
        resolved = base.resolve()
        candidates.append(resolved / ".env")
        candidates.extend(parent / ".env" for parent in resolved.parents)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    return root / ".env"


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


def _resolve_path(value: str | None, root: Path) -> Path:
    if not value:
        return root
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _read_windows_autostart_state() -> bool:
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            winreg.QueryValueEx(key, AUTOSTART_REGISTRY_NAME)
            return True
    except OSError:
        return False


def _autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    root = app_root().resolve()
    python = Path(sys.executable).resolve()
    return f'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath \'{root}\'; & \'{python}\' -m screen_activity_agent.gui"'


def set_windows_autostart(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, AUTOSTART_REGISTRY_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, AUTOSTART_REGISTRY_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass


def load_settings(project_root: Path | None = None) -> Settings:
    root = project_root or app_root()
    env_path = find_env_path(root)
    load_dotenv(env_path, override=True)

    data_root = env_path.parent if env_path.exists() else root
    data_dir = _resolve_path(os.getenv("SCREEN_AGENT_DATA_DIR"), data_root / "data")
    base_url_raw = os.getenv("SCREEN_AGENT_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model_raw = os.getenv("SCREEN_AGENT_MODEL") or os.getenv("MODEL_ID")
    base_url = _normalize_base_url(
        base_url_raw
        or DEFAULT_BASE_URL
    )
    model = _select_model(base_url)
    image_format = (os.getenv("SCREEN_AGENT_IMAGE_FORMAT") or DEFAULT_IMAGE_FORMAT).strip().lower()
    if image_format not in {"jpeg", "png"}:
        image_format = DEFAULT_IMAGE_FORMAT
    autostart_enabled = _bool_env("SCREEN_AGENT_AUTOSTART", False) or _read_windows_autostart_state()

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
        save_raw_screenshot=_bool_env("SCREEN_AGENT_SAVE_RAW_SCREENSHOT", False),
        privacy_protection_enabled=_bool_env("SCREEN_AGENT_PRIVACY_PROTECTION", True),
        sensitive_content_filter_enabled=_bool_env("SCREEN_AGENT_SENSITIVE_CONTENT_FILTER", True),
        autostart_enabled=autostart_enabled,
        env_path=env_path,
        has_base_url_config=bool(base_url_raw and base_url_raw.strip()),
        has_model_config=bool(model_raw and model_raw.strip()),
    )


def save_settings_to_env(
    *,
    env_path: Path,
    api_key: str,
    base_url: str,
    model: str,
    interval_seconds: int,
    data_dir: str | Path,
    save_raw_screenshot: bool,
    privacy_protection_enabled: bool,
    sensitive_content_filter_enabled: bool,
    autostart_enabled: bool,
) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    order: list[str] = []

    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key:
                existing[key] = value.strip()
                order.append(key)

    updates = {
        "OPENAI_API_KEY": api_key.strip(),
        "SCREEN_AGENT_BASE_URL": _normalize_base_url(base_url),
        "SCREEN_AGENT_MODEL": model.strip(),
        "SCREEN_AGENT_INTERVAL_SECONDS": str(max(1, int(interval_seconds))),
        "SCREEN_AGENT_DATA_DIR": str(data_dir),
        "SCREEN_AGENT_SAVE_RAW_SCREENSHOT": "true" if save_raw_screenshot else "false",
        "SCREEN_AGENT_PRIVACY_PROTECTION": "true" if privacy_protection_enabled else "false",
        "SCREEN_AGENT_SENSITIVE_CONTENT_FILTER": "true" if sensitive_content_filter_enabled else "false",
        "SCREEN_AGENT_AUTOSTART": "true" if autostart_enabled else "false",
    }
    existing.update(updates)

    for key in updates:
        if key not in order:
            order.append(key)

    env_path.write_text(
        "\n".join(f"{key}={existing[key]}" for key in order if key in existing) + "\n",
        encoding="utf-8",
    )
    set_windows_autostart(autostart_enabled)


def profiles_path_for(env_path: Path) -> Path:
    return env_path.parent / PROFILES_FILE


def load_api_profiles(env_path: Path) -> tuple[list[ApiProfile], str | None]:
    path = profiles_path_for(env_path)
    if not path.exists():
        return [], None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], None
    if not isinstance(raw, dict):
        return [], None

    profiles = []
    for item in raw.get("profiles", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        api_key = str(item.get("api_key", "")).strip()
        base_url = str(item.get("base_url", "")).strip()
        model = str(item.get("model", "")).strip()
        if name and api_key and base_url and model:
            profiles.append(ApiProfile(name=name, api_key=api_key, base_url=_normalize_base_url(base_url), model=model))

    active = raw.get("active")
    return profiles, str(active).strip() if active else None


def save_api_profiles(env_path: Path, profiles: list[ApiProfile], active: str | None) -> None:
    path = profiles_path_for(env_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "active": active,
        "profiles": [
            {
                "name": profile.name,
                "api_key": profile.api_key,
                "base_url": _normalize_base_url(profile.base_url),
                "model": profile.model,
            }
            for profile in profiles
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_api_profile(env_path: Path, profile: ApiProfile, *, make_active: bool) -> None:
    profiles, active = load_api_profiles(env_path)
    next_profiles = [item for item in profiles if item.name != profile.name]
    next_profiles.append(profile)
    next_profiles.sort(key=lambda item: item.name.lower())
    save_api_profiles(env_path, next_profiles, profile.name if make_active else active)


def delete_api_profile(env_path: Path, name: str) -> None:
    profiles, active = load_api_profiles(env_path)
    next_profiles = [item for item in profiles if item.name != name]
    next_active = None if active == name else active
    save_api_profiles(env_path, next_profiles, next_active)
