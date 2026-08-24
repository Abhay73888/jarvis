"""Filesystem path resolution for JARVIS.

Layout (repo/install root):
    jarvis/
      app/          code
      config/       user-editable YAML settings (created on first run)
      data/         SQLite DB, screenshots, artifacts
      logs/         structured logs
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


def _resolve_root() -> Path:
    """Root = repo/install dir. Override with JARVIS_HOME (used by tests)."""
    env = os.environ.get("JARVIS_HOME")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]



@dataclass(frozen=True)
class Paths:
    root: Path
    config: Path
    data: Path
    logs: Path
    screenshots: Path
    db_file: Path

    def ensure(self) -> "Paths":
        for p in (self.config, self.data, self.logs, self.screenshots):
            p.mkdir(parents=True, exist_ok=True)
        return self


def get_paths() -> Paths:
    root = _resolve_root()
    return Paths(
        root=root,
        config=root / "config",
        data=root / "data",
        logs=root / "logs",
        screenshots=root / "data" / "screenshots",
        db_file=root / "data" / "jarvis.db",
    ).ensure()


# Locations that JARVIS must never write to, regardless of configuration.
PROTECTED_WRITE_PREFIXES: tuple[Path, ...] = (
    Path("/bin"), Path("/sbin"), Path("/usr"), Path("/etc"), Path("/boot"), Path("/proc"), Path("/sys"),
)
if IS_WINDOWS:
    PROTECTED_WRITE_PREFIXES = (
        Path(os.environ.get("SystemRoot", r"C:\Windows")),
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
    ) + PROTECTED_WRITE_PREFIXES


def is_protected_write_target(path: Path) -> bool:
    """True if path lives inside an OS/system directory — writes are refused."""
    try:
        resolved = path.resolve()
    except OSError:
        return True

    # Check Unix-style root paths (e.g. /etc, /bin) regardless of host platform
    raw_str = str(path).replace("\\", "/").lower()
    for unix_prefix in ("/bin", "/sbin", "/usr", "/etc", "/boot", "/proc", "/sys"):
        if raw_str == unix_prefix or raw_str.startswith(unix_prefix + "/"):
            return True

    for prefix in PROTECTED_WRITE_PREFIXES:
        try:
            resolved.relative_to(prefix.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False

