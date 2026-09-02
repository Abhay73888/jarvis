"""Screenshot tool (Spec §54) — real capture via mss when available.

Honest failure: if the optional dependency or a display isn't available, the
tool says so instead of pretending (§61). OCR + vision reasoning land in
Phase 8 (docs/ROADMAP.md).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from app.core.exceptions import ToolError
from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult


class _ScreenshotArgs(BaseModel):
    pass


class ScreenshotTool(BaseTool):
    name = "screenshot"
    description = "Capture the screen to data/screenshots/ and return the file path. Requires the 'mss' package and a display."
    args_model = _ScreenshotArgs
    category = "diagnostics"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        from importlib.util import find_spec
        if find_spec("mss") is None:
            raise ToolError(
                "Screen capture needs the 'mss' package (requirements-windows.txt).",
                detail="mss not installed")

        import asyncio

        from app.utils.paths import get_paths

        def _capture() -> Path:
            import mss
            target_dir = get_paths().screenshots
            target_dir.mkdir(parents=True, exist_ok=True)
            out = target_dir / f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with mss.mss() as sct:
                sct.shot(mon=-1, output=str(out))
            return out

        try:
            path = await asyncio.to_thread(_capture)
        except Exception as exc:
            raise ToolError("I couldn't capture the screen on this machine.", detail=str(exc)) from exc
        return ToolResult(True, f"Screenshot saved: {path.name}.",
                          data={"path": str(path)}, verified=path.exists())


def register_all(registry) -> None:  # pragma: no cover — wiring helper
    from app.tools.builtin.apps import CloseApplicationTool, OpenApplicationTool
    from app.tools.builtin.browser import register_browser_tools
    from app.tools.builtin.files import (
        CompressTool,
        CopyFileTool,
        CreateFileTool,
        CreateFolderTool,
        DeleteFileTool,
        ExtractTool,
        ListDirTool,
        MoveFileTool,
        OpenPathTool,
        ReadFileTool,
        SearchFilesTool,
    )
    from app.tools.builtin.memory_tools import (
        ListTasksTool,
        RecallTool,
        RememberTool,
        SetReminderTool,
    )
    from app.tools.builtin.system import KillProcessTool, ProcessListTool, SystemInfoTool
    from app.tools.builtin.terminal import RunPythonTool, TerminalExecuteTool
    from app.tools.builtin.web import FetchUrlTool, OpenUrlTool, WebSearchTool
    for tool in (
        SystemInfoTool(), ProcessListTool(), KillProcessTool(),
        OpenApplicationTool(), CloseApplicationTool(),
        CreateFolderTool(), CreateFileTool(), ReadFileTool(), ListDirTool(),
        MoveFileTool(), CopyFileTool(), DeleteFileTool(), SearchFilesTool(),
        CompressTool(), ExtractTool(), OpenPathTool(),
        TerminalExecuteTool(), RunPythonTool(),
        OpenUrlTool(), WebSearchTool(), FetchUrlTool(),
        ScreenshotTool(),
        RememberTool(), RecallTool(), SetReminderTool(), ListTasksTool(),
    ):
        registry.register(tool)
    register_browser_tools(registry)
