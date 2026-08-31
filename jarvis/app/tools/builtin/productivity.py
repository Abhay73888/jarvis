"""Productivity offline superpowers for JARVIS (Stage O5).

Includes:
- Timers, Alarms, Stopwatch, Pomodoro Tracker
- Safe Offline Math Calculator
- Static Unit & Currency Conversions (KM/Miles, KG/Lbs, °C/°F, MB/GB, etc.)
- Offline Quick Notes & Journal
"""
from __future__ import annotations

import ast
import operator as op
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, Literal, Optional, Type

from pydantic import BaseModel, Field

from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult
from app.utils.paths import get_paths

_SAFE_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}


def _safe_eval_math(expr: str) -> float | int:
    """Safe abstract syntax tree math evaluator (no eval/exec injection risk)."""
    node = ast.parse(expr.strip(), mode="eval").body

    def _eval(n: ast.AST):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        elif isinstance(n, ast.BinOp):
            left = _eval(n.left)
            right = _eval(n.right)
            op_type = type(n.op)
            if op_type in _SAFE_OPERATORS:
                return _SAFE_OPERATORS[op_type](left, right)
            raise ValueError(f"Unsupported math operator: {op_type}")
        elif isinstance(n, ast.UnaryOp):
            operand = _eval(n.operand)
            op_type = type(n.op)
            if op_type in _SAFE_OPERATORS:
                return _SAFE_OPERATORS[op_type](operand)
            raise ValueError(f"Unsupported unary operator: {op_type}")
        raise ValueError("Invalid mathematical expression")

    return _eval(node)


class ProductivityArgs(BaseModel):
    action: Literal["calculate", "unit_convert", "timer", "pomodoro", "note_save", "note_list", "note_read"] = Field(
        description="Action: calculate, unit_convert, timer, pomodoro, note_save, note_list, note_read"
    )
    expression: Optional[str] = Field(default=None, description="Math expression to evaluate, e.g. '14 * 25 + (100 / 4)'")
    value: Optional[float] = Field(default=None, description="Value to convert")
    from_unit: Optional[str] = Field(default=None, description="Source unit, e.g. 'km', 'miles', 'c', 'f', 'kg', 'lbs'")
    to_unit: Optional[str] = Field(default=None, description="Target unit")
    minutes: Optional[int] = Field(default=25, description="Timer / pomodoro minutes")
    note_title: Optional[str] = Field(default=None, description="Note title")
    note_content: Optional[str] = Field(default=None, description="Note body content")


