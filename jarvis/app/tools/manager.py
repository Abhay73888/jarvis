"""Tool registry & execution pipeline.

Pipeline: validate args -> permission evaluate -> (confirm if needed) ->
execute -> publish events -> structured log (redacted) -> ToolResult.
Errors are translated to friendly messages; dev mode adds detail (Spec §42).
"""
from __future__ import annotations

import time
from typing import Any

from app.config.settings import Settings
from app.core.events import EventBus, Topics
from app.core.exceptions import ToolError
from app.core.logging import get_logger
from app.database.repo import ToolUsageRepo
from app.permissions.manager import PermissionManager, PermissionRequest
from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult

log = get_logger("tools")


class ToolManager:
    def __init__(self, settings: Settings, permissions: PermissionManager, bus: EventBus,
                 session_factory) -> None:
        self._settings = settings
        self._permissions = permissions
        self._bus = bus
        self._session_factory = session_factory
        self._tools: dict[str, BaseTool] = {}
        self._ctx: ToolContext | None = None
        self._disabled = set(settings.tools.disabled)

    # ------------------------------------------------------------- registry

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool registration: {tool.name}")
        if tool.name in self._disabled:
            log.info("tool %s disabled by config", tool.name)
            return
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        """JSON-schema tool list for LLM function calling."""
        return [tool.schema() for tool in self._tools.values()]

    def bind_context(self, ctx: ToolContext) -> None:
        self._ctx = ctx

    def context(self) -> ToolContext:
        if self._ctx is None:
            raise ToolError("Tool context not initialized.", detail="bind_context was never called")
        return self._ctx

    # ------------------------------------------------------------- execution

    async def execute(self, name: str, args: dict[str, Any] | None = None) -> ToolResult:
        args = args or {}
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(False, f"I don't have a tool called '{name}'.",
                              error=f"unknown tool: {name}")

        started = time.perf_counter()
        try:
            clean_args = tool.validate(args)
        except Exception as exc:
            friendly = getattr(exc, "friendly", "Invalid parameters.")
            await self._log_usage(name, args, tool.risk, "error", 0, str(getattr(exc, "detail", exc)))
            return ToolResult(False, friendly, error=str(getattr(exc, "detail", exc)))

        summary = {k: (str(v)[:80]) for k, v in clean_args.items()}
        decision = await self._permissions.evaluate(
            tool.name, tool.category, tool.risk, tool.destructive, summary)
        if not decision.allowed:
            await self._log_usage(name, clean_args, tool.risk, "denied", 0, decision.reason)
            return ToolResult(False, f"That action is blocked: {decision.reason}.",
                              error=decision.reason)

        if decision.needs_confirmation:
            request = PermissionRequest(
                subject=f"tool:{tool.name}", tool_name=tool.name, category=tool.category,
                risk=tool.risk, reason=decision.reason, args_summary=summary)
            choice = await self._permissions.confirm(request)
            if choice == "deny":
                await self._log_usage(name, clean_args, tool.risk, "denied", 0, "user denied")
                return ToolResult(False, "Understood — I skipped that action.",
                                  error="user denied confirmation")

        await self._bus.publish(Topics.TOOL_STARTED, {"tool": tool.name, "args": summary})
        try:
            result = await tool.execute(clean_args, self.context())
        except Exception as exc:
            duration = int((time.perf_counter() - started) * 1000)
            friendly = getattr(exc, "friendly", None) or "That action failed."
            detail = str(getattr(exc, "detail", exc))
            log.error("tool %s failed: %s", tool.name, detail, extra={"tool": tool.name})
            await self._log_usage(name, clean_args, tool.risk, "error", duration, detail)
            await self._bus.publish(Topics.TOOL_FINISHED, {
                "tool": tool.name, "success": False, "duration_ms": duration, "message": friendly})
            return ToolResult(False, friendly, error=detail)

        duration = int((time.perf_counter() - started) * 1000)
        await self._bus.publish(Topics.TOOL_FINISHED, {
            "tool": tool.name, "success": result.success, "duration_ms": duration,
            "message": result.message})
        await self._log_usage(name, clean_args, tool.risk,
                              "ok" if result.success else "error", duration,
                              None if result.success else result.error)
        return result

    async def _log_usage(self, name: str, args: dict, risk: RiskLevel, status: str,
                         duration_ms: int, error: str | None) -> None:
        try:
            async with self._session_factory() as session:
                await ToolUsageRepo(session).log(
                    tool=name, args=args, risk=risk.label, status=status,
                    duration_ms=duration_ms, error=error)
        except Exception:
            log.exception("failed to persist tool usage")
