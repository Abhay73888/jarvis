"""Conversation summarizer and long-term memory extractor (Spec Phase 9).

Summarizes completed conversations into persistent key facts, decisions, and
learned preferences stored in memory_items.
"""
from __future__ import annotations

import re
from typing import Optional

from app.brain.provider import ChatMessage
from app.brain.router import ModelRouter
from app.core.logging import get_logger

log = get_logger("memory.summarizer")


class ConversationSummarizer:
    """Extracts long-term facts, habits, and preferences from conversation history."""

    def __init__(self, router: Optional[ModelRouter] = None) -> None:
        self.router = router

    async def extract_facts(self, messages: list[ChatMessage]) -> list[str]:
        """Analyze message turns and extract concise memorable facts."""
        if not messages or len(messages) < 2:
            return []

        user_messages = [m.content for m in messages if m.role == "user" and m.content.strip()]
        if not user_messages:
            return []

        # Check for explicit preference keywords
        facts: list[str] = []
        for msg in user_messages:
            m = re.search(r"(?i)\b(?:yaad\s*rakho|remember\s*that|i\s*prefer|mujhe\s*pasand\s*hai|always\s+use)\s+(.+)", msg)
            if m:
                fact = m.group(1).strip(" .!?,;")
                if fact and fact not in facts:
                    facts.append(f"User preference: {fact}")

        # If LLM is available and conversation has substantive turns, run LLM summarization
        fast_provider = self.router.provider_for_role("fast") if self.router else None
        if fast_provider and len(user_messages) >= 3:
            transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in messages[-6:] if m.content)
            prompt = (
                f"Extract 1-3 key facts, user preferences, or project details from this conversation snippet.\n"
                f"Only return bullet points of facts worth remembering long-term. If nothing is worth remembering, return 'NONE'.\n\n"
                f"{transcript}"
            )
            try:
                resp = await fast_provider.chat([ChatMessage(role="user", content=prompt)], temperature=0.1)
                for line in resp.content.splitlines():
                    clean_line = line.strip(" -•*")
                    if clean_line and "NONE" not in clean_line.upper() and len(clean_line) > 5:
                        if clean_line not in facts:
                            facts.append(clean_line)
            except Exception as exc:
                log.debug("LLM summarization skipped: %s", exc)

        return facts
