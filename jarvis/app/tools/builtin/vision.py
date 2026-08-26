"""Built-in vision and screen understanding tools for JARVIS (Spec Phase 8).

Provides:
- AnalyzeScreenTool: Captures the screen, performs OCR, diagnoses errors, and suggests fixes.
- ReadScreenTool: Extracts on-screen text via OCR.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult
from app.vision.screen_analyzer import ScreenAnalyzer


class AnalyzeScreenArgs(BaseModel):
    query: str = Field(
        default="Explain what is on my screen and diagnose any visible errors.",
        description="Specific question or request regarding the on-screen content",
    )
    image_path: Optional[str] = Field(
        default=None,
        description="Optional path to a saved screenshot; if omitted, captures active screen",
    )


class AnalyzeScreenTool(BaseTool):
    name = "analyze_screen"
    description = (
        "Capture the screen, extract text via OCR, diagnose errors or active windows, "
        "and suggest safe remediation steps."
    )
    args_model = AnalyzeScreenArgs
    category = "vision"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        query = args.get("query") or "Explain what is on my screen and diagnose any visible errors."
        img_path = args.get("image_path")

        analyzer = ScreenAnalyzer(router=getattr(ctx, "router", None))
        res = await analyzer.analyze_screen(image_path=img_path, user_query=query)

        msg = res["explanation"]
        return ToolResult(
            success=True,
            message=msg,
            data=res,
            verified=True,
        )


class ReadScreenArgs(BaseModel):
    image_path: Optional[str] = Field(
        default=None,
        description="Optional image path; if omitted, captures current screen",
    )


class ReadScreenTool(BaseTool):
    name = "read_screen"
    description = "Extract and read all text currently visible on the user's screen using OCR."
    args_model = ReadScreenArgs
    category = "vision"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        img_path = args.get("image_path")
        analyzer = ScreenAnalyzer(router=getattr(ctx, "router", None))
        res = await analyzer.analyze_screen(
            image_path=img_path,
            user_query="Extract and return all visible text on the screen.",
        )

        ocr_text = res.get("ocr_text", "").strip()
        if not ocr_text:
            return ToolResult(
                success=True,
                message="No text was detected on the current screen.",
                data=res,
                verified=True,
            )

        return ToolResult(
            success=True,
            message=f"Screen Text Extracted:\n\n{ocr_text}",
            data=res,
            verified=True,
        )