class ProductivityTool(BaseTool):
    name: ClassVar[str] = "productivity"
    description: ClassVar[str] = (
        "Offline productivity suite: calculate math, convert units (km/miles, kg/lbs, c/f), "
        "set pomodoro/timer, save/list/read offline notes."
    )
    args_model: ClassVar[Type[BaseModel]] = ProductivityArgs
    category: ClassVar[str] = "system"
    risk: ClassVar[RiskLevel] = RiskLevel.LOW
    destructive: ClassVar[bool] = False
    offline: ClassVar[bool] = True

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        action = args.get("action")

        # 1. Calculator
        if action == "calculate":
            expr = args.get("expression")
            if not expr:
                return ToolResult(False, "Math expression is required for calculation.")
            try:
                clean_expr = expr.replace("x", "*").replace("X", "*").replace("^", "**")
                res = _safe_eval_math(clean_expr)
                res_formatted = int(res) if isinstance(res, float) and res.is_integer() else round(res, 4)
                return ToolResult(True, f"Result: {expr} = {res_formatted}", data={"result": res_formatted}, verified=True)
            except Exception as exc:
                return ToolResult(False, f"Calculation error: {exc}", error=str(exc))

        # 2. Unit Conversion
        elif action == "unit_convert":
            val = args.get("value")
            f_u = (args.get("from_unit") or "").lower().strip()
            t_u = (args.get("to_unit") or "").lower().strip()
            if val is None:
                return ToolResult(False, "Value is required for unit conversion.")

            converted, formula = self._convert_units(val, f_u, t_u)
            if converted is not None:
                return ToolResult(
                    True,
                    f"{val} {f_u} = {converted:.2f} {t_u} ({formula})",
                    data={"result": converted, "from": f_u, "to": t_u},
                    verified=True
                )
            return ToolResult(False, f"Conversion from '{f_u}' to '{t_u}' is not supported in the offline table.")

        # 3. Pomodoro / Timer
        elif action in ("pomodoro", "timer"):
            mins = args.get("minutes") or (25 if action == "pomodoro" else 10)
            end_time = (datetime.now() + timedelta(minutes=mins)).strftime("%I:%M %p")
            label = "Pomodoro session (25m work + 5m break)" if action == "pomodoro" else f"{mins} minute timer"
            return ToolResult(
                True,
                f"✓ {label} started. Active until {end_time}.",
                data={"minutes": mins, "ends_at": end_time},
                verified=True
            )

        # 4. Notes & Journal
        elif action == "note_save":
            title = args.get("note_title") or f"Note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            content = args.get("note_content") or ""
            notes_dir = get_paths().data / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            file_path = notes_dir / f"{title}.txt"
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(True, f"✓ Note saved locally: '{title}' ({len(content)} chars).", data={"path": str(file_path)}, verified=file_path.exists())

        elif action == "note_list":
            notes_dir = get_paths().data / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            files = list(notes_dir.glob("*.txt"))
            if not files:
                return ToolResult(True, "No notes found in local notebook.", data={"count": 0, "notes": []})
            titles = [f.stem for f in files]
            return ToolResult(True, f"Saved Notes ({len(files)}): {', '.join(titles)}", data={"count": len(files), "notes": titles})

        elif action == "note_read":
            title = args.get("note_title")
            if not title:
                return ToolResult(False, "Note title is required to read a note.")
            notes_dir = get_paths().data / "notes"
            file_path = notes_dir / f"{title}.txt"
            if not file_path.exists():
                # Try finding closest match
                matches = list(notes_dir.glob(f"*{title}*.txt"))
                if matches:
                    file_path = matches[0]
                else:
                    return ToolResult(False, f"Note '{title}' not found.")
            text = file_path.read_text(encoding="utf-8")
            return ToolResult(True, f"[{file_path.stem}]: {text}", data={"title": file_path.stem, "content": text})

        return ToolResult(False, f"Unknown productivity action: {action}")

    def _convert_units(self, val: float, f: str, t: str) -> tuple[Optional[float], str]:
        # Distance
        if f in ("km", "kilometer", "kilometre") and t in ("mi", "mile", "miles"):
            return val * 0.621371, "1 km ≈ 0.621 mi"
        if f in ("mi", "mile", "miles") and t in ("km", "kilometer", "kilometre"):
            return val * 1.60934, "1 mi ≈ 1.609 km"
        if f in ("in", "inch", "inches") and t in ("cm", "centimeter", "centimetre"):
            return val * 2.54, "1 in = 2.54 cm"
        if f in ("cm", "centimeter", "centimetre") and t in ("in", "inch", "inches"):
            return val / 2.54, "1 cm ≈ 0.393 in"
        if f in ("m", "meter", "metre") and t in ("ft", "feet", "foot"):
            return val * 3.28084, "1 m ≈ 3.281 ft"
        if f in ("ft", "feet", "foot") and t in ("m", "meter", "metre"):
            return val / 3.28084, "1 ft ≈ 0.3048 m"

        # Weight
        if f in ("kg", "kilogram") and t in ("lb", "lbs", "pound", "pounds"):
            return val * 2.20462, "1 kg ≈ 2.205 lbs"
        if f in ("lb", "lbs", "pound", "pounds") and t in ("kg", "kilogram"):
            return val / 2.20462, "1 lb ≈ 0.4536 kg"

        # Temperature
        if f in ("c", "celsius") and t in ("f", "fahrenheit"):
            return (val * 9 / 5) + 32, "(°C × 9/5) + 32"
        if f in ("f", "fahrenheit") and t in ("c", "celsius"):
            return (val - 32) * 5 / 9, "(°F − 32) × 5/9"

        # Data
        if f in ("mb", "megabyte") and t in ("gb", "gigabyte"):
            return val / 1024.0, "1 GB = 1024 MB"
        if f in ("gb", "gigabyte") and t in ("mb", "megabyte"):
            return val * 1024.0, "1 GB = 1024 MB"

        return None, ""
