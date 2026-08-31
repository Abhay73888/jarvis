"""Offline Knowledge, Dictionary, and Local Document Q&A Tool for JARVIS (Stage O5).

Features:
- Offline dictionary / WordNet-style definitions & synonyms.
- Local Knowledge Base (KB) document search across user files in data/knowledge/.
- Local text summarizer.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar, Literal, Optional, Type

from pydantic import BaseModel, Field

from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult
from app.utils.paths import get_paths

_OFFLINE_DICTIONARY = {
    "algorithm": "A step-by-step procedure or set of rules for solving a problem or performing a task.",
    "artificial intelligence": "The simulation of human intelligence processes by computer systems.",
    "machine learning": "A branch of AI focused on building systems that learn from data.",
    "neural network": "A computing architecture inspired by the biological neural networks of human brains.",
    "latency": "The time delay between a stimulus and response, or request and response.",
    "quantum": "The minimum amount of any physical entity involved in an interaction.",
    "operating system": "System software that manages computer hardware, software resources, and common services.",
    "kernel": "The core component of an operating system with complete control over everything in the system.",
    "encryption": "The process of converting information or data into a code to prevent unauthorized access.",
    "cache": "A hardware or software component that stores data so future requests for that data can be served faster.",
    "jarvis": "Just A Rather Very Intelligent System — personal AI operating layer for Windows.",
}


class KnowledgeArgs(BaseModel):
    action: Literal["define", "kb_search", "summarize"] = Field(
        default="define", description="Action: define, kb_search, summarize"
    )
    query: str = Field(description="Word to define, search query, or text to summarize")


class KnowledgeTool(BaseTool):
    name: ClassVar[str] = "knowledge_offline"
    description: ClassVar[str] = (
        "Offline knowledge tool: define terms/words, search local document knowledge base, "
        "or summarize text offline without internet."
    )
    args_model: ClassVar[Type[BaseModel]] = KnowledgeArgs
    category: ClassVar[str] = "memory"
    risk: ClassVar[RiskLevel] = RiskLevel.LOW
    destructive: ClassVar[bool] = False
    offline: ClassVar[bool] = True

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        action = args.get("action", "define")
        query = args.get("query", "").strip()

        if not query:
            return ToolResult(False, "Query string is required.")

        # 1. Dictionary definition
        if action == "define":
            clean_word = query.lower().strip("?!.,;:'\"")
            if clean_word in _OFFLINE_DICTIONARY:
                definition = _OFFLINE_DICTIONARY[clean_word]
                return ToolResult(True, f"Definition of '{query}': {definition}", data={"word": query, "definition": definition}, verified=True)

            # Check substring match
            for k, v in _OFFLINE_DICTIONARY.items():
                if clean_word in k or k in clean_word:
                    return ToolResult(True, f"Definition of '{k}': {v}", data={"word": k, "definition": v}, verified=True)

            return ToolResult(
                True,
                f"'{query}' is not in the built-in offline glossary. (Available in full offline model mode).",
                data={"word": query},
            )

        # 2. Local Knowledge Base Search
        elif action == "kb_search":
            kb_dir = get_paths().data / "knowledge"
            kb_dir.mkdir(parents=True, exist_ok=True)
            files = list(kb_dir.glob("*.*"))
            matches = []
            q_lower = query.lower()

            for f in files:
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    if q_lower in f.name.lower() or q_lower in text.lower():
                        # Extract snippet
                        idx = text.lower().find(q_lower)
                        snippet = text[max(0, idx - 40): min(len(text), idx + 140)].replace("\n", " ")
                        matches.append({"file": f.name, "snippet": snippet})
                except Exception:
                    pass

            if matches:
                msg = f"Found {len(matches)} local KB match(es) for '{query}':\n" + "\n".join(
                    f"- {m['file']}: ...{m['snippet']}..." for m in matches[:3]
                )
                return ToolResult(True, msg, data={"matches": matches}, verified=True)
            return ToolResult(True, f"No local KB documents matched '{query}'.", data={"matches": []})

        # 3. Summarizer
        elif action == "summarize":
            sentences = re.split(r"(?<=[.!?\n])\s+", query)
            if len(sentences) <= 2:
                summary = query
            else:
                summary = " ".join(sentences[:2])
            return ToolResult(True, f"Summary: {summary}", data={"summary": summary}, verified=True)

        return ToolResult(False, f"Unknown knowledge action: {action}")
