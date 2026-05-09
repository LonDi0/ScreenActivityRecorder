from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, ImageGrab


def _resize_for_model(image: Image.Image, max_width: int) -> Image.Image:
    if max_width <= 0 or image.width <= max_width:
        return image
    ratio = max_width / image.width
    height = max(1, int(image.height * ratio))
    return image.resize((max_width, height), Image.Resampling.LANCZOS)


def capture_image_bytes(
    *,
    max_width: int = 1280,
    all_screens: bool = False,
    image_format: str = "jpeg",
    jpeg_quality: int = 70,
) -> tuple[bytes, str]:
    try:
        image = ImageGrab.grab(all_screens=all_screens)
    except OSError:
        try:
            image = ImageGrab.grab()
        except OSError as exc:
            raise RuntimeError(
                "截图失败。请确认程序运行在 Windows 桌面会话中，而不是远程的非交互会话或受限沙箱中。"
            ) from exc
    image = _resize_for_model(image.convert("RGB"), max_width)
    buffer = BytesIO()
    if image_format.lower() == "png":
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), "image/png"
    image.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def capture_png_bytes(*, max_width: int = 1280, all_screens: bool = False) -> bytes:
    image_bytes, _mime_type = capture_image_bytes(
        max_width=max_width,
        all_screens=all_screens,
        image_format="png",
    )
    return image_bytes


def png_to_data_url(png_bytes: bytes) -> str:
    return image_to_data_url(png_bytes, "image/png")


def image_to_data_url(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def capture_data_url(
    *,
    max_width: int = 1280,
    all_screens: bool = False,
    image_format: str = "jpeg",
    jpeg_quality: int = 70,
) -> str:
    image_bytes, mime_type = capture_image_bytes(
        max_width=max_width,
        all_screens=all_screens,
        image_format=image_format,
        jpeg_quality=jpeg_quality,
    )
    return image_to_data_url(image_bytes, mime_type)
