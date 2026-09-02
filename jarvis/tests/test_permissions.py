"""Permission engine tests — the safety matrix must hold exactly."""
from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.core.events import EventBus
from app.permissions.manager import PermissionManager, PermissionStore
from app.security.risk import RiskLevel


class FakeStore(PermissionStore):
    def __init__(self) -> None:  # super().__init__ not needed for the fake
        self.grants: dict[str, str] = {}

    async def find(self, subject: str) -> str | None:
        return self.grants.get(subject)

    async def grant(self, subject: str, decision: str) -> None:
        self.grants[subject] = decision


@pytest.fixture()
def pm() -> tuple[PermissionManager, FakeStore]:
    store = FakeStore()
    settings = Settings()
    manager = PermissionManager(settings, store, EventBus())
    return manager, store


async def test_low_risk_auto_allows(pm):
    manager, _ = pm
    decision = await manager.evaluate("read_file", "filesystem", RiskLevel.LOW, False)
    assert decision.allowed and not decision.needs_confirmation


async def test_medium_asks_under_allow_policy(pm):
    manager, _ = pm
    decision = await manager.evaluate("move_file", "filesystem", RiskLevel.MEDIUM, False)
    assert decision.allowed and decision.needs_confirmation


async def test_high_always_asks(pm):
    manager, _ = pm
    decision = await manager.evaluate("delete_file", "filesystem", RiskLevel.HIGH, True)
    assert decision.allowed and decision.needs_confirmation


async def test_deny_category_blocks(pm):
    manager, store = pm
    store.grants["category:terminal"] = "deny"
    decision = await manager.evaluate("terminal_execute", "terminal", RiskLevel.LOW, False)
    assert not decision.allowed


async def test_standing_allow_always_bypasses_confirm(pm):
    manager, store = pm
    store.grants["tool:move_file"] = "allow_always"
    decision = await manager.evaluate("move_file", "filesystem", RiskLevel.MEDIUM, False)
    assert decision.allowed and not decision.needs_confirmation


async def test_critical_asks_even_with_standing_grant(pm):
    manager, store = pm
    store.grants["tool:terminal_execute"] = "allow_always"
    decision = await manager.evaluate("terminal_execute", "terminal", RiskLevel.CRITICAL, False)
    assert decision.needs_confirmation


async def test_confirm_policy_category_always_asks(pm):
    manager, _ = pm
    decision = await manager.evaluate("system_info", "system", RiskLevel.LOW, False)
    assert decision.allowed and decision.needs_confirmation


async def test_sensitive_defaults_to_deny(pm):
    manager, _ = pm
    decision = await manager.evaluate("some_tool", "sensitive", RiskLevel.LOW, False)
    assert not decision.allowed


async def test_no_handler_denies(pm):
    manager, _ = pm
    from app.permissions.manager import PermissionRequest
    from app.security.risk import RiskLevel
    request = PermissionRequest("tool:x", "x", "filesystem", RiskLevel.HIGH, "test")
    choice = await manager.confirm(request)
    assert choice == "deny"
