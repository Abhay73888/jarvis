"""Unit tests for Stage 3 Screen Vision, OCR, and Multimodal error diagnosis.

Tests image OCR extraction, error detection, untrusted fencing, and tool integration.
"""
from io import BytesIO
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock
from PIL import Image, ImageDraw

from app.brain.intent import IntentRouter
from app.brain.provider import ChatMessage, ChatResponse
from app.security.injection import FENCE_HEADER, FENCE_FOOTER
from app.tools.base import ToolContext
from app.tools.builtin.vision import AnalyzeScreenTool, ReadScreenTool
from app.vision.ocr import detect_errors, extract_text_from_image, is_ocr_available
from app.vision.screen_analyzer import ScreenAnalyzer


def _create_synthetic_error_image() -> Image.Image:
    """Create a synthetic test image containing an error traceback."""
    img = Image.new("RGB", (500, 150), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)
    text = "Traceback (most recent call last):\n  File 'app.py', line 12\nModuleNotFoundError: No module named 'requests'"
    draw.text((10, 10), text, fill=(255, 100, 100))
    return img


def test_detect_errors():
    sample_text = (
        "Starting application...\n"
        "Loading settings from config.yaml\n"
        "ERROR: Failed to connect to database at localhost:5432\n"
        "Traceback (most recent call last):\n"
        "ConnectionRefusedError: [Errno 111] Connection refused\n"
    )
    errors = detect_errors(sample_text)
    assert len(errors) >= 2
    assert any("ERROR" in e for e in errors)
    assert any("ConnectionRefusedError" in e for e in errors)


def test_ocr_availability_check():
    avail, msg = is_ocr_available()
    assert isinstance(avail, bool)
    assert isinstance(msg, str)


def test_ocr_untrusted_fencing():
    img = _create_synthetic_error_image()
    # Test text extraction with fencing
    fenced = extract_text_from_image(img, fence=True)
    if fenced:  # If tesseract binary is installed on machine
        assert FENCE_HEADER in fenced
        assert FENCE_FOOTER in fenced


@pytest.mark.asyncio
async def test_screen_analyzer_offline_flow(tmp_path):
    img = _create_synthetic_error_image()
    test_img_path = tmp_path / "test_error_screen.png"
    img.save(str(test_img_path))

    # Without router (offline mode)
    analyzer = ScreenAnalyzer(router=None)
    res = await analyzer.analyze_screen(image_path=test_img_path, user_query="ye error samjhao")

    assert "image_path" in res
    assert "explanation" in res
    assert isinstance(res["explanation"], str)


@pytest.mark.asyncio
async def test_screen_analyzer_vision_provider_flow(tmp_path):
    img = _create_synthetic_error_image()
    test_img_path = tmp_path / "test_error_screen.png"
    img.save(str(test_img_path))

    # Mock Vision LLM provider
    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(
        return_value=ChatResponse(
            content="The screen shows a Python ModuleNotFoundError. You need to install 'requests' by running pip install requests."
        )
    )

    mock_router = MagicMock()
    mock_router.provider_for_role.return_value = mock_provider

    analyzer = ScreenAnalyzer(router=mock_router)
    res = await analyzer.analyze_screen(image_path=test_img_path, user_query="ye error samjhao")

    assert "ModuleNotFoundError" in res["explanation"] or "requests" in res["explanation"]
    mock_provider.chat.assert_called_once()
    sent_msg = mock_provider.chat.call_args[0][0][0]
    assert len(sent_msg.images) == 1
    assert sent_msg.images[0][1] == "image/jpeg"


@pytest.mark.asyncio
async def test_vision_tools_execution(tmp_path):
    img = _create_synthetic_error_image()
    test_img_path = tmp_path / "test_screen.png"
    img.save(str(test_img_path))

    ctx = ToolContext(settings=MagicMock(), workdir=tmp_path, writable_roots=[tmp_path])

    # 1. AnalyzeScreenTool
    analyze_tool = AnalyzeScreenTool()
    res = await analyze_tool.execute({"image_path": str(test_img_path), "query": "what is this error?"}, ctx)
    assert res.success is True
    assert res.verified is True

    # 2. ReadScreenTool
    read_tool = ReadScreenTool()
    res_read = await read_tool.execute({"image_path": str(test_img_path)}, ctx)
    assert res_read.success is True
    assert res_read.verified is True


def test_vision_intent_routing():
    router = IntentRouter()

    intent1 = router.parse("screen pe jo error hai samjho")
    assert intent1 is not None
    assert intent1.tool == "analyze_screen"

    intent2 = router.parse("ye error samjhao")
    assert intent2 is not None
    assert intent2.tool == "analyze_screen"

    intent3 = router.parse("screen padho")
    assert intent3 is not None
    assert intent3.tool == "read_screen"

    intent4 = router.parse("screen par kya likha hai")
    assert intent4 is not None
    assert intent4.tool == "read_screen"
