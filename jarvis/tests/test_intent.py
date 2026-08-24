"""Intent fast-path tests: English / Hindi / Hinglish all map to the same tools."""
from __future__ import annotations

import pytest

from app.brain.intent import IntentRouter, normalize


@pytest.fixture(autouse=True)
def no_agent_browser(monkeypatch):
    """Intent tests assert the portable fallback (web_search). The agent-browser
    path is covered by tests/test_browser.py with real Chromium."""
    monkeypatch.setenv("JARVIS_NO_AGENT_BROWSER", "1")


@pytest.fixture()
def router() -> IntentRouter:
    return IntentRouter()


def cases(router, text) -> object:
    return router.parse(text)


def test_normalize_strips_wake_word():
    assert normalize("Jarvis, chrome kholo") == "chrome kholo"
    assert normalize("hey jarvis open chrome") == "open chrome"


def test_open_app_hinglish(router):
    intent = cases(router, "chrome kholo")
    assert intent.tool == "open_application" and intent.args["app"] == "chrome"


def test_open_app_english(router):
    intent = cases(router, "Can you open Chrome for me?")
    assert intent.tool == "open_application" and intent.args["app"] == "chrome"


def test_open_app_spotify_chalao(router):
    intent = cases(router, "spotify chalao")
    assert intent.tool == "open_application" and intent.args["app"] == "spotify"


def test_open_youtube_opens_url_not_app(router):
    intent = cases(router, "youtube kholo")
    assert intent.tool == "open_url" and intent.args["url"] == "youtube.com"


def test_close_app(router):
    intent = cases(router, "chrome band karo")
    assert intent.tool == "close_application" and intent.args["app"] == "chrome"


def test_system_diagnostics(router):
    for text in ("system info batao", "why is my laptop slow", "mera laptop slow kyu hai",
                 "ram usage kitna hai", "battery kitni hai"):
        intent = cases(router, text)
        assert intent is not None and intent.tool == "system_info", text


def test_processes(router):
    intent = cases(router, "kaun kaun se apps chal rahe hain")
    assert intent.tool == "process_list"


def test_screenshot(router):
    assert cases(router, "screenshot lo").tool == "screenshot"
    assert cases(router, "take a screenshot").tool == "screenshot"


def test_search_youtube_hinglish(router):
    intent = cases(router, "youtube pe arijit singh ke songs search karo")
    assert intent.tool == "web_search"
    assert intent.args["engine"] == "youtube"
    assert "arijit singh" in intent.args["query"]


def test_search_missing_query_asks_then_fills(router):
    first = cases(router, "search youtube")
    assert first.tool == "__ask__" and "search on youtube" in first.args["text"].lower()
    second = cases(router, "arijit singh")
    assert second.tool == "web_search" and second.args["engine"] == "youtube"
    assert "arijit singh" in second.args["query"]


def test_create_folder_hinglish(router):
    intent = cases(router, "desktop pe folder bana AI Projects naam ka")
    assert intent.tool == "create_folder"
    assert "AI Projects" in intent.args["path"]
    assert intent.args["path"].startswith("Desktop")


def test_create_folder_english(router):
    intent = cases(router, "create folder called notes")
    assert intent.tool == "create_folder"
    assert "notes" in intent.args["path"].lower()


def test_find_file_hinglish_object_first(router):
    intent = cases(router, "meri last week wali resume file dhundo")
    assert intent.tool == "search_files"
    assert "resume" in intent.args["query"].lower()
    assert intent.args.get("modified_within_days") == 7


def test_find_file_english(router):
    intent = cases(router, "find my resume")
    assert intent.tool == "search_files"
    assert "resume" in intent.args["query"].lower()


def test_reminder(router):
    intent = cases(router, "reminder set karo call manager")
    assert intent.tool == "set_reminder"


def test_stop_interrupts(router):
    assert cases(router, "stop").tool == "__interrupt__"
    assert cases(router, "ruk jao").tool == "__interrupt__"


def test_ordinal_selection_needs_candidates(router):
    intent = cases(router, "first wala open karo")
    assert intent.tool == "__say__"          # no prior list -> honest answer


def test_ordinal_selection_with_candidates(router):
    router.candidates = ["Google Chrome", "Chrome Dev"]
    intent = cases(router, "first wala kholo")
    assert intent.tool == "open_application" and intent.args["app"] == "Google Chrome"


def test_time_is_answered_locally(router):
    intent = cases(router, "time kya hua")
    assert intent.tool == "__say__" and "It's" in intent.args["text"]


def test_unrelated_text_returns_none(router):
    assert cases(router, "explain the theory of relativity") is None


def test_object_first_search_hinglish(router):
    intent = cases(router, "python automation tutorial search karo")
    assert intent.tool == "web_search"
    assert intent.args["query"] == "python automation tutorial"


def test_object_first_search_simple(router):
    intent = cases(router, "arijit singh dhundo")
    assert intent is None or intent.tool != "open_application"
