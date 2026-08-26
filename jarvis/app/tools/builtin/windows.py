"""Built-in tool for managing desktop windows on Windows (Spec Phase 5+).

Provides:
- ManageWindowTool: Semantic focus, minimize, maximize, restore, move, resize, close, list.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.computer.window_manager import WindowManager
from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult


class ManageWindowArgs(BaseModel):
    action: Literal["focus", "minimize", "maximize", "restore", "move", "resize", "close", "list"] = Field(
        description="Window operation to perform",
    )
    title: Optional[str] = Field(
        default=None,
        description="Title or process name of the target window (e.g. 'Chrome', 'Notepad', 'VS Code')",
    )
    x: Optional[int] = Field(default=0, description="New X coordinate for move/resize")
    y: Optional[int] = Field(default=0, description="New Y coordinate for move/resize")
    width: Optional[int] = Field(default=1024, description="New width for move/resize")
    height: Optional[int] = Field(default=768, description="New height for move/resize")


class ManageWindowTool(BaseTool):
    name = "manage_window"
    description = (
        "Focus, minimize, maximize, restore, move, resize, close, or list open application "
        "windows on the Windows desktop by their semantic title or process name."
    )
    args_model = ManageWindowArgs
    category = "computer"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        action = args.get("action", "list")
        title = args.get("title")

        if action == "list":
            windows = WindowManager.list_windows(visible_only=True)
            if not windows:
                return ToolResult(True, "No visible top-level windows detected.", data={"windows": []}, verified=True)

            lines = [f"• {w.title} (Process: {w.process_name})" for w in windows[:20]]
            msg = f"Open Windows ({len(windows)}):\n" + "\n".join(lines)
            data = [{"title": w.title, "process": w.process_name, "hwnd": w.hwnd} for w in windows]
            return ToolResult(True, msg, data={"windows": data}, verified=True)

        if not title:
            return ToolResult(False, f"Action '{action}' requires a target window 'title'.")

        if action == "focus":
            ok, msg = WindowManager.focus(title)
            return ToolResult(ok, msg, verified=ok)

        if action == "minimize":
            ok, msg = WindowManager.minimize(title)
            return ToolResult(ok, msg, verified=ok)

        if action == "maximize":
            ok, msg = WindowManager.maximize(title)
            return ToolResult(ok, msg, verified=ok)

        if action == "restore":
            ok, msg = WindowManager.restore(title)
            return ToolResult(ok, msg, verified=ok)

        if action in ("move", "resize"):
            x = int(args.get("x", 0))
            y = int(args.get("y", 0))
            w = int(args.get("width", 1024))
            h = int(args.get("height", 768))
            ok, msg = WindowManager.move_resize(title, x, y, w, h)
            return ToolResult(ok, msg, verified=ok)

        if action == "close":
            ok, msg = WindowManager.close(title)
            return ToolResult(ok, msg, verified=ok)

        return ToolResult(False, f"Unknown window action: '{action}'.")
