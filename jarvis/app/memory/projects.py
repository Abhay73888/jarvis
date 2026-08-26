"""Project Registry for semantic project resolution (Spec Phase 9).

Allows user to register named projects and open/manage them by name:
- "mera healthcare project kholo" -> finds registered path -> opens in VS Code / Explorer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.utils.paths import get_paths


class ProjectRegistry:
    """Stores and resolves developer projects on disk."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path or (get_paths().data / "projects.json")
        self._projects: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                self._projects = json.loads(self.storage_path.read_text(encoding="utf-8"))
            except Exception:
                self._projects = {}
        else:
            self._projects = {}

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(self._projects, indent=2, ensure_ascii=False), encoding="utf-8")

    def register(self, name: str, path: str | Path) -> None:
        clean_name = name.strip().lower()
        self._projects[clean_name] = str(Path(path).resolve())
        self._save()

    def find(self, query: str) -> Optional[Path]:
        clean = query.strip().lower()
        # Direct key match
        if clean in self._projects:
            return Path(self._projects[clean])

        # Substring match
        for name, p in self._projects.items():
            if clean in name or name in clean:
                return Path(p)

        # Fuzzy search in common developer directories (e.g. ~/Downloads, ~/Desktop, ~/Projects)
        home = Path.home()
        for root in (home / "Projects", home / "Downloads", home / "Desktop", home / "source"):
            if root.exists():
                for d in root.iterdir():
                    if d.is_dir() and clean in d.name.lower():
                        return d

        return None

    def list_all(self) -> dict[str, str]:
        return dict(self._projects)
