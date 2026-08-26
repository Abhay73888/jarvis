"""Optical Character Recognition (OCR) engine for JARVIS screen understanding.

Extracts on-screen English and Hindi text using pytesseract, identifies error
patterns, and sanitizes/fences all extracted text to defend against prompt injection.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Union

from PIL import Image

from app.core.logging import get_logger
from app.security.injection import fence_untrusted, sanitize_text

log = get_logger("vision.ocr")

_ERROR_KEYWORDS = re.compile(
    r"(?i)\b(\w*error|\w*exception|traceback|failed|failure|crash|fatal|"
    r"timeout|denied|invalid|warning|404|500|503)\b"
)


def is_ocr_available() -> tuple[bool, str]:
    """Check if pytesseract and the tesseract binary are available."""
    try:
        import pytesseract
        # Verify tesseract executable
        pytesseract.get_tesseract_version()
        return True, "tesseract OCR is available"
    except Exception as exc:
        return False, f"tesseract OCR unavailable: {exc}"


def extract_text_from_image(
    image_input: Union[str, Path, Image.Image],
    lang: str = "eng+hin",
    fence: bool = True,
) -> str:
    """Extract text from an image using pytesseract.
    
    Falls back gracefully to 'eng' if the Hindi language pack is missing.
    Fences output as untrusted external content.
    """
    try:
        import pytesseract
    except ImportError:
        log.warning("pytesseract is not installed")
        return ""

    if isinstance(image_input, (str, Path)):
        img = Image.open(str(image_input))
    else:
        img = image_input

    raw_text = ""
    try:
        raw_text = pytesseract.image_to_string(img, lang=lang)
    except Exception as exc:
        log.debug("tesseract lang='%s' failed (%s), falling back to 'eng'", lang, exc)
        try:
            raw_text = pytesseract.image_to_string(img, lang="eng")
        except Exception as fallback_exc:
            log.warning("tesseract OCR failed: %s", fallback_exc)
            return ""

    cleaned = sanitize_text(raw_text).strip()
    if not cleaned:
        return ""

    if fence:
        return fence_untrusted(cleaned, source="screen_ocr")
    return cleaned


def detect_errors(text: str) -> list[str]:
    """Identify error signatures and lines containing stack traces or failures."""
    if not text:
        return []
    
    error_lines = []
    for line in text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        if _ERROR_KEYWORDS.search(line_clean):
            error_lines.append(line_clean)
    return error_lines
