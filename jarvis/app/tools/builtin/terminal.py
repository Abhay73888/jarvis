"""Terminal tools (Spec §17, §18) — real command execution with risk gating.

The classifier (app.security.risk) assigns LOW/MEDIUM/HIGH/CRITICAL; the
permission engine decides auto-run vs confirmation vs block. Output is capped
and always returned with the exit code. Verification = exit code + output
inspection (Spec §41).
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from app.security.risk import RiskAssessment, RiskLevel, classify_command
from app.tools.base import BaseTool, ToolContext, ToolResult
from app.utils.paths import IS_WINDOWS

MAX_OUTPUT_CHARS = 8_000


def _shell_command(command: str) -> list[str]:
    if IS_WINDOWS:
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    return ["/bin/bash", "-lc", command]


class _TerminalArgs(BaseModel):
    command: str = Field(description="Shell command to execute (PowerShell on Windows, bash elsewhere)")
    working_dir: str | None = Field(default=None, description="Directory to run in")
    timeout_s: int = Field(default=60, ge=1, le=600)
    explanation: str | None = Field(default=None, description="Why this command is being run")


class TerminalExecuteTool(BaseTool):
    name = "terminal_execute"
    description = ("Execute a shell command (PowerShell on Windows) and return exit code, "
                   "stdout and stderr. Risky commands require the user's confirmation. "
                   "Use for git, builds, pip, npm, diagnostics.")
    args_model = _TerminalArgs
    category = "terminal"
    risk = RiskLevel.MEDIUM          # per-command classification overrides this

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        command = args["command"].strip()

        from app.security.sandbox import inspect_command
        threat = inspect_command(command)
        if threat.is_threat and threat.severity in ("LETHAL", "CRITICAL"):
            return ToolResult(
                False,
                f"SECURITY ALERT: Blocked by Zero-Trust Sandbox. {threat.reason}",
                error=threat.reason,
                verified=True,
            )

        assessment: RiskAssessment = classify_command(command)
        if assessment.level == RiskLevel.CRITICAL:
            # Even with confirmation, refuse the worst tier by default; the
            # permission engine will still have asked before we get here.
            if any("download-and-execute" in r or "execution policy" in r for r in assessment.reasons):
                return ToolResult(False,
                                  "I won't run download-and-execute pipelines — they're a common malware pattern. "
                                  "Download the file, inspect it, then run it deliberately.",
                                  error=f"blocked: {assessment.reasons}", verified=True)
        cwd = ctx.workdir
        if args.get("working_dir"):
            from app.tools.pathing import resolve_path
            cwd = resolve_path(args["working_dir"], ctx, must_exist=True)

        proc = await asyncio.create_subprocess_exec(
            *_shell_command(command),
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=args["timeout_s"])
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(False, f"The command didn't finish within {args['timeout_s']}s and was stopped.",
                              error="timeout", verified=True)

        out = stdout.decode("utf-8", errors="replace").strip()[:MAX_OUTPUT_CHARS]
        err = stderr.decode("utf-8", errors="replace").strip()[:2000]
        data = {"exit_code": proc.returncode, "stdout": out, "stderr": err,
                "risk": assessment.level.label}
        if proc.returncode == 0:
            return ToolResult(True, "Command completed successfully.", data=data, verified=True)
        return ToolResult(False, f"The command failed with exit code {proc.returncode}.", data=data,
                          error=err or out or "no output", verified=True)


class _RunPythonArgs(BaseModel):
    file: str | None = Field(default=None, description="Python file to run")
    code: str | None = Field(default=None, description="Inline Python code (runs from a temp file)")
    working_dir: str | None = None
    timeout_s: int = Field(default=60, ge=1, le=600)


class RunPythonTool(BaseTool):
    name = "run_python"
    description = "Run a Python file or a snippet in a subprocess and return the output."
    args_model = _RunPythonArgs
    category = "terminal"
    risk = RiskLevel.MEDIUM

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        import sys
        import tempfile
        from pathlib import Path

        cwd = ctx.workdir
        if args.get("working_dir"):
            from app.tools.pathing import resolve_path
            cwd = resolve_path(args["working_dir"], ctx, must_exist=True)

        if args.get("file"):
            from app.tools.pathing import resolve_path
            script = resolve_path(args["file"], ctx, must_exist=True)
            cmd = [sys.executable, str(script)]
        elif args.get("code"):
            import os
            fd, tmp_path = tempfile.mkstemp(suffix=".py", dir=cwd)
            os.close(fd)
            tmp = Path(tmp_path)
            tmp.write_text(args["code"], encoding="utf-8")
            cmd = [sys.executable, str(tmp)]
        else:
            from app.core.exceptions import ToolValidationError
            raise ToolValidationError("Provide either 'file' or 'code'.")

        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(cwd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=args["timeout_s"])
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(False, f"Python didn't finish within {args['timeout_s']}s.", verified=True)
        finally:
            if args.get("code"):
                tmp.unlink(missing_ok=True)

        out = stdout.decode("utf-8", errors="replace").strip()[:MAX_OUTPUT_CHARS]
        err = stderr.decode("utf-8", errors="replace").strip()[:2000]
        ok = proc.returncode == 0
        return ToolResult(ok, "Python finished." if ok else f"Python exited with code {proc.returncode}.",
                          data={"exit_code": proc.returncode, "stdout": out, "stderr": err},
                          error=None if ok else (err or out), verified=True)
