from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

from openai import OpenAI
from PIL import Image

from screen_activity_agent.config import load_settings
from screen_activity_agent.screenshot import capture_data_url, image_to_data_url


def _error_text(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {str(exc)[:500]}"


def _print_result(name: str, ok: bool, detail: str) -> None:
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")


def _tiny_image_data_url() -> str:
    image = Image.new("RGB", (64, 64), color=(245, 245, 245))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=70)
    return image_to_data_url(buffer.getvalue(), "image/jpeg")


def _chat_text(client: OpenAI, model: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Return compact JSON only."},
            {"role": "user", "content": "Return {\"ok\": true}."},
        ],
    )
    return response.choices[0].message.content or ""


def _chat_image(client: OpenAI, model: str, image_data_url: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Return compact JSON only."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image with JSON: {\"description\":\"...\"}"},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ],
    )
    return response.choices[0].message.content or ""


def main() -> int:
    settings = load_settings(Path.cwd())
    print("Screen Activity Agent diagnostics")
    print(f"base_url={settings.base_url}")
    print(f"model={settings.model}")
    print(f"api_key={'configured' if settings.has_api_key else 'missing'}")
    print(
        "capture="
        f"{settings.image_format}, max_width={settings.screenshot_max_width}, "
        f"all_screens={settings.screenshot_all_screens}"
    )

    if not settings.has_api_key:
        _print_result("api key", False, "OPENAI_API_KEY is missing")
        return 1

    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    failed = False

    try:
        text = _chat_text(client, settings.model)
        _print_result("text chat", True, text[:200])
    except Exception as exc:
        failed = True
        _print_result("text chat", False, _error_text(exc))

    try:
        text = _chat_image(client, settings.model, _tiny_image_data_url())
        _print_result("tiny image chat", True, text[:200])
    except Exception as exc:
        failed = True
        _print_result("tiny image chat", False, _error_text(exc))

    try:
        screenshot_url = capture_data_url(
            max_width=settings.screenshot_max_width,
            all_screens=settings.screenshot_all_screens,
            image_format=settings.image_format,
            jpeg_quality=settings.jpeg_quality,
        )
        print(f"screenshot_data_url_chars={len(screenshot_url)}")
        text = _chat_image(client, settings.model, screenshot_url)
        _print_result("screenshot image chat", True, text[:200])
    except Exception as exc:
        failed = True
        _print_result("screenshot image chat", False, _error_text(exc))

    print(json.dumps({"failed": failed}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
