"""Offline Dictation Mode for JARVIS (Stage O5).

When dictation mode is activated, speech is transcribed 100% locally via
faster-whisper and typed directly into whichever application window currently has focus.
"""
from __future__ import annotations

import asyncio
from typing import Any, ClassVar, Literal, Optional, Type

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult

log = get_logger("tools.dictation")

# Global dictation active flag
_DICTATION_ACTIVE = False


def is_dictation_active() -> bool:
    return _DICTATION_ACTIVE


def set_dictation_active(active: bool) -> None:
    global _DICTATION_ACTIVE
    _DICTATION_ACTIVE = active


def type_text_into_focused_window(text: str) -> bool:
    """Simulate keyboard typing into active focused window."""
    if not text:
        return False
    try:
        import pyautogui
        pyautogui.write(text + " ", interval=0.01)
        return True
    except Exception:
        try:
            import keyboard
            keyboard.write(text + " ")
            return True
        except Exception as exc:
            log.debug("could not simulate keyboard: %s", exc)
            return False


class DictationArgs(BaseModel):
    action: Literal["on", "off", "status", "type_text"] = Field(
        default="status", description="Action: on, off, status, type_text"
    )
    text: Optional[str] = Field(default=None, description="Text to type if action is type_text")


class DictationTool(BaseTool):
    name: ClassVar[str] = "dictation"
    description: ClassVar[str] = (
        "Offline speech dictation: 'dictation on' types speech into any focused application, "
        "'dictation off' returns to normal assistant mode."
    )
    args_model: ClassVar[Type[BaseModel]] = DictationArgs
    category: ClassVar[str] = "system"
    risk: ClassVar[RiskLevel] = RiskLevel.LOW
    destructive: ClassVar[bool] = False
    offline: ClassVar[bool] = True

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        action = args.get("action", "status")

        if action == "on":
            set_dictation_active(True)
            return ToolResult(
                True,
                "✓ Dictation mode ON. Speak naturally — your speech will be typed into the active window. Say 'dictation off' to exit.",
                data={"active": True},
                verified=True,
            )

        elif action == "off":
            set_dictation_active(False)
            return ToolResult(
                True,
                "✓ Dictation mode OFF. Normal voice assistant mode resumed.",
                data={"active": False},
                verified=True,
            )

        elif action == "type_text":
            text = args.get("text", "")
            typed = await asyncio.to_thread(type_text_into_focused_window, text)
            return ToolResult(
                typed,
                f"Typed {len(text)} characters." if typed else "Could not type text.",
                data={"typed": typed, "length": len(text)},
                verified=typed,
            )

        # status
        active = is_dictation_active()
        return ToolResult(
            True,
            f"Dictation mode is currently {'ACTIVE' if active else 'INACTIVE'}.",
            data={"active": active},
            verified=True,
        )
