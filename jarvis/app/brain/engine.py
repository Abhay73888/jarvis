"""AgentEngine — the orchestrating brain (Spec §3, §20, §51, §68).

Flow per turn:
  1. Persist user message; publish "thinking".
  2. Intent fast-path (deterministic, instant, offline-capable). If it matches,
     execute the mapped tool through the full permission/verification pipeline.
  3. Otherwise, LLM tool-calling loop (bounded iterations, cancellable) with
     system prompt = personality + preferences + working memory + security rules.
  4. Persist assistant message; publish status.

Every tool execution — fast-path or LLM — goes through ToolManager, so
permissions, confirmation, verification, and logging are unavoidable.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.brain.intent import Intent, IntentRouter
from app.brain.provider import ChatMessage, LLMProvider
from app.brain.router import ModelRouter
from app.config.settings import Settings
from app.core.events import EventBus, Topics
from app.core.logging import get_logger
from app.memory.manager import ConversationManager, WorkingMemory
from app.security.injection import SYSTEM_CLAUSE
from app.tools.manager import ToolManager

log = get_logger("engine")


@dataclass
class TurnResult:
    text: str
    actions: list[dict[str, Any]] = field(default_factory=list)   # tool executions this turn
    used_fast_path: bool = False


class AgentEngine:
    def __init__(self, settings: Settings, router: ModelRouter, tools: ToolManager,
                 conversations: ConversationManager, bus: EventBus) -> None:
        self._settings = settings
        self._router = router
        self._tools = tools
        self._conversations = conversations
        self._bus = bus
        self._intent = IntentRouter()
        self.working = WorkingMemory()
        self._cancelled = asyncio.Event()

    # ------------------------------------------------------------------ API

    def interrupt(self) -> None:
        """Emergency stop (Spec §59): cancels the current turn."""
        self._cancelled.set()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._bus.publish(Topics.INTERRUPT))
        except RuntimeError:
            pass  # no loop running — nothing to cancel

    async def turn(self, user_text: str) -> TurnResult:
        self._cancelled.clear()
        await self.load_preferences_text()
        await self._conversations.append("user", user_text)
        await self._status("thinking")

        actions: list[dict[str, Any]] = []

        # ---- 1. deterministic fast-path
        if self._settings.agent.intent_fast_path:
            intent = self._intent.parse(user_text)
            if intent is not None:
                result = await self._run_intent(intent, actions)
                if result is not None:
                    await self._conversations.append("assistant", result.text, {"fast_path": True})
                    await self._status("idle")
                    return result

        # ---- 2. LLM path
        provider = self._router.provider_for_role()
        if provider is None:
            text = ("I'm running in offline mode — no AI model is configured, so I can only "
                    "handle direct commands (open apps, files, system info, searches, reminders). "
                    "Add a provider in config/models.yaml to unlock full reasoning. "
                    "Say 'help' to see what works right now.")
            await self._conversations.append("assistant", text)
            await self._status("idle")
            return TurnResult(text=text, actions=actions)

        try:
            text = await self._llm_turn(provider, user_text, actions)
        except asyncio.CancelledError:
            text = "Stopped."
        except Exception as exc:  # noqa: BLE001 — friendly errors (§42)
            friendly = getattr(exc, "friendly", None)
            text = friendly if friendly else "I hit an unexpected problem handling that."
            if self._settings.dev.enabled:
                text += f" [dev: {exc!r}]"
            log.exception("turn failed")

        await self._conversations.append("assistant", text)
        await self._status("idle")
        return TurnResult(text=text, actions=actions)

    # ------------------------------------------------------------ fast-path

    async def _run_intent(self, intent: Intent, actions: list[dict]) -> TurnResult | None:
        if intent.tool == "__say__":
            return TurnResult(text=intent.args["text"], used_fast_path=True)
        if intent.tool == "__ask__":
            return TurnResult(text=intent.args["text"], used_fast_path=True)
        if intent.tool == "__interrupt__":
            self._cancelled.set()
            return TurnResult(text="Stopped.", used_fast_path=True)
        if intent.tool == "__lockdown__":
            from app.security.lockdown import execute_emergency_lockdown
            res = execute_emergency_lockdown(self)
            return TurnResult(
                text="🚨 EMERGENCY PROTOCOL ZERO EXECUTED. Workstation locked, volatile data purged, active sessions terminated.",
                actions=[{"tool": "emergency_lockdown", "ok": True, "message": str(res)}],
                used_fast_path=True,
            )

        if intent.missing:
            return None  # shouldn't happen; pending handled in IntentRouter

        if intent.speech:
            await self._bus.publish(Topics.STATUS, {"state": "speaking", "detail": intent.speech})
        result = await self._tools.execute(intent.tool, intent.args)
        actions.append({"tool": intent.tool, "ok": result.success, "message": result.message})
        self.working.observe_result(intent.tool, result.data)
        self.working.last_app = self._intent.last_app or self.working.last_app
        self.working.candidates = self._intent.candidates or self.working.candidates

        follow: str | None = None
        if result.data.get("ambiguous"):
            follow = "Which one did you mean?"
        self._intent.candidates = result.data.get("candidates") or self._intent.candidates
        if intent.tool == "browser_search":
            self._intent.search_results = result.data.get("results", []) if result.success else []
        if intent.tool in ("browser_navigate", "browser_search") and result.data.get("url"):
            self.working.last_path = result.data["url"]
        return TurnResult(text=result.message + (f" {follow}" if follow else ""),
                          actions=actions, used_fast_path=True)

    # ------------------------------------------------------------- LLM path

    async def _llm_turn(self, provider: LLMProvider, user_text: str,
                        actions: list[dict]) -> str:
        system = self._system_prompt()
        messages: list[ChatMessage] = [ChatMessage(role="system", content=system)]
        # history() already ends with the user message we appended in turn().
        history = await self._conversations.history()
        if not history or history[-1].content != user_text or history[-1].role != "user":
            history.append(ChatMessage(role="user", content=user_text))
        messages += history

        tools = self._tools.schemas()
        max_iter = self._settings.agent.max_tool_iterations
        assistant_text = ""

        for iteration in range(max_iter):
            if self._cancelled.is_set():
                return "Stopped."
            await self._status("thinking" if iteration == 0 else "working")
            response = await provider.chat(
                messages, tools=tools,
                temperature=self._settings.ai.temperature,
                max_tokens=self._settings.ai.max_tokens)
            assistant_text = response.content

            if not response.wants_tools:
                return assistant_text or "Done."

            messages.append(ChatMessage(role="assistant", content=assistant_text,
                                        tool_calls=response.tool_calls))
            for call in response.tool_calls:
                if self._cancelled.is_set():
                    return "Stopped."
                await self._status("working", detail=call.name)
                result = await self._tools.execute(call.name, call.arguments)
                actions.append({"tool": call.name, "ok": result.success, "message": result.message})
                self.working.observe_result(call.name, result.data)
                payload = {"success": result.success, "message": result.message}
                if result.data:
                    payload["data"] = _slim(result.data)
                if result.error and self._settings.dev.enabled:
                    payload["error_detail"] = result.error
                messages.append(ChatMessage(role="tool", content=str(payload),
                                            tool_call_id=call.id, name=call.name))

        return (assistant_text or
                f"I stopped after {max_iter} steps to stay safe — here's where things stand. "
                f"Tell me to continue if you want more.")

    # ------------------------------------------------------------ helpers

    def _system_prompt(self) -> str:
        s = self._settings
        prefs_text = getattr(self, "_prefs_text", "")
        lang = {"auto": "Match the user's language (English / Hindi / Hinglish).",
                "english": "Reply in clear English.",
                "hinglish": "Reply in natural Hinglish (Roman Hindi + English)."}[s.personality.language_style]
        from datetime import datetime
        now = datetime.now().strftime("%A, %d %B %Y %H:%M")
        working = self.working.summary()
        return (
            f"You are {s.personality.name}, a personal AI assistant running on the user's "
            f"computer. {s.personality.style}\n"
            f"{lang}\n"
            f"Current local time: {now}. Platform: see system_info if needed.\n"
            f"Rules:\n"
            f"- Prefer real tools over guessing. Verify results before claiming success.\n"
            f"- If a request is clear, act. Ask only when genuinely ambiguous or dangerous.\n"
            f"- Destructive or high-risk actions will ask the user for confirmation — that's "
            f"by design; don't apologize for it.\n"
            f"- Never reveal API keys or secrets.\n"
            f"- {SYSTEM_CLAUSE}\n"
            f"{prefs_text}"
            + (f"\nWorking memory:\n{working}" if working else "")
        )

    async def load_preferences_text(self) -> None:
        try:
            prefs = await self._conversations.preferences()
        except Exception:  # noqa: BLE001
            prefs = {}
        self._prefs_text = ("User preferences:\n" + "\n".join(
            f"- {k}: {v}" for k, v in prefs.items())) + "\n" if prefs else ""
    async def _status(self, state: str, detail: str | None = None) -> None:
        await self._bus.publish(Topics.STATUS, {"state": state, "detail": detail})


def _slim(data: dict[str, Any], limit: int = 4000) -> dict[str, Any]:
    """Keep tool payloads small enough for context windows."""
    text = str(data)
    if len(text) <= limit:
        return data
    return {"preview": text[:limit], "truncated": True}
