"""Browser agent tests — REAL headless Chromium against a local fixture server.
Deterministic (no external network). Covers the Spec §14/§15 flows:
navigate → snapshot → semantic click → type+submit → read (untrusted fencing)
→ extract results → tabs → screenshot → permission pipeline integration.
"""
from __future__ import annotations

import http.server
import threading
from pathlib import Path

import pytest

from app.browser.driver import PlaywrightDriver, set_driver

pytestmark = pytest.mark.browser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def server_url() -> str:
    """Local HTTP server serving tests/fixtures on an ephemeral port."""
    class FixtureHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, directory=str(FIXTURES), **kwargs)

        def log_message(self, *args) -> None:  # silence
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


@pytest.fixture()
async def driver(server_url: str):
    d = PlaywrightDriver(headless=True)
    set_driver(d)
    try:
        yield d
    finally:
        await d.stop()
        set_driver(None)


async def test_navigate_and_snapshot_semantic_elements(driver, server_url):
    state = await driver.navigate(server_url + "/index.html")
    assert state.verified
    assert state.title == "JARVIS Test Home"
    refs = {e["ref"] for e in state.elements}
    tags = [e["tag"] for e in state.elements]
    assert len(refs) >= 3 and "a" in tags and "input" in tags and "button" in tags
    # every element has a stable selector + text for the LLM to reason about
    for element in state.elements:
        assert element["selector"] and "ref" in element


async def test_semantic_click_navigates_and_verifies(driver, server_url):
    await driver.navigate(server_url + "/index.html")
    target = next(e for e in driver.last_snapshot["elements"] if e.get("href", "").endswith("page2.html"))
    result = await driver.click(target["ref"])
    assert result.ok and result.state.verified
    assert result.state.title == "Page Two — Fixtures"
    assert result.detail["navigated"] is True


async def test_type_and_submit_form(driver, server_url):
    await driver.navigate(server_url + "/index.html")
    box = next(e for e in driver.last_snapshot["elements"] if e["tag"] == "input")
    result = await driver.type_text(box["ref"], "python automation", submit=True)
    assert result.ok
    assert "q=python+automation" in result.state.url, "form submission must carry the typed query"


async def test_click_unknown_ref_fails_honestly(driver, server_url):
    from app.core.exceptions import ToolError
    await driver.navigate(server_url + "/index.html")
    with pytest.raises(ToolError):
        await driver.click("e999")


async def test_read_pages_fences_untrusted_content(driver, server_url):
    await driver.navigate(server_url + "/results.html")
    page = await driver.read()
    assert page["content"].startswith("<untrusted-external-content>")
    assert page["injection_flags"], "injection phrasing on the page must be flagged"
    assert "python automation" in page["content"].lower()


async def test_extract_search_results(driver, server_url):
    await driver.navigate(server_url + "/results.html")
    results = await driver.extract_results("duckduckgo")
    assert len(results) == 3
    assert results[0]["url"] == "https://example.com/tutorial-1"
    assert "Beginners" in results[0]["title"]


async def test_tabs_lifecycle(driver, server_url):
    await driver.navigate(server_url + "/index.html")
    result = await driver.new_tab(server_url + "/page2.html")
    assert "Page Two" in result.message
    tabs = await driver.tabs()
    assert len(tabs) == 2
    switched = await driver.switch_tab(0)
    assert switched.ok
    closed = await driver.close_tab(1)
    assert closed.ok
    assert len(await driver.tabs()) == 1


async def test_screenshot_saved(driver, server_url, jarvis_home):
    await driver.navigate(server_url + "/index.html")
    import os
    target = str(jarvis_home / "data" / "screenshots" / "t.png")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    path = await driver.screenshot(target)
    assert Path(path).exists() and Path(path).stat().st_size > 1000


# ------------------------------------------------ tool-layer integration

async def test_browser_tools_through_permission_pipeline(jarvis_home, stack, driver, server_url):
    """browser_navigate + browser_read_page as real tools: schemas validate,
    permissions apply, results verify, tool_usage logs."""
    await stack.build()
    result = await stack.tools.execute("browser_navigate", {"url": server_url + "/index.html"})
    assert result.success and result.verified
    assert result.data["title"] == "JARVIS Test Home"
    assert any(e["tag"] == "input" for e in result.data["elements"])

    read = await stack.tools.execute("browser_read_page", {})
    assert read.success
    assert read.data["content"].startswith("<untrusted-external-content>")

    from app.database.repo import ToolUsageRepo
    async with stack.session_factory() as session:
        rows = await ToolUsageRepo(session).recent()
    assert any(r.tool == "browser_navigate" and r.status == "ok" for r in rows)


async def test_browser_search_tool_reports_results(jarvis_home, stack, driver, server_url,
                                                   monkeypatch):
    await stack.build()
    # Point the engine map at the local fixture for a deterministic "search"
    from app.browser import driver as driver_mod
    monkeypatch.setitem(driver_mod.SEARCH_ENGINES, "duckduckgo", server_url + "/results.html?q={q}")
    result = await stack.tools.execute("browser_search",
                                       {"query": "python automation tutorial",
                                        "engine": "duckduckgo"})
    assert result.success
    assert len(result.data["results"]) == 3
    assert result.data["results"][0]["url"].startswith("https://example.com/")
    assert "1)" in result.message, "results must be numbered for 'first wala' follow-ups"


async def test_full_67_flow_search_then_first_wala(jarvis_home, stack, driver, server_url,
                                                   monkeypatch):
    """Spec §67: search → 'first wala open karo' → opens the first result."""
    from app.browser import driver as driver_mod
    for engine_key in ("duckduckgo", "google", "bing"):
        monkeypatch.setitem(driver_mod.SEARCH_ENGINES, engine_key, server_url + "/results.html?q={q}")
    await stack.build()



    first = await stack.engine.turn("python automation tutorial search karo")
    assert first.used_fast_path and first.actions[0]["tool"] == "browser_search"
    assert stack.engine._intent.search_results, "results must be remembered for follow-ups"

    second = await stack.engine.turn("first wala kholo")
    assert second.actions[0]["tool"] == "browser_navigate"
    assert "tutorial-1" in second.actions[0]["message"] or second.text


async def test_click_tool_semantic_ref(jarvis_home, stack, driver, server_url):
    await stack.build()
    await stack.tools.execute("browser_navigate", {"url": server_url + "/index.html"})
    result = await stack.tools.execute("browser_click", {"ref": "e999"})
    assert not result.success, "unknown ref must fail honestly through the tool layer"
