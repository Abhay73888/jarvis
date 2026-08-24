"""Tool framework base classes (Spec §34).

Every tool declares: name, description, parameters (JSON schema via a pydantic
Args model), category, risk level, destructive flag; implements validate(),
execute(), and rollback() where possible. Tools verify their own effects and
report honestly via ToolResult.verified.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Type

from pydantic import BaseModel

from app.core.exceptions import ToolValidationError
from app.security.risk import RiskLevel


@dataclass
class ToolResult:
    success: bool
    message: str                      # user-facing, clean language
    data: dict[str, Any] = field(default_factory=dict)
    verified: bool = False            # did we actually confirm the effect? (Spec §41)
    error: str | None = None          # dev-mode detail


@dataclass
class ToolContext:
    """Shared services handed to every tool at execution time."""
    settings: Any                     # Settings
    workdir: Any                      # pathlib.Path — where relative paths resolve
    writable_roots: Any               # list[Path]
    session_factory: Any = None       # async_sessionmaker — DB access for tools that persist


class BaseTool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]                        # given to the LLM
    args_model: ClassVar[Type[BaseModel]]             # validated + exported as JSON schema
    category: ClassVar[str] = "system"
    risk: ClassVar[RiskLevel] = RiskLevel.LOW
    destructive: ClassVar[bool] = False

    def validate(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            validated = self.args_model.model_validate(args)
        except Exception as exc:
            raise ToolValidationError(
                f"That action's parameters were invalid: {exc.error_count()} issue(s).",
                detail=str(exc.errors())) from exc
        return validated.model_dump(exclude_none=True)

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_model.model_json_schema(),
        }

    @abstractmethod
    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult: ...

    async def rollback(self, args: dict[str, Any], ctx: ToolContext) -> bool:
        """Best-effort undo. Default: not possible."""
        return False
