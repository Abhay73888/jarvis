"""Permission & confirmation engine (Spec §25, §26).

Decision matrix (no standing grant):
  - CRITICAL risk               -> always confirm (config can never bypass)
  - HIGH risk / destructive     -> confirm
  - MEDIUM risk                 -> confirm under "allow" policy; confirm under "confirm"
  - LOW risk                    -> auto under "allow"; confirm under "confirm"; deny under "deny"
  - Standing grant "allow_always" on tool/category -> auto (except CRITICAL)
  - Standing grant "deny"       -> blocked

The UI/CLI supplies an async confirmation handler; without one, deny-by-default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.config.settings import Settings
from app.core.events import EventBus, Topics
from app.core.logging import get_logger
from app.database.repo import PermissionRepo
from app.security.risk import RiskLevel

log = get_logger("permissions")

ConfirmChoice = str  # "allow_once" | "allow_always" | "deny"
ConfirmHandler = Callable[["PermissionRequest"], Awaitable[ConfirmChoice]]


@dataclass
class PermissionRequest:
    subject: str                      # e.g. "tool:delete_file"
    tool_name: str
    category: str
    risk: RiskLevel
    reason: str
    args_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "tool": self.tool_name,
            "category": self.category,
            "risk": self.risk.label,
            "reason": self.reason,
            "args": self.args_summary,
        }


@dataclass
class Decision:
    allowed: bool
    needs_confirmation: bool
    reason: str


class PermissionStore:
    """Async facade over the permission-grants table (short-lived sessions)."""

    def __init__(self, session_factory) -> None:
        self._factory = session_factory

    async def find(self, subject: str) -> str | None:
        async with self._factory() as session:
            return await PermissionRepo(session).find(subject)

    async def grant(self, subject: str, decision: str) -> None:
        async with self._factory() as session:
            await PermissionRepo(session).grant(subject, decision)


class PermissionManager:
    def __init__(self, settings: Settings, store: PermissionStore, bus: EventBus) -> None:
        self._settings = settings
        self._store = store
        self._bus = bus
        self._confirm_handler: ConfirmHandler | None = None

    def set_confirm_handler(self, handler: ConfirmHandler) -> None:
        """Installed by CLI/GUI. Until installed, confirmations resolve to deny."""
        self._confirm_handler = handler

    async def evaluate(self, tool_name: str, category: str, risk: RiskLevel,
                       destructive: bool, args_summary: dict[str, Any] | None = None) -> Decision:
        args_summary = args_summary or {}
        policy = self._settings.permissions.categories.get(category, "confirm")

        # Standing grants
        for subject in (f"tool:{tool_name}", f"category:{category}"):
            standing = await self._store.find(subject)
            if standing == "deny":
                return Decision(False, False, f"Denied by standing permission for {subject}")
            if standing == "allow_always":
                if risk == RiskLevel.CRITICAL and self._settings.permissions.critical_always_confirms:
                    break  # CRITICAL always asks, regardless of grants
                return Decision(True, False, f"Allowed by standing permission for {subject}")

        if policy == "deny":
            return Decision(False, False, f"Category '{category}' is set to deny")

        needs_confirmation = (
            risk >= RiskLevel.HIGH
            or destructive
            or (risk >= RiskLevel.MEDIUM)
            or policy == "confirm"
        )
        return Decision(True, needs_confirmation,
                        f"risk={risk.label}, category={category}, policy={policy}")

    async def confirm(self, request: PermissionRequest) -> ConfirmChoice:
        await self._bus.publish(Topics.PERMISSION_REQUESTED, request.to_dict())
        if self._confirm_handler is None:
            log.warning("No confirm handler installed; denying %s", request.subject)
            return "deny"
        choice = await self._confirm_handler(request)
        if choice == "allow_always":
            await self._store.grant(request.subject, "allow_always")
        return choice
