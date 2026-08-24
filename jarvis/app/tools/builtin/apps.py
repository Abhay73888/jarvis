"""Application control tools (Spec §10) — open/close with discovery & verification.

Open flow: resolve via app index -> launch -> verify the process actually
appeared (Spec §41). Close flow: graceful close (WM_CLOSE via taskkill without
/f on Windows) -> verify termination.
"""
from __future__ import annotations

import asyncio
import os
import subprocess

import psutil
from pydantic import BaseModel, Field

from app.computer.discovery import AppEntry, build_index, find_apps
from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult
from app.utils.paths import IS_WINDOWS


class AppIndexCache:
    """Lazily built, TTL-refreshed application registry (Spec §11)."""

    def __init__(self, ttl_s: float = 300.0) -> None:
        self._index: list[AppEntry] | None = None
        self._built_at: float = 0.0
        self._ttl = ttl_s

    async def get(self, refresh: bool = False) -> list[AppEntry]:
        import time
        if self._index is None or refresh or (time.monotonic() - self._built_at) > self._ttl:
            self._index = await build_index()
            self._built_at = time.monotonic()
        return self._index


CACHE = AppIndexCache()


def _launch(entry: AppEntry) -> None:
    if entry.kind == "shortcut":            # Windows .lnk — shell launch
        os.startfile(entry.launch)          # type: ignore[attr-defined]  (Windows only)
    elif entry.kind == "desktop":           # Linux .desktop Exec= line
        cmd = entry.launch.split()[0]
        subprocess.Popen([cmd], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:                                    # executable path
        subprocess.Popen([entry.launch], shell=False, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def _verify_running(token: str, timeout_s: float = 6.0) -> bool:
    token = token.lower().removesuffix(".exe")

    def _running() -> bool:
        return any(token in (p.info["name"] or "").lower()
                   for p in psutil.process_iter(["name"]))

    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        if await asyncio.to_thread(_running):
            return True
        await asyncio.sleep(0.5)
    return False


class _OpenAppArgs(BaseModel):
    app: str = Field(description="Application name as the user said it, e.g. 'chrome', 'VS Code', 'Spotify'")


class OpenApplicationTool(BaseTool):
    name = "open_application"
    description = ("Open an installed application by name. Finds it automatically "
                   "(Start Menu / PATH / aliases) — no paths needed. Reports whether "
                   "the app actually launched.")
    args_model = _OpenAppArgs
    category = "applications"
    risk = RiskLevel.LOW
    # Rationale: opening an app is an explicit, low-surprise user request — it
    # runs instantly under the "applications: allow" policy (matching the §67
    # UX: "Chrome kholo" → "Opening Chrome." with no friction). Users wanting
    # an ask-first policy set applications: confirm in permissions.yaml.

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        index = await CACHE.get()
        matches = find_apps(args["app"], index)
        if not matches:
            all_names = sorted({e.name for e in index})[:40]
            return ToolResult(False, f"I couldn't find an app called '{args['app']}'.",
                              data={"candidates": all_names}, verified=True)
        if len(matches) > 1 and args["app"].strip().lower() not in {m.name.lower() for m in matches}:
            return ToolResult(
                True, f"That name is ambiguous — candidates: {', '.join(m.name for m in matches)}.",
                data={"ambiguous": True, "candidates": [m.name for m in matches],
                      "current_app": args["app"]},
                verified=True)
        entry = matches[0]
        try:
            await asyncio.to_thread(_launch, entry)
        except Exception as exc:
            return ToolResult(False, f"Launching {entry.name} failed.",
                              error=f"launch error: {exc}")
        verified = await _verify_running(entry.name)
        message = f"Opening {entry.name}." if verified else f"Launched {entry.name} (started, but I couldn't confirm the window yet)."
        return ToolResult(verified, message, data={"app": entry.name}, verified=verified)


class _CloseAppArgs(BaseModel):
    app: str = Field(description="Application name to close, e.g. 'chrome'")
    force: bool = Field(default=False, description="Force-kill if graceful close fails")


class CloseApplicationTool(BaseTool):
    name = "close_application"
    description = "Close an application by name. Graceful close first; verifies it exited. May lose unsaved work."
    args_model = _CloseAppArgs
    category = "applications"
    risk = RiskLevel.HIGH
    destructive = True                 # unsaved work can be lost

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        query = args["app"].lower().removesuffix(".exe")

        def _targets() -> list[psutil.Process]:
            return [p for p in psutil.process_iter(["name"])
                    if query in (p.info["name"] or "").lower()]

        victims = await asyncio.to_thread(_targets)
        if not victims:
            return ToolResult(True, f"'{args['app']}' isn't running.", verified=True)
        try:
            if IS_WINDOWS:
                exe = (victims[0].info["name"] or "").removesuffix(".exe") + ".exe"
                subprocess.run(["taskkill", "/IM", exe, "/T"],
                               capture_output=True, timeout=15, check=False)
            else:
                for p in victims:
                    p.terminate()
        except Exception as exc:
            return ToolResult(False, f"Closing '{args['app']}' failed.", error=str(exc))

        gone, alive = psutil.wait_procs(victims, timeout=5)
        if alive and args.get("force"):
            for p in alive:
                try:
                    p.kill()
                except psutil.AccessDenied:
                    pass
            gone, alive = psutil.wait_procs(alive, timeout=3)
        verified = not alive
        msg = f"Closed {args['app']}." if verified else f"'{args['app']}' didn't fully close (may need elevated rights)."
        return ToolResult(verified, msg, data={"closed": len(gone), "remaining": len(alive)},
                          verified=verified)
