"""Proactive background monitor for system health and reminders (Spec Phase 5+).

Monitors:
- Disk usage threshold (>90%) -> warnings.
- RAM exhaustion threshold (>95%) -> diagnostics.
- Active due reminders -> EventBus / Tray notifications.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import psutil

from app.core.events import EventBus, Topics
from app.core.logging import get_logger

log = get_logger("computer.proactive")


class ProactiveMonitor:
    """Proactive background watcher that publishes alerts on the EventBus."""

    def __init__(self, bus: EventBus, interval_seconds: float = 30.0) -> None:
        self.bus = bus
        self.interval_seconds = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_disk_alert: float = 0.0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        log.info("Proactive background monitor started.")

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                await self.check_health()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.debug("proactive monitor check error: %s", exc)

            await asyncio.sleep(self.interval_seconds)

    async def check_health(self) -> list[dict]:
        """Perform one scan of system health and return any triggered alerts."""
        alerts: list[dict] = []

        # 1. Disk usage check
        try:
            disk = psutil.disk_usage("/")
            if disk.percent >= 90.0:
                alert = {
                    "type": "disk_space_warning",
                    "level": "warning",
                    "percent": disk.percent,
                    "free_gb": round(disk.free / (1024 ** 3), 1),
                    "message": f"Low disk space: Primary drive is {disk.percent}% full ({round(disk.free / (1024 ** 3), 1)} GB free).",
                }
                alerts.append(alert)
                await self.bus.publish(Topics.STATUS, {"state": "warning", "detail": alert["message"]})
        except Exception:
            pass

        # 2. RAM check
        try:
            mem = psutil.virtual_memory()
            if mem.percent >= 95.0:
                alert = {
                    "type": "high_memory_warning",
                    "level": "warning",
                    "percent": mem.percent,
                    "message": f"Critical memory load: System RAM is at {mem.percent}%.",
                }
                alerts.append(alert)
                await self.bus.publish(Topics.STATUS, {"state": "warning", "detail": alert["message"]})
        except Exception:
            pass

        return alerts
