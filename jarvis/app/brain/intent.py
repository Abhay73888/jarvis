"""Intent fast-path: deterministic local NLU for common commands (Spec §48).

Handles English, Hindi, and Hinglish phrasings of frequent requests without a
round-trip to any LLM. High-confidence matches only — anything ambiguous
returns None and the AgentEngine falls through to the LLM.

This is a REAL rule-based router (not a mock): it maps utterances to actual
tool invocations, and supports one turn of context for missing parameters
("Search YouTube." → "What should I search?" → "Arijit Singh").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_WAKE = re.compile(r"\b(hey\s+|ok\s+)?jarvis[,!.\s]*", re.I)
_FILLERS = {
    "please", "karo", "kar", "do", "dena", "kya", "mujhe", "mera", "mere", "liye",
    "for", "me", "the", "a", "an", "can", "you", "could", "would", "will", "hey",
    "app", "application", "yaar", "bhai", "jara", "zara", "帮我", "it", "its",
    "khol", "kholo", "open", "launch", "start", "chalao", "chalu", "band",
    "close", "quit", "exit", "search", "dhundo", "dhoondo", "khojo", "pe", "par", "on", "in",
}

_SITES = {
    "google": "google.com", "youtube": "youtube.com", "github": "github.com",
    "gmail": "mail.google.com", "gmail.com": "mail.google.com", "stack overflow": "stackoverflow.com",
    "stackoverflow": "stackoverflow.com", "twitter": "twitter.com", "x": "x.com",
    "instagram": "instagram.com", "facebook": "facebook.com", "linkedin": "linkedin.com",
    "reddit": "reddit.com", "wikipedia": "wikipedia.org", "amazon": "amazon.in",
    "flipkart": "flipkart.com", "chatgpt": "chat.openai.com", "whatsapp web": "web.whatsapp.com",
    "spotify web": "open.spotify.com", "netflix": "netflix.com", "maps": "maps.google.com",
}
_DOMAINISH = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$|^localhost:\d+$")
_SEARCH_ENGINES = {"google", "youtube", "bing", "duckduckgo"}


@dataclass
class Intent:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    missing: str | None = None        # parameter name we need from the user
    speech: str = ""                  # optional pre-tool acknowledgement


def normalize(text: str) -> str:
    text = _WAKE.sub("", text.strip())
    text = re.sub(r"[?!.]+$", "", text).strip()
    return re.sub(r"\s+", " ", text)


def _strip_fillers(tokens: list[str]) -> str:
    kept = [t for t in tokens if t.lower() not in _FILLERS]
    return " ".join(kept).strip()


# ------------------------------------------------------------------ patterns

_OPEN = re.compile(r"(?:khol\s?do|kholo|kholna|khol|open|launch|start|chalao|chalu\s?karo|run)\b", re.I)
_CLOSE = re.compile(r"(?:band\s?karo|band\s?kar|band\s?do|band|close|quit|exit|kill)\b", re.I)
_SYSINFO = re.compile(r"\b(system|laptop|pc|computer)\b.*\b(info|information|detail|details|status|report|diagnostic|check)\b"
                      r"|(?:why\s+is\s+my|mera|mere)\s+(?:laptop|pc|system|computer)\s+(?:slow|slow\s?ho\s?raha?|hang\s?ho\s?raha?)", re.I)
_RAM = re.compile(r"\b(ram|memory)\b.*\b(usage|kitna|kitni|how\s+much|percent|free)\b", re.I)
_CPU = re.compile(r"\b(cpu|processor)\b.*\b(usage|kitna|how\s+much|percent)\b", re.I)
_BATTERY = re.compile(r"\b(battery|charge)\b.*\b(kitna|kitni|percent|how\s+much|status|remaining)\b", re.I)
_PROCESSES = re.compile(r"\b(kaun\s?kaun\s?se|which|what|running|chal\s?rahe|chal\s?rahe\s?hain|active)\b.*\b(apps?|applications?|programs?|processes)\b"
                        r"|\b(task\s+manager|running\s+apps?|open\s+apps?)\b", re.I)
_SCREENSHOT = re.compile(r"\b(screenshot|screen\s+shot|screen\s+capture)\b.*\b(lo|lena|le|take|capture|click)\b"
                         r"|^(take|le|lena|lo)\b.*\b(screenshot|screen\s+shot)\b$"
                         r"|^screenshot$", re.I)
_TIME = re.compile(r"\b(time|samay|baje|baja)\b.*\b(kya|kitne|what|how\s+much|bolo|batao|tell)\b"
                   r"|^(what('| i)?s\s+the\s+time|time\s+ky[aa]\s+hua|kitne\s+baje\s+hain)$", re.I)
_DATE = re.compile(r"\b(date|tareekh|din)\b.*\b(kya|what|aaj|today|bolo|batao)\b|aaj\s+(?:ki\s+)?(?:date|tareekh)", re.I)
_SEARCH1 = re.compile(r"(?:search|dhundo|dhoondo|khojo)\s+(?:for\s+|karo\s+|kar\s+)?(.+)$", re.I)
_SEARCH3 = re.compile(r"(.+?)\s+(?:search|dhundo|dhoondo|khojo)\s*(?:karo|kar|do)?$", re.I)
_SEARCH2 = re.compile(r"(\w+)\s+(?:pe|par|on|in)\s+(.+?)\s*(?:search|dhundo|dhoondo|khojo)\s*(?:karo|kar)?$", re.I)
_NEWFOLDER = re.compile(r"(?:folder|file)\s+(?:banao|bana|create\s+kar[oa]|create)\s*(?:naam\s*(?:ka|ki|se)|name(?:d)?)?\s*[\"']?([^\"']+)[\"']?$"
                        r"|(?:create|banao|bana)\s+(?:a\s+)?(?:folder|file)\s+(?:called|named|naam\s*ka|naam\s*ki)?\s*[\"']?([^\"']+)[\"']?$", re.I)
_FINDFILE = re.compile(
    r"(?i)(?:find|search|dhundo|dhoondo|khojo|locate)\s+(?:my\s+|meri\s+|mere\s+)?(.+?)(?:\s*(?:file|files|pdf|pdfs|document|documents), re.I)?$"
    r"|(.+?)\s*(?:file|files|pdf|pdfs|document|documents)?\s+(?:dhundo|dhoondo|khojo)$")
_REMINDER = re.compile(r"(?:reminder|yaad)\s*(?:set\s*karo|set\s+kar[oa]|dilana|dila\s?do|set)?\s*[:]?\s*(.+)?$", re.I)
_STOP = re.compile(r"^(stop|stop\s*it|cancel|abort|ruk\s*jao|ruko|band\s+karo|khatam\s*karo)$", re.I)
_LOCKDOWN = re.compile(r"\b(protocol\s+zero|code\s+red|emergency\s+lockdown|lockdown|lock\s+(?:the\s+)?(?:pc|laptop|screen|computer)|screen\s+lock|lock\s+karo)\b", re.I)



def _agent_browser_ok() -> bool:
    """True when the Playwright agent browser can be used (cached import check)."""
    from importlib.util import find_spec
    import os
    return find_spec("playwright") is not None and \
        os.environ.get("JARVIS_NO_AGENT_BROWSER", "") != "1"


class IntentRouter:
    """Stateless parser + small context slots for follow-up answers."""

    def __init__(self) -> None:
        self.pending: Intent | None = None
        self.candidates: list[str] = []       # last ambiguous app candidates
        self.last_app: str | None = None
        self.search_results: list[dict[str, str]] = []   # last browser results
        self.search_engine: str | None = None

    def parse(self, text: str) -> Intent | None:
        clean = normalize(text)

        if _STOP.match(clean):
            return Intent(tool="__interrupt__")

        if _LOCKDOWN.search(clean):
            return Intent(tool="__lockdown__", speech="Executing emergency lockdown.")


        if self.pending is not None:
            filled = self._fill_pending(clean)
            if filled is not None:
                return filled

        if _SYSINFO.search(clean) or _RAM.search(clean) or _CPU.search(clean) or _BATTERY.search(clean):
            return Intent(tool="system_info", speech="Checking the system.")

        if _SCREENSHOT.search(clean):
            return Intent(tool="screenshot", speech="Taking a screenshot.")

        if _PROCESSES.search(clean):
            return Intent(tool="process_list", args={"limit": 15}, speech="Reading running processes.")

        if _TIME.match(clean):
            from datetime import datetime
            now = datetime.now().strftime("%I:%M %p").lstrip("0")
            return Intent(tool="__say__", args={"text": f"It's {now}."})
        if _DATE.search(clean):
            from datetime import datetime
            today = datetime.now().strftime("%A, %d %B %Y")
            return Intent(tool="__say__", args={"text": f"Today is {today}."})

        # "chrome kholo" / "open chrome" / "spotify chalao"
        if _OPEN.search(clean):
            obj = self._object_after_verb(clean, _OPEN).lower()
            if not obj:
                return None
            if obj.lower() in _SITES or _DOMAINISH.match(obj.lower(), re.I):
                return Intent(tool="open_url", args={"url": _SITES.get(obj.lower(), obj)},
                              speech=f"Opening {obj}.")
            if self._is_ordinal_selection(obj):
                return self._select_candidate(obj)
            self.last_app = obj
            return Intent(tool="open_application", args={"app": obj})

        # "chrome band karo" / "close chrome"
        if _CLOSE.search(clean) and not _STOP.match(clean):
            obj = self._object_after_verb(clean, _CLOSE).lower()
            if obj:
                if obj.lower() in ("it", "this", "ye", "is", "us") and self.last_app:
                    obj = self.last_app
                return Intent(tool="close_application", args={"app": obj})

        # "search X on youtube" / "youtube pe X search karo" / "search X"
        # search intents go through the agent browser when available (results
        # JARVIS can actually read/verify), else open a tab in the user's browser.
        use_agent = _agent_browser_ok()

        m2 = _SEARCH2.search(clean)
        if m2:
            engine, query = m2.group(1).lower(), m2.group(2).strip()
            if engine in _SEARCH_ENGINES:
                tool = "browser_search" if use_agent else "web_search"
                return Intent(tool=tool, args={"query": query, "engine": engine},
                              speech=f"Searching {engine} for {query}.")
        m3 = _SEARCH3.search(clean)
        if m3 and not re.search(r"(?i)(file|files|pdf|pdfs|document|documents)", m3.group(1)):
            query = m3.group(1).strip()
            for token in query.lower().split():
                if token in _SEARCH_ENGINES:
                    self.pending = Intent(tool="browser_search" if use_agent else "web_search",
                                          args={"engine": token}, missing="query")
                    return Intent(tool="__ask__", args={
                        "text": f"What would you like me to search on {token}?"})
            tool = "browser_search" if use_agent else "web_search"
            return Intent(tool=tool, args={"query": query},
                          speech=f"Searching for {query}.")
        m1 = _SEARCH1.search(clean)
        if m1:
            query = m1.group(1).strip()
            if not re.search(r"(?i)(file|files|pdf|pdfs|document|documents)", query):
                for token in query.lower().split():
                    if token in _SEARCH_ENGINES:  # "search youtube"
                        self.pending = Intent(tool="browser_search" if use_agent else "web_search",
                                              args={"engine": token}, missing="query")
                        return Intent(tool="__ask__", args={
                            "text": f"What would you like me to search on {token}?"})
                tool = "browser_search" if use_agent else "web_search"
                return Intent(tool=tool, args={"query": query},
                              speech=f"Searching for {query}.")

        # "page par kya hai" / "read the page" — agent browser read
        if re.search(r"(?i)\b(page|site|website|screen)\b.*\b(kya|kya hai|kya likha|read|batao|samjho|content|text)\b", clean) \
                or re.search(r"(?i)^(read|is )?(the )?(page|site) (par|pe)? ?(kya|read)", clean):
            if _agent_browser_ok():
                return Intent(tool="browser_read_page", args={}, speech="Reading the page.")

        folder = _NEWFOLDER.search(clean)
        if folder:
            name = next((g for g in folder.groups() if g), None)
            if name:
                name = re.sub(r"(?i)\s*(naam\s*(ka|ki|se)|named?).*$", "", name).strip()
                name = _strip_fillers(name.split()).strip()
            if name:
                loc = re.match(r"(?i)^(desktop|downloads|documents)\b", clean)
                path = f"{loc.group(1).capitalize()}/{name}" if loc else name
                return Intent(tool="create_folder", args={"path": path},
                              speech=f"Creating folder '{name}'.")

        reminder = _REMINDER.search(clean)
        if reminder and re.search(r"(?i)(list|show|dikhao|batao)\b.*\b(reminders?|tasks?|to-?do)", clean):
            return Intent(tool="list_reminders", args={}, speech="Here are your reminders.")
        if reminder and re.search(r"(?i)(reminder|yaad)", clean):
            detail = (reminder.group(1) or "").strip()
            if detail:
                title, due_at = detail, None
                time_match = re.search(
                    r"(?i)\b(?:tomorrow|today|tonight|day after tomorrow)\b.*$|\b\d{1,2}:\d{2}\b.*$",
                    detail)
                if time_match and time_match.start() > 0:
                    due_at = time_match.group(0).strip()
                    title = detail[: time_match.start()].strip(" ,:;-") or detail
                return Intent(tool="set_reminder",
                              args={"title": title, **({"due_at": due_at} if due_at else {})},
                              speech="Setting a reminder.")
            self.pending = Intent(tool="set_reminder", args={}, missing="title")
            return Intent(tool="__ask__", args={"text": "What should I remind you about?"})

        find = _FINDFILE.search(clean)
        if find and re.search(r"(?i)(file|pdf|document|resume|project|folder)", clean):
            query = next((g for g in find.groups() if g), "") or clean
            query = query.strip()
            query = re.sub(r"(?i)^(meri|mere|my|the)\s+", "", query)
            if re.search(r"(?i)(last\s+week|pichle\s+hafte)", query):
                query = re.sub(r"(?i)(last\s+week|pichle\s+hafte)\s*(wali|waali|ke|ki)?\s*", "", query).strip()
                days = 7
            else:
                days = None
            query = query.strip() or "file"
            return Intent(tool="search_files", args={"query": query, **({"modified_within_days": days} if days else {})},
                          speech=f"Looking for {query} files.")

        return None

    # ------------------------------------------------------------ helpers

    def _object_after_verb(self, text: str, verb: re.Pattern[str]) -> str:
        """Object = tokens minus the verb phrase and fillers, wherever the verb sits."""
        tokens = text.split()
        verb_words = {"khol", "kholo", "kholna", "khol", "band", "close", "quit", "exit",
                      "kill", "open", "launch", "start", "run", "chalao", "chalu",
                      "karo", "kar", "do", "kholna"}
        kept = [t for t in tokens if t.lower() not in verb_words]
        obj = _strip_fillers(kept)
        return obj

    def _is_ordinal_selection(self, obj: str) -> bool:
        return bool(re.match(
            r"(?i)^(first|second|third|1st|2nd|3rd|pehla|dusra)(\s+(wala|wali|one|result|link|option))?$",
            obj.strip()))

    def _select_candidate(self, obj: str) -> Intent:
        order = {"first": 0, "1st": 0, "pehla": 0, "second": 1, "2nd": 1, "dusra": 1,
                 "third": 2, "3rd": 2}
        idx = order.get(obj.strip().lower().split()[0], 0)
        # Browser search results win (§67 flow: search → "first wala open karo")
        if self.search_results:
            if idx < len(self.search_results):
                pick = self.search_results[idx]
                return Intent(tool="browser_navigate", args={"url": pick["url"]},
                              speech=f"Opening: {pick['title'][:70]}")
            return Intent(tool="__say__",
                          args={"text": f"There were only {len(self.search_results)} results."})
        if not self.candidates:
            return Intent(tool="__say__", args={"text": "I don't have a previous list to pick from."})
        if idx >= len(self.candidates):
            return Intent(tool="__say__", args={"text": f"There were only {len(self.candidates)} options."})
        choice = self.candidates[idx]
        self.last_app = choice
        return Intent(tool="open_application", args={"app": choice})

    def _fill_pending(self, clean: str) -> Intent | None:
        """If the last turn asked for a missing parameter, treat this text as the answer."""
        pending, self.pending = self.pending, None
        if pending is None:
            return None
        if len(clean.split()) <= 6 and not _OPEN.search(clean) and not _CLOSE.search(clean):
            args = dict(pending.args)
            args[pending.missing] = clean.strip(' "\'')
            if pending.tool == "browser_search":
                return Intent(tool="browser_search", args=args,
                              speech=f"Searching {args.get('engine', 'the web')} for {args['query']}.")
            if pending.tool == "web_search":
                return Intent(tool="web_search", args=args, speech=f"Searching {args.get('engine', 'the web')} for {args['query']}.")
            if pending.tool == "set_reminder":
                return Intent(tool="set_reminder", args=args, speech="Setting a reminder.")
        return None
