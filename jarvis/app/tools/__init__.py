from app.tools.base import BaseTool, ToolContext, ToolResult
from app.tools.manager import ToolManager

__all__ = ["BaseTool", "ToolContext", "ToolResult", "ToolManager"]


def build_tool_manager(settings, permissions, bus, session_factory) -> ToolManager:
    """Register all built-in tools (respecting tools.disabled config)."""
    from app.tools.builtin.screenshot import register_all
    manager = ToolManager(settings, permissions, bus, session_factory)
    register_all(manager)
    return manager
