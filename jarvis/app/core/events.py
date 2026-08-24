"""Async event bus — the nervous system connecting engine, GUI, voice, tools.

Modules publish typed topics; the UI subscribes and renders status. This keeps
app/ui from being imported by core logic (Spec §44: never block the caller).
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger("jarvis.bus")


class Topics:
    """Canonical event topics. Payloads are plain JSON-able dicts."""

    STATUS = "status"                      # {state: listening|thinking|working|speaking|idle|error, detail}
    RESPONSE_DELTA = "response.delta"      # {delta: str} — live streaming tokens
    TOOL_STARTED = "tool.started"          # {tool, args}
    TOOL_FINISHED = "tool.finished"        # {tool, success, duration_ms, message}
    PERMISSION_REQUESTED = "permission.requested"  # PermissionRequest.to_dict()
    NOTIFICATION = "notification"          # {level, title, message}
    INTERRUPT = "interrupt"                # {} — emergency stop
    MEMORY_UPDATED = "memory.updated"      # {kind}



Handler = Callable[[str, dict[str, Any]], None] | Callable[[str, dict[str, Any]], Any]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> Callable[[], None]:
        """Subscribe; returns an unsubscribe function."""
        self._subs[topic].append(handler)

        def _unsub() -> None:
            try:
                self._subs[topic].remove(handler)
            except ValueError:
                pass

        return _unsub

    async def publish(self, topic: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        for handler in list(self._subs.get(topic, [])):
            try:
                result = handler(topic, payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001 — a bad subscriber must not break the bus
                log.exception("Event handler failed for topic=%s", topic)

    async def request(self, topic: str, payload: dict[str, Any] | None = None) -> Any:
        """Publish and wait for the first subscriber that returns a value
        (used for permission prompts driven by UI/CLI)."""
        payload = dict(payload or {})
        for handler in list(self._subs.get(topic, [])):
            try:
                result = handler(topic, payload)
                if asyncio.iscoroutine(result):
                    result = await result
                if result is not None:
                    return result
            except Exception:  # noqa: BLE001
                log.exception("Request handler failed for topic=%s", topic)
        return None
