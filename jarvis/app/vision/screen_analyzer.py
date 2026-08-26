"""Multimodal Screen Analyzer for JARVIS (Spec Phase 8).

Combines:
1. Screen Capture via mss / Pillow
2. Optical Character Recognition (pytesseract)
3. Multimodal Vision Reasoning (Gemini Vision)
4. Honest heuristics fallback for offline mode
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

from PIL import Image

from app.brain.provider import ChatMessage
from app.brain.router import ModelRouter
from app.core.exceptions import ToolError
from app.core.logging import get_logger
from app.utils.paths import get_paths
from app.vision.ocr import detect_errors, extract_text_from_image, is_ocr_available

log = get_logger("vision.analyzer")


class ScreenAnalyzer:
    """Performs visual analysis and error diagnosis on user's active screen."""

    def __init__(self, router: Optional[ModelRouter] = None) -> None:
        self.router = router

    @staticmethod
    def capture_screen() -> Path:
        """Capture the current primary screen to disk."""
        from datetime import datetime
        target_dir = get_paths().screenshots
        target_dir.mkdir(parents=True, exist_ok=True)
        out = target_dir / f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        try:
            import mss
            with mss.mss() as sct:
                sct.shot(mon=-1, output=str(out))
            return out
        except Exception:
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                img.save(str(out))
                return out
            except Exception as exc:
                raise ToolError("Screen capture failed — no display available.", detail=str(exc)) from exc

    async def analyze_screen(
        self,
        image_path: Optional[Union[str, Path]] = None,
        user_query: str = "Explain what is on the screen and diagnose any visible errors.",
    ) -> dict[str, str]:
        """Perform OCR and AI Vision diagnosis on the screen."""
        if image_path is None:
            image_path = self.capture_screen()
        else:
            image_path = Path(image_path)

        if not image_path.exists():
            raise ToolError(f"Image file does not exist: {image_path}")

        # 1. Run OCR
        img = Image.open(str(image_path))
        ocr_text = extract_text_from_image(img, lang="eng+hin", fence=False)
        detected_errors = detect_errors(ocr_text)

        # 2. Check if Vision Model is available
        vision_provider = self.router.provider_for_role("vision") if self.router else None

        if vision_provider is not None:
            # Encode image to Base64 JPEG
            buf = BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            prompt = (
                f"You are JARVIS analyzing the user's active screen.\n"
                f"User question: {user_query}\n\n"
                f"Extracted Screen Text (OCR):\n{ocr_text[:2000]}\n\n"
                f"Instructions:\n"
                f"1. Explain what application or window is visible on the screen.\n"
                f"2. If an error, stack trace, or warning is visible, explain what caused it in simple, clear words (English/Hindi as appropriate).\n"
                f"3. Propose a concrete and safe fix or next step.\n"
                f"4. Keep the response concise and helpful."
            )

            msg = ChatMessage(
                role="user",
                content=prompt,
                images=[(img_b64, "image/jpeg")],
            )

            try:
                resp = await vision_provider.chat([msg], temperature=0.2)
                return {
                    "image_path": str(image_path),
                    "ocr_text": ocr_text,
                    "explanation": resp.content,
                    "errors_found": ", ".join(detected_errors) if detected_errors else "None",
                }
            except Exception as exc:
                log.warning("Vision LLM call failed, falling back to local OCR analysis: %s", exc)

        # Heuristic offline fallback explanation
        if detected_errors:
            explanation = (
                f"I detected the following error on your screen:\n\n"
                f"• " + "\n• ".join(detected_errors[:4]) + "\n\n"
                f"Please review the error message. If you would like me to help resolve it, let me know."
            )
        elif ocr_text:
            snippet = ocr_text[:300].replace("\n", " ")
            explanation = f"Screen contents extracted via OCR:\n\"{snippet}...\""
        else:
            explanation = "I captured your screen, but no clear text or error messages were detected."

        return {
            "image_path": str(image_path),
            "ocr_text": ocr_text,
            "explanation": explanation,
            "errors_found": ", ".join(detected_errors) if detected_errors else "None",
        }
