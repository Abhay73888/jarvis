"""Lightweight Background Network Connectivity Monitor for JARVIS.

Periodically probes internet reachability via fast non-blocking DNS/socket
lookup with a short timeout (0.5s), caching results so tool execution and
conversations never block on network latency.
"""
from __future__ import annotations

import asyncio
import socket
import time
from typing import Optional

from app.core.events import EventBus, Topics
from app.core.logging import get_logger

log = get_logger("brain.connectivity")

DEFAULT_PROBE_HOST = "1.1.1.1"
DEFAULT_PROBE_PORT = 53
PROBE_TIMEOUT_S = 0.5
CACHE_TTL_S = 4.0


class ConnectivityMonitor:
    """Non-blocking connectivity checker with TTL caching and EventBus notifications."""

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        probe_host: str = DEFAULT_PROBE_HOST,
        probe_port: int = DEFAULT_PROBE_PORT,
    ) -> None:
        self.bus = bus
        self.probe_host = probe_host
        self.probe_port = probe_port
        self._is_online = True
        self._last_checked = 0.0
        self._force_offline = False

    @property
    def is_online_cached(self) -> bool:
        """Returns cached online status if checked within CACHE_TTL_S."""
        if self._force_offline:
            return False
        if time.time() - self._last_checked < CACHE_TTL_S:
            return self._is_online
        return self._is_online

    def set_force_offline(self, offline: bool) -> None:
        """Force offline mode (e.g. for privacy mode or manual toggle)."""
        self._force_offline = offline
        self._is_online = not offline
        self._last_checked = time.time()
        if self.bus:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self.bus.publish(
                        Topics.STATUS,
                        {"state": "idle", "detail": "Local brain active (Privacy Mode)" if offline else "Online"}
                    )
                )
            except RuntimeError:
                pass

    async def check_connectivity(self, force_refresh: bool = False) -> bool:
        """Performs a fast socket connection test asynchronously."""
        if self._force_offline:
            self._is_online = False
            return False

        now = time.time()
        if not force_refresh and (now - self._last_checked < CACHE_TTL_S):
            return self._is_online

        self._last_checked = now
        loop = asyncio.get_running_loop()

        def _probe() -> bool:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(PROBE_TIMEOUT_S)
                sock.connect((self.probe_host, self.probe_port))
                sock.close()
                return True
            except Exception:
                return False

        online = await loop.run_in_executor(None, _probe)
        if online != self._is_online:
            log.info("connectivity state changed: online=%s", online)
            self._is_online = online
            if self.bus:
                await self.bus.publish(
                    Topics.STATUS,
                    {"state": "idle", "detail": "Online" if online else "Local brain active (Offline)"}
                )
        else:
            self._is_online = online

        return self._is_online
