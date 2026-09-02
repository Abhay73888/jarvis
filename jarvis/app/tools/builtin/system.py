"""System tools: info, processes, kill (Spec §37)."""
from __future__ import annotations

import platform
from datetime import UTC, datetime

import psutil
from pydantic import BaseModel, Field

from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult

# Prime cpu_percent on module load so subsequent calls with interval=None are non-blocking (0ms)
try:
    psutil.cpu_percent(interval=None)
except Exception:
    pass


class _SystemInfoArgs(BaseModel):
    pass


class SystemInfoTool(BaseTool):
    name = "system_info"
    description = ("Get a diagnostic snapshot of this computer: CPU, RAM, disk, battery, "
                   "network, OS. Use for questions like 'why is my laptop slow'.")
    args_model = _SystemInfoArgs
    category = "diagnostics"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(ctx.workdir.anchor if hasattr(ctx.workdir, "anchor") else "/")
        boot = datetime.fromtimestamp(psutil.boot_time(), tz=UTC)
        battery = psutil.sensors_battery()
        data = {
            "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "cpu_percent": psutil.cpu_percent(interval=None),

            "cpu_cores": psutil.cpu_count(logical=True),
            "ram_percent": vm.percent,
            "ram_used_gb": round(vm.used / 1e9, 2),
            "ram_total_gb": round(vm.total / 1e9, 2),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / 1e9, 1),
            "disk_total_gb": round(disk.total / 1e9, 1),
            "uptime": str(datetime.now(tz=UTC) - boot).split(".")[0],
        }
        if battery is not None:
            data["battery_percent"] = battery.percent
            if battery.secsleft and battery.secsleft > 0:
                data["battery_time_left_min"] = round(battery.secsleft / 60)
        top = sorted(psutil.process_iter(["name", "cpu_percent"]),
                     key=lambda p: (p.info.get("cpu_percent") or 0), reverse=True)[:5]
        data["top_cpu_processes"] = [f"{p.info['name']} ({p.info.get('cpu_percent') or 0:.0f}%)" for p in top]
        return ToolResult(True, "System snapshot ready.", data=data, verified=True)


class _ProcessListArgs(BaseModel):
    filter: str | None = Field(default=None, description="Only show processes whose name contains this")
    limit: int = Field(default=15, ge=1, le=100)


class ProcessListTool(BaseTool):
    name = "process_list"
    description = "List running processes sorted by CPU or memory, optionally filtered by name."
    args_model = _ProcessListArgs
    category = "diagnostics"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            name = (p.info["name"] or "").lower()
            name_filter = args.get("filter")
            if name_filter and name_filter.lower() not in name:
                continue
            procs.append(p.info)
        procs.sort(key=lambda p: (p.get("memory_percent") or 0), reverse=True)
        rows = [{"pid": p["pid"], "name": p["name"],
                 "mem_pct": round(p.get("memory_percent") or 0, 1)} for p in procs[: args["limit"]]]
        return ToolResult(True, f"{len(rows)} processes shown ({len(procs)} matched).",
                          data={"processes": rows, "total_matched": len(procs)}, verified=True)


class _KillProcessArgs(BaseModel):
    name: str = Field(description="Process name to terminate, e.g. 'chrome' or 'chrome.exe'")
    force: bool = Field(default=False, description="Hard kill instead of graceful close")


class KillProcessTool(BaseTool):
    name = "kill_process"
    description = "Terminate running processes by name. Use when asked to close/quit an app that ignores normal close."
    args_model = _KillProcessArgs
    category = "system"
    risk = RiskLevel.HIGH
    destructive = True

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        target = args["name"].lower().removesuffix(".exe")
        victims = [p for p in psutil.process_iter(["pid", "name"])
                   if target in (p.info["name"] or "").lower()]
        if not victims:
            return ToolResult(False, f"No running process matches '{args['name']}'.", verified=True)
        terminated = 0
        for p in victims:
            try:
                p.kill() if args["force"] else p.terminate()
                terminated += 1
            except psutil.AccessDenied:
                continue
        psutil.wait_procs(victims, timeout=3)
        still = [p for p in psutil.process_iter(["name"]) if target in (p.info["name"] or "").lower()]
        verified = not still
        msg = f"Terminated {terminated} process(es)."
        if still:
            msg += f" {len(still)} still running (may need admin rights or force)."
        return ToolResult(verified, msg, data={"terminated": terminated, "remaining": len(still)},
                          verified=verified)
